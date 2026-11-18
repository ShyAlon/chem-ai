from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Surface(StrEnum):
    STANDARD = "studio_display_standard_glass"
    UNKNOWN = "unknown"


class Materials(StrEnum):
    WATER_AND_CLOTH = "water_and_microfiber_only"
    UNKNOWN = "unknown"


class Locale(StrEnum):
    EN = "en"
    HE = "he"


class Interpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    surface: Surface
    materials: Materials


class AssessmentInput(Interpretation):
    confirmed: bool


class Status(StrEnum):
    APPROVED = "approved"
    UNVERIFIED = "unverified"


class Source(BaseModel):
    title: str
    url: str
    language: Locale


class Decision(BaseModel):
    status: Status
    rule: str
    version: str
    source: Source | None = None


POLICY_VERSION = "2026-11-18.1"
DISPLAY_SOURCE = Source(
    title="Clean the Studio Display",
    url="https://support.apple.com/en-gb/guide/studio-display/apd1cf09caf2/2026/mac/27",
    language=Locale.EN,
)


def assess(inputs: AssessmentInput) -> Decision:
    if not inputs.confirmed:
        return Decision(status=Status.UNVERIFIED, rule="confirmation_required", version=POLICY_VERSION)
    if inputs.surface != Surface.STANDARD or inputs.materials != Materials.WATER_AND_CLOTH:
        return Decision(status=Status.UNVERIFIED, rule="outside_reviewed_scope", version=POLICY_VERSION)
    return Decision(
        status=Status.APPROVED,
        rule="studio_display_water_cleaning",
        version=POLICY_VERSION,
        source=DISPLAY_SOURCE,
    )
