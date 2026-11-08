"""/chat/stream uses the same key check, grounded prompt and fallback as /chat."""

from fastapi.testclient import TestClient

from app import main
from app.services.context_builder import build_turn, fallback_reply
from tests.sse_utils import sse_events, sse_text

client = TestClient(main.app)
QUESTION = "What nail services do you offer?"
GROUNDING = "If the context does not contain the answer, say so politely"


def test_stream_without_key_streams_same_fallback_as_chat(fake_groq):
    chat_reply = client.post("/api/ai/chat", json={"message": QUESTION}).json()["reply"]
    response = client.post("/api/ai/chat/stream", json={"message": QUESTION})
    assert response.status_code == 200
    assert response.headers["x-session-id"]
    assert sse_text(response.text) == chat_reply
    assert fake_groq.calls == []


def test_stream_live_uses_grounding_prompt(live_llm):
    response = client.post("/api/ai/chat/stream", json={"message": QUESTION})
    assert sse_text(response.text) == live_llm.reply
    assert GROUNDING in live_llm.last_system_prompt


def test_chat_and_stream_send_identical_system_prompt(live_llm):
    client.post("/api/ai/chat", json={"message": QUESTION})
    chat_prompt = live_llm.last_system_prompt
    client.post("/api/ai/chat/stream", json={"message": QUESTION})
    assert live_llm.last_system_prompt == chat_prompt


def test_stream_groq_error_falls_back_to_context(live_llm):
    chat_fallback = client.post("/api/ai/chat", json={"message": QUESTION})
    live_llm.raise_exc = RuntimeError("simulated outage")
    streamed = sse_text(client.post("/api/ai/chat/stream", json={"message": QUESTION}).text)
    assert "I apologize" not in streamed
    assert streamed == fallback_reply(build_turn(QUESTION))
    assert chat_fallback.status_code == 200


def test_multiline_text_is_framed_as_multiple_data_lines(live_llm):
    live_llm.reply = "Line one.\nLine two."
    response = client.post("/api/ai/chat/stream", json={"message": QUESTION})
    assert "data: one.\ndata: \n\n" in response.text
    assert sse_text(response.text) == "Line one.\nLine two."
    assert sse_events(response.text)[-1] == "[DONE]"
