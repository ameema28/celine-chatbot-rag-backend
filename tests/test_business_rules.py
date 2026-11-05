"""Business rules are applied in code: discount math, deposits, and the pricing prompt."""

from decimal import Decimal

from fastapi.testclient import TestClient

from app import main
from app.business_rules import (
    calculate_price,
    detect_client_status,
    find_chf_amounts,
    get_deposit_info,
    price_items_from_entry,
)
from app.database import vector_db

client = TestClient(main.app)
ENTRIES = {doc["id"]: doc for doc in vector_db.documents}


def test_vip_beats_first_time():
    result = calculate_price(45, is_vip=True, is_first_time=True)
    assert result["discount_percent"] == 10
    assert result["final"] == 40.5


def test_first_time_discount():
    assert calculate_price(45, is_first_time=True)["final"] == 38.25


def test_rounding_is_half_up_to_centime():
    # 47.50 * 0.85 = 40.375 -> 40.38 (Python's round() would give 40.37)
    assert calculate_price(47.50, is_first_time=True)["final"] == 40.38


def test_no_status_means_no_discount():
    assert calculate_price(45)["final"] == 45.0


def test_deposit_match():
    lux = get_deposit_info("Eyelash extensions")
    assert lux["required"] is True and lux["rate_percent"] == 20
    assert get_deposit_info("Manicure")["required"] is False


def test_detect_client_status_english_and_french():
    assert detect_client_status("I'm a VIP and it's my first time") == (True, True)
    assert detect_client_status("C'est ma première fois chez vous") == (False, True)
    assert detect_client_status("How much is a manicure?") == (False, False)


def test_find_chf_amounts_formats():
    amounts = find_chf_amounts("CHF 45, CHF 35-50, 20 CHF and CHF 12,50")
    assert amounts == [Decimal("45.00"), Decimal("35.00"), Decimal("50.00"),
                       Decimal("20.00"), Decimal("12.50")]


def test_price_items_list_format_and_deposits():
    items = {(i.service, i.base): i for i in price_items_from_entry(ENTRIES["srv_nail_care"])}
    assert items[("Manicure", Decimal("45.00"))].deposit is None
    assert items[("Gel application", Decimal("65.00"))].deposit == Decimal("13.00")


def test_price_items_detail_format_uses_entry_for_deposit():
    items = price_items_from_entry(ENTRIES["srv_head_spa_japanese"])
    assert [i.base for i in items] == [Decimal("120.00")]
    assert items[0].deposit == Decimal("24.00")


def test_pricing_prompt_contains_computed_first_time_price(live_llm):
    client.post("/api/ai/chat",
                json={"message": "This is my first time - how much is a manicure?"})
    prompt = live_llm.last_system_prompt
    assert "COMPUTED PRICES" in prompt
    assert "CHF 38.25" in prompt
    assert "first visit" in prompt
    assert "LUXURY SERVICES (20% deposit on the listed price): Head Spa Japanese" in prompt


def test_pricing_prompt_contains_deposit_for_luxury_service(live_llm):
    client.post("/api/ai/chat", json={"message": "How much is the Japanese head spa?"})
    assert "deposit 20%: CHF 24" in live_llm.last_system_prompt


def test_non_pricing_question_has_no_computed_block(live_llm):
    client.post("/api/ai/chat", json={"message": "What are your opening hours?"})
    assert "COMPUTED PRICES" not in live_llm.last_system_prompt
