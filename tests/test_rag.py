"""RAG service: FAISS retrieval and the response dict (no API key, offline fallback)."""

from app.database import vector_db
from app.services.rag_service import generate_rag_response


def test_vector_search_retrieves_relevant_context():
    """FAISS returns relevant salon documents for a location query."""
    results = vector_db.search_context("Where is the luxury salon located in Switzerland?", top_k=1)
    assert len(results) > 0, "FAISS index search yielded 0 records."
    assert "lausanne" in results[0]["answer"].lower() or "1003" in results[0]["answer"]


def test_rag_service_generates_structured_response():
    """generate_rag_response returns the expected dict schema."""
    output = generate_rag_response(
        user_query="Tell me about your japanese head spa",
        session_id="test-session-001",
        history=[],
    )
    for key in ("reply", "intent", "retrieved_context", "fallback_used", "response_time_ms"):
        assert key in output
    assert output["intent"] == "service_head_spa"


def test_rag_service_uses_conversation_history():
    """A pricing question after a services question is tagged as pricing."""
    history = [
        {"role": "user", "content": "What nail services do you offer?"},
        {"role": "assistant", "content": "We offer manicure, pedicure, gel, and more."},
    ]
    output = generate_rag_response(
        user_query="How much is a manicure?",
        session_id="test-session-002",
        history=history,
    )
    assert "reply" in output
    assert output["intent"] == "intent_pricing"
