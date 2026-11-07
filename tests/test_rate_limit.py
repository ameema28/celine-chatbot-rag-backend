"""Rate limiting: 10/min per client IP; preflight and health/docs are exempt."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import main
from app.config import Settings, settings

client = TestClient(main.app)
LIMIT_BODY = {"detail": "Rate limit exceeded. Max 10 requests per minute."}
PREFLIGHT = {
    "Origin": "http://localhost:3000",
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "content-type",
}


def _chat(headers=None):
    return client.post("/api/ai/chat", json={"message": "Hello"}, headers=headers or {})


def test_eleventh_post_in_a_minute_gets_429():
    for _ in range(10):
        assert _chat().status_code == 200
    response = _chat()
    assert response.status_code == 429
    assert response.json() == LIMIT_BODY


def test_preflight_health_and_docs_are_not_counted():
    for _ in range(20):
        assert client.options("/api/ai/chat", headers=PREFLIGHT).status_code == 200
        assert client.get("/health").status_code == 200
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 200
    assert main.RATE_LIMIT_STORE == {}
    for _ in range(10):
        assert _chat().status_code == 200


def test_forwarded_for_ignored_by_default(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY", False)
    for _ in range(10):
        assert _chat({"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert _chat({"X-Forwarded-For": "2.2.2.2"}).status_code == 429


def test_forwarded_for_right_most_entry_used_when_proxy_trusted(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY", True)
    for _ in range(10):
        assert _chat({"X-Forwarded-For": "1.1.1.1, 10.0.0.1"}).status_code == 200
    assert _chat({"X-Forwarded-For": "10.0.0.1"}).status_code == 429
    assert _chat({"X-Forwarded-For": "1.1.1.1"}).status_code == 200


def test_spoofed_left_entries_are_ignored(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY", True)
    for i in range(10):
        assert _chat({"X-Forwarded-For": f"203.0.113.{i}, 9.9.9.9"}).status_code == 200
    assert _chat({"X-Forwarded-For": "198.51.100.7, 9.9.9.9"}).status_code == 429


def test_spoofed_header_line_before_proxy_line_is_ignored(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY", True)
    for i in range(10):
        headers = [("X-Forwarded-For", f"203.0.113.{i}"), ("X-Forwarded-For", "9.9.9.9")]
        assert client.post("/api/ai/chat", json={"message": "Hello"}, headers=headers).status_code == 200
    assert _chat({"X-Forwarded-For": "9.9.9.9"}).status_code == 429


def test_proxy_hops_two_uses_second_entry_from_right(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY", True)
    monkeypatch.setattr(settings, "TRUST_PROXY_HOPS", 2)
    for i in range(10):
        assert _chat({"X-Forwarded-For": f"203.0.113.{i}, 9.9.9.9, 10.0.0.1"}).status_code == 200
    assert _chat({"X-Forwarded-For": "9.9.9.9, 10.0.0.2"}).status_code == 429
    assert _chat({"X-Forwarded-For": "8.8.8.8, 10.0.0.1"}).status_code == 200


def test_too_few_forwarded_entries_fall_back_to_socket_peer(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY", True)
    monkeypatch.setattr(settings, "TRUST_PROXY_HOPS", 2)
    for i in range(10):
        assert _chat({"X-Forwarded-For": f"203.0.113.{i}"}).status_code == 200
    assert _chat().status_code == 429


def test_proxy_hops_must_be_at_least_one():
    with pytest.raises(ValidationError):
        Settings(TRUST_PROXY_HOPS=0)


def test_429_keeps_cors_header_for_allowed_origin():
    origin = {"Origin": "http://localhost:3000"}
    for _ in range(10):
        _chat(origin)
    response = _chat(origin)
    assert response.status_code == 429
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
