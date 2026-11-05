"""Groq client access.

This is the only place a Groq client is constructed, so tests can replace
`get_groq_client` with a fake and no real API call can happen.
"""

import groq

from app.config import settings


def groq_key_usable() -> bool:
    """True when the configured key looks real (not missing, not a placeholder)."""
    key = settings.GROQ_API_KEY or ""
    return bool(key) and not key.startswith("your_") and len(key) >= 20


def get_groq_client() -> groq.Groq:
    """Return a Groq client for the configured key."""
    return groq.Groq(api_key=settings.GROQ_API_KEY)
