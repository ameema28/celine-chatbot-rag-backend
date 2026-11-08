"""FAISS relevance cutoff: off-topic questions get no salon context."""

from fastapi.testclient import TestClient

from app import main
from app.config import Settings, settings
from app.database import vector_db

client = TestClient(main.app)
PHONE_FALLBACK = "Please contact us at +41 78 949 40 39."


def test_default_cutoff():
    assert Settings().RAG_MAX_L2_DISTANCE == 1.20


def test_on_topic_query_keeps_context():
    data = client.post("/api/ai/chat", json={"message": "How much is a manicure?"}).json()
    assert data["retrieved_context"]
    assert data["retrieved_context"][0]["id"] == "srv_manicure_detail"


def test_off_topic_query_gets_no_context_and_phone_fallback():
    data = client.post(
        "/api/ai/chat", json={"message": "What is the capital of Australia?"}
    ).json()
    assert data["retrieved_context"] == []
    assert data["reply"] == PHONE_FALLBACK


def test_scores_sorted_and_cutoff_applied(monkeypatch):
    scored = vector_db.search_with_scores("How much is a manicure?", top_k=3)
    distances = [d for _, d in scored]
    assert distances == sorted(distances)
    assert distances[0] < settings.RAG_MAX_L2_DISTANCE

    monkeypatch.setattr(settings, "RAG_MAX_L2_DISTANCE", distances[0] - 0.01)
    assert vector_db.search_context("How much is a manicure?", top_k=3) == []


def test_no_context_prompt_states_nothing_matched(live_llm):
    client.post("/api/ai/chat", json={"message": "What is the capital of Australia?"})
    assert "No specific salon documents matched." in live_llm.last_system_prompt
