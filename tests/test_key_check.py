"""One key check for both endpoints, with the same log line."""

import logging

import pytest
from fastapi.testclient import TestClient

from app import llm, main
from app.config import settings

client = TestClient(main.app)


@pytest.mark.parametrize("key, status", [
    (None, "missing"),
    ("", "missing"),
    ("your_groq_api_key_here", "placeholder"),
    ("short-key", "placeholder"),
    ("test-not-a-real-key-000000000000", "ok"),
])
def test_key_status(monkeypatch, key, status):
    monkeypatch.setattr(settings, "GROQ_API_KEY", key)
    assert llm.key_status() == status
    assert llm.groq_key_usable() is (status == "ok")


@pytest.mark.parametrize("key, status", [(None, "missing"), ("your_groq_api_key_here", "placeholder")])
def test_both_endpoints_log_the_same_key_warning(monkeypatch, caplog, fake_groq, key, status):
    monkeypatch.setattr(settings, "GROQ_API_KEY", key)
    with caplog.at_level(logging.WARNING):
        client.post("/api/ai/chat", json={"message": "hello"})
        client.post("/api/ai/chat/stream", json={"message": "hello"}).read()
    line = f"No usable GROQ_API_KEY ({status}): offline fallback"
    assert caplog.text.count(line) == 2
    assert fake_groq.calls == []
