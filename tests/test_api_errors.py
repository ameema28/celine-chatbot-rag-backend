"""Error responses share the {"detail": ...} JSON shape; /health reports a usable key."""

from fastapi.testclient import TestClient

from app import main
from app.config import settings

client = TestClient(main.app)


def test_429_has_retry_after():
    for _ in range(10):
        client.post("/api/ai/chat", json={"message": ""})
    response = client.post("/api/ai/chat", json={"message": ""})
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert isinstance(response.json()["detail"], str)


def test_unexpected_error_returns_json_500(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("simulated bug")

    monkeypatch.setattr(main, "generate_rag_response", boom)
    response = TestClient(main.app, raise_server_exceptions=False).post(
        "/api/ai/chat", json={"message": "hello"}
    )
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Internal server error."}
    assert "simulated bug" not in response.text


def test_health_llm_ready_false_for_placeholder_key(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "your_groq_api_key_here")
    assert client.get("/health").json()["llm_ready"] is False


def test_health_llm_ready_true_for_usable_key(live_llm):
    assert client.get("/health").json()["llm_ready"] is True
