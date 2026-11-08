"""Blank messages are rejected before any retrieval or LLM call."""

import pytest
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


@pytest.mark.parametrize("path", ["/api/ai/chat", "/api/ai/chat/stream"])
@pytest.mark.parametrize("blank", ["", " ", "   \n\t "])
def test_blank_message_is_422_and_never_reaches_the_llm(live_llm, path, blank):
    response = client.post(path, json={"message": blank})
    assert response.status_code == 422
    assert live_llm.calls == []


def test_message_is_stripped_before_use(live_llm):
    data = client.post("/api/ai/chat", json={"message": "  How much is a manicure?  \n"}).json()
    assert live_llm.calls[-1]["messages"][-1] == {"role": "user", "content": "How much is a manicure?"}
    assert main._load_session(data["session_id"])[0]["content"] == "How much is a manicure?"


def test_500_character_limit_applies_after_stripping():
    assert client.post("/api/ai/chat", json={"message": "  " + "a" * 500 + "  "}).status_code == 200
    assert client.post("/api/ai/chat", json={"message": "a" * 501}).status_code == 422
