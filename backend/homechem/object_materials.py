"""Compare free external knowledge graphs without inferring exposed materials."""

import asyncio
from collections import OrderedDict
from datetime import UTC, datetime
import json
import re
from time import monotonic, perf_counter
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from .activities import activity


class MaterialClaim(BaseModel):
    label: str
    source_id: str
    component: str | None = None
    references: list[str] = Field(default_factory=list)


class ObjectCandidate(BaseModel):
    id: str
    label: str
    description: str = ""
    url: str
    materials: list[MaterialClaim] = Field(default_factory=list)


class ProviderResult(BaseModel):
    provider: str
    status: Literal['matched', 'no_material_data', 'no_matches', 'unavailable']
    elapsed_ms: float
    cached: bool = False
    mode: Literal['live', 'fixture'] = 'live'
    retrieved_at: str
    candidates: list[ObjectCandidate] = Field(default_factory=list)
    reason: str | None = None


class ObjectMaterialsResult(BaseModel):
    query: str
    component: str | None = None
    providers: list[ProviderResult]
    # A product-level material statement is not proof of the exposed component/finish.
    requires_confirmation: bool = True


class ObjectMaterialClient:
    def __init__(self, client: httpx.AsyncClient, fixture: bool = False):
        self.client = client
        self.fixture = fixture
        self.cache: OrderedDict[tuple[str, str], tuple[float, ProviderResult]] = OrderedDict()

    async def compare(self, query: str, component: str | None = None) -> ObjectMaterialsResult:
        results = await asyncio.gather(*(self.lookup(provider, query) for provider in ('wikidata', 'dbpedia')))
        return ObjectMaterialsResult(query=query, component=component, providers=list(results))

    async def lookup(self, provider: str, query: str) -> ProviderResult:
        started = perf_counter()
        key = (provider, query.strip().casefold())
        with activity('retrieval', 'object_materials.' + provider, provider=provider, timeout_seconds=6) as step:
            step.debug['query'] = query
            cached = self.cache.get(key)
            if cached and monotonic() - cached[0] < 3600:
                self.cache.move_to_end(key)
                result = cached[1].model_copy(update={'cached': True, 'elapsed_ms': 0})
            else:
                try:
                    async with asyncio.timeout(6):
                        if self.fixture:
                            candidates = [ObjectCandidate(id='fixture:watch', label='Apple Watch', description='Product family (test fixture)', url='https://www.wikidata.org/wiki/Q18010946')] if query.casefold() == 'apple watch' else []
                        else:
                            candidates = await (self.wikidata(query) if provider == 'wikidata' else self.dbpedia(query))
                    status = 'matched' if any(item.materials for item in candidates) else 'no_material_data' if candidates else 'no_matches'
                    result = ProviderResult(provider=provider, status=status, candidates=candidates,
                        elapsed_ms=round((perf_counter() - started) * 1000, 2), retrieved_at=datetime.now(UTC).isoformat(), mode='fixture' if self.fixture else 'live')
                    self.cache[key] = (monotonic(), result)
                    while len(self.cache) > 128:
                        self.cache.popitem(last=False)
                except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError, AttributeError) as error:
                    result = ProviderResult(provider=provider, status='unavailable', reason=type(error).__name__,
                        elapsed_ms=round((perf_counter() - started) * 1000, 2), retrieved_at=datetime.now(UTC).isoformat())
            step.details.update(outcome=result.status, matches=len(result.candidates), material_claims=sum(len(item.materials) for item in result.candidates), cached=result.cached, mode=result.mode)
            step.debug['candidate_ids'] = [item.id for item in result.candidates]
            step.debug['material_claims'] = [f'{item.label}: {claim.label} ({claim.component or "component unspecified"})' for item in result.candidates for claim in item.materials]
            return result

    async def wd_get(self, **params):
        response = await self.client.get('https://www.wikidata.org/w/api.php', params={'format': 'json', **params}, headers={'User-Agent': 'HomeChem/0.1 (material identification; public read-only API)'})
        response.raise_for_status()
        data = response.json()
        if 'error' in data:
            raise ValueError('Wikidata API error')
        return data

    async def wikidata(self, query: str) -> list[ObjectCandidate]:
        search = await self.wd_get(action='wbsearchentities', search=query, language='en', limit=3)
        ids = [item['id'] for item in search['search'] if re.fullmatch(r'Q\d+', item['id'])]
        if not ids:
            return []
        data = await self.wd_get(action='wbgetentities', ids='|'.join(ids), props='labels|descriptions|claims', languages='en')
        candidates, pending, label_ids = [], [], set()
        for entity_id in ids:
            entity = data['entities'][entity_id]
            candidate = ObjectCandidate(id=entity_id, label=entity.get('labels', {}).get('en', {}).get('value', entity_id), description=entity.get('descriptions', {}).get('en', {}).get('value', ''), url='https://www.wikidata.org/wiki/' + entity_id)
            candidates.append(candidate)
            for statement in entity.get('claims', {}).get('P186', [])[:12]:
                if statement.get('rank') == 'deprecated':
                    continue
                value = statement.get('mainsnak', {}).get('datavalue', {}).get('value', {})
                material = value.get('id') if isinstance(value, dict) else None
                if not material or not re.fullmatch(r'Q\d+', material):
                    continue
                parts = [part.get('datavalue', {}).get('value', {}).get('id') for part in statement.get('qualifiers', {}).get('P518', [])]
                parts = [part for part in parts if part and re.fullmatch(r'Q\d+', part)]
                references = []
                for reference in statement.get('references', []):
                    for snak in reference.get('snaks', {}).get('P854', []):
                        url = snak.get('datavalue', {}).get('value')
                        if isinstance(url, str) and url.startswith('https://'):
                            references.append(url)
                label_ids.update([material, *parts])
                pending.append((candidate, material, parts, references[:5]))
        labels = {}
        ordered_ids = sorted(label_ids)
        for offset in range(0, len(ordered_ids), 50):
            labels.update((await self.wd_get(action='wbgetentities', ids='|'.join(ordered_ids[offset:offset + 50]), props='labels', languages='en'))['entities'])
        def label(entity_id):
            return labels.get(entity_id, {}).get('labels', {}).get('en', {}).get('value', entity_id)
        for candidate, material, parts, references in pending:
            candidate.materials.append(MaterialClaim(label=label(material), source_id=material, component=', '.join(map(label, parts)) or None, references=references))
        return candidates

    async def dbpedia(self, query: str) -> list[ObjectCandidate]:
        # Exact label variants avoid guessing resource URLs or issuing full-graph fuzzy scans.
        labels = sorted({query.strip(), query.strip().title(), query.strip().capitalize()})
        values = ' '.join(json.dumps(label, ensure_ascii=False) + '@en' for label in labels)
        sparql = '''PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?entity ?label ?material ?materialLabel WHERE {
 VALUES ?label { ''' + values + ''' }
 ?entity rdfs:label ?label .
 OPTIONAL { ?entity (<http://dbpedia.org/ontology/material>|<http://dbpedia.org/property/material>) ?material .
 OPTIONAL { ?material rdfs:label ?materialLabel . FILTER(lang(?materialLabel) = "en") } }
} LIMIT 24'''
        response = await self.client.get('https://dbpedia.org/sparql', params={'query': sparql, 'format': 'application/sparql-results+json'}, headers={'User-Agent': 'HomeChem/0.1 (material identification; public read-only API)'})
        response.raise_for_status()
        candidates = {}
        for row in response.json()['results']['bindings']:
            entity_id = row['entity']['value']
            if not entity_id.startswith('http://dbpedia.org/resource/') or ':' in entity_id.removeprefix('http://dbpedia.org/resource/'):
                continue
            if entity_id not in candidates:
                if len(candidates) >= 3:
                    continue
                candidates[entity_id] = ObjectCandidate(id=entity_id, label=row['label']['value'], url=entity_id.replace('http://', 'https://', 1))
            if 'material' in row:
                claim = MaterialClaim(label=row.get('materialLabel', row['material'])['value'], source_id=row['material']['value'])
                if claim not in candidates[entity_id].materials:
                    candidates[entity_id].materials.append(claim)
        return list(candidates.values())
