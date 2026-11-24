"""Runtime English dictionaries derived from validated backend catalogs."""

from .catalog import load_materials
from .definitions import PROCEDURE_DEFINITIONS, read_data
from .normalization import category_terms

LEXICON = read_data("lexicon.json")
OBJECT_TERMS = LEXICON["objects"]
OBJECT_CATEGORIES = {key: category_terms(sense) for key, sense in LEXICON["object_categories"].items()}
DEVICE_TERMS = LEXICON["devices"]
MATERIAL_CATALOG = load_materials()
SUBSTRATE_TERMS = {item.id: tuple(item.aliases) for item in MATERIAL_CATALOG.materials}
FINISH_TERMS = LEXICON["finishes"]
REVIEWED_SURFACES = {(entry.object, entry.material): entry.surface for entry in PROCEDURE_DEFINITIONS if entry.intent == "clean"}
REVIEWED_TARGETS = {(entry.intent, entry.object, entry.material): entry.surface for entry in PROCEDURE_DEFINITIONS}
COMPATIBLE_FINISHES = {entry.surface: set(entry.finishes) for entry in PROCEDURE_DEFINITIONS}
MATERIAL_TERMS = LEXICON["cleaning_supplies"]
SURFACE_EXCLUSIONS = LEXICON["exclusions"]
CLEANING_TERMS = LEXICON["cleaning_verbs"]
QUESTION_WORDS = frozenset(LEXICON["question_words"])

SURFACE_TERMS = {(entry["object"], entry["material"]): entry["term"] for entry in LEXICON["surface_descriptions"]}


MATERIALS_BY_ID = {item.id: item for item in MATERIAL_CATALOG.materials}


def material_lineage(material_id: str | None) -> tuple[str, ...]:
    pending = [material_id] if material_id else []
    result = []
    while pending:
        value = pending.pop(0)
        if value not in result:
            result.append(value)
            definition = MATERIALS_BY_ID.get(value)
            if definition:
                pending.extend(definition.parents)
    return tuple(result)
