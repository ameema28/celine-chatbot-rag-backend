"""Intent keywords match at the start of a word, not inside other words."""

import pytest

from app.services.context_builder import classify_intent


@pytest.mark.parametrize("text", [
    "Is the salon warm and charming?",   # "arm" inside warm/charm
    "What an elegant place",             # "leg" inside elegant
    "Do you have angel decorations?",    # "gel" inside angel
    "Is there a pharmacy nearby?",       # "arm" inside pharmacy
])
def test_keywords_inside_other_words_do_not_match(text):
    assert classify_intent(text) == "general_salon_info"


@pytest.mark.parametrize("text, intent", [
    ("How much is a manicure?", "intent_pricing"),
    ("What are your prices?", "intent_pricing"),
    ("Can I book for Friday?", "intent_booking"),
    ("What is your cancellation policy?", "intent_booking"),
    ("Do you do gel nails?", "service_nails"),
    ("Eyelash extensions please", "service_eyes"),
    ("Eyebrow tinting", "service_eyes"),
    ("Leg waxing", "service_waxing"),
    ("armpit waxing", "service_waxing"),
    ("Tell me about the Japanese head spa", "service_head_spa"),
    ("Which skincare products do you sell?", "intent_shop"),
])
def test_real_keywords_still_match(text, intent):
    assert classify_intent(text) == intent
