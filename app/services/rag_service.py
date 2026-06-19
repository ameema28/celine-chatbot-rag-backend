import logging
from typing import List, Dict

from groq import Groq, APIError, APIConnectionError, AuthenticationError
from app.database import vector_db
from app.config import settings

logger = logging.getLogger(__name__)
GROQ_MODEL = getattr(settings, 'GROQ_MODEL_NAME', 'llama-3.3-70b-versatile')

def generate_rag_response(
    user_query: str,
    session_id: str = "unknown",
    history: List[Dict[str, str]] = None
) -> dict:
    history = history or []

    retrieved_chunks = vector_db.search_context(user_query, top_k=3)

    context_blocks = []
    for i, chunk in enumerate(retrieved_chunks, 1):
        context_blocks.append(
            f"[{i}] Category: {chunk['category']}\nQ: {chunk['question']}\nA: {chunk['answer']}"
        )
    context_text = "\n\n".join(context_blocks) if context_blocks else "No specific salon documents matched this query."

    system_prompt = (
        "You are Celine, the exclusive AI concierge for Celine Esthétique — a luxury beauty and nail salon "
        "in Lausanne, Switzerland (Cheneau-de-Bourg Street, Billens Stairs 1, 1003). "
        "14+ years experience, 50+ happy clients, 200+ reviews.\n\n"
        "PERSONA RULES:\n"
        "- Tone: Elegant, warm, refined, five-star spa professionalism.\n"
        "- Language: English primarily. If user writes French, reply in elegant French.\n"
        "- Use 'we', 'our salon', 'our team'. Never robotic.\n"
        "- Base answers STRICTLY on VERIFIED SALON CONTEXT below.\n"
        "- If context lacks the answer, politely offer to connect with reception (+41 78 949 40 39).\n"
        "- Always offer to help schedule an appointment after service answers.\n\n"
        f"VERIFIED SALON CONTEXT:\n{context_text}\n\n"
        "You represent Swiss luxury. Every word should feel like silk."
    )

    messages = [{"role": "system", "content": system_prompt}]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_query})

    ai_reply = ""
    fallback_used = False

    if not settings.GROQ_API_KEY:
        logger.error(f"[{session_id}] GROQ_API_KEY missing")
        fallback_used = True
    elif settings.GROQ_API_KEY.startswith("your_") or len(settings.GROQ_API_KEY) < 20:
        logger.warning(f"[{session_id}] GROQ_API_KEY placeholder")
        fallback_used = True
    else:
        try:
            logger.info(f"[{session_id}] Calling Groq: {GROQ_MODEL}")
            client = Groq(api_key=settings.GROQ_API_KEY)
            completion = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.4,
                max_tokens=350
            )
            ai_reply = completion.choices[0].message.content
            logger.info(f"[{session_id}] Groq success")
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

    if fallback_used:
        if retrieved_chunks:
            primary = retrieved_chunks[0]['answer']
            ai_reply = (
                f"Welcome to Celine Esthétique. {primary} "
                "Our team would be delighted to orchestrate this experience for you. "
                "Would you like help scheduling an appointment?"
            )
        else:
            ai_reply = (
                "Welcome to Celine Esthétique. Please contact our reception at +41 78 949 40 39 "
                "to arrange your personalized package."
            )

    intent_flag = "general_salon_info"
    q = user_query.lower()
    if any(w in q for w in ["nail", "manicure", "pedicure", "gel", "varnish"]):
        intent_flag = "service_nails"
    elif any(w in q for w in ["eye", "lash", "brow", "tint"]):
        intent_flag = "service_eyes"
    elif any(w in q for w in ["hair removal", "wax", "bikini", "leg", "arm", "upper lip", "chin", "cheek"]):
        intent_flag = "service_waxing"
    elif any(w in q for w in ["head spa", "scalp", "hair wellness", "japanese"]):
        intent_flag = "service_head_spa"
    elif any(w in q for w in ["book", "appointment", "schedule", "reserve", "booking"]):
        intent_flag = "intent_booking"
    elif any(w in q for w in ["price", "cost", "how much", "chf", "estimate"]):
        intent_flag = "intent_pricing"
    elif any(w in q for w in ["product", "shop", "cream", "skincare", "buy"]):
        intent_flag = "intent_shop"

    return {
        "reply": ai_reply,
        "intent": intent_flag,
        "retrieved_context": retrieved_chunks,
        "fallback_used": fallback_used
    }