from math import isfinite
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from .definitions import PROCEDURE_DEFINITIONS, ProcedureContent, read_data
from .lexicon import MATERIAL_CATALOG
from .policy import Interpretation, Materials, PROCEDURES_BY_SURFACE
from .presentation import DisplayField, InputField, Language, Text
from .telemetry import event
from .activities import activity

router = APIRouter(prefix="/api")

MESSAGES = read_data("messages.json")
LABELS = read_data("labels.json")
GUIDE = read_data("guide.json")


class ScenarioSource(BaseModel):
    title: str
    url: str


class ScenarioView(BaseModel):
    id: str
    title: Text
    example: Text
    steps: dict[Language, list[str]]
    why: Text
    source: ScenarioSource
    fields: list[InputField]
    submit: Text


class Classification(BaseModel):
    kind: Literal["classification"]
    field: str
    thresholds: list[float]
    results: dict[Language, list[str]]


class Ratio(BaseModel):
    kind: Literal["ratio"]
    numerator: str
    denominator: str
    templates: Text


class Lookup(BaseModel):
    kind: Literal["lookup"]
    field: str
    values: dict[str, Text]


class ScenarioDefinition(ScenarioView):
    calculation: Classification | Ratio | Lookup | None = Field(default=None, discriminator="kind")

    @model_validator(mode="after")
    def consistent(self):
        fields = {field.id: field for field in self.fields}
        if len(fields) != len(self.fields):
            raise ValueError("Scenario input IDs must be unique")
        for field in self.fields:
            if set(field.label) != {"en", "he"}:
                raise ValueError("Scenario inputs require bilingual labels")
            if field.kind == "number" and (field.minimum is None or not isfinite(field.minimum)):
                raise ValueError("Numeric inputs require a finite minimum")
            if field.kind == "select" and (not field.options or len({option.id for option in field.options}) != len(field.options)):
                raise ValueError("Select inputs require unique options")
        calculation = self.calculation
        if calculation is None:
            if self.fields:
                raise ValueError("Scenario inputs require a calculation")
            return self
        if isinstance(calculation, Ratio):
            if set(fields) != {calculation.numerator, calculation.denominator}:
                raise ValueError("Ratio calculation must reference its two inputs")
            if any(field.kind != "number" for field in self.fields):
                raise ValueError("Ratio inputs must be numeric")
            if fields[calculation.denominator].minimum <= 0:
                raise ValueError("Ratio denominator must have a positive minimum")
            if set(calculation.templates) != {"en", "he"}:
                raise ValueError("Ratio output requires both languages")
            for template in calculation.templates.values():
                template.format(ratio="1.00")
        else:
            if set(fields) != {calculation.field}:
                raise ValueError("Calculation must reference its input")
            if isinstance(calculation, Classification):
                if fields[calculation.field].kind != "number":
                    raise ValueError("Classification input must be numeric")
                if any(not isfinite(value) for value in calculation.thresholds) or sorted(set(calculation.thresholds)) != calculation.thresholds:
                    raise ValueError("Classification thresholds must be finite and strictly ascending")
                if set(calculation.results) != {"en", "he"} or any(len(results) != len(calculation.thresholds) + 1 for results in calculation.results.values()):
                    raise ValueError("Classification requires bilingual output for every interval")
            elif fields[calculation.field].kind != "select" or set(calculation.values) != {option.id for option in fields[calculation.field].options}:
                raise ValueError("Lookup outputs must match its input options")
        return self


SCENARIO_DEFINITIONS = [ScenarioDefinition.model_validate(item) for item in read_data("scenarios.json")]
if len({item.id for item in SCENARIO_DEFINITIONS}) != len(SCENARIO_DEFINITIONS):
    raise ValueError("Scenario IDs must be unique")
SCENARIOS = [item.model_dump() for item in SCENARIO_DEFINITIONS]


class GuideStep(BaseModel):
    title: str
    text: str


class GuideView(BaseModel):
    title: str
    intro: str
    steps: list[GuideStep]
    exampleTitle: str
    question: str
    fields: list[list[str]]
    exampleResult: str
    back: str


class ApplicationCatalog(BaseModel):
    messages: dict[Language, dict[str, str]]
    management_messages: dict[Language, dict[str, str]]
    example_text: Text
    procedures: list[dict[Language, ProcedureContent]]
    scenarios: list[ScenarioView]
    guide: dict[Language, GuideView]


EXAMPLE_PROCEDURE = next(
    entry for entry in PROCEDURE_DEFINITIONS
    if entry.id == read_data("settings.json")["example_procedure"]
)
APPLICATION_CATALOG = ApplicationCatalog(
    example_text={locale: content.hint for locale, content in EXAMPLE_PROCEDURE.content.items()},
    messages=MESSAGES,
    management_messages=read_data("management_messages.json"),
    procedures=[entry.content for entry in PROCEDURE_DEFINITIONS],
    scenarios=[ScenarioView.model_validate(item) for item in SCENARIOS],
    guide=GUIDE,
)


@router.get("/catalog", operation_id="application_catalog")
def application_catalog() -> ApplicationCatalog:
    return APPLICATION_CATALOG


@router.get("/hints", operation_id="question_hints")
def hints(text: str = Query(default="", max_length=1000), locale: Language = "en") -> list[str]:
    terms = text.casefold().split()
    return [
        entry.content[locale].hint for entry in PROCEDURE_DEFINITIONS
        if entry.content[locale].hint != text
        and all(term in entry.content[locale].hint.casefold() for term in terms)
    ]


class AssessmentPayload(BaseModel):
    surface: str
    materials: str
    confirmed: bool = True


class ReviewView(BaseModel):
    fields: list[DisplayField]
    confirmation: str | None = None
    accept: str | None = None
    assessment: AssessmentPayload | None = None


def review_view(result: Interpretation, details: dict) -> dict[Language, ReviewView]:
    procedure = PROCEDURES_BY_SURFACE.get(result.surface)
    supported = procedure is not None and result.materials in (Materials.NOT_STATED, procedure.supplies)
    views = {}
    for locale in ("en", "he"):
        labels, messages = LABELS[locale], MESSAGES[locale]
        known = {**labels["objects"], **{item.id: item.labels.model_dump()[locale] for item in MATERIAL_CATALOG.materials}}
        surface = procedure.content[locale].title if procedure else known.get(details.get("surface_term"), messages["unknown"])
        fields = [DisplayField(label=messages["surface"], value=surface)]
        for key, title, names in (
            ("object_type", "objectType", labels["objects"]),
            ("device", "device", labels["devices"]),
            ("substrate", "substrate", {item.id: item.labels.model_dump()[locale] for item in MATERIAL_CATALOG.materials}),
            ("finish", "finish", labels["finishes"]),
        ):
            if details.get(key):
                fields.append(DisplayField(label=messages[title], value=names.get(details[key], details[key])))
        fields.append(DisplayField(label=messages["material"], value=labels["supplies"].get(result.materials, result.materials)))
        if supported:
            content = procedure.content[locale]
            views[locale] = ReviewView(
                fields=fields, confirmation=content.confirmation,
                accept=content.accept if result.materials == Materials.NOT_STATED else messages["assess"],
                assessment=AssessmentPayload(surface=procedure.surface, materials=procedure.supplies),
            )
        else:
            explanation = labels["screen_material"] if details.get("object_type") == "screen" and not details.get("substrate") else labels["outside_scope"]
            views[locale] = ReviewView(fields=fields, confirmation=explanation)
    return views


class ScenarioRequest(BaseModel):
    locale: Language = "en"
    values: dict[str, Annotated[str, Field(max_length=100)]] = Field(max_length=10)


class ScenarioResult(BaseModel):
    result: str


@router.post("/scenarios/{scenario_id}/evaluate", operation_id="evaluate_scenario")
def evaluate(scenario_id: str, data: ScenarioRequest) -> ScenarioResult:
    with activity("calculation", "scenario.evaluate", scenario=scenario_id) as operation:
        result = calculate_scenario(scenario_id, data)
        operation.details["result"] = result.result
        return result


def calculate_scenario(scenario_id: str, data: ScenarioRequest) -> ScenarioResult:
    scenario = next((item for item in SCENARIOS if item["id"] == scenario_id), None)
    if scenario is None:
        raise HTTPException(404, "Unknown scenario")
    calculation = scenario["calculation"]
    if calculation is None:
        raise HTTPException(422, "This scenario has no calculation")
    if set(data.values) != {field["id"] for field in scenario["fields"]}:
        raise HTTPException(422, "Provide exactly the defined scenario inputs")
    values = {}
    for field in scenario["fields"]:
        value = data.values[field["id"]]
        if field["kind"] == "number":
            try:
                number = float(value)
            except ValueError:
                raise HTTPException(422, "Numeric measurement required") from None
            if not isfinite(number) or number < field["minimum"]:
                raise HTTPException(422, "Measurement outside the supported range")
            values[field["id"]] = number
        else:
            if value not in {option["id"] for option in field["options"]}:
                raise HTTPException(422, "Unknown ingredient class")
            values[field["id"]] = value
    if calculation["kind"] == "classification":
        value = values[calculation["field"]]
        index = sum(value > boundary for boundary in calculation["thresholds"])
        result = calculation["results"][data.locale][index]
    elif calculation["kind"] == "ratio":
        ratio = values[calculation["numerator"]] / values[calculation["denominator"]]
        if not isfinite(ratio):
            raise HTTPException(422, "Measurement ratio outside the supported range")
        result = calculation["templates"][data.locale].format(ratio=f"{ratio:.2f}")
    else:
        result = calculation["values"][values[calculation["field"]]][data.locale]
    event("scenario.evaluated", scenario=scenario_id, method="deterministic")
    return ScenarioResult(result=result)
