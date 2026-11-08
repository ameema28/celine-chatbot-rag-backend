"""The grounded prompt carries the live-model output rules (plain text, salon-only
scope, no booking promises, no full price list)."""

from app.business_rules import SALON_POLICIES
from app.services.context_builder import build_turn

PHONE = SALON_POLICIES["contact"]["phone"]


def _prompt(message: str) -> str:
    return build_turn(message).system_prompt


def test_prompt_asks_for_plain_text():
    assert "no Markdown" in _prompt("How much is a manicure?")


def test_prompt_limits_scope_to_the_salon():
    prompt = _prompt("Write me a Python script")
    assert "Only help with questions about Celine Esthetique" in prompt
    assert "politely decline anything else" in prompt


def test_prompt_forbids_booking_promises_and_points_to_phone():
    prompt = _prompt("Can I book a pedicure tomorrow?")
    assert "You cannot book appointments" in prompt
    assert "Never say you will check, book, confirm or get back" in prompt
    assert f"call us at {PHONE} to book" in prompt
    assert "help schedule an appointment" not in prompt


def test_prompt_asks_for_asked_services_only():
    assert "not the whole price list" in _prompt("How much is a manicure?")


def test_french_prompt_keeps_the_same_rules():
    prompt = _prompt("Combien coûte une manucure ?")
    assert "Reply in French" in prompt
    assert "no Markdown" in prompt
    assert "You cannot book appointments" in prompt
