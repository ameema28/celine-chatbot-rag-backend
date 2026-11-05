"""CORS allowlist from CORS_ALLOW_ORIGINS."""

from fastapi.testclient import TestClient

from app import main
from app.config import Settings

client = TestClient(main.app)
ALLOWED = "http://localhost:3000"
BLOCKED = "http://evil.example"


def test_origins_parsed_from_env_string():
    assert Settings(CORS_ALLOW_ORIGINS=" https://a.example , https://b.example ,").cors_origins == [
        "https://a.example",
        "https://b.example",
    ]


def test_allowed_origin_is_echoed():
    response = client.get("/health", headers={"Origin": ALLOWED})
    assert response.headers.get("access-control-allow-origin") == ALLOWED


def test_disallowed_origin_gets_no_cors_header():
    response = client.get("/health", headers={"Origin": BLOCKED})
    assert "access-control-allow-origin" not in response.headers


def test_null_origin_not_allowed():
    response = client.get("/health", headers={"Origin": "null"})
    assert "access-control-allow-origin" not in response.headers


def test_preflight_for_allowed_origin():
    response = client.options(
        "/api/ai/chat",
        headers={
            "Origin": ALLOWED,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ALLOWED


def test_session_id_header_exposed_to_browsers():
    response = client.post(
        "/api/ai/chat/stream", json={"message": "Hello"}, headers={"Origin": ALLOWED}
    )
    assert "x-session-id" in response.headers.get("access-control-expose-headers", "").lower()
