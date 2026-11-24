import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DATA = Path(__file__).parent / "data"


def read_data(name: str):
    return json.loads((DATA / name).read_text())


class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceSource(Definition):
    title: str
    url: str = Field(pattern=r"^https://")
    language: Literal["en", "he"]


class ProcedureContent(Definition):
    title: str = Field(min_length=1)
    confirmation: str = Field(min_length=1)
    accept: str = Field(min_length=1)
    steps: list[str] = Field(min_length=1)
    why: str = Field(min_length=1)
    hint: str = Field(min_length=1)
    blocked_reason: str | None = None


class ProcedureCheck(Definition):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    label: dict[Literal["en", "he"], str]


class FactRequirement(Definition):
    predicate: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    expected: str | bool
    check: str | None = None
    question: dict[Literal["en", "he"], str]


class ProcedureDefinition(Definition):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    surface: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    object: str
    material: str | None
    intent: str = "clean"
    checks: list[ProcedureCheck] = Field(default_factory=list)
    requirements: list[FactRequirement] = Field(default_factory=list)
    finishes: list[str | None]
    supplies: str
    source: EvidenceSource
    chemistry_source: EvidenceSource | None = None
    content: dict[Literal["en", "he"], ProcedureContent]

    @model_validator(mode="after")
    def both_languages(self):
        if set(self.content) != {"en", "he"}:
            raise ValueError("Procedures require English and Hebrew content")
        return self


class ProcedureCatalog(Definition):
    procedures: list[ProcedureDefinition] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def consistent(self):
        from .catalog import load_materials
        materials = {item.id for item in load_materials().materials}
        lexicon = read_data("lexicon.json")
        ids, surfaces, targets = set(), set(), set()
        for entry in self.procedures:
            if entry.surface == "unknown":
                raise ValueError("The unknown surface is reserved")
            if entry.id in ids or entry.surface in surfaces or (entry.intent, entry.object, entry.material) in targets:
                raise ValueError("Procedure IDs, surfaces, and object/material targets must be unique")
            if (entry.material is not None and entry.material not in materials) or entry.object not in lexicon["objects"]:
                raise ValueError("Unknown procedure material or object")
            if entry.supplies not in lexicon["supply_combinations"]:
                raise ValueError("Unknown procedure supplies")
            if any(finish is not None and finish not in lexicon["finishes"] for finish in entry.finishes):
                raise ValueError("Unknown procedure finish")
            if entry.intent != "clean" and entry.intent not in lexicon.get("task_verbs", {}):
                raise ValueError("Unknown procedure intent")
            if entry.material is None and entry.intent == "clean":
                raise ValueError("Surface cleaning requires a material")
            if len({check.id for check in entry.checks}) != len(entry.checks) or any(set(check.label) != {"en", "he"} for check in entry.checks):
                raise ValueError("Procedure checks require unique IDs and bilingual labels")
            check_ids = {check.id for check in entry.checks}
            if any(set(requirement.question) != {"en", "he"} or (requirement.check and requirement.check not in check_ids) for requirement in entry.requirements):
                raise ValueError("Fact requirements need bilingual questions and valid check references")
            ids.add(entry.id)
            surfaces.add(entry.surface)
            targets.add((entry.intent, entry.object, entry.material))
        if read_data("settings.json")["example_procedure"] not in ids:
            raise ValueError("The configured example procedure must remain")
        return self


PROCEDURE_CATALOG = ProcedureCatalog(procedures=read_data("procedures.json"))
PROCEDURE_DEFINITIONS = PROCEDURE_CATALOG.procedures
