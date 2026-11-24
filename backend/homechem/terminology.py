"""Source-linked chemical candidates; ontology results never grant policy approval."""

import asyncio
import os

from pydantic import BaseModel, Field

from .activities import activity
from .knowledge_client import KnowledgeClient, KnowledgeUnavailable


class OntologyParent(BaseModel):
    iri: str
    label: list[str] = Field(default_factory=list)


class OntologyTerm(BaseModel):
    iri: str
    curie: str
    label: list[str]
    definition: list[str] = Field(default_factory=list)
    isObsolete: bool = False
    directParent: list[OntologyParent] = Field(default_factory=list)


class OntologyResults(BaseModel):
    items: list[OntologyTerm]


def create_terminology_client() -> KnowledgeClient:
    return KnowledgeClient(os.getenv("OLS_MCP_URL", "https://www.ebi.ac.uk/ols4/api/mcp"), provider="ols")


async def lookup_terms(client: KnowledgeClient, query: str) -> OntologyResults:
    with activity("retrieval", "terminology.ols", ontology="chebi", timeout_seconds=5) as step:
        step.debug["query"] = query
        try:
            async with asyncio.timeout(5):
                results = await client.call("searchClasses", {
                    "query": query, "ontologyId": "chebi", "pageSize": 5,
                    "lang": "en", "includeObsoleteEntities": False,
                }, OntologyResults)
            results.items = [item for item in results.items if not item.isObsolete]
            step.details.update(outcome="candidates" if results.items else "no_matches", matches=len(results.items))
            step.debug["candidate_ids"] = [item.curie for item in results.items]
            step.debug["candidate_labels"] = [" / ".join(item.label) for item in results.items]
            return results
        except (TimeoutError, KnowledgeUnavailable):
            step.details["outcome"] = "unavailable"
            raise KnowledgeUnavailable("Terminology lookup unavailable") from None
