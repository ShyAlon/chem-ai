import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import httpx

from homechem.main import app


def test_application_catalog_and_backend_scenario_validation(evidence_client):
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            catalog = (await client.get("/api/catalog")).json()
            assert len(catalog["scenarios"]) == 8
            assert len(catalog["procedures"]) == 5
            assert catalog["procedures"][0]["he"]["steps"]
            hints = (await client.get("/api/hints", params={"text": "ceramic sink", "locale": "en"})).json()
            assert len(hints) == 1 and "ceramic sink" in hints[0]
            for value, expected in [("0", "Soft"), ("60", "Soft"), ("60.01", "Moderately hard"), ("120", "Moderately hard"), ("120.01", "Hard"), ("180", "Hard"), ("180.01", "Very hard")]:
                response = await client.post("/api/scenarios/water/evaluate", json={"locale": "en", "values": {"hardness": value}})
                assert response.status_code == 200
                assert response.json()["result"] == expected
            for values in ({"hardness": "-1"}, {"hardness": "NaN"}, {"hardness": "Infinity"}, {"hardness": ""}, {"hardness": "4", "extra": "2"}, {}):
                assert (await client.post("/api/scenarios/water/evaluate", json={"values": values})).status_code == 422
            ratio = await client.post("/api/scenarios/experiments/evaluate", json={"values": {"still": "60", "stirred": "20"}})
            assert "3.00" in ratio.json()["result"]
            assert (await client.post("/api/scenarios/experiments/evaluate", json={"values": {"still": "60", "stirred": "0"}})).status_code == 422
            hebrew = await client.post("/api/scenarios/labels/evaluate", json={"locale": "he", "values": {"ingredient": "enzymes"}})
            assert "אנזימים" in hebrew.json()["result"]
            assert (await client.post("/api/scenarios/labels/evaluate", json={"values": {"ingredient": "other"}})).status_code == 422
            assert (await client.post("/api/scenarios/missing/evaluate", json={"values": {}})).status_code == 404
    asyncio.run(exercise())


def test_new_procedure_requires_only_catalog_data(tmp_path):
    package = Path(__file__).resolve().parents[1] / "homechem"
    shutil.copytree(package, tmp_path / "homechem", ignore=shutil.ignore_patterns("__pycache__"))
    path = tmp_path / "homechem" / "data" / "procedures.json"
    entries = json.loads(path.read_text())
    addition = json.loads(json.dumps(next(item for item in entries if item["surface"] == "glass_tabletop")))
    addition.update(id="test_glass_mirror", surface="test_glass_mirror_surface", object="mirror")
    for locale in ("en", "he"):
        addition["content"][locale]["title"] = "Catalog-only test"
    entries.append(addition)
    path.write_text(json.dumps(entries))
    code = """
from homechem.interpretation import resolve
from homechem.policy import AssessmentInput, assess
from homechem.application import application_catalog, review_view
result = resolve("Clean my glass mirror with water and a microfiber cloth")
assert result.interpretation.surface == "test_glass_mirror_surface"
view = review_view(result.interpretation, {"surface_term": result.surface_term})["en"]
assert view.assessment.surface == "test_glass_mirror_surface"
decision = assess(AssessmentInput(**view.assessment.model_dump()))
assert decision.status == "approved"
assert decision.procedure["en"].title == "Catalog-only test"
assert len(application_catalog().procedures) == 6
"""
    env = {**os.environ, "PYTHONPATH": str(tmp_path), "NLTK_DATA": str(package.parent / ".nltk-data")}
    subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env, check=True, capture_output=True, text=True)
