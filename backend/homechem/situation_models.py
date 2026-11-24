"""Stable semantic contract shared by parsing, clarification, and policy."""
from typing import Literal
from pydantic import BaseModel, Field


class TextSpan(BaseModel):
    start: int
    end: int
    text: str


class SituationEntity(BaseModel):
    id: str
    kind: Literal['object', 'material', 'finish', 'product', 'tool', 'device', 'problem', 'condition']
    value: str
    role: Literal['target', 'problem', 'supply', 'context', 'attribute']
    evidence: TextSpan


class SituationAction(BaseModel):
    intent: str
    verb: str
    modality: Literal['requested', 'historical', 'negated', 'uncertain']
    evidence: TextSpan
    targets: list[str] = Field(default_factory=list)


class SituationRelation(BaseModel):
    subject: str
    predicate: str
    object: str
    evidence: TextSpan


class SituationFact(BaseModel):
    subject: str
    predicate: str
    value: str | bool
    polarity: Literal['affirmed', 'negated', 'uncertain'] = 'affirmed'
    time: Literal['past', 'current', 'proposed', 'unknown'] = 'current'
    origin: Literal['stated', 'inferred', 'clarification'] = 'stated'
    evidence: list[TextSpan] = Field(default_factory=list)


class Situation(BaseModel):
    version: str = '1'
    original_text: str
    english_text: str
    source_language: str = 'en'
    translation_provider: str | None = None
    actions: list[SituationAction] = Field(default_factory=list)
    entities: list[SituationEntity] = Field(default_factory=list)
    relations: list[SituationRelation] = Field(default_factory=list)
    facts: list[SituationFact] = Field(default_factory=list)
    target_ids: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    covered_positions: list[int] = Field(default_factory=list)
    ignored_positions: list[int] = Field(default_factory=list)

    def values(self, predicate: str, subject: str | None = None) -> set[str | bool]:
        subjects = {subject} if subject else set(self.target_ids)
        facts = [fact for fact in self.facts if fact.predicate == predicate and fact.subject in subjects]
        if predicate in {'material','finish'} and any(fact.origin == 'clarification' for fact in facts):
            facts = [fact for fact in facts if fact.origin == 'clarification']
        return {fact.value for fact in facts if fact.polarity == 'affirmed' and fact.time in {'past', 'current'}}

    def targets(self) -> list[SituationEntity]:
        return [entity for entity in self.entities if entity.id in self.target_ids]
