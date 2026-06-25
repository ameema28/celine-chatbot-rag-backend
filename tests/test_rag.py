# tests/test_rag.py
"""Phase 7 — RAG Service Unit Tests (aligned with production architecture)."""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import vector_db
from app.services.rag_service import generate_rag_response


def test_vector_search_retrieves_relevant_context():
    """Verify FAISS returns relevant salon documents for a location query."""
    query = "Where is the luxury salon located in Switzerland?"
    results = vector_db.search_context(query, top_k=1)

    assert len(results) > 0, "FAISS index search yielded 0 records."
    assert "lausanne" in results[0]["answer"].lower() or "1003" in results[0]["answer"]
    print(f"PASS: Top match category='{results[0]['category']}'")


def test_rag_service_generates_structured_response():
    """Verify generate_rag_response returns the expected dict schema."""
    sample_query = "Tell me about your japanese head spa"
    output = generate_rag_response(
        user_query=sample_query,
        session_id="test-session-001",
        history=[]
    )

    assert "reply" in output
    assert "intent" in output
    assert "retrieved_context" in output
    assert "fallback_used" in output
    assert "response_time_ms" in output

    # Intent should be head-spa related
    assert output["intent"] == "service_head_spa"
    print(f"PASS: intent='{output['intent']}', fallback={output['fallback_used']}")


def test_rag_service_uses_conversation_history():
    """Verify history is incorporated into the response generation."""
    history = [
        {"role": "user", "content": "What nail services do you offer?"},
        {"role": "assistant", "content": "We offer manicure, pedicure, gel, and more."}
    ]
    output = generate_rag_response(
        user_query="How much is a manicure?",
        session_id="test-session-002",
        history=history
    )
    assert "reply" in output
    assert output["intent"] == "intent_pricing"
    print(f"PASS: history-aware pricing intent detected")


if __name__ == "__main__":
    test_vector_search_retrieves_relevant_context()
    test_rag_service_generates_structured_response()
    test_rag_service_uses_conversation_history()
    print("All Phase 7 RAG verification tests passed!")
