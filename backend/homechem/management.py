from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .activities import activity
from .evidence import retrieve_evidence
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
from .entities import CONFIG
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
    material: str | None
    intent: str = "clean"
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
    entity_sources: dict = Field(default_factory=dict)
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
                object=entry.object, material=entry.material, intent=entry.intent, surface=entry.surface,
                finishes=entry.finishes,
                rules=[ProcedureRule(supplies=entry.supplies, rule=entry.id,
                                     source=entry.source, chemistry_source=entry.chemistry_source)],
            )
            for entry in PROCEDURE_CATALOG.procedures
        ],
        policy_version=POLICY_VERSION,
        procedure_definitions=PROCEDURE_CATALOG.procedures,
        scenarios=SCENARIO_DEFINITIONS,
        entity_sources={**CONFIG, "chemical_ontology": "ChEBI via official OLS MCP", "ontology_results": "candidates only; never policy approval"},
        algorithm=[
            "Hebrew detection → configured translator → English input",
            "Unicode normalization → possessive removal → tokenization → English stemming",
            "Cleaning supplies matched first and excluded from target matching",
            "spaCy noun phrases → WordNet physical-object classes → catalog overlay",
            "Specific material identity → explicit parent classes → finish → damage exclusions",
            "Unknown substance modifiers → optional OLS MCP ChEBI candidates (5-second budget)",
            "Task intent → object/material phrase linking, or a material-independent mechanical procedure",
            "Remaining words → supply combination or unknown",
            "Shared MCP evidence search → matched sources, no matches, or unavailable",
            "Model fallback only for unresolved cleaning targets; no automatic approval",
            "User confirmation and required condition checks → deterministic intent/surface/supplies assessment",
        ],
    )


@router.post("/validate", operation_id="management_validate")
def validate_catalog(data: MaterialCatalog) -> MaterialCatalog:
    try:
        return validate_material_references(data, {entry.material for entry in PROCEDURE_CATALOG.procedures if entry.material is not None})
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.post("/validate-procedures", operation_id="management_validate_procedures")
def validate_procedures(data: ProcedureCatalog) -> ProcedureCatalog:
    return data


class DebugInput(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@router.post("/resolve", operation_id="management_resolve")
async def debug_resolution(data: DebugInput, request: Request) -> dict:
    if has_hebrew(data.text):
        return {"requires_translation": True, "message": "Enter the English translation to inspect deterministic resolution."}
    with activity("normalization", "normalization.resolve"):
        result = {
            "requires_translation": False,
            "tokens": words(data.text), "noun_lemmas": words(data.text, nouns=True),
            "resolution": asdict(resolve(data.text)),
        }
    resolved = result["resolution"]
    object_client = getattr(request.app.state, "object_materials", None)
    if resolved["object_query"] and object_client:
        result["object_materials"] = await object_client.compare(resolved["object_query"], resolved["requested_component"])
    result["evidence"] = await retrieve_evidence(getattr(request.app.state, "knowledge", None), data.text)
    return result
