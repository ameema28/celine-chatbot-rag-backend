"""The suite never reaches a real Groq client and never uses the repo's sessions.db."""

import os

import pytest
from fastapi.testclient import TestClient

from app import main, session_store


def test_real_groq_never_constructed():
    import groq

    with pytest.raises(RuntimeError, match="never be constructed"):
        groq.Groq(api_key="anything")


def test_live_path_uses_fake_client(live_llm):
    client = TestClient(main.app)
    data = client.post("/api/ai/chat", json={"message": "Hello"}).json()
    assert data["fallback_used"] is False
    assert data["reply"] == live_llm.reply
    assert len(live_llm.calls) == 1


def test_no_key_means_no_client_call(fake_groq):
    client = TestClient(main.app)
    data = client.post("/api/ai/chat", json={"message": "Hello"}).json()
    assert data["fallback_used"] is True
    assert fake_groq.calls == []


def test_sessions_db_is_isolated():
    repo_db = os.path.abspath(
        os.path.join(os.path.dirname(session_store.__file__), "..", "sessions.db")
    )
    assert os.path.abspath(session_store.DB_PATH) != repo_db
