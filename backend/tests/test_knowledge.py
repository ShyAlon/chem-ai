import asyncio

import httpx

from homechem import knowledge_server
from homechem.activities import Collection, current
from homechem.knowledge_models import Compound
from homechem.main import app


def test_pubchem_adapter_parses_identity_and_keeps_provenance(monkeypatch):
    monkeypatch.delenv("KNOWLEDGE_MODE", raising=False)
    original = httpx.AsyncClient
    def respond(request):
        assert request.url.host == "pubchem.ncbi.nlm.nih.gov"
        assert "/name/water/property/" in request.url.path
        return httpx.Response(200, json={"PropertyTable": {"Properties": [{
            "CID": 962, "IUPACName": "water", "MolecularFormula": "H2O", "MolecularWeight": "18.015",
        }]}})
    monkeypatch.setattr(knowledge_server.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    value = asyncio.run(knowledge_server.lookup_compound("water"))
    assert value.cid == 962 and value.molecular_weight == 18.015
    assert value.provenance.mode == "live"
    assert value.provenance.url.endswith("/962")


def test_curated_evidence_search_and_condition_specific_reference():
    result = knowledge_server.search_evidence("surfactants")
    assert result.items[0].id == "surfactants"
    assert result.searched_documents == 4
    assert result.search_method == "keyword_overlap"
    assert result.search_terms == ["surfactants"]
    assert result.items[0].provenance.mode == "curated"
    reference = knowledge_server.get_reference("water-density-21")
    assert reference.value == 0.99802
    assert reference.temperature_c == 21
    assert reference.unit == "g/mL"
    assert not knowledge_server.search_evidence("zzzxxyy").items


def test_research_comparison_runs_reference_retrieval_then_calculation(monkeypatch):
    class DataClient:
        async def call(self, tool, arguments, output):
            assert tool == "get_reference"
            return knowledge_server.get_reference(arguments["reference_id"])
    monkeypatch.setattr(app.state, "knowledge", DataClient(), raising=False)
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/research/compare", json={"values": {
                "mass_g": "99.802", "volume_ml": "100", "reference_id": "water-density-21",
            }})
            assert response.status_code == 200
            result = response.json()["cards"][0]
            assert result["fields"][-1]["value"] == "+0.000%"
            assert result["provenance"]["publisher"] == "USGS"
            bad = await client.post("/api/research/compare", json={"values": {
                "mass_g": "nan", "volume_ml": "0", "reference_id": "water-density-21",
            }})
            assert bad.status_code == 422
    asyncio.run(exercise())
