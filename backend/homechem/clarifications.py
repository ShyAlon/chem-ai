"""Catalog-driven questions and bounded continuations; no model calls on answers."""
from collections import OrderedDict
from dataclasses import dataclass, field
from time import monotonic
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field

from .definitions import PROCEDURE_DEFINITIONS, read_data
from .catalog import load_materials
from .presentation import InputField, InputOption
from .situation_models import Situation

CONFIG = read_data('situation.json')['questions']
MATERIALS = load_materials().materials
LABELS = read_data('labels.json')


def options(items):
    return [InputOption(id='', label={'en':'Choose an answer', 'he':'בחרו תשובה'}), *items]


def questions_for(frame: Situation, intent: str, object_type, substrate, candidate) -> list[InputField]:
    targets = frame.targets()
    candidates = targets if len(targets) > 1 else [entity for entity in frame.entities if entity.kind == 'object'] if not targets and any(action.modality == 'requested' for action in frame.actions) else []
    if candidates:
        return [InputField(id='target', label=CONFIG['target'], kind='select', options=options([
            InputOption(id=entity.id, label={locale: LABELS[locale]['objects'].get(entity.value, entity.value) + ' · ' + entity.evidence.text for locale in ('en','he')}) for entity in candidates
        ]))]
    eligible = [entry for entry in PROCEDURE_DEFINITIONS if entry.intent == intent and entry.object == object_type]
    denied_materials = {fact.value for fact in frame.facts if fact.subject in frame.target_ids and fact.predicate == 'material' and fact.polarity == 'negated'}
    if len(targets) == 1 and not substrate and candidate is None and any(entry.material for entry in eligible):
        return [InputField(id='material', label=CONFIG['material'], kind='select', options=options([
            *[InputOption(id=item.id, label=item.labels.model_dump()) for item in MATERIALS if item.id not in denied_materials],
            InputOption(id='other', label=CONFIG['other']), InputOption(id='unknown', label=CONFIG['unknown']),
        ]))]
    result = []
    if candidate:
        for requirement in candidate.requirements:
            if frame.values(requirement.predicate):
                continue
            if any(fact.subject in frame.target_ids and fact.predicate == requirement.predicate and fact.polarity == 'uncertain' for fact in frame.facts):
                result.append(InputField(id=requirement.predicate, kind='select', label=requirement.question, options=options([
                    InputOption(id='true', label={'en':'Yes', 'he':'כן'}), InputOption(id='false', label={'en':'No', 'he':'לא'}), InputOption(id='unknown', label=CONFIG['unknown']),
                ])))
    return result


class ClarifyInput(BaseModel):
    context_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    answers: dict[str, str] = Field(min_length=1, max_length=8)


@dataclass
class Budget:
    remaining: int = 8


@dataclass
class Context:
    english: str
    original: str
    translated: str | None
    provider: str | None
    situation: Situation
    answers: dict[str, str]
    allowed: dict[str, set[str]]
    assessment: dict | None
    budget: Budget = field(default_factory=Budget)


stored: OrderedDict[str, tuple[float, Context]] = OrderedDict()
TTL, MAX_CONTEXTS = 600, 500


def remember(context: Context) -> str:
    now = monotonic()
    for key in list(stored):
        if now - stored[key][0] > TTL:
            del stored[key]
    key = uuid4().hex
    stored[key] = (now, context)
    while len(stored) > MAX_CONTEXTS:
        stored.popitem(last=False)
    return key


def get_context(key: str) -> Context:
    item = stored.get(key)
    if item is None or monotonic() - item[0] > TTL:
        stored.pop(key, None)
        raise HTTPException(404, 'Clarification context expired; submit the question again')
    return item[1]


def consume(data: ClarifyInput) -> Context:
    context = get_context(data.context_id)
    if any(key not in context.allowed or value not in context.allowed[key] or not value for key, value in data.answers.items()):
        raise HTTPException(422, 'Answer was not offered for this question')
    if context.budget.remaining <= 0:
        raise HTTPException(409, 'Clarification limit reached; submit the question again')
    context.budget.remaining -= 1
    return context
