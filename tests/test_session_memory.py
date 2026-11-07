"""In-memory session copy: TTL and size cap; SQLite stays the source of truth."""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import settings

client = TestClient(main.app)
HISTORY = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]


@pytest.fixture
def clock(monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(main, "_now", lambda: now["t"])
    return now


@pytest.fixture
def no_sqlite(monkeypatch):
    """SQLite unavailable, so only the in-memory copy can answer."""

    def broken(*args, **kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr(main, "save_session", broken)
    monkeypatch.setattr(main, "load_session", broken)


def test_idle_sessions_are_evicted_after_ttl(clock, monkeypatch, no_sqlite):
    monkeypatch.setattr(settings, "SESSION_TTL_MINUTES", 60)
    main._persist_session("old", HISTORY)
    clock["t"] += 59 * 60
    assert main._load_session("old") == HISTORY  # still within the TTL; touched again
    clock["t"] += 60 * 60 + 1
    assert main._load_session("old") is None
    assert "old" not in main.SESSION_MEMORY and "old" not in main.SESSION_LAST_USED


def test_cap_evicts_least_recently_used(clock, monkeypatch, no_sqlite):
    monkeypatch.setattr(settings, "SESSION_MEMORY_MAX_SESSIONS", 2)
    main._persist_session("a", HISTORY)
    clock["t"] += 1
    main._persist_session("b", HISTORY)
    clock["t"] += 1
    assert main._load_session("a") == HISTORY  # "a" is now the most recently used
    main._persist_session("c", HISTORY)
    assert list(main.SESSION_MEMORY) == ["a", "c"]
    assert set(main.SESSION_LAST_USED) == {"a", "c"}


def test_sqlite_still_has_evicted_session(clock, monkeypatch):
    monkeypatch.setattr(settings, "SESSION_MEMORY_MAX_SESSIONS", 1)
    first = client.post("/api/ai/chat", json={"message": "How much is a manicure?"}).json()
    client.post("/api/ai/chat", json={"message": "Where is the salon?"})
    assert first["session_id"] not in main.SESSION_MEMORY
    history = main._load_session(first["session_id"])
    assert history is not None and history[0]["content"] == "How much is a manicure?"


def test_settings_have_safe_defaults():
    from app.config import Settings

    defaults = Settings(_env_file=None)
    assert defaults.SESSION_TTL_MINUTES == 60
    assert defaults.SESSION_MEMORY_MAX_SESSIONS == 1000
    with pytest.raises(ValueError):
        Settings(_env_file=None, SESSION_TTL_MINUTES=0)
    with pytest.raises(ValueError):
        Settings(_env_file=None, SESSION_MEMORY_MAX_SESSIONS=0)
