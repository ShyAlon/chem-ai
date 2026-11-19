import asyncio

import httpx

from homechem.policy import AssessmentInput, Materials, Status, Surface, assess
from homechem.providers import ModelProvider
from homechem.translation import AzureTranslator


def test_reviewed_scope_requires_confirmation_and_known_inputs():
    for surface in Surface:
        for materials in Materials:
            for confirmed in (True, False):
                decision = assess(AssessmentInput(surface=surface, materials=materials, confirmed=confirmed))
                approved_pairs = {
                    (Surface.GLASS_SCREEN, Materials.DRY_MICROFIBER),
                    (Surface.GLASS_TABLE, Materials.WATER_AND_CLOTH),
                    (Surface.CERAMIC_SINK, Materials.DISH_SOAP_AND_CLOTH),
                    (Surface.CERAMIC_TILE_FLOOR, Materials.WATER_AND_MOP),
                }
                approved = confirmed and (surface, materials) in approved_pairs
                assert (decision.status == Status.APPROVED) == approved
                assert (decision.source is not None) == approved


def test_ceramic_detergent_procedure_cites_the_chemistry():
    decision = assess(AssessmentInput(
        surface=Surface.CERAMIC_SINK, materials=Materials.DISH_SOAP_AND_CLOTH, confirmed=True,
    ))
    assert decision.status == Status.APPROVED
    assert decision.chemistry_source and "chemistry-cleaning" in decision.chemistry_source.url


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
            "text": '{"surface":"unknown"}',
        }]}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            result = await ModelProvider(client, "deepseek").suggest_surface("unclear")
            assert result == Surface.UNKNOWN

    asyncio.run(run())


def test_provider_translation_uses_a_plain_string_schema():
    def respond(request: httpx.Request) -> httpx.Response:
        import json

        payload = json.loads(request.content)
        assert payload["format"]["properties"]["text"] == {"title": "Text", "type": "string"}
        assert "Translate" in payload["messages"][0]["content"]
        return httpx.Response(200, json={"message": {"content": '{"text":"Care for my laptop screen"}'}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            result = await ModelProvider(client, "ollama").translate_to_english("איך מנקים את מסך המחשב הנייד?")
            assert result == "Care for my laptop screen"

    asyncio.run(run())


def test_azure_translates_hebrew_without_calling_an_llm():
    def respond(request: httpx.Request) -> httpx.Response:
        import json

        assert request.url.host == "api.cognitive.microsofttranslator.com"
        assert dict(request.url.params) == {"api-version": "3.0", "from": "he", "to": "en"}
        assert request.headers["ocp-apim-subscription-region"] == "test-region"
        assert json.loads(request.content) == [{"Text": "איך מנקים מסך זכוכית?"}]
        return httpx.Response(200, json=[{"translations": [{"text": "How do I clean a glass screen?"}]}])

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            translated = await AzureTranslator(client, "test-key", "test-region").translate_to_english(
                "איך מנקים מסך זכוכית?",
            )
            assert translated == "How do I clean a glass screen?"

    asyncio.run(run())


def test_assessment_api_runs_without_an_mcp_server():
    from homechem.main import app

    async def run():
        # No application lifespan or MCP session manager is started.
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for confirmed, surface, status, rule in [
                (True, "glass_screen", "approved", "glass_screen_dry_cleaning"),
                (False, "glass_screen", "unverified", "confirmation_required"),
                (True, "unlisted_surface", "unverified", "outside_reviewed_scope"),
            ]:
                response = await client.post("/api/assess", json={
                    "surface": surface, "materials": "dry_microfiber_only", "confirmed": confirmed,
                })
                assert response.status_code == 200
                assert response.headers["x-request-id"]
                decision = response.json()
                assert decision["status"] == status
                assert decision["rule"] == rule
                if status == "approved":
                    assert decision["procedure"]["en"]["steps"]
                    assert decision["source"]["url"]
    asyncio.run(run())
