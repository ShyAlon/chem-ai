from dataclasses import dataclass

from pydantic import BaseModel, Field

from .lexicon import (
    CLEANING_TERMS, COMPATIBLE_FINISHES, DEVICE_TERMS, FINISH_TERMS, MATERIAL_TERMS, OBJECT_CATEGORIES, OBJECT_TERMS,
    QUESTION_WORDS, REVIEWED_TARGETS, SUBSTRATE_TERMS, SURFACE_EXCLUSIONS, SURFACE_TERMS,
)
from .normalization import words
from .entities import EntityReference, extract_targets, analyze_task_roles
from .lexicon import MATERIALS_BY_ID, material_lineage
from .lexicon import LEXICON
from .policy import Interpretation, Materials, Surface, PROCEDURES_BY_SURFACE
from .situation import build_situation
from .situation_models import Situation, SituationFact
from .clarifications import questions_for
from .presentation import InputField

from .matching import compile_terms, match_terms, find_terms


OBJECTS = compile_terms(OBJECT_TERMS)
OBJECT_CATEGORY_TERMS = compile_terms(OBJECT_CATEGORIES, nouns=True)
DEVICES = compile_terms(DEVICE_TERMS)
SUBSTRATES = compile_terms(SUBSTRATE_TERMS)
FINISHES = compile_terms(FINISH_TERMS)
MATERIALS = compile_terms(MATERIAL_TERMS)
EXCLUSIONS = compile_terms({"excluded": SURFACE_EXCLUSIONS})
CLEANING = compile_terms({"cleaning": CLEANING_TERMS})
TASKS = compile_terms({"clean": CLEANING_TERMS, **LEXICON.get("task_verbs", {})})
QUESTION_TOKENS = frozenset(words(" ".join(QUESTION_WORDS)))
MATERIAL_SETS = {
    frozenset(combination): result
    for result, combinations in LEXICON["supply_combinations"].items()
    for combination in combinations
}


def unique(matches: set[str]) -> str | None:
    return next(iter(matches)) if len(matches) == 1 else None



class ResolutionDiagnostics(BaseModel):
    tokens: list[str]
    noun_lemmas: list[str]
    matches: dict[str, list[str]]
    unrecognized_tokens: list[str]
    target_linked: bool
    candidate_surface: str
    model_fallback: bool
    reason_codes: list[str] = Field(default_factory=list)
    noun_phrases: list[str] = Field(default_factory=list)
    material_classes: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class Resolution:
    interpretation: Interpretation
    surface_term: str | None
    object_type: str | None
    device: str | None
    substrate: str | None
    finish: str | None
    allow_model: bool
    diagnostics: ResolutionDiagnostics
    entities: list[EntityReference]
    terminology_queries: list[str]
    object_query: str | None
    requested_component: str | None
    situation: Situation
    questions: list[InputField]


def resolve(text: str, answers: dict[str, str] | None = None) -> Resolution:
    tokens = words(text)
    ingredients, ingredient_positions = match_terms(tokens, MATERIALS)
    # A material phrase such as "glass cleaner" describes the cleaner, not the target.
    target_tokens = [word if index not in ingredient_positions else "" for index, word in enumerate(tokens)]
    objects, object_positions = match_terms(target_tokens, OBJECTS)
    noun_tokens = words(text, nouns=True)
    category_tokens = [
        token if index not in ingredient_positions | object_positions else ""
        for index, token in enumerate(noun_tokens)
    ]
    categories, category_positions = match_terms(category_tokens, OBJECT_CATEGORY_TERMS)
    objects.update(categories)
    object_positions.update(category_positions)
    devices, device_positions = match_terms(target_tokens, DEVICES)
    substrates, substrate_positions = match_terms(target_tokens, SUBSTRATES)
    finishes, finish_positions = match_terms(target_tokens, FINISHES)
    excluded, exclusion_positions = match_terms(target_tokens, EXCLUSIONS)
    cleaning, cleaning_positions = match_terms(target_tokens, CLEANING)
    tasks, task_positions = match_terms(target_tokens, TASKS)
    doc, inferred_tasks, inferred_actions = analyze_task_roles(text)
    tasks.update(inferred_tasks)
    if inferred_actions:
        _, action_positions = match_terms(tokens, compile_terms({"action": inferred_actions}))
        task_positions.update(action_positions)
    specific_tasks = tasks - {"clean"}
    intent = unique(specific_tasks) if specific_tasks else "clean"
    blocked_surfaces = set()

    entities = []
    targets = extract_targets(text, {token for _, phrase in TASKS for token in phrase} | set(words(" ".join(inferred_actions))), doc=doc, intent=intent or "unknown") if tasks else []
    context_positions = {index for target in targets for index in target.context_positions}
    reserved = ingredient_positions | substrate_positions | finish_positions | device_positions
    for target in targets:
        _, positions = match_terms(tokens, compile_terms({"target": (target.head,)}))
        if target.entity:
            entities.append(target.entity)
        if target.entity and not positions.intersection(object_positions | reserved):
            objects.add(target.lemma)
            object_positions.update(positions)
    groups = {
        'objects': find_terms(target_tokens, OBJECTS), 'categories': find_terms(category_tokens, OBJECT_CATEGORY_TERMS),
        'substrates': find_terms(target_tokens, SUBSTRATES), 'finishes': find_terms(target_tokens, FINISHES),
        'devices': find_terms(target_tokens, DEVICES), 'supplies': find_terms(tokens, MATERIALS),
        'exclusions': find_terms(target_tokens, EXCLUSIONS),
    }
    situation = build_situation(text, doc, targets, groups, intent, task_positions)
    requested_intents = {action.intent for action in situation.actions if action.modality == 'requested'}
    if len(requested_intents) == 1:
        intent = next(iter(requested_intents))
    elif len(requested_intents) > 1:
        intent = 'unknown'
        situation.ambiguities.append('intent')
    for predicate, value in (answers or {}).items():
        if predicate == 'target':
            chosen = next((item for item in situation.entities if item.kind == "object" and item.id == value), None)
            if chosen:
                situation.target_ids = [chosen.id]
        elif predicate in {'material', 'finish'}:
            if value != 'unknown' and len(situation.target_ids) == 1:
                situation.facts.append(SituationFact(subject=situation.target_ids[0], predicate=predicate, value=value, origin='clarification'))
        elif len(situation.target_ids) == 1 and value in {'true','false'}:
            # Clarification can resolve uncertainty; it cannot erase contrary stated facts.
            situation.facts.append(SituationFact(subject=situation.target_ids[0], predicate=predicate, value=value == 'true', origin='clarification'))
    objects = {item.value for item in situation.targets()}
    substrates = {str(value) for value in situation.values('material')}
    finishes = {str(value) for value in situation.values('finish')}
    devices = {str(value) for value in situation.values('device')}
    ingredients = {str(fact.value) for fact in situation.facts if fact.subject in situation.target_ids and fact.predicate == 'supplies'
                   and fact.polarity == 'affirmed' and fact.time == 'proposed'}
    excluded = situation.values('damage')
    # Retain a stated material for an object-free fragment without linking it to a target.
    if not situation.targets() and not groups['objects'] and not groups['categories']:
        substrates = {item.value for item in groups['substrates']}
    object_type, substrate, finish = unique(objects), unique(substrates), unique(finishes)
    material_classes = list(material_lineage(substrate))
    if substrate:
        definition = MATERIALS_BY_ID.get(substrate)
        entities.append(EntityReference(
            id=f"material:{substrate}", kind="material",
            label=definition.labels.en if definition else substrate, source="catalog",
            classes=[f"material:{value}" for value in material_classes[1:]],
            external_ids=definition.external_ids if definition else {},
        ))
    device = unique(devices)
    linked = bool(len(situation.target_ids) == 1 and situation.values('material'))
    candidates = {
        REVIEWED_TARGETS[(intent, object_type, material)] for material in material_classes
        if (intent, object_type, material) in REVIEWED_TARGETS
    } if linked else set()
    generic_surface = REVIEWED_TARGETS.get((intent, object_type, None))
    matched_surface = generic_surface or unique(candidates) or Surface.UNKNOWN
    surface_term = matched_surface if matched_surface != Surface.UNKNOWN else object_type or substrate
    if linked:
        surface_term = SURFACE_TERMS.get((object_type, substrate), surface_term)

    procedure = PROCEDURES_BY_SURFACE.get(matched_surface)
    pending_requirements = []
    if procedure:
        for requirement in procedure.requirements:
            if any(value != requirement.expected for value in situation.values(requirement.predicate)):
                blocked_surfaces.add(matched_surface)
            if not situation.values(requirement.predicate) and any(fact.predicate == requirement.predicate and fact.subject in situation.target_ids and fact.polarity == 'uncertain' for fact in situation.facts):
                pending_requirements.append(requirement.predicate)
    surface = Surface.UNKNOWN
    compatible_finishes = COMPATIBLE_FINISHES.get(matched_surface, ())
    if not excluded and (generic_surface or (len(finishes) <= 1 and finish in compatible_finishes)) and matched_surface not in blocked_surfaces and not pending_requirements:
        surface = matched_surface
    elif matched_surface != Surface.UNKNOWN:
        surface_term = object_type

    covered = ingredient_positions | object_positions | device_positions | substrate_positions | finish_positions | exclusion_positions | cleaning_positions | task_positions | context_positions
    covered.update(situation.covered_positions)
    covered.update(situation.ignored_positions)
    remaining = {token for index, token in enumerate(tokens) if index not in covered}
    materials = Materials.UNKNOWN
    if remaining <= QUESTION_TOKENS:
        if ingredients:
            materials = MATERIAL_SETS.get(frozenset(ingredients), Materials.UNKNOWN)
        else:
            materials = Materials.NOT_STATED

    # The model can suggest an unfamiliar surface phrase. Material evidence stays local.
    allow_model = bool(
        intent == "clean" and cleaning and not objects and not devices and not substrates and not finishes and not excluded
        and "other" not in ingredients and (remaining - QUESTION_TOKENS)
    )
    reasons = []
    if not tasks:
        reasons.append("cleaning_intent_not_recognized")
    if len(objects) != 1:
        reasons.append("object_not_recognized" if not objects else "ambiguous_object")
    if len(substrates) != 1 and not generic_surface:
        reasons.append("material_not_identified" if not substrates else "ambiguous_material")
    if objects and substrates and not linked:
        reasons.append("object_material_not_linked")
    if linked and matched_surface == Surface.UNKNOWN:
        reasons.append("object_material_outside_catalog")
    if excluded:
        reasons.append("damaged_surface")
    if len(finishes) > 1:
        reasons.append("ambiguous_finish")
    if matched_surface != Surface.UNKNOWN and not generic_surface and finish not in compatible_finishes:
        reasons.append("unsupported_finish")
    if pending_requirements:
        reasons.append("required_fact_unknown")
    if matched_surface in blocked_surfaces:
        reasons.append("procedure_excluded")
    if materials == Materials.UNKNOWN:
        reasons.append("supplies_unverified")
    if remaining - QUESTION_TOKENS:
        reasons.append("unrecognized_terms")
    if allow_model:
        reasons.append("model_fallback_unfamiliar_target")
    questions = questions_for(situation, intent or "unknown", object_type, substrate, procedure)
    diagnostics = ResolutionDiagnostics(
        tokens=tokens, noun_lemmas=noun_tokens,
        noun_phrases=[target.phrase for target in targets], material_classes=material_classes,
        matches={name: sorted(values) for name, values in {
            "intents": tasks, "blocked_procedures": blocked_surfaces, "objects": objects, "categories": categories, "devices": devices, "substrates": substrates,
            "finishes": finishes, "supplies": ingredients, "exclusions": excluded, "cleaning": cleaning,
        }.items()},
        unrecognized_tokens=sorted(remaining - QUESTION_TOKENS), target_linked=linked,
        candidate_surface=matched_surface, model_fallback=allow_model, reason_codes=reasons,
    )
    return Resolution(
        interpretation=Interpretation(surface=surface, materials=materials, intent=intent or "unknown"),
        surface_term=surface_term,
        object_type=object_type,
        device=device,
        substrate=substrate,
        finish=finish,
        allow_model=allow_model,
        diagnostics=diagnostics,
        entities=entities,
        object_query=targets[0].object_query if len(targets) == 1 and object_type and not substrates and matched_surface == Surface.UNKNOWN else None,
        requested_component=targets[0].component if len(targets) == 1 else None,
        situation=situation,
        questions=questions,
        terminology_queries=list(dict.fromkeys(
            candidate for target in targets for candidate in target.material_candidates
            if not match_terms(words(candidate), SUBSTRATES)[0]
            and not match_terms(words(candidate), FINISHES)[0]
            and words(candidate) != words(target.lemma)
        ))[:2] if not substrates else [],
    )
