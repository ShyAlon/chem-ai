"""Single longest-match implementation used by the semantic extractor."""
from dataclasses import dataclass
from .normalization import words

type CompiledTerms = tuple[tuple[str, tuple[str, ...]], ...]


@dataclass(frozen=True)
class TermMatch:
    value: str
    positions: frozenset[int]


def compile_terms(groups, *, nouns: bool = False) -> CompiledTerms:
    return tuple(sorted(((key, tuple(words(alias, nouns=nouns))) for key, aliases in groups.items() for alias in aliases), key=lambda item: len(item[1]), reverse=True))


def find_terms(tokens: list[str], terms: CompiledTerms) -> list[TermMatch]:
    found, covered = [], set()
    for key, phrase in terms:
        for index in range(len(tokens) - len(phrase) + 1):
            positions = frozenset(range(index, index + len(phrase)))
            if not covered.intersection(positions) and tuple(tokens[index:index + len(phrase)]) == phrase:
                found.append(TermMatch(key, positions))
                covered.update(positions)
    return found


def match_terms(tokens: list[str], terms: CompiledTerms) -> tuple[set[str], set[int]]:
    matches = find_terms(tokens, terms)
    return {item.value for item in matches}, {position for item in matches for position in item.positions}
