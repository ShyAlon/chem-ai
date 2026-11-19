from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .activities import activity
from .definitions import read_data
from .knowledge_client import KnowledgeClient, KnowledgeUnavailable
from .presentation import DisplayField, InputField, Language
from .knowledge_models import Compound, EvidenceResults, Provenance, ReferenceMeasurement

router = APIRouter(prefix="/api/research")


class ResearchTool(BaseModel):
    id: str
    title: dict[str, str]
    description: dict[str, str]
    fields: list[InputField]


class ResearchCatalog(BaseModel):
    title: dict[str, str]
    intro: dict[str, str]
    tools: list[ResearchTool]


class ResearchCard(BaseModel):
    title: str
    text: str
    fields: list[DisplayField] = Field(default_factory=list)
    provenance: Provenance | None = None


class ResearchResult(BaseModel):
    cards: list[ResearchCard]


class ResearchInput(BaseModel):
    locale: Language = "en"
    values: dict[str, str] = Field(max_length=5)


class CompoundInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=120)


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=200)


class CompareInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    mass_g: float = Field(ge=0.001, le=1000000)
    volume_ml: float = Field(ge=0.001, le=1000000)
    reference_id: str = Field(max_length=80)


RESEARCH_DATA = read_data("research.json")
INPUT_MODELS = {"compound": CompoundInput, "evidence": EvidenceInput, "compare": CompareInput}
REFERENCES = {item["id"]: item for item in read_data("knowledge.json")["references"]}
for tool in RESEARCH_DATA["tools"]:
    properties = INPUT_MODELS[tool["id"]].model_json_schema()["properties"]
    for field in tool["fields"]:
        constraints = properties[field["id"]]
        field.update(
            minimum=constraints.get("minimum"),
            maximum=constraints.get("maximum"),
            max_length=constraints.get("maxLength"),
        )
        if field["id"] == "reference_id":
            field["options"] = [
                {"id": item["id"], "label": {"en": f"{item['temperature_c']:g} °C", "he": f"{item['temperature_c']:g} °C"}}
                for item in REFERENCES.values()
            ]
RESEARCH_CATALOG = ResearchCatalog.model_validate(RESEARCH_DATA)
LABELS = RESEARCH_DATA["labels"]


@router.get("/catalog", operation_id="research_catalog")
def catalog() -> ResearchCatalog:
    return RESEARCH_CATALOG


@router.post("/{tool}", operation_id="research_evaluate")
async def evaluate(tool: Literal["compound", "evidence", "compare"], data: ResearchInput, request: Request) -> ResearchResult:
    labels = LABELS[data.locale]
    client: KnowledgeClient = request.app.state.knowledge
    try:
        if tool == "compound":
            inputs = CompoundInput.model_validate(data.values)
            compound = await client.call("lookup_compound", {"query": inputs.query}, Compound)
            return ResearchResult(cards=[ResearchCard(
                title=compound.name, text=labels["compound_note"], provenance=compound.provenance,
                fields=[
                    DisplayField(label="PubChem CID", value=str(compound.cid)),
                    DisplayField(label=labels["formula"], value=compound.formula),
                    DisplayField(label=labels["weight"], value=f"{compound.molecular_weight:g} {compound.unit}"),
                ],
            )])
        if tool == "evidence":
            inputs = EvidenceInput.model_validate(data.values)
            results = await client.call("search_evidence", {"query": inputs.query}, EvidenceResults)
            return ResearchResult(cards=[
                ResearchCard(title=item.title[data.locale], text=item.summary[data.locale], provenance=item.provenance)
                for item in results.items
            ])
        inputs = CompareInput.model_validate(data.values)
        if inputs.reference_id not in REFERENCES:
            raise ValueError("Unknown reference")
        reference = await client.call("get_reference", {"reference_id": inputs.reference_id}, ReferenceMeasurement)
        with activity("calculation", "reference.compare", reference_id=reference.id, unit=reference.unit) as step:
            measured = inputs.mass_g / inputs.volume_ml
            difference = measured - reference.value
            percentage = difference / reference.value * 100
            step.details.update(measured=round(measured, 8), reference=reference.value, difference_percent=round(percentage, 4))
        return ResearchResult(cards=[ResearchCard(
            title=labels["comparison_title"], text=labels["comparison_note"], provenance=reference.provenance,
            fields=[
                DisplayField(label=labels["temperature"], value=f"{reference.temperature_c:g} °C"),
                DisplayField(label=labels["measured"], value=f"{measured:.5f} {reference.unit}"),
                DisplayField(label=labels["reference"], value=f"{reference.value:.5f} {reference.unit}"),
                DisplayField(label=labels["difference"], value=f"{percentage:+.3f}%"),
            ],
        )])
    except KnowledgeUnavailable:
        raise HTTPException(503, labels["unavailable"]) from None
    except ValueError:
        raise HTTPException(422, labels["invalid"]) from None
