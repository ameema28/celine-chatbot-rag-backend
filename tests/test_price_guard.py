"""CHF price guard on /chat and /chat/stream."""

from decimal import Decimal

from fastapi.testclient import TestClient

from app import main
from app.price_guard import KB_PRICES, check_reply, safe_message
from tests.sse_utils import sse_text

client = TestClient(main.app)
SAFE = safe_message("en")


def test_kb_prices_loaded_from_data():
    assert {Decimal("45.00"), Decimal("120.00"), Decimal("180.00")} <= KB_PRICES
    assert Decimal("999.00") not in KB_PRICES


def test_check_reply_unit():
    assert check_reply("A manicure is CHF 45.") == (True, [])
    assert check_reply("Today only CHF 999!") == (False, [Decimal("999.00")])
    assert check_reply("First visit: CHF 38.25", [Decimal("38.25")]) == (True, [])
    assert check_reply("No prices here, call +41 78 949 40 39.") == (True, [])


def test_invented_price_replaced_and_persisted(live_llm):
    live_llm.reply = "Our manicure costs CHF 999."
    data = client.post("/api/ai/chat", json={"message": "How much is a manicure?"}).json()
    assert data["reply"] == SAFE
    history = main._load_session(data["session_id"])
    assert history[-1] == {"role": "assistant", "content": SAFE}


def test_real_price_kept(live_llm):
    live_llm.reply = "A manicure is CHF 45 and takes 45 minutes."
    data = client.post("/api/ai/chat", json={"message": "How much is a manicure?"}).json()
    assert data["reply"] == live_llm.reply


def test_computed_discounted_price_kept(live_llm):
    live_llm.reply = "For your first visit, a manicure is CHF 38.25."
    data = client.post(
        "/api/ai/chat", json={"message": "This is my first time - how much is a manicure?"}
    ).json()
    assert data["reply"] == live_llm.reply


def test_user_typed_amount_is_not_allowed(live_llm):
    live_llm.reply = "With CHF 100 you could book a pedicure."
    data = client.post(
        "/api/ai/chat", json={"message": "My budget is CHF 100, what can I get?"}
    ).json()
    assert data["reply"] == SAFE


def test_fallback_reply_passes_guard_without_key():
    data = client.post("/api/ai/chat", json={"message": "How much is a manicure?"}).json()
    assert data["fallback_used"] is True
    assert "CHF 45" in data["reply"]


def test_stream_invented_price_replaced(live_llm):
    live_llm.reply = "Our manicure costs CHF 999."
    body = client.post("/api/ai/chat/stream", json={"message": "How much is a manicure?"}).text
    assert sse_text(body) == SAFE
    assert "999" not in body


def test_stream_real_price_kept(live_llm):
    live_llm.reply = "A manicure is CHF 45."
    body = client.post("/api/ai/chat/stream", json={"message": "How much is a manicure?"}).text
    assert sse_text(body) == live_llm.reply
