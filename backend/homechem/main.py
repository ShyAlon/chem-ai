import os
from collections import deque
from contextlib import asynccontextmanager
from math import ceil
from time import monotonic, perf_counter
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from opentelemetry import metrics, trace
from opentelemetry.propagate import extract
from pydantic import BaseModel, Field

from .interpretation import resolve
from .activities import Collection, activity, begin, current, finish, router as activity_router
from .application import router as application_router, ReviewView, review_view
from .knowledge_client import KnowledgeClient
from .research import router as research_router
from .management import router as management_router
from .normalization import has_hebrew
from .policy import AssessmentInput, Decision, Interpretation, Materials, Surface, assess
from .providers import ProviderUnavailable, create_provider
from .rate_limit import QuestionCooldown, client_key
from .telemetry import RELEASE, configure, event
from .translation import select_translator

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
    with activity("policy", "policy.assess") as operation:
        span = trace.get_current_span()
        result = assess(inputs)
        operation.details.update(rule=result.rule, decision=result.status.value, policy_version=result.version)
        span.set_attributes({"policy.rule": result.rule, "policy.version": result.version, "decision": result.status.value})
        policy_outcomes.add(1, {"decision": result.status.value})
        event("decision", rule=result.rule, outcome=result.status.value)
        return result


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.knowledge = KnowledgeClient()
    app.state.question_cooldown = QuestionCooldown(int(os.getenv("QUESTION_COOLDOWN_SECONDS", "10")))
    app.state.trust_proxy_client_ip = os.getenv("TRUST_PROXY_CLIENT_IP") == "1"
    app.state.interpretations = deque()
    app.state.interpretation_limit = max(1, int(os.getenv("LLM_REQUESTS_PER_MINUTE", "12")))
    tracer_provider, meter_provider = configure()
    try:
        async with httpx.AsyncClient(timeout=35) as client, mcp.session_manager.run():
            app.state.provider = create_provider(client)
            app.state.translation_provider, app.state.translator = select_translator(client, app.state.provider)
            yield
    finally:
        tracer_provider.shutdown()
        meter_provider.shutdown()


app = FastAPI(title="HomeChem", version="0.1.0", lifespan=lifespan)
app.include_router(management_router)
app.include_router(application_router)
app.include_router(activity_router)
app.include_router(research_router)


@app.middleware("http")
async def instrument(request: Request, call_next):
    request_id = uuid4().hex
    request.state.request_id = request_id
    start = perf_counter()
    with tracer.start_as_current_span("http.request", context=extract(request.headers), kind=trace.SpanKind.SERVER) as span:
        span.set_attribute("http.request.method", request.method)
        span.set_attribute("request.id", request_id)
        collection = Collection(request_id)
        activity_key = begin(collection, request.headers.get("X-Activity-Key")) if request.method == "POST" and request.url.path.startswith("/api/") else None
        activity_token = current.set(collection)
        response = None
        try:
            response = await call_next(request)
        except Exception as error:
            span.set_status(trace.StatusCode.ERROR, type(error).__name__)
            event("http.error", request_id=request_id, error_type=type(error).__name__)
            response = JSONResponse({"detail": "internal_error"}, status_code=500)
        finally:
            current.reset(activity_token)
            finish(collection, response is not None and response.status_code < 400)
        if activity_key:
            response.headers["X-Activity-ID"] = activity_key
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


class InterpretResult(Interpretation):
    method: Literal["dictionary", "model"]
    surface_term: str | None
    object_type: str | None = None
    device: str | None = None
    substrate: str | None = None
    finish: str | None = None
    translated_text: str | None = None
    translation_provider: str | None = None
    presentation: dict[str, ReviewView] = Field(default_factory=dict)


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    return {"status": "ok", "release": RELEASE}


@app.post("/api/interpret", operation_id="interpret")
async def interpret(inputs: InterpretInput, request: Request) -> InterpretResult:
    now = monotonic()
    peer = request.client.host if request.client else None
    forwarded = request.headers.get("X-HomeChem-Client-IP") if request.app.state.trust_proxy_client_ip else None
    wait = request.app.state.question_cooldown.take(client_key(peer, forwarded), now)
    if wait is not None:
        return rate_limited(request, "question_cooldown", wait)

    text = inputs.text
    translated = None
    translation_provider = None
    if has_hebrew(text):
        translation_provider = request.app.state.translation_provider
        if translation_provider == "llm":
            wait = reserve_model_call(request)
            if wait is not None:
                return rate_limited(request, "llm_budget", wait)
        try:
            translated = await request.app.state.translator.translate_to_english(text)
            if not translated.strip() or has_hebrew(translated):
                raise ProviderUnavailable
        except ProviderUnavailable:
            event("translation_unavailable", request_id=request.state.request_id)
            return JSONResponse({"detail": "translation_unavailable"}, status_code=503)
        text = translated

    with activity("normalization", "normalization.resolve") as operation:
        resolved = resolve(text)
        operation.details.update(object_type=resolved.object_type, substrate=resolved.substrate, surface=resolved.interpretation.surface, model_fallback=resolved.allow_model)
    if not resolved.allow_model:
        return report_interpretation(request, InterpretResult(
            **resolved.interpretation.model_dump(), method="dictionary", surface_term=resolved.surface_term,
            object_type=resolved.object_type, device=resolved.device, substrate=resolved.substrate, finish=resolved.finish,
            translated_text=translated, translation_provider=translation_provider,
        ))

    wait = reserve_model_call(request)
    if wait is not None:
        return rate_limited(request, "llm_budget", wait)
    try:
        surface = await request.app.state.provider.suggest_surface(text)
    except ProviderUnavailable:
        return JSONResponse({"detail": "provider_unavailable"}, status_code=503)
    return report_interpretation(request, InterpretResult(
        surface=surface, materials=Materials.UNKNOWN, method="model",
        surface_term=surface if surface != Surface.UNKNOWN else None, translated_text=translated, translation_provider=translation_provider,
    ))


def reserve_model_call(request: Request) -> int | None:
    recent = request.app.state.interpretations
    now = monotonic()
    while recent and recent[0] <= now - 60:
        recent.popleft()
    if len(recent) >= request.app.state.interpretation_limit:
        return ceil(recent[0] + 60 - now)
    recent.append(now)
    return None


def rate_limited(request: Request, limit: str, retry_after: int) -> JSONResponse:
    trace.get_current_span().set_attribute("rate_limit.kind", limit)
    event("rate_limited", request_id=request.state.request_id, limit=limit, retry_after=retry_after)
    return JSONResponse({"detail": "rate_limited", "limit": limit}, status_code=429,
                        headers={"Retry-After": str(retry_after)})


def report_interpretation(request: Request, result: InterpretResult) -> InterpretResult:
    result.presentation = review_view(result, result.model_dump())
    attributes = {
        "interpretation.method": result.method,
        "interpretation.translated": result.translated_text is not None,
        "interpretation.surface": result.surface,
        "interpretation.materials": result.materials,
    }
    span = trace.get_current_span()
    span.set_attributes(attributes)
    if result.translation_provider:
        span.set_attribute("interpretation.translation_provider", result.translation_provider)
    if result.surface_term:
        span.set_attribute("interpretation.surface_term", result.surface_term)
    for field in ("object_type", "device", "substrate", "finish"):
        value = getattr(result, field)
        if value:
            span.set_attribute(f"interpretation.{field}", value)
    event(
        "interpretation", request_id=request.state.request_id,
        method=result.method, surface=result.surface, surface_term=result.surface_term,
        materials=result.materials, object_type=result.object_type, device=result.device, substrate=result.substrate,
        finish=result.finish, translated=result.translated_text is not None,
        translation_provider=result.translation_provider,
    )
    return result


@app.post("/api/assess", operation_id="assess")
def assess_request(inputs: AssessmentInput) -> Decision:
    return assess_cleaning(inputs)


app.mount("/", mcp.streamable_http_app())
