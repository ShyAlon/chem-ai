import asyncio
from collections import deque
import json

import httpx

from homechem.activities import Collection, current
from homechem.debug_bundle import HTTP_HOOKS
from homechem.interpretation import resolve
from homechem.main import app
from homechem.object_materials import ObjectMaterialClient
from homechem.rate_limit import QuestionCooldown


def test_product_and_exposed_component_are_extracted_without_device_aliases():
    direct = resolve('How do I clean my Apple Watch')
    assert direct.object_query == 'Apple Watch'
    assert direct.object_type == 'watch'
    assert direct.substrate is None
    part = resolve('How do I clean the screen of my Apple Watch')
    assert part.object_query == 'Apple Watch'
    assert part.requested_component == 'screen'
    assert resolve('Clean my ceramic sink').object_query is None


def test_free_providers_keep_material_claims_parts_sources_and_cache():
    calls = []
    def respond(request):
        calls.append(request)
        if request.url.host == 'dbpedia.org':
            assert 'VALUES ?label' in request.url.params['query']
            return httpx.Response(200, json={'results': {'bindings': [{
                'entity': {'value': 'http://dbpedia.org/resource/Example'}, 'label': {'value': 'Example'},
                'material': {'value': 'http://dbpedia.org/resource/Glass'}, 'materialLabel': {'value': 'glass'},
            }]}})
        params = request.url.params
        if params['action'] == 'wbsearchentities':
            return httpx.Response(200, json={'search': [{'id': 'Q1'}]})
        if params['props'] == 'labels':
            return httpx.Response(200, json={'entities': {'Q2': {'labels': {'en': {'value': 'glass'}}}, 'Q3': {'labels': {'en': {'value': 'screen'}}}}})
        return httpx.Response(200, json={'entities': {'Q1': {
            'labels': {'en': {'value': 'Example'}}, 'claims': {'P186': [{
                'mainsnak': {'datavalue': {'value': {'id': 'Q2'}}},
                'qualifiers': {'P518': [{'datavalue': {'value': {'id': 'Q3'}}}]},
                'references': [{'snaks': {'P854': [{'datavalue': {'value': 'https://example.org/specs'}}]}}],
            }, {'rank': 'deprecated', 'mainsnak': {'datavalue': {'value': {'id': 'Q9'}}}}]},
        }}})
    async def exercise():
        collection = Collection('free-api-request')
        token = current.set(collection)
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond), event_hooks=HTTP_HOOKS) as http:
                client = ObjectMaterialClient(http)
                result = await client.compare('Example', 'screen')
                assert all(provider.status == 'matched' for provider in result.providers)
                claim = result.providers[0].candidates[0].materials[0]
                assert claim.label == 'glass' and claim.component == 'screen'
                assert claim.references == ['https://example.org/specs']
                assert result.providers[1].candidates[0].materials[0].component is None
                assert result.requires_confirmation
                initial_calls = len(calls)
                cached = await client.compare('Example', 'case')
                assert all(provider.cached for provider in cached.providers)
                assert cached.component == 'case'
                assert len(calls) == initial_calls
                assert collection.requests and all(record['status'] == 200 for record in collection.requests)
        finally:
            current.reset(token)
    asyncio.run(exercise())


def test_provider_failures_and_missing_material_are_distinct():
    def respond(request):
        if request.url.host == 'dbpedia.org':
            return httpx.Response(503)
        if request.url.params['action'] == 'wbsearchentities':
            return httpx.Response(200, json={'search': [{'id': 'Q1'}]})
        return httpx.Response(200, json={'entities': {'Q1': {'labels': {'en': {'value': 'Example'}}}}})
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            result = await ObjectMaterialClient(http).compare('Example')
            assert [provider.status for provider in result.providers] == ['no_material_data', 'unavailable']
    asyncio.run(exercise())


def test_object_lookup_is_used_by_interpretation_management_and_data_lab(monkeypatch, evidence_client):
    async def exercise():
        async with httpx.AsyncClient() as http:
            app.state.object_materials = ObjectMaterialClient(http, fixture=True)
            monkeypatch.setattr(app.state, 'question_cooldown', QuestionCooldown(0), raising=False)
            monkeypatch.setattr(app.state, 'trust_proxy_client_ip', False, raising=False)
            monkeypatch.setattr(app.state, 'interpretations', deque(), raising=False)
            monkeypatch.setattr(app.state, 'interpretation_limit', 12, raising=False)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
                response = await api.post('/api/interpret', json={'text': 'How do I clean the screen of my Apple Watch'})
                assert response.status_code == 200
                result = response.json()
                assert result['object_materials']['query'] == 'Apple Watch'
                assert result['object_materials']['component'] == 'screen'
                assert result['substrate'] is None and result['surface'] == 'unknown'
                assert result['presentation']['en']['assessment'] is None
                assert any('wikidata' in field['label'] for field in result['presentation']['en']['fields'])
                inspector = await api.post('/api/management/resolve', json={'text': 'Clean my Apple Watch'})
                assert inspector.json()['object_materials']['providers'][0]['cached']
                for locale in ('en', 'he'):
                    research = await api.post('/api/research/object_materials', json={'locale': locale, 'values': {'query': 'Apple Watch', 'component': 'screen'}})
                    assert research.status_code == 200
                    assert research.json()['cards'][1]['provenance']['mode'] == 'fixture'
                assert 'Apple Watch' in json.dumps(result['object_materials'])
    asyncio.run(exercise())


def test_lowercase_product_phrases_survive_parser_pos_and_chunk_variations():
    for question in ('how do I clean my apple watch', 'how do I clean my apple watch?', 'How do I clean my Apple Watch'):
        result = resolve(question)
        assert result.object_type == 'watch'
        assert result.object_query.casefold() == 'apple watch'
        assert result.substrate is None
        assert not result.allow_model
    assert resolve('Clean my laptop keyboard and mouse').object_type is None
