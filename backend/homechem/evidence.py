"""Shared MCP evidence stage for chemistry workflows."""

import asyncio

from .activities import activity
from .definitions import read_data
from .knowledge_client import KnowledgeClient, KnowledgeUnavailable
from .knowledge_models import EvidenceContext, EvidenceResults

MESSAGES = read_data("messages.json")


async def retrieve_evidence(client: KnowledgeClient | None, query: str) -> EvidenceContext:
    with activity("retrieval", "evidence.search", tool="search_evidence", query_truncated=len(query) > 200, timeout_seconds=4) as step:
        step.debug["query"] = query[:200]
        searched_documents = None
        search_method = None
        try:
            if client is None:
                raise KnowledgeUnavailable("Data client not initialized")
            # Supplementary evidence has a tighter budget than explicit Data lab lookups.
            async with asyncio.timeout(4):
                results = await client.call("search_evidence", {"query": query[:200]}, EvidenceResults)
            status = "matched" if results.items else "no_matches"
            message_key = "evidenceMatched" if results.items else "evidenceNoMatches"
            items = results.items
            searched_documents, search_method = results.searched_documents, results.search_method
            step.debug["search_terms"] = results.search_terms
        except (KnowledgeUnavailable, TimeoutError) as error:
            step.details["cause_type"] = type(error).__name__
            status, message_key, items = "unavailable", "evidenceUnavailable", []
        step.details.update(searched_documents=searched_documents, search_method=search_method, outcome=status, matches=len(items), source_ids=", ".join(item.id for item in items))
        return EvidenceContext(
            status=status, items=items, searched_documents=searched_documents, search_method=search_method,
            message={locale: messages[message_key] for locale, messages in MESSAGES.items()},
        )
