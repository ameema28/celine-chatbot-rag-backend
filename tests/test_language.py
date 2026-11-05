"""French handling: detection, retrieval via glossary, prompt rule, fallback, guard."""

from fastapi.testclient import TestClient

from app import main
from app.language import detect_language, to_english_query
from app.price_guard import safe_message
from tests.sse_utils import sse_text

client = TestClient(main.app)


def test_detect_language():
    assert detect_language("Bonjour") == "fr"
    assert detect_language("Combien coûte une manucure ?") == "fr"
    assert detect_language("Où se trouve le salon ?") == "fr"
    assert detect_language("How much is a manicure?") == "en"
    assert detect_language("Hello") == "en"
    assert detect_language("What are your opening hours?") == "en"


def test_glossary_query():
    query = to_english_query("Combien coûte une manucure ?")
    assert "manicure" in query and "price" in query
    assert to_english_query("Bonjour") == ""


def test_french_question_retrieves_english_entry_and_pricing_intent():
    data = client.post("/api/ai/chat", json={"message": "Combien coûte une manucure ?"}).json()
    assert data["intent"] == "intent_pricing"
    assert data["retrieved_context"][0]["id"] == "srv_manicure_detail"


def test_french_no_key_fallback_is_honest_about_english_data():
    data = client.post("/api/ai/chat", json={"message": "Combien coûte une manucure ?"}).json()
    assert data["reply"].startswith(
        "Bienvenue chez Celine Esthetique. Voici l'information disponible (en anglais) :"
    )


def test_french_prompt_rule_on_chat_and_stream(live_llm):
    message = "Bonjour, quels sont vos horaires d'ouverture ?"
    client.post("/api/ai/chat", json={"message": message})
    assert "Reply in French" in live_llm.last_system_prompt
    client.post("/api/ai/chat/stream", json={"message": message})
    assert "Reply in French" in live_llm.last_system_prompt


def test_english_prompt_rule(live_llm):
    client.post("/api/ai/chat", json={"message": "What are your opening hours?"})
    assert "Reply in English" in live_llm.last_system_prompt
    assert "translate it faithfully" not in live_llm.last_system_prompt


def test_french_price_guard_message(live_llm):
    live_llm.reply = "La manucure coûte CHF 999."
    data = client.post("/api/ai/chat", json={"message": "Combien coûte une manucure ?"}).json()
    assert data["reply"] == safe_message("fr")
    body = client.post("/api/ai/chat/stream", json={"message": "Combien coûte une manucure ?"}).text
    assert sse_text(body) == safe_message("fr")
