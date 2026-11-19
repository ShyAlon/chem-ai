from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .activities import activity
from .catalog import MaterialCatalog, MaterialDefinition, validate_material_references
from .definitions import PROCEDURE_CATALOG, ProcedureCatalog, ProcedureDefinition, EvidenceSource
from .application import SCENARIO_DEFINITIONS, ScenarioDefinition
from .interpretation import MATERIAL_SETS, resolve
from .lexicon import (
    CLEANING_TERMS, DEVICE_TERMS, FINISH_TERMS,
    MATERIAL_CATALOG, MATERIAL_TERMS, OBJECT_CATEGORIES, OBJECT_TERMS, QUESTION_WORDS,
    SURFACE_EXCLUSIONS,
)
from .normalization import has_hebrew, words
from .policy import POLICY_VERSION

router = APIRouter(prefix="/api/management")


class SupplyCombination(BaseModel):
    supplies: list[str]
    result: str


class ProcedureRule(BaseModel):
    supplies: str
    rule: str
    source: EvidenceSource
    chemistry_source: EvidenceSource | None


class ProcedureRelation(BaseModel):
    object: str
    material: str
    surface: str
    finishes: list[str | None]
    rules: list[ProcedureRule]


class ManagementCatalog(BaseModel):
    debug_example: str
    materials: list[MaterialDefinition]
    objects: dict[str, list[str]]
    object_categories: dict[str, list[str]]
    devices: dict[str, list[str]]
    finishes: dict[str, list[str]]
    cleaning_supplies: dict[str, list[str]]
    exclusions: list[str]
    cleaning_verbs: list[str]
    question_words: list[str]
    supply_combinations: list[SupplyCombination]
    procedures: list[ProcedureRelation]
    policy_version: str
    procedure_definitions: list[ProcedureDefinition]
    scenarios: list[ScenarioDefinition]
    algorithm: list[str]


@router.get("/catalog", operation_id="management_catalog")
def catalog() -> ManagementCatalog:
    return ManagementCatalog(
        debug_example=PROCEDURE_CATALOG.procedures[0].content["en"].hint,
        materials=MATERIAL_CATALOG.materials,
        objects=OBJECT_TERMS, object_categories=OBJECT_CATEGORIES,
        devices=DEVICE_TERMS, finishes=FINISH_TERMS,
        cleaning_supplies=MATERIAL_TERMS, exclusions=SURFACE_EXCLUSIONS,
        cleaning_verbs=CLEANING_TERMS, question_words=sorted(QUESTION_WORDS),
        supply_combinations=[
            SupplyCombination(supplies=sorted(supplies), result=result)
            for supplies, result in MATERIAL_SETS.items()
        ],
        procedures=[
            ProcedureRelation(
                object=entry.object, material=entry.material, surface=entry.surface,
                finishes=entry.finishes,
                rules=[ProcedureRule(supplies=entry.supplies, rule=entry.id,
                                     source=entry.source, chemistry_source=entry.chemistry_source)],
            )
            for entry in PROCEDURE_CATALOG.procedures
        ],
        policy_version=POLICY_VERSION,
        procedure_definitions=PROCEDURE_CATALOG.procedures,
        scenarios=SCENARIO_DEFINITIONS,
        algorithm=[
            "Hebrew detection → configured translator → English input",
            "Unicode normalization → possessive removal → tokenization → English stemming",
            "Cleaning supplies matched first and excluded from target matching",
            "Objects and WordNet categories → device → substrate → finish → damage exclusions",
            "Object/material phrase linking → reviewed surface and compatible finish",
            "Remaining words → supply combination or unknown",
            "Model fallback only for unresolved cleaning targets; no automatic approval",
            "User confirmation → deterministic assessment over surface and supplies",
        ],
    )


@router.post("/validate", operation_id="management_validate")
def validate_catalog(data: MaterialCatalog) -> MaterialCatalog:
    try:
        return validate_material_references(data, {entry.material for entry in PROCEDURE_CATALOG.procedures})
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.post("/validate-procedures", operation_id="management_validate_procedures")
def validate_procedures(data: ProcedureCatalog) -> ProcedureCatalog:
    return data


class DebugInput(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@router.post("/resolve", operation_id="management_resolve")
def debug_resolution(data: DebugInput) -> dict:
    if has_hebrew(data.text):
        return {"requires_translation": True, "message": "Enter the English translation to inspect deterministic resolution."}
    with activity("normalization", "normalization.resolve"):
        return {
            "requires_translation": False,
            "tokens": words(data.text), "noun_lemmas": words(data.text, nouns=True),
            "resolution": asdict(resolve(data.text)),
        }
