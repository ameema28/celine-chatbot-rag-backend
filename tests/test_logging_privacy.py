"""Logging privacy: no API-key characters and no raw user messages in logs."""

import logging

from fastapi.testclient import TestClient

from app import main
from app.config import settings

FAKE_KEY = "test-not-a-real-key-000000000000"
MARKER_MESSAGE = "zebra-umbrella-marker-7731"


def test_startup_log_says_yes_without_key_characters(monkeypatch, caplog):
    monkeypatch.setattr(settings, "GROQ_API_KEY", FAKE_KEY)
    with caplog.at_level(logging.INFO):
        main._startup_tasks()
    assert "GROQ_API_KEY loaded: yes" in caplog.text
    assert FAKE_KEY[:8] not in caplog.text
    assert FAKE_KEY[-4:] not in caplog.text


def test_startup_log_says_no_without_key(monkeypatch, caplog):
    monkeypatch.setattr(settings, "GROQ_API_KEY", None)
    with caplog.at_level(logging.INFO):
        main._startup_tasks()
    assert "GROQ_API_KEY loaded: no" in caplog.text


def test_chat_logs_length_not_message(caplog):
    client = TestClient(main.app)
    with caplog.at_level(logging.INFO):
        response = client.post("/api/ai/chat", json={"message": MARKER_MESSAGE})
    session_id = response.json()["session_id"]
    assert MARKER_MESSAGE not in caplog.text
    assert session_id in caplog.text
    assert f"len={len(MARKER_MESSAGE)}" in caplog.text


def test_stream_logs_length_not_message(caplog):
    client = TestClient(main.app)
    with caplog.at_level(logging.INFO):
        response = client.post("/api/ai/chat/stream", json={"message": MARKER_MESSAGE})
        _ = response.text
    session_id = response.headers["x-session-id"]
    assert MARKER_MESSAGE not in caplog.text
    assert session_id in caplog.text
    assert f"len={len(MARKER_MESSAGE)}" in caplog.text
