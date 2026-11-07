"""Offline fallback: the greeting is used only on the first reply of a session."""

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


def test_english_greeting_only_on_first_reply():
    first = _chat("How much is a manicure?")
    second = _chat("What is included in a pedicure?", first["session_id"])
    assert first["reply"].startswith(EN_GREETING)
    assert EN_GREETING not in second["reply"]
    assert second["reply"].endswith("Would you like help scheduling an appointment?")


def test_french_greeting_only_on_first_reply():
    first = _chat("Combien coûte une manucure ?")
    second = _chat("Combien coûte une pédicure ?", first["session_id"])
    assert first["reply"].startswith(FR_GREETING)
    assert FR_GREETING not in second["reply"]
    assert second["reply"].startswith("Voici l'information disponible (en anglais) :")


def test_no_context_reply_without_greeting_on_later_turns():
    first = _chat("How much is a manicure?")
    second = _chat("Who won the football world cup?", first["session_id"])
    assert second["reply"] == f"Please contact us at {PHONE}."


def test_stream_greets_only_on_first_reply():
    response = client.post("/api/ai/chat/stream", json={"message": "How much is a manicure?"})
    session_id = response.headers["x-session-id"]
    assert sse_text(response.text).startswith(EN_GREETING)
    later = client.post(
        "/api/ai/chat/stream", json={"message": "What is included in a pedicure?", "session_id": session_id}
    )
    assert EN_GREETING not in sse_text(later.text)


def test_first_reply_flag_from_history():
    assert build_turn("Hello").first_reply is True
    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}]
    turn = build_turn("Combien coûte une manucure ?", history)
    assert turn.first_reply is False
    assert not fallback_reply(turn).startswith(FR_GREETING)
