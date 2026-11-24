import asyncio
from collections import deque

import httpx
import pytest
from pydantic import ValidationError

from homechem.application import review_view
from homechem.interpretation import resolve
from homechem.main import app
from homechem.policy import AssessmentInput, PROCEDURES_BY_SURFACE, assess
from homechem.rate_limit import QuestionCooldown


@pytest.mark.parametrize('question', [
    'How do I unclog my sink?', 'Unblock my sink', 'My sink is clogged',
    "My sink won't drain", 'My sink is not draining',
    'Unclog my glazed ceramic sink', 'Unclog my stainless steel sink with a plunger',
])
def test_unclogging_is_a_distinct_deterministic_task(question):
    result = resolve(question)
    assert result.interpretation.intent == 'unclog'
    assert result.interpretation.surface == 'sink_drain'
    assert not result.allow_model
    assert result.object_query is None  # No basin-material guess is needed.
    assert 'material_not_identified' not in result.diagnostics.reason_codes
    view = review_view(result.interpretation, {'diagnostics': result.diagnostics.model_dump()})['en']
    assert view.assessment.intent == 'unclog'
    assert len(view.checks) == 3


def test_cleaning_and_unclogging_do_not_select_each_others_procedures():
    assert resolve('Clean my ceramic sink').interpretation.surface == 'ceramic_sink'
    assert resolve('Unclog my ceramic sink').interpretation.surface == 'sink_drain'
    assert resolve('Unclog my glass table').interpretation.surface == 'unknown'
    assert resolve('Clean my sink').interpretation.surface == 'unknown'


@pytest.mark.parametrize('question', [
    'Unclog my sink after I used drain cleaner',
    'Unclog my sink with bleach', 'Unclog my sink with baking soda and vinegar',
    'Unclog my cracked sink', 'Unclog my leaking sink',
])
def test_mentioned_chemicals_or_damage_prevent_a_plunging_offer(question):
    result = resolve(question)
    assert result.interpretation.surface == 'unknown'
    view = review_view(result.interpretation, {'diagnostics': result.diagnostics.model_dump()})['en']
    assert view.assessment is None
    if 'procedure_excluded' in result.diagnostics.reason_codes:
        assert 'do not plunge' in view.confirmation


def test_policy_requires_each_structured_condition_and_matching_intent():
    procedure = PROCEDURES_BY_SURFACE['sink_drain']
    payload = {'surface': 'sink_drain', 'materials': procedure.supplies, 'intent': 'unclog', 'confirmed': True}
    checks = {check.id: True for check in procedure.checks}
    assert assess(AssessmentInput(**payload)).rule == 'procedure_checks_required'
    for key in checks:
        assert assess(AssessmentInput(**payload, checks={**checks, key: False})).status == 'unverified'
    assert assess(AssessmentInput(**{**payload, 'intent': 'clean'}, checks=checks)).rule == 'intent_mismatch'
    assert assess(AssessmentInput(**payload, checks=checks)).status == 'approved'
    with pytest.raises(ValidationError):
        AssessmentInput(**payload, checks={'chemical_free': 'true'})


def test_api_confirms_conditions_before_returning_unclogging_steps(monkeypatch, evidence_client):
    monkeypatch.setattr(app.state, 'question_cooldown', QuestionCooldown(0), raising=False)
    monkeypatch.setattr(app.state, 'trust_proxy_client_ip', False, raising=False)
    monkeypatch.setattr(app.state, 'interpretations', deque(), raising=False)
    monkeypatch.setattr(app.state, 'interpretation_limit', 12, raising=False)
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
            interpreted = await api.post('/api/interpret', json={'text': 'How do I unclog my sink?'})
            assert interpreted.status_code == 200
            result = interpreted.json()
            assert result['resolution_status'] == 'ready_for_confirmation'
            assert result['substrate'] is None
            view = result['presentation']['en']
            missing = await api.post('/api/assess', json=view['assessment'])
            assert missing.json()['status'] == 'unverified'
            approved = await api.post('/api/assess', json={**view['assessment'], 'checks': {check['id']: True for check in view['checks']}})
            assert approved.json()['rule'] == 'sink_drain_mechanical_unclogging'
            assert approved.json()['procedure']['he']['why']
            blocked = await api.post('/api/interpret', json={'text': 'Unclog my sink after using drain cleaner'})
            assert blocked.json()['presentation']['en']['assessment'] is None
            assert 'do not plunge' in blocked.json()['presentation']['en']['confirmation']
    asyncio.run(exercise())


@pytest.mark.parametrize('question', [
    'How do I clear a clog in the sink?',
    'How do I remove the blockage from my sink?',
    'Clear an obstruction in my sink',
])
def test_problem_nouns_are_not_competing_physical_targets(question):
    result = resolve(question)
    assert result.interpretation.intent == 'unclog'
    assert result.interpretation.surface == 'sink_drain'
    assert result.interpretation.materials == 'not_stated'
    assert result.object_type == 'sink'
    assert result.diagnostics.unrecognized_tokens == []
    assert {entity.label for entity in result.entities if entity.kind == 'object'} == {'sink'}
    assert not result.allow_model


@pytest.mark.parametrize('question', [
    'Clear a clog in my sink and bathtub',
    'Clear a clog in the pipe under my sink',
    'Clear a clog in the sink after using drain cleaner',
])
def test_problem_role_resolution_preserves_ambiguity_and_exclusions(question):
    assert resolve(question).interpretation.surface == 'unknown'


def test_cleaning_footwear_is_not_a_blockage_task():
    result = resolve('Clean my wooden clogs in the sink')
    assert result.interpretation.intent == 'clean'
    assert result.interpretation.surface != 'sink_drain'
