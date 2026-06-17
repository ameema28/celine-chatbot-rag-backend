# tests/test_rag.py
import sys
import os

# Append project workspace root path safely
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import vector_db
from app.services.rag_service import RAGService

def test_vector_search():
    print("--- Testing Vector Database Index Match ---")
    query = "Where is the luxury salon located in Switzerland?"
    results = vector_db.search_context(query, top_k=1)
    
    assert len(results) > 0, "Error: Index search yielded 0 records."
    print(f"Query: '{query}'")
    print(f"Top Matched Concept Category: {results[0]['category']}")
    print(f"Extracted Answer Fragment: {results[0]['answer']}\n")

def test_rag_service_routing():
    print("--- Testing Complete Mock RAG Pipeline Endpoint Output ---")
    sample_query = "Tell me about your japanese head spa"
    output = RAGService.process_query(sample_query)
    
    assert "reply" in output
    assert output["intent"] == "service_info"
    print(f"Query: '{sample_query}'")
    print(f"Identified Intent Token: {output['intent']}")
    print(f"Mock AI Pipeline Reply text: {output['reply']}\n")
    print("All Phase 1 Verification Sub-routines Passed Successfully!")

if __name__ == "__main__":
    test_vector_search()
    test_rag_service_routing()