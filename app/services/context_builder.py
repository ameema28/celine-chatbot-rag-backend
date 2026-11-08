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
from app.language import LANGUAGE_NAMES, _words, detect_language, to_english_query
from app.spelling import correct_service_words

PHONE = SALON_POLICIES["contact"]["phone"]

PRICING_WORDS = ["price", "cost", "how much", "chf", "discount", "first-time", "vip", "deposit"]
BOOKING_WORDS = ["book", "appointment", "schedule", "reserve", "cancel"]
# Checked in this order after the pricing and booking words.
SERVICE_INTENTS = {
    "service_nails": ["nail", "manicure", "pedicure", "gel", "varnish"],
    "service_eyes": ["eye", "lash", "brow", "tint"],
    "service_waxing": ["hair removal", "wax", "bikini", "leg", "arm", "upper lip", "chin", "cheek"],
    "service_head_spa": ["head spa", "scalp", "hair wellness", "japanese"],
    "intent_shop": ["product", "shop", "cream", "skincare", "buy"],
}

# Follow-ups: a message with no match of its own is searched together with the
# previous user message if it is this short, starts with a cue, or refers back.
FOLLOW_UP_MAX_WORDS = 3
FOLLOW_UP_CUES = ("and", "also", "what about", "how about", "same for", "et", "aussi", "pour")
FOLLOW_UP_PRONOUNS = {"it", "that", "them", "ca", "cela"}


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
    # True when the session has no earlier reply (the offline fallback greets only then).
    first_reply: bool = True


def classify_intent(user_query: str) -> str:
    """Keyword intent tag (pricing keywords are checked first)."""
    q = user_query.lower()
    if any(w in q for w in PRICING_WORDS):
        return "intent_pricing"
    if any(w in q for w in BOOKING_WORDS):
        return "intent_booking"
    for intent, words in SERVICE_INTENTS.items():
        if any(w in q for w in words):
            return intent
    return "general_salon_info"


def _previous_user_message(history: list[dict]) -> str:
    for turn in reversed(history):
        if turn.get("role") == "user" and turn.get("content"):
            return turn["content"]
    return ""


def _is_follow_up(text: str) -> bool:
    """Very short, starts with a follow-up cue ("and ...", "et pour ..."), or refers back ("it")."""
    words = _words(text)  # lowercase, accents removed
    if not words:
        return False
    starts_with_cue = any(" ".join(words).startswith(cue + " ") for cue in FOLLOW_UP_CUES)
    return len(words) <= FOLLOW_UP_MAX_WORDS or starts_with_cue or bool(FOLLOW_UP_PRONOUNS & set(words))


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


def _search(queries: list[str]) -> list[dict]:
    """Top-3 within the cutoff over all queries (best distance per entry wins).

    The queries are the user's message plus its variants: English glossary terms
    for French, the typo-corrected text, and the follow-up combination.
    """
    queries = [q for i, q in enumerate(queries) if q and q not in queries[:i]]
    if len(queries) == 1:
        return vector_db.search_context(queries[0], top_k=3)
    best: dict[str, tuple[dict, float]] = {}
    for query in queries:
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
        "Write plain text only: no Markdown, no asterisks, no headings, no bullet lists, no tables. "
        "Only help with questions about Celine Esthetique (services, prices, booking, "
        "opening hours, location, products); politely decline anything else in one sentence. "
        "Use the conversation history to understand what the user is referring to. "
        "Base factual details on the verified salon context below. "
        f"If the context does not contain the answer, say so politely and offer the phone number {PHONE}. "
        "Only quote CHF prices that appear in the verified context or the computed prices; "
        "never restate other amounts as prices. "
        "Quote only the services the customer asked about, not the whole price list; "
        "mention the VIP and first-time discounts in one short sentence at most. "
        f"{_language_rule(lang)}"
        "You cannot book appointments, check availability or contact anyone. Never say you "
        "will check, book, confirm or get back to the customer. "
        f"When booking is relevant, end by inviting them to call us at {PHONE} to book.\n\n"
        f"VERIFIED CONTEXT:\n{context_text}"
        f"{business_context}"
    )


def build_turn(user_query: str, history: list[dict] | None = None) -> Turn:
    """Retrieve context and build the prompt/messages for one user message."""
    history = history or []
    lang = detect_language(user_query)
    english_query = to_english_query(user_query) if lang == "fr" else ""
    corrected = correct_service_words(user_query)
    chunks = _search([user_query, english_query, corrected])
    previous = _previous_user_message(history)
    if not chunks and previous and _is_follow_up(user_query):
        # Follow-up with no match of its own: search it together with the previous
        # user message. Retrieval only; the prompt and messages keep the real message.
        follow_up = [f"{correct_service_words(previous)} {corrected}"]
        if lang == "fr" or detect_language(previous) == "fr":
            follow_up.append(to_english_query(f"{previous} {user_query}"))
        chunks = _search(follow_up)
    # Keyword rules are English; French questions are matched via their glossary terms
    # and misspelled service words via their corrected form.
    rule_text = " ".join(t for t in (corrected, english_query) if t)
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
        first_reply=not any(t.get("role") == "assistant" for t in history),
    )


def fallback_reply(turn: Turn) -> str:
    """Offline reply built only from retrieved salon data (no LLM).

    The data is English-only, so the French version says so instead of
    pretending to translate. The greeting is only used on a session's first reply.
    """
    if turn.lang == "fr":
        greeting = "Bienvenue chez Celine Esthetique. " if turn.first_reply else ""
        if turn.chunks:
            return (
                f"{greeting}Voici l'information disponible (en anglais) : "
                f"{turn.chunks[0]['answer']} Souhaitez-vous prendre rendez-vous ? "
                f"Appelez-nous au {PHONE}."
            )
        return f"{greeting}Veuillez nous contacter au {PHONE}."
    greeting = "Welcome to Celine Esthetique. " if turn.first_reply else ""
    if turn.chunks:
        return (
            f"{greeting}{turn.chunks[0]['answer']} "
            "Would you like help scheduling an appointment?"
        )
    return f"{greeting}Please contact us at {PHONE}."


def word_chunks(text: str) -> list[str]:
    """Split text into word-sized pieces (word + trailing whitespace) for SSE."""
    return re.findall(r"\S+\s*", text)
