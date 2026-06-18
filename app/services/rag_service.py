import os
from groq import Groq
from app.database import vector_db
from app.config import settings

def generate_rag_response(user_query: str) -> dict:
    # 1. Retrieve the closest matching context chunks from local FAISS cache
    retrieved_chunks = vector_db.search_context(user_query, top_k=2)
    
    # 2. Compile matched chunks into a string structure for the model
    context_text = ""
    for chunk in retrieved_chunks:
        context_text += f"Question: {chunk['question']}\nAnswer: {chunk['answer']}\n\n"
        
    system_prompt = (
        "You are Celine, an elegant, highly professional AI concierge for 'Celine Esthétique'.\n"
        f"VERIFIED SALON CONTEXT:\n{context_text}"
    )
    
    # 3. Network Safe Execution Flow
    try:
        if settings.GROQ_API_KEY and not settings.GROQ_API_KEY.startswith("your_"):
            groq_client = Groq(api_key=settings.GROQ_API_KEY)
            completion = groq_client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.3,
                max_tokens=250
            )
            ai_reply = completion.choices[0].message.content
        else:
            raise ValueError("Offline Mode Fallback triggered.")
            
    except Exception:
        # Offline Luxury Formatting Engine (Failsafe for environment/network blocks)
        if retrieved_chunks:
            primary_answer = retrieved_chunks[0]['answer']
            ai_reply = f"Welcome to Celine Esthétique. {primary_answer} Our specialized team would be delighted to orchestrate this luxurious experience for you. Would you like me to assist you with scheduling an appointment today?"
        else:
            ai_reply = "Welcome to Celine Esthétique. I would be absolutely delighted to assist you. Could you please contact our premium salon reception desk directly to arrange your personalized custom package?"

    # 4. Establish structural intent flag mappings
    intent_flag = "general_salon_info"
    if any(word in user_query.lower() for word in ["nail", "manicure", "pedicure"]):
        intent_flag = "service_nails"
    elif any(word in user_query.lower() for word in ["eye", "lash", "brow"]):
        intent_flag = "service_eyes"

    return {
        "reply": ai_reply,
        "intent": intent_flag,
        "retrieved_context": retrieved_chunks
    }