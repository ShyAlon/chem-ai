import re
import unicodedata
from pathlib import Path

from nltk import data
from nltk.corpus import wordnet
from nltk.stem import SnowballStemmer

data.path.insert(0, str(Path(__file__).resolve().parents[1] / ".nltk-data"))
stemmer = SnowballStemmer("english")


def has_hebrew(text: str) -> bool:
    return any("א" <= character <= "ת" for character in text)


def words(text: str, *, nouns: bool = False) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"\b([a-z0-9]+)['’]s\b", r"\1", normalized)
    normalized = "".join(
        character for character in normalized if not unicodedata.category(character).startswith("M")
    )
    tokens = re.findall(r"[^\W_]+", normalized)
    if nouns:
        return [wordnet.morphy(token, wordnet.NOUN) or token for token in tokens]
    return [stemmer.stem(token) if token.isascii() and token.isalpha() else token for token in tokens]


def synonyms(*senses: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        lemma.replace("_", " ") for sense in senses for lemma in wordnet.synset(sense).lemma_names()
    ))


def category_terms(sense: str) -> tuple[str, ...]:
    root = wordnet.synset(sense)
    descendants = root.closure(lambda synset: synset.hyponyms())
    return synonyms(sense, *(synset.name() for synset in descendants))
