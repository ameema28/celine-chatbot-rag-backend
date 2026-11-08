"""Offline fallback never greets: the demo page already shows a welcome message."""

from fastapi.testclient import TestClient

from app import main
from app.services.context_builder import build_turn, fallback_reply
from tests.sse_utils import sse_text

client = TestClient(main.app)

EN_GREETING = "Welcome to Celine Esthetique."
FR_GREETING = "Bienvenue chez Celine Esthetique."
PHONE = "+41 78 949 40 39"


def _chat(message: str, session_id: str | None = None) -> dict:
    body = {"message": message}
    if session_id:
        body["session_id"] = session_id
    return client.post("/api/ai/chat", json=body).json()


def test_english_fallback_has_no_greeting():
    first = _chat("How much is a manicure?")
    second = _chat("What is included in a pedicure?", first["session_id"])
    assert EN_GREETING not in first["reply"]
    assert "CHF 45" in first["reply"]
    assert second["reply"].endswith(f"To book, call us at {PHONE}.")
    assert "scheduling an appointment" not in first["reply"] + second["reply"]


def test_french_fallback_booking_line_unchanged():
    reply = _chat("Combien coûte une manucure ?")["reply"]
    assert reply.endswith(f"Souhaitez-vous prendre rendez-vous ? Appelez-nous au {PHONE}.")


def test_french_fallback_has_no_greeting():
    first = _chat("Combien coûte une manucure ?")
    assert FR_GREETING not in first["reply"]
    assert first["reply"].startswith("Voici l'information disponible (en anglais) :")


def test_no_context_reply():
    assert _chat("Who won the football world cup?")["reply"] == f"Please contact us at {PHONE}."
    assert fallback_reply(build_turn("Qui a gagné la coupe du monde de football ?")) == (
        f"Veuillez nous contacter au {PHONE}."
    )


def test_stream_fallback_has_no_greeting():
    response = client.post("/api/ai/chat/stream", json={"message": "How much is a manicure?"})
    assert EN_GREETING not in sse_text(response.text)


def test_demo_page_still_greets_once():
    assert client.get("/").text.count(EN_GREETING) == 1
