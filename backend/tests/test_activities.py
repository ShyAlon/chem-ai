import asyncio

import httpx
import pytest

from homechem import activities
from homechem.activities import Collection, activity, begin, current, finish, get_trace
from homechem.main import app


def test_activity_records_live_progress_nested_steps_and_errors(monkeypatch):
    collection = Collection("test-request")
    token = current.set(collection)
    key = begin(collection)
    try:
        with activity("mcp", "test.lookup", tool="get_reference") as outer:
            assert get_trace(key).status == "running"
            assert get_trace(key).activities[0].status == "running"
            with activity("calculation", "test.calculation"):
                pass
        assert collection.records[1].parent_id == outer.id
        with pytest.raises(ValueError):
            with activity("model", "test.failure"):
                raise ValueError("secret prompt must not appear")
        finish(collection, False)
        result = get_trace(key)
        assert result.status == "error"
        assert [item.status for item in result.activities] == ["success", "success", "error"]
        assert "secret prompt" not in result.model_dump_json()
        created = activities.stored[key][0]
        monkeypatch.setattr(activities, "monotonic", lambda: created + activities.TTL + 1)
        with pytest.raises(Exception) as error:
            get_trace(key)
        assert error.value.status_code == 404
    finally:
        current.reset(token)


def test_http_assessment_and_failed_calculation_return_correlated_traces():
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            key = "a" * 32
            response = await client.post("/api/assess", headers={"X-Activity-Key": key}, json={
                "surface": "glass_screen", "materials": "dry_microfiber_only", "confirmed": True,
            })
            assert response.status_code == 200
            trace = (await client.get("/api/activities/" + response.headers["x-activity-id"])).json()
            assert trace["request_id"] == response.headers["x-request-id"]
            assert trace["activities"][0]["kind"] == "policy"
            assert trace["status"] == "success"
            failed = await client.post("/api/scenarios/water/evaluate", json={"values": {"hardness": "-1"}})
            failure_trace = (await client.get("/api/activities/" + failed.headers["x-activity-id"])).json()
            assert failed.status_code == 422
            assert failure_trace["status"] == "error"
            assert failure_trace["activities"][0]["status"] == "error"
            assert (await client.get("/api/activities/missing")).status_code == 404
    asyncio.run(exercise())


def test_model_activity_contains_usage_and_excludes_prompts(monkeypatch):
    from homechem.providers import ModelProvider
    monkeypatch.setenv("DEEPSEEK_API_KEY", "private-test-key")
    collection = Collection("model-request")

    def respond(request):
        return httpx.Response(200, json={
            "usage": {"input_tokens": 11, "output_tokens": 3},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": '{"surface":"unknown"}'}]}],
        })

    async def exercise():
        token = current.set(collection)
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                result = await ModelProvider(client, "deepseek").suggest_surface("private test question")
                assert result == "unknown"
        finally:
            current.reset(token)

    asyncio.run(exercise())
    assert len(collection.records) == 1
    record = collection.records[0]
    assert record.kind == "model" and record.status == "success"
    assert record.details["input_tokens"] == 11
    assert record.details["output_tokens"] == 3
    assert "private" not in record.model_dump_json()
