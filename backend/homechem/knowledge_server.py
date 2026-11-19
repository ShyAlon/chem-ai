"""Independent MCP data service. No dependency on the app's policy or resolver."""

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from typing import Annotated

from .knowledge_models import Compound, EvidenceItem, EvidenceResults, Provenance, ReferenceMeasurement

data = json.loads((Path(__file__).parent / "data" / "knowledge.json").read_text())
server = FastMCP(
    "HomeChem chemistry data", stateless_http=True, json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*", "knowledge:*"],
        allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://knowledge:*"],
    ),
)


def provenance(url: str, publisher: str, mode="curated") -> Provenance:
    return Provenance(url=url, publisher=publisher, mode=mode, retrieved_at=datetime.now(UTC).isoformat())


@server.tool()
async def lookup_compound(query: Annotated[str, Field(min_length=1, max_length=120)]) -> Compound:
    """Resolve an English compound name or CID to PubChem identity and properties."""
    if os.getenv("KNOWLEDGE_MODE") == "fixture":
        if query.casefold().strip() not in {"water", "962"}:
            raise ValueError("Fixture contains only water")
        return Compound(cid=962, name="water", formula="H2O", molecular_weight=18.015,
                        provenance=provenance("https://pubchem.ncbi.nlm.nih.gov/compound/962", "PubChem", "fixture"))
    namespace = "cid" if query.isdecimal() else "name"
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/{namespace}/{quote(query, safe='')}/property/MolecularFormula,MolecularWeight,IUPACName/JSON"
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url)
        response.raise_for_status()
        candidates = response.json()["PropertyTable"]["Properties"]
    if len(candidates) != 1:
        raise ValueError("Ambiguous compound; use a PubChem CID")
    item = candidates[0]
    return Compound(
        cid=item["CID"], name=item["IUPACName"], formula=item["MolecularFormula"],
        molecular_weight=float(item["MolecularWeight"]),
        provenance=provenance(f"https://pubchem.ncbi.nlm.nih.gov/compound/{item['CID']}", "PubChem", "live"),
    )


@server.tool()
def search_evidence(query: Annotated[str, Field(min_length=1, max_length=200)]) -> EvidenceResults:
    """Search curated bilingual chemistry summaries with citations; not a live web search."""
    terms = set(re.findall(r"[^\W_]+", query.casefold())).difference(data["stop_words"])
    ranked = []
    for entry in data["evidence"]:
        content = " ".join([*entry["keywords"], *entry["title"].values(), *entry["summary"].values()])
        score = len(terms.intersection(re.findall(r"[^\W_]+", content.casefold())))
        if score:
            ranked.append((score, entry))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return EvidenceResults(items=[
        EvidenceItem(id=entry["id"], title=entry["title"], summary=entry["summary"],
                     provenance=provenance(entry["url"], entry["publisher"]))
        for _, entry in ranked[:5]
    ])


@server.tool()
def get_reference(reference_id: str) -> ReferenceMeasurement:
    """Retrieve a published water-density value at an explicitly selected temperature."""
    entry = next((item for item in data["references"] if item["id"] == reference_id), None)
    if entry is None:
        raise ValueError("Unknown reference measurement")
    values = {key: value for key, value in entry.items() if key not in {"url", "publisher"}}
    return ReferenceMeasurement(**values, provenance=provenance(entry["url"], entry["publisher"]))


app = server.streamable_http_app()
