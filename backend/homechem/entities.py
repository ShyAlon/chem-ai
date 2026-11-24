"""Local linguistic extraction and source-linked entity identities."""

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
import spacy

from .activities import activity
from .normalization import wordnet, words

CONFIG = json.loads((Path(__file__).parent / "data" / "entities.json").read_text())


class EntityReference(BaseModel):
    id: str
    kind: Literal["object", "material"]
    label: str
    source: Literal["catalog", "wordnet"]
    classes: list[str] = Field(default_factory=list)
    sense_ids: list[str] = Field(default_factory=list)
    modifiers: list[str] = Field(default_factory=list)
    external_ids: dict[str, str] = Field(default_factory=dict)


@dataclass(frozen=True)
class ExtractedTarget:
    head: str
    lemma: str
    phrase: str
    modifiers: list[str]
    material_candidates: list[str]
    entity: EntityReference | None
    object_query: str
    component: str | None
    context_positions: list[int]
    problem: str | None
    start: int
    end: int
    head_index: int


@lru_cache(maxsize=1)
def pipeline():
    return spacy.load(CONFIG["spacy_model"], exclude=["ner"])


@lru_cache(maxsize=2048)
def object_senses(phrase: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    senses = []
    ancestors = []
    for sense in wordnet.synsets(phrase.replace(" ", "_"), pos=wordnet.NOUN):
        hierarchy = {sense.name(), *(parent.name() for parent in sense.closure(lambda node: node.hypernyms()))}
        if hierarchy.intersection(CONFIG["object_roots"]):
            senses.append(sense.name())
            ancestors.append(hierarchy)
    common = set.intersection(*ancestors) if ancestors else set()
    return tuple(senses), tuple(sorted(common - set(senses)))


def nominal_chunks(doc):
    """Repair adjacent nominal objects without joining coordinated targets."""
    chunks = [(chunk, chunk.root) for chunk in doc.noun_chunks]
    # Ambiguous nouns such as "watch" can be tagged as verbs despite occupying
    # an object slot. Require a nominal compound and a physical WordNet sense.
    for root in doc:
        if (root.dep_ in {"dobj", "obj"} and root.pos_ == "VERB"
                and any(child.dep_ == "compound" and child.pos_ in {"NOUN", "PROPN"} for child in root.children)
                and object_senses(root.lemma_.casefold())[0]):
            span = doc[root.left_edge.i:root.i + 1]
            chunks = [(chunk, head) for chunk, head in chunks if not (span.start <= chunk.start and chunk.end <= span.end)]
            chunks.append((span, root))
    merged = []
    for chunk, root in sorted(chunks, key=lambda item: item[0].start):
        if merged:
            previous, head = merged[-1]
            if (previous.end == chunk.start and root.head == head.head
                    and root.dep_ in {"dobj", "obj"} and head.dep_ in {"dobj", "obj"}
                    and root.pos_ in {"NOUN", "PROPN"} and head.pos_ in {"NOUN", "PROPN"}):
                merged[-1] = (doc[previous.start:chunk.end], root)
                continue
        merged.append((chunk, root))
    return merged


@lru_cache(maxsize=2048)
def is_task_problem(lemma: str, intent: str) -> bool:
    roots = set(CONFIG.get("problem_task_roles", {}).get(intent, {}).get("patient_roots", []))
    return any(roots.intersection({sense.name(), *(parent.name() for parent in sense.closure(lambda node: node.hypernyms()))})
               for sense in wordnet.synsets(lemma, pos=wordnet.NOUN))


def analyze_task_roles(text: str):
    with activity("normalization", "nlp.task_roles", model=CONFIG["spacy_model"]) as operation:
        doc = pipeline()(text)
        intents, actions = set(), []
        for root in doc:
            if root.dep_ not in {"dobj", "obj", "nsubjpass"}:
                continue
            for intent, rule in CONFIG.get("problem_task_roles", {}).items():
                if root.head.lemma_.casefold() in rule["actions"] and is_task_problem(root.lemma_.casefold(), intent):
                    intents.add(intent)
                    actions.append(root.head.text)
        operation.details["inferred_intents"] = ", ".join(sorted(intents))
        return doc, intents, actions


def extract_targets(text: str, cleaning_words: set[str], *, doc=None, intent: str = "clean") -> list[ExtractedTarget]:
    with activity("normalization", "nlp.spacy", model=CONFIG["spacy_model"]) as operation:
        doc = doc if doc is not None else pipeline()(text)
        targets = []
        chunks = list(doc.noun_chunks)
        patients = []
        for chunk, root in nominal_chunks(doc):
            governing = root
            while governing.dep_ == "conj":
                governing = governing.head
            if governing.dep_ not in {"dobj", "obj", "nsubjpass"} or not set(words(governing.head.lemma_)).intersection(cleaning_words):
                continue
            rule = CONFIG.get("problem_task_roles", {}).get(intent, {})
            locations = []
            if is_task_problem(root.lemma_.casefold(), intent):
                for other in chunks:
                    location = other.root
                    while location.dep_ == "conj":
                        location = location.head
                    if (location.dep_ == "pobj" and location.head.lemma_ in rule.get("locations", [])
                            and location.head.head in {root, root.head}):
                        positions = [index for token in (root, location.head)
                                     for index in range(len(words(text[:token.idx])), len(words(text[:token.idx + len(token.text)])))]
                        locations.append((other, other.root, positions, root.lemma_))
            patients.extend(locations or [(chunk, root, [], None)])
        for chunk, root, context_positions, problem in patients:
            modifiers = [token for token in root.children if token.dep_ in {"amod", "compound"}]
            siblings = [token for token in chunk if token.i < root.i and token.head == root.head and token.dep_ in {"dobj", "obj"}]
            modifiers = sorted({*modifiers, *siblings}, key=lambda token: token.i)
            compounds = [token.lemma_.casefold() for token in modifiers if token.dep_ == "compound" or token in siblings]
            lemma = root.lemma_.casefold()
            senses, classes = object_senses(" ".join([*compounds, lemma]))
            if not senses:
                senses, classes = object_senses(lemma)
            entity = None
            if senses and lemma not in CONFIG["generic_heads"]:
                entity = EntityReference(
                    id=f"wordnet:{lemma}", kind="object", label=lemma, source="wordnet",
                    classes=[f"wordnet:{value}" for value in classes], sense_ids=list(senses),
                    modifiers=[token.text for token in modifiers],
                )
            owners = [other for other in chunks if other.root.dep_ == "pobj" and other.root.head.lemma_ == "of" and other.root.head.head == root]
            query_chunk = owners[0] if len(owners) == 1 else chunk
            query = " ".join(token.text for token in query_chunk if token.pos_ in {"NOUN", "PROPN", "NUM"} or (not owners and token == root))
            targets.append(ExtractedTarget(
                head=root.text, lemma=lemma, phrase=chunk.text,
                modifiers=[token.text for token in modifiers],
                material_candidates=[token.lemma_.casefold() for token in modifiers if token.pos_ in {"NOUN", "ADJ"} and any(sense.lexname() == "noun.substance" for sense in wordnet.synsets(token.lemma_))],
                entity=entity, object_query=query[:120], component=lemma if owners else None,
                context_positions=context_positions, problem=problem,
                start=chunk.start_char, end=chunk.end_char, head_index=root.i,
            ))
        operation.details.update(targets=len(targets), classified=sum(target.entity is not None for target in targets))
        operation.debug["noun_phrases"] = [target.phrase for target in targets]
        operation.debug["problems"] = [target.problem for target in targets if target.problem]
        return targets
