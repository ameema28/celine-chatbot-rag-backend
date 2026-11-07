"""Typo correction for service words (retrieval only)."""

from app.services.context_builder import build_turn
from app.spelling import _vocabulary_from, correct_service_words, service_vocabulary


def test_misspelled_service_words_are_corrected():
    assert correct_service_words("peducure") == "pedicure"
    assert correct_service_words("manicur") == "manicure"
    assert correct_service_words("how much is a manicur and pedicur") == "how much is a manicure and pedicure"
    assert correct_service_words("eyelash extentions?") == "eyelash extensions?"


def test_prices_numbers_and_punctuation_are_unchanged():
    text = "Manicur (CHF 45, 45 min) or CHF 40.50?"
    assert correct_service_words(text) == "manicure (CHF 45, 45 min) or CHF 40.50?"
    assert correct_service_words("CHF 999") == "CHF 999"


def test_correct_short_and_unrelated_words_are_unchanged():
    for text in [
        "How much is a manicure?",
        "gel nail wax",
        "Where is the salon located?",
        "What's the weather in Lausanne tomorrow?",
        "I would like to schedule an appointment",
    ]:
        assert correct_service_words(text) == text


def test_never_correct_list():
    assert correct_service_words("I left a message") == "I left a message"


def test_vocabulary_comes_from_service_names():
    vocab = service_vocabulary()
    assert {"manicure", "pedicure", "eyelash", "bikini", "massage"} <= vocab
    assert all(len(word) >= 5 for word in vocab)
    assert not {"general", "policy", "includes", "weeks"} & vocab


def test_vocabulary_builder_ignores_non_service_entries():
    entries = [
        {"id": "policy_booking", "category": "Policy", "answer": "Call us."},
        {"id": "srv_foot_spa", "category": "Feet", "answer": "Our range includes Foot spa (CHF 70)."},
    ]
    assert _vocabulary_from(entries) == frozenset()  # all words shorter than 5 or not services


def test_typo_query_retrieves_service_but_prompt_keeps_original():
    turn = build_turn("how much is a peducure")
    ids = [chunk["id"] for chunk in turn.chunks]
    assert {"srv_pedicure_detail", "srv_nail_care"} & set(ids)
    assert turn.messages[-1]["content"] == "how much is a peducure"
    assert turn.user_query == "how much is a peducure"


def test_typo_query_gets_service_intent():
    assert build_turn("peducure please").intent == "service_nails"
