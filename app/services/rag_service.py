import logging
import time
from typing import List, Dict

from groq import Groq, APIError, APIConnectionError, AuthenticationError
from app.database import vector_db
from app.config import settings
from app.business_rules import SALON_POLICIES, get_cancellation_policy

logger = logging.getLogger(__name__)
GROQ_MODEL = getattr(settings, 'GROQ_MODEL_NAME', 'llama-3.3-70b-versatile')

def generate_rag_response(
    user_query: str,
    session_id: str = "unknown",
    history: List[Dict[str, str]] = None
) -> dict:
    history = history or []

    # 1. FAISS Retrieval
    retrieved_chunks = vector_db.search_context(user_query, top_k=3)

    # 2. Context Compilation
    context_blocks = []
    for i, chunk in enumerate(retrieved_chunks, 1):
        context_blocks.append(
            f"[{i}] {chunk['category']}: {chunk['answer']}"
        )
    context_text = "\n".join(context_blocks) if context_blocks else "No specific salon documents matched."

    # 3. Intent Classification (PRICING FIRST)
    intent_flag = "general_salon_info"
    q = user_query.lower()
    if any(w in q for w in ["price", "cost", "how much", "chf", "discount", "first-time", "vip", "deposit"]):
        intent_flag = "intent_pricing"
    elif any(w in q for w in ["book", "appointment", "schedule", "reserve", "cancel"]):
        intent_flag = "intent_booking"
    elif any(w in q for w in ["nail", "manicure", "pedicure", "gel", "varnish"]):
        intent_flag = "service_nails"
    elif any(w in q for w in ["eye", "lash", "brow", "tint"]):
        intent_flag = "service_eyes"
    elif any(w in q for w in ["hair removal", "wax", "bikini", "leg", "arm", "upper lip", "chin", "cheek"]):
        intent_flag = "service_waxing"
    elif any(w in q for w in ["head spa", "scalp", "hair wellness", "japanese"]):
        intent_flag = "service_head_spa"
    elif any(w in q for w in ["product", "shop", "cream", "skincare", "buy"]):
        intent_flag = "intent_shop"

    # 4. Business Rules Injection (keyword-based)
    business_context = ""
    if any(w in q for w in ["price", "cost", "how much", "chf", "discount", "first-time", "vip", "deposit"]):
        business_context = (
            f"\n\nPRICING RULES:\n"
            f"- VIP: {SALON_POLICIES['discounts']['vip']['percentage']}% off\n"
            f"- First-time: {SALON_POLICIES['discounts']['first_time']['percentage']}% off\n"
            f"- Luxury deposit: {int(SALON_POLICIES['deposits']['luxury_rate']*100)}%\n"
            f"- {get_cancellation_policy()}\n"
        )
    elif any(w in q for w in ["book", "appointment", "schedule", "reserve", "cancel"]):
        business_context = (
            f"\n\nBOOKING RULES:\n"
            f"- {get_cancellation_policy()}\n"
            f"- Phone: {SALON_POLICIES['contact']['phone']}\n"
        )

    # 5. CONCISE Luxury Persona System Prompt
    system_prompt = (
        "You are Celine, AI concierge for Celine Esthétique luxury salon in Lausanne, Switzerland. "
        "14+ years experience. Tone: elegant, warm, professional. "
        "Use 'we' and 'our salon'. "
        "CRITICAL: Be concise. Answer in 2-3 sentences maximum unless the user asks for detail. "
        "Base answers strictly on the verified context below. "
        "If context lacks the answer, say so politely and offer the phone number +41 78 949 40 39. "
        "Always offer to help schedule an appointment at the end.\n\n"
        f"VERIFIED CONTEXT:\n{context_text}"
        f"{business_context}"
    )

    # 6. Build Messages with Memory
    messages = [{"role": "system", "content": system_prompt}]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_query})

    # 7. LLM Orchestration with Performance Timing
    ai_reply = ""
    fallback_used = False
    response_time_ms = 0

    if not settings.GROQ_API_KEY:
        logger.error(f"[{session_id}] GROQ_API_KEY missing")
        fallback_used = True
    elif settings.GROQ_API_KEY.startswith("your_") or len(settings.GROQ_API_KEY) < 20:
        logger.warning(f"[{session_id}] GROQ_API_KEY placeholder")
        fallback_used = True
    else:
        try:
            start_time = time.time()
            
            logger.info(f"[{session_id}] Calling Groq: {GROQ_MODEL}")
            client = Groq(api_key=settings.GROQ_API_KEY)
            completion = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=200
            )
            ai_reply = completion.choices[0].message.content
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[{session_id}] Groq success in {response_time_ms}ms")
            
            if response_time_ms > 4000:
                logger.warning(f"[{session_id}] SLOW: {response_time_ms}ms > 4s target")
                
        except AuthenticationError as e:
            logger.error(f"[{session_id}] AUTH ERROR: {e}")
            fallback_used = True
        except APIConnectionError as e:
            logger.error(f"[{session_id}] CONNECTION ERROR: {e}")
            fallback_used = True
        except APIError as e:
            status = getattr(e, 'status_code', 'unknown')
            logger.error(f"[{session_id}] API ERROR ({status}): {e}")
            fallback_used = True
        except Exception as e:
            logger.error(f"[{session_id}] UNEXPECTED: {type(e).__name__}: {e}")
            fallback_used = True

    # 8. Offline Fallback
    if fallback_used:
        if retrieved_chunks:
            primary = retrieved_chunks[0]['answer']
            ai_reply = (
                f"Welcome to Celine Esthétique. {primary} "
                "Would you like help scheduling an appointment?"
            )
        else:
            ai_reply = (
                "Welcome to Celine Esthétique. Please contact us at +41 78 949 40 39."
            )

    return {
        "reply": ai_reply,
        "intent": intent_flag,
        "retrieved_context": retrieved_chunks,
        "fallback_used": fallback_used,
        "response_time_ms": response_time_ms
    }