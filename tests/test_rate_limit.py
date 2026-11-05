"""Rate limiting: 10/min per client IP; preflight and health/docs are exempt."""

from fastapi.testclient import TestClient

from app import main
from app.config import settings

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


def test_forwarded_for_used_when_proxy_trusted(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY", True)
    for _ in range(10):
        assert _chat({"X-Forwarded-For": "1.1.1.1, 10.0.0.1"}).status_code == 200
    assert _chat({"X-Forwarded-For": "1.1.1.1"}).status_code == 429
    assert _chat({"X-Forwarded-For": "2.2.2.2"}).status_code == 200


def test_429_keeps_cors_header_for_allowed_origin():
    origin = {"Origin": "http://localhost:3000"}
    for _ in range(10):
        _chat(origin)
    response = _chat(origin)
    assert response.status_code == 429
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
