import asyncio

import httpx

from homechem.main import app
from homechem.policy import AssessmentInput, Materials, Status, Surface, assess
from homechem.providers import ModelProvider


def test_reviewed_scope_requires_confirmation_and_known_inputs():
    for surface in Surface:
        for materials in Materials:
            for confirmed in (True, False):
                decision = assess(AssessmentInput(surface=surface, materials=materials, confirmed=confirmed))
                approved = surface == Surface.STANDARD and materials == Materials.WATER_AND_CLOTH and confirmed
                assert (decision.status == Status.APPROVED) == approved
                assert (decision.source is not None) == approved


def test_fixture_interpretation_and_request_id(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fixture")

    async def run():
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/interpret", json={"text": "unclear"})
                assert response.json() == {"surface": "unknown", "materials": "unknown"}
                assert response.headers["x-request-id"]
                assert response.headers["cache-control"] == "no-store"

    asyncio.run(run())


def test_deepseek_adapter_reads_structured_response(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    def respond(request: httpx.Request) -> httpx.Response:
        import json

        payload = json.loads(request.content)
        assert request.url.path == "/responses"
        assert payload["text"]["format"]["type"] == "json_schema"
        assert payload["store"] is False
        return httpx.Response(200, json={"output": [{"type": "message", "content": [{
            "type": "output_text",
            "text": '{"surface":"unknown","materials":"unknown"}',
        }]}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            result = await ModelProvider(client, "deepseek").interpret("unclear")
            assert result.surface == Surface.UNKNOWN
            assert result.materials == Materials.UNKNOWN

    asyncio.run(run())
