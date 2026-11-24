import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from homechem.catalog import MaterialCatalog
from homechem.interpretation import resolve
from homechem.knowledge_client import KnowledgeClient, KnowledgeUnavailable
from homechem.terminology import OntologyResults, lookup_terms


@pytest.mark.parametrize('text,object_type', [
    ('Clean my copper saucepan', 'saucepan'),
    ('Wash my velvet curtains', 'curtain'),
    ('How should I clean my mac keyboard', 'keyboard'),
])
def test_unlisted_physical_targets_have_wordnet_identity(text, object_type):
    result = resolve(text)
    assert result.object_type == object_type
    assert not result.allow_model
    assert result.substrate is None
    assert result.entities[0].sense_ids
    assert result.entities[0].source == 'wordnet'
    assert result.interpretation.surface == 'unknown'


def test_specific_material_retains_identity_and_parent():
    result = resolve('Clean my porcelain sink')
    assert result.substrate == 'porcelain'
    assert result.diagnostics.material_classes == ['porcelain', 'ceramic']
    assert result.interpretation.surface == 'ceramic_sink'
    material = next(entity for entity in result.entities if entity.kind == 'material')
    assert material.id == 'material:porcelain'
    assert material.classes == ['material:ceramic']
    assert resolve('Clean my copper saucepan').terminology_queries == ['copper']
    assert resolve('Clean my dirty keyboard').terminology_queries == []
    assert resolve('Clean the laptop keyboard and mouse').object_type is None


@pytest.mark.parametrize('parents', [['missing'], ['sample']])
def test_material_hierarchy_rejects_missing_parents_and_cycles(parents):
    with pytest.raises(ValidationError):
        MaterialCatalog(materials=[{'id': 'sample', 'labels': {'en': 'Sample', 'he': 'דוגמה'}, 'aliases': ['sample'], 'parents': parents}])


def test_ols_uses_official_text_json_format_and_cache(monkeypatch):
    from homechem import knowledge_client
    import json
    payload = {'items': [{'iri': 'http://purl.obolibrary.org/obo/CHEBI_26710', 'curie': 'CHEBI:26710', 'label': ['sodium chloride']}]}
    session = AsyncMock()
    session.call_tool.return_value = SimpleNamespace(isError=False, structuredContent=None, content=[SimpleNamespace(type='text', text=json.dumps(payload))])
    @asynccontextmanager
    async def transport(*args, **kwargs):
        yield None, None, None
    @asynccontextmanager
    async def client_session(*args):
        yield session
    monkeypatch.setattr(knowledge_client, 'streamablehttp_client', transport)
    monkeypatch.setattr(knowledge_client, 'ClientSession', client_session)
    async def exercise():
        client = KnowledgeClient('https://www.ebi.ac.uk/ols4/api/mcp', 'ols')
        result = await lookup_terms(client, 'sodium chloride')
        assert result.items[0].curie == 'CHEBI:26710'
        await lookup_terms(client, 'sodium chloride')
        session.call_tool.assert_awaited_once()
        assert session.call_tool.await_args.args[0] == 'searchClasses'
        assert session.call_tool.await_args.args[1]['ontologyId'] == 'chebi'
        session.call_tool.return_value.content[0].text = '{invalid'
        with pytest.raises(KnowledgeUnavailable):
            await lookup_terms(client, 'different query')
    asyncio.run(exercise())


def test_ols_candidates_do_not_change_policy_and_unavailability_is_explicit():
    async def exercise():
        client = AsyncMock()
        client.call.return_value = OntologyResults(items=[])
        assert not (await lookup_terms(client, 'copper')).items
        client.call.side_effect = KnowledgeUnavailable('offline')
        with pytest.raises(KnowledgeUnavailable):
            await lookup_terms(client, 'copper')
        assert resolve('Clean my copper saucepan').interpretation.surface == 'unknown'
    asyncio.run(exercise())


def test_terminology_workflow_returns_provenance_and_never_promotes_candidates(monkeypatch, evidence_client):
    from collections import deque
    import httpx
    from homechem.main import app
    from homechem.rate_limit import QuestionCooldown
    client = AsyncMock()
    client.call.return_value = OntologyResults(items=[{
        'iri': 'http://purl.obolibrary.org/obo/CHEBI_28694', 'curie': 'CHEBI:28694',
        'label': ['copper atom'], 'definition': ['A copper atom.'],
    }])
    for key, value in {'terminology': client, 'question_cooldown': QuestionCooldown(0), 'trust_proxy_client_ip': False,
                       'interpretations': deque(), 'interpretation_limit': 12}.items():
        monkeypatch.setattr(app.state, key, value, raising=False)
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
            lookup = await api.post('/api/research/terminology', json={'values': {'query': 'copper'}})
            assert lookup.status_code == 200
            card = lookup.json()['cards'][0]
            assert card['fields'][0]['value'] == 'CHEBI:28694'
            assert card['provenance']['publisher'] == 'EMBL-EBI OLS / ChEBI'
            assert card['provenance']['url'].startswith('https://www.ebi.ac.uk/ols4/')
            response = await api.post('/api/interpret', json={'text': 'Clean my copper saucepan'})
            assert response.status_code == 200
            result = response.json()
            assert result['object_type'] == 'saucepan'
            assert result['substrate'] is None
            assert result['surface'] == 'unknown'
            assert result['terminology'][0]['items'][0]['curie'] == 'CHEBI:28694'
            assert result['presentation']['en']['assessment'] is None
            activities = (await api.get('/api/activities/' + response.headers['x-activity-id'])).json()['activities']
            assert any(item['name'] == 'terminology.ols' and item['details']['outcome'] == 'candidates' for item in activities)
            client.call.side_effect = KnowledgeUnavailable('offline')
            unavailable = await api.post('/api/interpret', json={'text': 'Clean my copper saucepan'})
            assert unavailable.status_code == 200
            assert unavailable.json()['object_type'] == 'saucepan'
            assert unavailable.json()['terminology'] == []
    asyncio.run(exercise())
