from unittest.mock import AsyncMock

import pytest

from homechem.knowledge_models import EvidenceResults
from homechem.main import app


@pytest.fixture
def evidence_client(monkeypatch):
    """Isolate API tests from external data; browser tests exercise real MCP transport."""
    monkeypatch.setattr(app.state, "object_materials", None, raising=False)
    monkeypatch.setattr("homechem.main.ObjectMaterialClient", lambda *args, **kwargs: None)
    client = AsyncMock()
    client.call.return_value = EvidenceResults(items=[])
    monkeypatch.setattr(app.state, "knowledge", client, raising=False)
    monkeypatch.setattr("homechem.main.KnowledgeClient", lambda: client)
    return client
