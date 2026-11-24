from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .knowledge_models import EvidenceContext
from .situation_models import Situation
from .definitions import PROCEDURE_DEFINITIONS, EvidenceSource as Source, ProcedureContent


class Surface(StrEnum):
    CERAMIC_TILE_FLOOR = "ceramic_tile_floor"
    CERAMIC_SINK = "ceramic_sink"
    GLASS_SCREEN = "glass_screen"
    GLASS_TABLE = "glass_tabletop"
    UNKNOWN = "unknown"


class Materials(StrEnum):
    DISH_SOAP_AND_CLOTH = "mild_dish_soap_water_and_soft_cloth"
    DRY_MICROFIBER = "dry_microfiber_only"
    NOT_STATED = "not_stated"
    WATER_AND_MOP = "water_and_mop_only"
    WATER_AND_CLOTH = "water_and_microfiber_only"
    UNKNOWN = "unknown"


class Interpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    surface: str
    materials: str
    intent: str = "clean"


class AssessmentInput(Interpretation):
    confirmed: bool
    checks: dict[str, StrictBool] = Field(default_factory=dict)
    context_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


class Status(StrEnum):
    APPROVED = "approved"
    UNVERIFIED = "unverified"


class Decision(BaseModel):
    status: Status
    rule: str
    version: str
    source: Source | None = None
    chemistry_source: Source | None = None
    procedure: dict[str, ProcedureContent] | None = None
    evidence: EvidenceContext | None = None


POLICY_VERSION = "2026-11-20.10"
PROCEDURES = {(entry.surface, entry.supplies): entry for entry in PROCEDURE_DEFINITIONS}
PROCEDURES_BY_SURFACE = {entry.surface: entry for entry in PROCEDURE_DEFINITIONS}


def assess(inputs: AssessmentInput, *, situation: Situation | None = None) -> Decision:
    if not inputs.confirmed:
        return Decision(status=Status.UNVERIFIED, rule="confirmation_required", version=POLICY_VERSION)
    procedure = PROCEDURES.get((inputs.surface, inputs.materials))
    if procedure is None:
        return Decision(status=Status.UNVERIFIED, rule="outside_reviewed_scope", version=POLICY_VERSION)
    if inputs.intent != procedure.intent:
        return Decision(status=Status.UNVERIFIED, rule="intent_mismatch", version=POLICY_VERSION)
    if situation:
        for requirement in procedure.requirements:
            if any(value != requirement.expected for value in situation.values(requirement.predicate)):
                return Decision(status=Status.UNVERIFIED, rule="stated_fact_conflict", version=POLICY_VERSION)
    def known_check(check_id):
        return situation is not None and any(requirement.check == check_id and situation.values(requirement.predicate) == {requirement.expected} for requirement in procedure.requirements)
    if any(inputs.checks.get(check.id) is not True and not known_check(check.id) for check in procedure.checks):
        return Decision(status=Status.UNVERIFIED, rule="procedure_checks_required", version=POLICY_VERSION)
    return Decision(
        status=Status.APPROVED, rule=procedure.id, version=POLICY_VERSION,
        source=procedure.source, chemistry_source=procedure.chemistry_source, procedure=procedure.content,
    )
