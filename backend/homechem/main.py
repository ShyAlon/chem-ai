import os
from collections import deque
from contextlib import asynccontextmanager
from time import monotonic, perf_counter
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from opentelemetry import metrics, trace
from opentelemetry.propagate import extract, inject
from pydantic import BaseModel, Field, ValidationError

from .policy import AssessmentInput, Decision, Interpretation, assess
from .providers import ProviderUnavailable, create_provider
from .telemetry import RELEASE, configure, event

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)
request_duration = meter.create_histogram("homechem.request.duration", unit="s")
policy_outcomes = meter.create_counter("homechem.policy.decisions")
mcp = FastMCP(
    "HomeChem", stateless_http=True, json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*", *os.getenv("PUBLIC_HOST", "").split()],
        allowed_origins=["http://127.0.0.1:*", "http://localhost:*"],
    ),
)


@mcp.tool()
def assess_cleaning(inputs: AssessmentInput) -> Decision:
    """Evaluate confirmed inputs against HomeChem's reviewed cleaning scope."""
    with tracer.start_as_current_span("policy.assess") as span:
        result = assess(inputs)
        span.set_attributes({"policy.rule": result.rule, "policy.version": result.version, "decision": result.status.value})
        policy_outcomes.add(1, {"decision": result.status.value})
        event("decision", rule=result.rule, outcome=result.status.value)
        return result


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.interpretations = deque()
    app.state.interpretation_limit = max(1, int(os.getenv("LLM_REQUESTS_PER_MINUTE", "12")))
    tracer_provider, meter_provider = configure()
    try:
        async with httpx.AsyncClient(timeout=35) as client, mcp.session_manager.run():
            app.state.provider = create_provider(client)
            yield
    finally:
        tracer_provider.shutdown()
        meter_provider.shutdown()


app = FastAPI(title="HomeChem", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def instrument(request: Request, call_next):
    request_id = uuid4().hex
    request.state.request_id = request_id
    start = perf_counter()
    trace_context = None
    if request.url.path == "/mcp" and request.client and request.client.host == "127.0.0.1":
        trace_context = extract(request.headers)
    with tracer.start_as_current_span("http.request", context=trace_context, kind=trace.SpanKind.SERVER) as span:
        span.set_attribute("http.request.method", request.method)
        span.set_attribute("request.id", request_id)
        try:
            response = await call_next(request)
        except Exception as error:
            span.set_status(trace.StatusCode.ERROR, type(error).__name__)
            event("http.error", request_id=request_id, error_type=type(error).__name__)
            response = JSONResponse({"detail": "internal_error"}, status_code=500)
        route = request.scope.get("route")
        route_path = getattr(route, "path", "") or (
            "/mcp" if request.url.path == "/mcp" else "unmatched"
        )
        elapsed = perf_counter() - start
        span.set_attribute("http.route", route_path)
        span.set_attribute("http.response.status_code", response.status_code)
        if response.status_code >= 500:
            span.set_status(trace.StatusCode.ERROR)
        request_duration.record(elapsed, {
            "http.route": route_path, "http.response.status_code": response.status_code,
        })
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "no-store"
        event("http.response", request_id=request_id, route=route_path,
              status=response.status_code, elapsed_ms=round(elapsed * 1000))
        return response


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, error: RequestValidationError):
    return JSONResponse({"detail": "invalid_request"}, status_code=422)


class InterpretInput(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    return {"status": "ok", "release": RELEASE}


@app.post("/api/interpret", operation_id="interpret")
async def interpret(inputs: InterpretInput, request: Request) -> Interpretation:
    recent = request.app.state.interpretations
    now = monotonic()
    while recent and recent[0] <= now - 60:
        recent.popleft()
    if len(recent) >= request.app.state.interpretation_limit:
        return JSONResponse({"detail": "rate_limited"}, status_code=429, headers={"Retry-After": "60"})
    recent.append(now)
    try:
        return await request.app.state.provider.interpret(inputs.text)
    except ProviderUnavailable:
        return JSONResponse({"detail": "provider_unavailable"}, status_code=503)


@app.post("/api/assess", operation_id="assess")
async def assess_request(inputs: AssessmentInput) -> Decision:
    with tracer.start_as_current_span("mcp.assess_cleaning"):
        headers: dict[str, str] = {}
        inject(headers)
        url = os.getenv("INTERNAL_MCP_URL", "http://127.0.0.1:8000/mcp")
        try:
            async with streamablehttp_client(url, headers=headers) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool("assess_cleaning", {"inputs": inputs.model_dump(mode="json")})
                    if not result.isError:
                        return Decision.model_validate(result.structuredContent)
        except (ExceptionGroup, ValidationError, httpx.HTTPError):
            event("mcp.unavailable", tool="assess_cleaning")
        return JSONResponse({"detail": "assessment_unavailable"}, status_code=503)


app.mount("/", mcp.streamable_http_app())
