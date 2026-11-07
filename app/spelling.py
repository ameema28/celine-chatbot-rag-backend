"""Typo correction for salon service words, used for retrieval only (stdlib difflib).

Only words close to a known service term are changed. The vocabulary comes from
data/salon_knowledge.json: category names, the words of the service entry ids
(srv_*) and the service names listed as "Name (CHF ..)". Numbers, prices and
short words are never touched. The corrected text is an extra search query; the
user's message, the prompt and the price guard keep the original text.
"""

import difflib
import json
import re
from functools import lru_cache
from pathlib import Path

from app.business_rules import _clean_service_name

KB_PATH = Path(__file__).resolve().parent.parent / "data" / "salon_knowledge.json"

MIN_WORD_LENGTH = 5
SIMILARITY_CUTOFF = 0.85
# Real words that are close to a service term but mean something else.
NEVER_CORRECT = {"message", "messages", "massages"}

# Words in categories and ids that are not service terms.
NOT_SERVICE_WORDS = {
    "general", "detail", "policy", "items", "provide", "selling", "weeks", "comprehensive",
    "precise", "premium", "professional", "specialized", "natural", "combined", "luxury",
    "beauty",
}

_WORD = re.compile(r"[A-Za-z]+")
_PRICE_PARENS = re.compile(r"\([^()]*CHF[^()]*\)")


def _vocabulary_from(entries: list[dict]) -> frozenset[str]:
    texts: list[str] = []
    for entry in entries:
        texts.append(entry.get("category", ""))
        if entry.get("id", "").startswith("srv_"):
            texts.append(entry["id"][len("srv_"):].replace("_", " "))
        answer = entry.get("answer", "")
        texts += [_clean_service_name(answer[: m.start()]) for m in _PRICE_PARENS.finditer(answer)]
    return frozenset(
        word.lower()
        for text in texts
        for word in _WORD.findall(text)
        if len(word) >= MIN_WORD_LENGTH and word.lower() not in NOT_SERVICE_WORDS
    )


@lru_cache(maxsize=1)
def service_vocabulary() -> frozenset[str]:
    with open(KB_PATH, encoding="utf-8") as f:
        return _vocabulary_from(json.load(f))


def _correct_word(word: str, vocabulary: frozenset[str]) -> str:
    lower = word.lower()
    if len(lower) < MIN_WORD_LENGTH or lower in vocabulary or lower in NEVER_CORRECT:
        return word
    candidates = [term for term in vocabulary if term[0] == lower[0]]
    match = difflib.get_close_matches(lower, candidates, n=1, cutoff=SIMILARITY_CUTOFF)
    return match[0] if match else word


def correct_service_words(text: str) -> str:
    """The text with likely misspelled service words replaced (unchanged if none)."""
    vocabulary = service_vocabulary()
    return _WORD.sub(lambda m: _correct_word(m.group(0), vocabulary), text or "")
