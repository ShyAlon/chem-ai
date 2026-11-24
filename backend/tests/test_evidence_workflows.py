import asyncio
from collections import deque

import httpx

from homechem.knowledge_client import KnowledgeUnavailable
from homechem.knowledge_server import search_evidence
from homechem.main import app
from homechem.providers import FixtureProvider
from homechem.rate_limit import QuestionCooldown


def test_unresolved_cleaning_retrieves_evidence_without_inventing_a_procedure(monkeypatch, evidence_client):
    for key, value in {
        "provider": FixtureProvider(), "question_cooldown": QuestionCooldown(0),
        "trust_proxy_client_ip": False, "interpretations": deque(), "interpretation_limit": 12,
    }.items():
        monkeypatch.setattr(app.state, key, value, raising=False)
    question = "How do I clean my mac keyboard"

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/interpret", json={"text": question})
            assert response.status_code == 200
            result = response.json()
            assert result["surface"] == "unknown"
            assert result["resolution_status"] == "needs_details"
            assert "model_no_catalog_match" not in result["diagnostics"]["reason_codes"]
            assert "evidence_no_matches" in result["diagnostics"]["reason_codes"]
            assert result["evidence"]["status"] == "no_matches"
            assert result["presentation"]["en"]["assessment"] is None
            evidence_client.call.assert_awaited_once()
            assert evidence_client.call.await_args.args[:2] == ("search_evidence", {"query": question})
            trace = (await client.get("/api/activities/" + response.headers["x-activity-id"])).json()
            retrieval = next(item for item in trace["activities"] if item["name"] == "evidence.search")
            assert retrieval["details"]["outcome"] == "no_matches"
    asyncio.run(exercise())


def test_evidence_stage_covers_assessment_scenarios_and_management(evidence_client):
    evidence_client.call.return_value = search_evidence("surfactants")

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            responses = [
                await client.post("/api/assess", json={"surface": "ceramic_sink", "materials": "mild_dish_soap_water_and_soft_cloth", "confirmed": True}),
                await client.post("/api/scenarios/food/evidence", json={}),
                await client.post("/api/scenarios/water/evaluate", json={"values": {"hardness": "100"}}),
                await client.post("/api/management/resolve", json={"text": "Clean my ceramic sink"}),
            ]
            for response in responses:
                assert response.status_code == 200
                data = response.json()
                context = data if "items" in data else data["evidence"]
                assert context["status"] == "matched"
                assert context["items"][0]["provenance"]["publisher"] == "American Cleaning Institute"
            assert responses[0].json()["status"] == "approved"
            assert responses[2].json()["result"] == "Moderately hard"
            assert evidence_client.call.await_count == 4
            assert all(call.args[0] == "search_evidence" for call in evidence_client.call.await_args_list)
    asyncio.run(exercise())


def test_unavailable_evidence_does_not_block_a_reviewed_policy(evidence_client):
    evidence_client.call.side_effect = KnowledgeUnavailable("offline")
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/assess", json={
                "surface": "glass_screen", "materials": "dry_microfiber_only", "confirmed": True,
            })
            assert response.status_code == 200
            assert response.json()["status"] == "approved"
            assert response.json()["evidence"]["status"] == "unavailable"
            assert not response.json()["evidence"]["items"]
    asyncio.run(exercise())
