# tests/conftest.py
"""Shared test setup.

- No real API key is ever used: GROQ_API_KEY is forced to None for every test.
- Groq is replaced by FakeGroq; constructing a real client raises.
- Rate-limit and in-memory session state are reset around every test.
- The SQLite session store points at a temp file, not the repo's sessions.db.
"""

import os
import re
import sys
import tempfile
from types import SimpleNamespace

# Add project root to Python path so pytest can find 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Must be set before app.session_store is imported (it reads it at import time).
os.environ["SESSIONS_DB_PATH"] = os.path.join(
    tempfile.mkdtemp(prefix="celine-tests-"), "sessions-test.db"
)

import groq
import pytest

from app import llm, main
from app.config import settings

FAKE_KEY = "test-not-a-real-key-000000000000"
DEFAULT_REPLY = (
    "Thank you for your question. We would be happy to help you schedule an appointment."
)


class FakeGroq:
    """Minimal stand-in for groq.Groq: records calls, returns a canned reply."""

    def __init__(self):
        self.calls = []
        self.reply = DEFAULT_REPLY
        self.raise_exc = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.raise_exc is not None:
            raise self.raise_exc
        if kwargs.get("stream"):
            return iter(
                SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=part))])
                for part in re.findall(r"\S+\s*", self.reply)
            )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))]
        )

    @property
    def last_system_prompt(self):
        return self.calls[-1]["messages"][0]["content"]


def _real_groq_forbidden(*args, **kwargs):
    raise RuntimeError("Real Groq client must never be constructed in tests")


@pytest.fixture(autouse=True)
def fake_groq(monkeypatch):
    """Every test: no key, fake client, no real Groq, fresh in-memory state."""
    monkeypatch.setattr(settings, "GROQ_API_KEY", None)
    fake = FakeGroq()
    monkeypatch.setattr(llm, "get_groq_client", lambda: fake)
    monkeypatch.setattr(groq, "Groq", _real_groq_forbidden)
    main.RATE_LIMIT_STORE.clear()
    main.SESSION_MEMORY.clear()
    yield fake
    main.RATE_LIMIT_STORE.clear()
    main.SESSION_MEMORY.clear()


@pytest.fixture
def live_llm(monkeypatch, fake_groq):
    """Opt in to the 'live' code path, answered by FakeGroq (no network)."""
    monkeypatch.setattr(settings, "GROQ_API_KEY", FAKE_KEY)
    return fake_groq
