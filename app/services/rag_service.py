# app/services/rag_service.py
from app.database import vector_db

class RAGService:
    @staticmethod
    def process_query(user_message: str):
        # Query matching vectors from index
        matched_chunks = vector_db.search_context(user_message, top_k=2)
        
        # Build contextual prompt augmentation string
        context_str = "\n".join([
            f"- [{chunk['category']}] Q: {chunk['question']} A: {chunk['answer']}"
            for chunk in matched_chunks
        ])
        
        # Infer core message intent string for routing classification
        inferred_intent = "general_salon_info"
        if matched_chunks:
            primary_cat = matched_chunks[0]["category"].lower()
            if "nail" in primary_cat:
                inferred_intent = "service_info"
            elif "spa" in primary_cat or "hair" in primary_cat:
                inferred_intent = "service_info"
            elif "policy" in primary_cat:
                inferred_intent = "policy_query"

        # Structural mock payload representing Phase 1 offline fulfillment
        # Phase 2 will plug this context payload directly into the OpenAI completions instance
        system_response_mock = f"Celine AI Placeholder Response based on Context: {matched_chunks[0]['answer'] if matched_chunks else 'How can I assist you with our luxury services?'}"

        return {
            "reply": system_response_mock,
            "intent": inferred_intent,
            "retrieved_context": matched_chunks
        }