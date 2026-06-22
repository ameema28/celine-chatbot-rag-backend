# app/services/streaming_service.py
import logging
from typing import AsyncGenerator, List, Dict

from groq import Groq
from app.database import vector_db
from app.config import settings
from app.business_rules import SALON_POLICIES, get_cancellation_policy

logger = logging.getLogger(__name__)
GROQ_MODEL = getattr(settings, 'GROQ_MODEL_NAME', 'llama-3.3-70b-versatile')

async def generate_streaming_rag_response(
    user_query: str,
    session_id: str = "unknown",
    history: List[Dict[str, str]] = None
) -> AsyncGenerator[str, None]:
    history = history or []

    retrieved_chunks = vector_db.search_context(user_query, top_k=3)
    
    context_blocks = []
    for i, chunk in enumerate(retrieved_chunks, 1):
        context_blocks.append(
            f"[{i}] {chunk['category']}: {chunk['answer']}"
        )
    context_text = "\n".join(context_blocks) if context_blocks else "No specific salon documents matched."

    business_context = ""
    q = user_query.lower()
    if any(w in q for w in ["price", "cost", "how much", "chf", "discount", "first-time", "vip", "deposit"]):
        business_context = (
            f" VIP: {SALON_POLICIES['discounts']['vip']['percentage']}% off. "
            f"First-time: {SALON_POLICIES['discounts']['first_time']['percentage']}% off. "
            f"Luxury deposit: {int(SALON_POLICIES['deposits']['luxury_rate']*100)}%."
        )
    elif any(w in q for w in ["book", "appointment", "schedule", "reserve", "cancel"]):
        business_context = f" Cancellation: {get_cancellation_policy()}"

    system_prompt = (
        "You are Celine, AI concierge for Celine Esthétique luxury salon in Lausanne. "
        "14+ years experience. Elegant, warm, professional tone. "
        "Use 'we', 'our salon'. Offer booking assistance. "
        "CRITICAL: Be concise. Answer in 2-3 sentences maximum unless the user asks for detail. "
        f"Context: {context_text}{business_context}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_query})

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        stream = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=200,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
                
    except Exception as e:
        logger.error(f"[{session_id}] Streaming error: {e}")
        yield "I apologize, but I am unable to process your request at this moment. "
        yield "Please contact our reception at +41 78 949 40 39."