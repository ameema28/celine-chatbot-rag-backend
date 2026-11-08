"""An empty model reply (e.g. a reasoning model that used its whole token budget)
is treated as an LLM failure on both endpoints: the offline fallback is used."""

import pytest
from fastapi.testclient import TestClient

from app import llm, main
from app.config import settings
from tests.sse_utils import sse_text

client = TestClient(main.app)
QUESTION = "How much is a manicure?"


@pytest.mark.parametrize("empty", [None, "", "   \n"])
def test_chat_empty_reply_uses_fallback(live_llm, empty):
    live_llm.reply = empty
    response = client.post("/api/ai/chat", json={"message": QUESTION})
    assert response.status_code == 200
    data = response.json()
    assert data["fallback_used"] is True
    assert data["response_time_ms"] == 0
    assert "CHF 45" in data["reply"]


@pytest.mark.parametrize("empty", [None, ""])
def test_stream_empty_reply_matches_chat_fallback(live_llm, empty):
    live_llm.reply = empty
    chat_reply = client.post("/api/ai/chat", json={"message": QUESTION}).json()["reply"]
    streamed = sse_text(client.post("/api/ai/chat/stream", json={"message": QUESTION}).text)
    assert streamed == chat_reply


def test_completion_kwargs_for_gpt_oss(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_MODEL_NAME", "openai/gpt-oss-20b")
    kwargs = llm.completion_kwargs([{"role": "user", "content": "hi"}])
    assert kwargs["reasoning_effort"] == "low"
    assert kwargs["max_completion_tokens"] == llm.MAX_COMPLETION_TOKENS
    assert "stream" not in kwargs


def test_completion_kwargs_other_model_has_no_reasoning_effort(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_MODEL_NAME", "llama-3.3-70b-versatile")
    kwargs = llm.completion_kwargs([], stream=True)
    assert "reasoning_effort" not in kwargs
    assert kwargs["stream"] is True


def test_both_endpoints_send_the_same_arguments(live_llm):
    client.post("/api/ai/chat", json={"message": QUESTION})
    client.post("/api/ai/chat/stream", json={"message": QUESTION})
    chat_call, stream_call = live_llm.calls[-2], live_llm.calls[-1]
    assert {k: v for k, v in stream_call.items() if k != "stream"} == chat_call
