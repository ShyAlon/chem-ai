from dataclasses import dataclass

from .lexicon import (
    CLEANING_TERMS, COMPATIBLE_FINISHES, DEVICE_TERMS, FINISH_TERMS, MATERIAL_TERMS, OBJECT_CATEGORIES, OBJECT_TERMS,
    QUESTION_WORDS, REVIEWED_SURFACES, SUBSTRATE_TERMS, SURFACE_EXCLUSIONS, SURFACE_TERMS,
)
from .normalization import words
from .lexicon import LEXICON
from .policy import Interpretation, Materials, Surface

type CompiledTerms = tuple[tuple[str, tuple[str, ...]], ...]


def compile_terms(groups: dict[str, tuple[str, ...]], *, nouns: bool = False) -> CompiledTerms:
    terms = [(key, tuple(words(alias, nouns=nouns))) for key, aliases in groups.items() for alias in aliases]
    return tuple(sorted(terms, key=lambda item: len(item[1]), reverse=True))


OBJECTS = compile_terms(OBJECT_TERMS)
OBJECT_CATEGORY_TERMS = compile_terms(OBJECT_CATEGORIES, nouns=True)
DEVICES = compile_terms(DEVICE_TERMS)
SUBSTRATES = compile_terms(SUBSTRATE_TERMS)
FINISHES = compile_terms(FINISH_TERMS)
MATERIALS = compile_terms(MATERIAL_TERMS)
EXCLUSIONS = compile_terms({"excluded": SURFACE_EXCLUSIONS})
CLEANING = compile_terms({"cleaning": CLEANING_TERMS})
QUESTION_TOKENS = frozenset(words(" ".join(QUESTION_WORDS)))
MATERIAL_SETS = {
    frozenset(combination): result
    for result, combinations in LEXICON["supply_combinations"].items()
    for combination in combinations
}


def match_terms(tokens: list[str], terms: CompiledTerms) -> tuple[set[str], set[int]]:
    found, covered = set(), set()
    for key, phrase in terms:
        width = len(phrase)
        for index in range(len(tokens) - width + 1):
            positions = range(index, index + width)
            if covered.intersection(positions):
                continue
            if tuple(tokens[index:index + width]) != phrase:
                continue
            found.add(key)
            covered.update(positions)
    return found, covered


def unique(matches: set[str]) -> str | None:
    return next(iter(matches)) if len(matches) == 1 else None


def has_phrase_link(
    tokens: list[str], object_positions: set[int], qualifier_positions: set[int],
    finish_positions: set[int], links: set[tuple[str, ...]],
) -> bool:
    return any(
        tuple(tokens[index] for index in range(min(obj, mat) + 1, max(obj, mat))
              if index not in finish_positions) in links
        for obj in object_positions for mat in qualifier_positions
    )


@dataclass(frozen=True)
class Resolution:
    interpretation: Interpretation
    surface_term: str | None
    object_type: str | None
    device: str | None
    substrate: str | None
    finish: str | None
    allow_model: bool


def resolve(text: str) -> Resolution:
    tokens = words(text)
    ingredients, ingredient_positions = match_terms(tokens, MATERIALS)
    # A material phrase such as "glass cleaner" describes the cleaner, not the target.
    target_tokens = [word if index not in ingredient_positions else "" for index, word in enumerate(tokens)]
    objects, object_positions = match_terms(target_tokens, OBJECTS)
    category_tokens = [
        token if index not in ingredient_positions | object_positions else ""
        for index, token in enumerate(words(text, nouns=True))
    ]
    categories, category_positions = match_terms(category_tokens, OBJECT_CATEGORY_TERMS)
    objects.update(categories)
    object_positions.update(category_positions)
    devices, device_positions = match_terms(target_tokens, DEVICES)
    substrates, substrate_positions = match_terms(target_tokens, SUBSTRATES)
    finishes, finish_positions = match_terms(target_tokens, FINISHES)
    excluded, exclusion_positions = match_terms(target_tokens, EXCLUSIONS)
    cleaning, cleaning_positions = match_terms(target_tokens, CLEANING)

    object_type, substrate, finish = unique(objects), unique(substrates), unique(finishes)
    device = unique(devices)
    links = {(), ("of",), ("made", "of"), ("made", "from")}
    if object_type == "screen":
        links.add(("with",))
    linked = has_phrase_link(tokens, object_positions, substrate_positions, finish_positions | device_positions, links)
    matched_surface = REVIEWED_SURFACES.get((object_type, substrate), Surface.UNKNOWN) if linked else Surface.UNKNOWN
    surface_term = matched_surface if matched_surface != Surface.UNKNOWN else object_type or substrate
    if linked:
        surface_term = SURFACE_TERMS.get((object_type, substrate), surface_term)

    surface = Surface.UNKNOWN
    compatible_finishes = COMPATIBLE_FINISHES.get(matched_surface, ())
    if not excluded and len(finishes) <= 1 and finish in compatible_finishes:
        surface = matched_surface
    elif matched_surface != Surface.UNKNOWN:
        surface_term = object_type

    covered = ingredient_positions | object_positions | device_positions | substrate_positions | finish_positions | exclusion_positions | cleaning_positions
    remaining = {token for index, token in enumerate(tokens) if index not in covered}
    materials = Materials.UNKNOWN
    if remaining <= QUESTION_TOKENS:
        if ingredients:
            materials = MATERIAL_SETS.get(frozenset(ingredients), Materials.UNKNOWN)
        else:
            materials = Materials.NOT_STATED

    # The model can suggest an unfamiliar surface phrase. Material evidence stays local.
    allow_model = bool(
        cleaning and not objects and not devices and not substrates and not finishes and not excluded
        and "other" not in ingredients and (remaining - QUESTION_TOKENS)
    )
    return Resolution(
        interpretation=Interpretation(surface=surface, materials=materials),
        surface_term=surface_term,
        object_type=object_type,
        device=device,
        substrate=substrate,
        finish=finish,
        allow_model=allow_model,
    )
