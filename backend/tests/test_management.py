import asyncio

import httpx
import pytest
from pydantic import ValidationError

from homechem.catalog import MaterialCatalog, load_materials
from homechem.interpretation import compile_terms, resolve
from homechem.main import app


def test_catalog_rejects_normalized_alias_collisions():
    entries = load_materials().model_dump()["materials"]
    entries.append({"id": "another", "labels": {"en": "Another", "he": "אחר"}, "aliases": ["glasses"]})
    with pytest.raises(ValidationError, match="Alias collision"):
        MaterialCatalog(materials=entries)


def test_new_material_is_recognized_without_approving_a_procedure(monkeypatch):
    import homechem.interpretation as interpretation
    entries = load_materials().model_dump()["materials"]
    entries.append({"id": "copper", "labels": {"en": "Copper", "he": "נחושת"}, "aliases": ["copper"]})
    validated = MaterialCatalog(materials=entries)
    monkeypatch.setattr(interpretation, "SUBSTRATES", compile_terms({item.id: tuple(item.aliases) for item in validated.materials}))
    result = resolve("Clean my copper sink")
    assert result.substrate == "copper"
    assert result.interpretation.surface == "unknown"
    assert not result.allow_model


def test_management_api_exposes_runtime_rules_validates_and_resolves(evidence_client):
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/management/catalog")
            assert response.status_code == 200
            data = response.json()
            assert len(data["procedures"]) == 5
            assert "teaspoon" in data["object_categories"]["cutlery"]
            assert any(item["id"] == "ceramic" for item in data["materials"])
            assert (await client.post("/api/management/validate", json={"materials": data["materials"]})).status_code == 200
            without_glass = [item for item in data["materials"] if item["id"] != "glass"]
            assert (await client.post("/api/management/validate", json={"materials": without_glass})).status_code == 422
            resolved = (await client.post("/api/management/resolve", json={"text": "Clean my ceramic sink"})).json()
            assert resolved["resolution"]["substrate"] == "ceramic"
            assert resolved["resolution"]["interpretation"]["surface"] == "ceramic_sink"
            translated = (await client.post("/api/management/resolve", json={"text": "כיור קרמי"})).json()
            assert translated["requires_translation"]
    asyncio.run(exercise())
