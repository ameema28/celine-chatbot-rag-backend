"""Groq client access.

This is the only place a Groq client is constructed, so tests can replace
`get_groq_client` with a fake and no real API call can happen.
"""

import groq

from app.config import settings


def key_status() -> str:
    """'ok', 'missing' or 'placeholder' (a your_... value or shorter than 20 characters)."""
    key = settings.GROQ_API_KEY or ""
    if not key:
        return "missing"
    if key.startswith("your_") or len(key) < 20:
        return "placeholder"
    return "ok"


def groq_key_usable() -> bool:
    """True when the configured key looks real (not missing, not a placeholder)."""
    return key_status() == "ok"


def get_groq_client() -> groq.Groq:
    """Return a Groq client for the configured key."""
    return groq.Groq(api_key=settings.GROQ_API_KEY)


TEMPERATURE = 0.3
# Reasoning models (gpt-oss) spend completion tokens on reasoning before the
# answer, so the budget covers both; the prompt asks for 2-3 sentences.
MAX_COMPLETION_TOKENS = 400


def completion_kwargs(messages: list[dict], stream: bool = False) -> dict:
    """Arguments for chat.completions.create, shared by /chat and /chat/stream."""
    kwargs = {
        "model": settings.GROQ_MODEL_NAME,
        "messages": messages,
        "temperature": TEMPERATURE,
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
    }
    # Only gpt-oss models are sent reasoning_effort; other models may reject it.
    if settings.GROQ_MODEL_NAME.startswith("openai/gpt-oss"):
        kwargs["reasoning_effort"] = "low"
    if stream:
        kwargs["stream"] = True
    return kwargs
