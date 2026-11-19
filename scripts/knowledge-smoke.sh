#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
PYTHONPATH=backend backend/.venv/bin/python - "${1:-http://127.0.0.1:8002/mcp}" <<'PY'
import asyncio
import os
import sys

from homechem.knowledge_client import KnowledgeClient
from homechem.knowledge_models import Compound, EvidenceResults, ReferenceMeasurement

async def main():
    os.environ["MCP_DATA_URL"] = sys.argv[1]
    client = KnowledgeClient()
    compound = await client.call("lookup_compound", {"query": "water"}, Compound)
    evidence = await client.call("search_evidence", {"query": "surfactants"}, EvidenceResults)
    reference = await client.call("get_reference", {"reference_id": "water-density-21"}, ReferenceMeasurement)
    assert compound.cid == 962
    assert evidence.items
    assert reference.unit == "g/mL" and reference.temperature_c == 21
    print(f"PubChem CID {compound.cid} ({compound.provenance.mode}); {len(evidence.items)} evidence result(s); reference {reference.value} {reference.unit} at {reference.temperature_c} °C")
asyncio.run(main())
PY
