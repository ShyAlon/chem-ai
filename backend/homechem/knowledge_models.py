from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Provenance(KnowledgeModel):
    url: str = Field(pattern=r"^https://")
    publisher: str
    retrieved_at: str
    mode: Literal["live", "curated", "fixture"]


class Compound(KnowledgeModel):
    cid: int = Field(gt=0)
    name: str
    formula: str
    molecular_weight: float = Field(gt=0)
    unit: Literal["g/mol"] = "g/mol"
    provenance: Provenance


class EvidenceItem(KnowledgeModel):
    id: str
    title: dict[str, str]
    summary: dict[str, str]
    provenance: Provenance


class EvidenceResults(KnowledgeModel):
    items: list[EvidenceItem]


class ReferenceMeasurement(KnowledgeModel):
    id: str
    substance: str
    property: str
    value: float = Field(gt=0)
    unit: Literal["g/mL"]
    temperature_c: float
    conditions: str
    provenance: Provenance
