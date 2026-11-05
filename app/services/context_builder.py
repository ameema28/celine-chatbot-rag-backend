"""Builds everything both chat paths (/chat and /chat/stream) need for one turn.

Keeping this in one place guarantees the JSON and streaming endpoints use the
same retrieval, intent, business rules, grounded prompt and fallback text.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal

from app.business_rules import (
    SALON_POLICIES,
    calculate_price,
    detect_client_status,
    get_cancellation_policy,
    money,
    price_items_from_entry,
)
from app.config import settings
from app.database import vector_db
from app.language import LANGUAGE_NAMES, detect_language, to_english_query

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
    computed_prices: list[Decimal] = field(default_factory=list)
    lang: str = "en"


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


def format_chf(value: Decimal) -> str:
    """CHF 45 for whole amounts, CHF 40.50 otherwise."""
    value = money(value)
    return f"CHF {int(value)}" if value == value.to_integral_value() else f"CHF {value:.2f}"


def _pricing_block(chunks: list[dict], user_query: str) -> tuple[str, list[Decimal]]:
    """Computed discount/deposit figures for the prices in the retrieved entries."""
    vip_pct = SALON_POLICIES["discounts"]["vip"]["percentage"]
    first_pct = SALON_POLICIES["discounts"]["first_time"]["percentage"]
    deposit_pct = int(SALON_POLICIES["deposits"]["luxury_rate"] * 100)

    lines: list[str] = []
    computed: list[Decimal] = []
    for chunk in chunks:
        for item in price_items_from_entry(chunk):
            vip = money(calculate_price(item.base, is_vip=True)["final"])
            first = money(calculate_price(item.base, is_first_time=True)["final"])
            parts = [
                f"- {item.service}: {format_chf(item.base)}",
                f"VIP {vip_pct}%: {format_chf(vip)}",
                f"first-time {first_pct}%: {format_chf(first)}",
            ]
            computed += [vip, first]
            if item.deposit is not None:
                parts.append(f"deposit {deposit_pct}%: {format_chf(item.deposit)}")
                computed.append(item.deposit)
            lines.append(" | ".join(parts))

    is_vip, is_first = detect_client_status(user_query)
    if is_vip:
        status = (
            f"Client mentions VIP: the VIP {vip_pct}% price applies to VIP clients "
            "(VIP and first-time discounts never combine)."
        )
    elif is_first:
        status = f"Client mentions a first visit: the first-time {first_pct}% price applies."
    else:
        status = (
            "Client status not stated: quote the listed price and mention the VIP and "
            "first-time discounts if relevant."
        )
    luxury = ", ".join(SALON_POLICIES["deposits"]["luxury_services"])
    block = ""
    if lines:
        block += (
            "\n\nCOMPUTED PRICES (exact figures; do not calculate other amounts):\n"
            + "\n".join(lines)
            + "\n"
        )
    block += f"{status}\nLUXURY SERVICES ({deposit_pct}% deposit on the listed price): {luxury}\n"
    return block, computed


def _language_rule(lang: str) -> str:
    rule = f"Reply in {LANGUAGE_NAMES[lang]}, the language of the customer's message. "
    if lang != "en":
        rule += (
            "The salon information below is in English; translate it faithfully and keep "
            "CHF amounts and the phone number unchanged. "
        )
    return rule


def _search(user_query: str, english_query: str) -> list[dict]:
    """Top-3 within the cutoff; French questions also search their English terms."""
    if not english_query:
        return vector_db.search_context(user_query, top_k=3)
    best: dict[str, tuple[dict, float]] = {}
    for query in (user_query, english_query):
        for doc, dist in vector_db.search_with_scores(query, top_k=3):
            if doc["id"] not in best or dist < best[doc["id"]][1]:
                best[doc["id"]] = (doc, dist)
    ranked = sorted(best.values(), key=lambda pair: pair[1])
    return [doc for doc, dist in ranked if dist <= settings.RAG_MAX_L2_DISTANCE][:3]


def _system_prompt(chunks: list[dict], business_context: str, lang: str = "en") -> str:
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
        "Only quote CHF prices that appear in the verified context or the computed prices; "
        "never restate other amounts as prices. "
        f"{_language_rule(lang)}"
        "Always offer to help schedule an appointment at the end.\n\n"
        f"VERIFIED CONTEXT:\n{context_text}"
        f"{business_context}"
    )


def build_turn(user_query: str, history: list[dict] | None = None) -> Turn:
    """Retrieve context and build the prompt/messages for one user message."""
    history = history or []
    lang = detect_language(user_query)
    english_query = to_english_query(user_query) if lang == "fr" else ""
    chunks = _search(user_query, english_query)
    # Keyword rules are English; French questions are matched via their glossary terms.
    rule_text = f"{user_query} {english_query}".strip()
    intent = classify_intent(rule_text)
    business = _business_context(rule_text)
    computed: list[Decimal] = []
    if intent == "intent_pricing":
        pricing, computed = _pricing_block(chunks, user_query)
        business += pricing
    system_prompt = _system_prompt(chunks, business, lang)
    messages = [{"role": "system", "content": system_prompt}]
    messages += [{"role": t["role"], "content": t["content"]} for t in history]
    messages.append({"role": "user", "content": user_query})
    return Turn(
        user_query=user_query,
        intent=intent,
        chunks=chunks,
        system_prompt=system_prompt,
        messages=messages,
        computed_prices=computed,
        lang=lang,
    )


def fallback_reply(turn: Turn) -> str:
    """Offline reply built only from retrieved salon data (no LLM).

    The data is English-only, so the French version says so instead of
    pretending to translate.
    """
    if turn.lang == "fr":
        if turn.chunks:
            return (
                "Bienvenue chez Celine Esthetique. Voici l'information disponible (en anglais) : "
                f"{turn.chunks[0]['answer']} Souhaitez-vous prendre rendez-vous ? "
                f"Appelez-nous au {PHONE}."
            )
        return f"Bienvenue chez Celine Esthetique. Veuillez nous contacter au {PHONE}."
    if turn.chunks:
        return (
            f"Welcome to Celine Esthetique. {turn.chunks[0]['answer']} "
            "Would you like help scheduling an appointment?"
        )
    return f"Welcome to Celine Esthetique. Please contact us at {PHONE}."


def word_chunks(text: str) -> list[str]:
    """Split text into word-sized pieces (word + trailing whitespace) for SSE."""
    return re.findall(r"\S+\s*", text)
