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


def test_http_assessment_and_failed_calculation_return_correlated_traces(evidence_client):
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
    assert record.details["returned_surface"] == "unknown"
    assert record.details["result_code"] == "no_catalog_match"
    assert "glass_tabletop" in record.debug["allowed_surfaces"]
    assert "private" not in record.model_dump_json()


def test_debug_zip_contains_correlated_request_response_logs_and_trace(evidence_client):
    from io import BytesIO
    import json
    from zipfile import ZipFile

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            payload = {'surface': 'glass_screen', 'materials': 'dry_microfiber_only', 'confirmed': True}
            response = await client.post('/api/assess', json=payload, headers={'Authorization': 'Bearer private-header'})
            archive_response = await client.get('/api/activities/' + response.headers['x-activity-id'] + '/download')
            assert archive_response.status_code == 200
            assert archive_response.headers['content-type'] == 'application/zip'
            assert archive_response.headers['cache-control'] == 'no-store'
            assert response.headers['x-request-id'] in archive_response.headers['content-disposition']
            with ZipFile(BytesIO(archive_response.content)) as archive:
                assert set(archive.namelist()) == {'manifest.json', 'trace.json', 'requests.json', 'logs.jsonl'}
                trace = json.loads(archive.read('trace.json'))
                assert trace['request_id'] == response.headers['x-request-id']
                requests = json.loads(archive.read('requests.json'))
                incoming = requests[0]
                assert incoming['request']['json']['surface'] == 'glass_screen'
                assert incoming['response']['json'] == response.json()
                logs = [json.loads(line) for line in archive.read('logs.jsonl').splitlines()]
                assert any(log['event'] == 'decision' for log in logs)
                assert any(log['event'] == 'http.response' and log['request_id'] == trace['request_id'] for log in logs)
                combined = b''.join(archive.read(name) for name in archive.namelist())
                assert b'private-value' not in combined and b'private-header' not in combined
            failed = await client.post('/api/scenarios/water/evaluate', json={'values': {'hardness': '-1'}})
            failed_zip = await client.get('/api/activities/' + failed.headers['x-activity-id'] + '/download')
            assert failed_zip.status_code == 200
            with ZipFile(BytesIO(failed_zip.content)) as archive:
                assert json.loads(archive.read('trace.json'))['status'] == 'error'
                assert json.loads(archive.read('requests.json'))[0]['status'] == 422
            assert (await client.get('/api/activities/missing/download')).status_code == 404
    asyncio.run(exercise())


def test_debug_zip_rejects_running_and_expired_trace(monkeypatch):
    from homechem.activities import download_trace
    key = begin(Collection('pending'))
    with pytest.raises(Exception) as error:
        download_trace(key)
    assert error.value.status_code == 409
    created = activities.stored[key][0]
    monkeypatch.setattr(activities, 'monotonic', lambda: created + activities.TTL + 1)
    with pytest.raises(Exception) as error:
        download_trace(key)
    assert error.value.status_code == 404


def test_debug_capture_bounds_json_and_redacts_outbound_credentials():
    from homechem.debug_bundle import HTTP_HOOKS, BODY_LIMIT, json_body
    collection = Collection('outbound')
    async def exercise():
        token = current.set(collection)
        try:
            async with httpx.AsyncClient(event_hooks=HTTP_HOOKS, transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'ok': True}))) as client:
                await client.post('https://example.org/tool?api_key=hidden&query=water', headers={'Authorization': 'Bearer hidden'}, json={'messages': ['private prompt']})
        finally:
            current.reset(token)
    asyncio.run(exercise())
    record = collection.requests[0]
    assert record['status'] == 200
    assert 'hidden' not in str(record) and 'private prompt' not in str(record)
    assert 'query=water' in record['url']
    assert json_body(b'x' * (BODY_LIMIT + 1))['omitted'] == 'body_limit'
    assert json_body(b'{"api_key":"private-value","text":"original text"}')['json'] == {'api_key': '[redacted]', 'text': 'original text'}


def test_debug_redaction_preserves_nlp_tokens_but_not_auth_tokens():
    from homechem.debug_bundle import json_body, safe_url
    import json
    payload = {
        'diagnostics': {'tokens': ['clear', 'clog', 'sink'], 'unrecognized_tokens': [], 'access_token': 'secret'},
        'tokens': 'credential', 'refresh_token': 'secret', 'input_tokens': 12,
        'other': {'tokens': ['credential']},
    }
    result = json_body(json.dumps(payload).encode())['json']
    assert result['diagnostics']['tokens'] == ['clear', 'clog', 'sink']
    assert result['diagnostics']['unrecognized_tokens'] == []
    assert result['diagnostics']['access_token'] == '[redacted]'
    assert result['tokens'] == result['refresh_token'] == '[redacted]'
    assert result['other']['tokens'] == '[redacted]'
    assert result['input_tokens'] == 12
    assert 'credential' not in safe_url('https://example.org?tokens=credential')
