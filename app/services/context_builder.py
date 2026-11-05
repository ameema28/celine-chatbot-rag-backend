"""Builds everything both chat paths (/chat and /chat/stream) need for one turn.

Keeping this in one place guarantees the JSON and streaming endpoints use the
same retrieval, intent, business rules, grounded prompt and fallback text.
"""

import re
from dataclasses import dataclass

from app.business_rules import SALON_POLICIES, get_cancellation_policy
from app.database import vector_db

PHONE = SALON_POLICIES["contact"]["phone"]

PRICING_WORDS = ["price", "cost", "how much", "chf", "discount", "first-time", "vip", "deposit"]
BOOKING_WORDS = ["book", "appointment", "schedule", "reserve", "cancel"]


@dataclass
class Turn:
    """Everything needed to answer one user message."""

    user_query: str
    intent: str
    chunks: list[dict]
    system_prompt: str
    messages: list[dict]


def classify_intent(user_query: str) -> str:
    """Keyword intent tag (pricing keywords are checked first)."""
    q = user_query.lower()
    if any(w in q for w in PRICING_WORDS):
        return "intent_pricing"
    if any(w in q for w in BOOKING_WORDS):
        return "intent_booking"
    if any(w in q for w in ["nail", "manicure", "pedicure", "gel", "varnish"]):
        return "service_nails"
    if any(w in q for w in ["eye", "lash", "brow", "tint"]):
        return "service_eyes"
    if any(w in q for w in ["hair removal", "wax", "bikini", "leg", "arm", "upper lip", "chin", "cheek"]):
        return "service_waxing"
    if any(w in q for w in ["head spa", "scalp", "hair wellness", "japanese"]):
        return "service_head_spa"
    if any(w in q for w in ["product", "shop", "cream", "skincare", "buy"]):
        return "intent_shop"
    return "general_salon_info"


def _business_context(user_query: str) -> str:
    q = user_query.lower()
    if any(w in q for w in PRICING_WORDS):
        return (
            "\n\nPRICING RULES:\n"
            f"- VIP: {SALON_POLICIES['discounts']['vip']['percentage']}% off\n"
            f"- First-time: {SALON_POLICIES['discounts']['first_time']['percentage']}% off\n"
            f"- Luxury deposit: {int(SALON_POLICIES['deposits']['luxury_rate'] * 100)}%\n"
            f"- {get_cancellation_policy()}\n"
        )
    if any(w in q for w in BOOKING_WORDS):
        return (
            "\n\nBOOKING RULES:\n"
            f"- {get_cancellation_policy()}\n"
            f"- Phone: {PHONE}\n"
        )
    return ""


def _system_prompt(chunks: list[dict], business_context: str) -> str:
    context_blocks = [f"[{i}] {c['category']}: {c['answer']}" for i, c in enumerate(chunks, 1)]
    context_text = "\n".join(context_blocks) if context_blocks else "No specific salon documents matched."
    return (
        "You are Celine, AI concierge for Celine Esthetique luxury salon in Lausanne, Switzerland. "
        "14+ years experience. Tone: elegant, warm, professional. "
        "Use 'we' and 'our salon'. "
        "Be concise. Answer in 2-3 sentences unless the user asks for detail. "
        "Use the conversation history to understand what the user is referring to. "
        "Base factual details on the verified salon context below. "
        f"If the context does not contain the answer, say so politely and offer the phone number {PHONE}. "
        "Always offer to help schedule an appointment at the end.\n\n"
        f"VERIFIED CONTEXT:\n{context_text}"
        f"{business_context}"
    )


def build_turn(user_query: str, history: list[dict] | None = None) -> Turn:
    """Retrieve context and build the prompt/messages for one user message."""
    history = history or []
    chunks = vector_db.search_context(user_query, top_k=3)
    system_prompt = _system_prompt(chunks, _business_context(user_query))
    messages = [{"role": "system", "content": system_prompt}]
    messages += [{"role": t["role"], "content": t["content"]} for t in history]
    messages.append({"role": "user", "content": user_query})
    return Turn(
        user_query=user_query,
        intent=classify_intent(user_query),
        chunks=chunks,
        system_prompt=system_prompt,
        messages=messages,
    )


def fallback_reply(turn: Turn) -> str:
    """Offline reply built only from retrieved salon data (no LLM)."""
    if turn.chunks:
        return (
            f"Welcome to Celine Esthetique. {turn.chunks[0]['answer']} "
            "Would you like help scheduling an appointment?"
        )
    return f"Welcome to Celine Esthetique. Please contact us at {PHONE}."


def word_chunks(text: str) -> list[str]:
    """Split text into word-sized pieces (word + trailing whitespace) for SSE."""
    return re.findall(r"\S+\s*", text)
