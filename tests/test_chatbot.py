# tests/test_chatbot.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    """Verify health endpoint returns 200 and correct structure."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["llm_ready"] is True
    assert "version" in data

def test_chat_endpoint_basic():
    """Verify standard chat endpoint returns valid JSON structure."""
    response = client.post("/api/ai/chat", json={"message": "Hello"})
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "intent" in data
    assert "session_id" in data
    assert "fallback_used" in data
    assert "response_time_ms" in data
    assert data["fallback_used"] is False

def test_chat_intent_classification():
    """Verify intent is correctly classified for known categories."""
    test_cases = [
        ("What nail services do you offer?", "service_nails"),
        ("How much for a manicure?", "intent_pricing"),
        ("How do I book an appointment?", "intent_booking"),
    ]
    for message, expected_intent in test_cases:
        response = client.post("/api/ai/chat", json={"message": message})
        data = response.json()
        assert data["intent"] == expected_intent, f"Failed for: {message}"

def test_session_memory_continuity():
    """Verify session_id persists across requests."""
    # First request
    r1 = client.post("/api/ai/chat", json={"message": "What is eyelash lift?"})
    session_id = r1.json()["session_id"]
    
    # Second request with same session_id
    r2 = client.post("/api/ai/chat", json={
        "message": "How long does it take?",
        "session_id": session_id
    })
    assert r2.json()["session_id"] == session_id
    assert r2.status_code == 200

def test_chat_stream_endpoint():
    """Verify streaming endpoint returns 200 and SSE headers."""
    response = client.post("/api/ai/chat/stream", json={"message": "Hello"})
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

def test_message_validation_too_long():
    """Verify max length validation rejects oversized messages."""
    long_message = "A" * 501
    response = client.post("/api/ai/chat", json={"message": long_message})
    assert response.status_code == 422  # Unprocessable Entity

def test_empty_message_rejected():
    """Verify empty messages are rejected."""
    response = client.post("/api/ai/chat", json={"message": ""})
    assert response.status_code == 422