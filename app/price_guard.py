"""CHF price guard.

Every CHF amount in a reply must be a price from data/salon_knowledge.json or a
figure computed by the business rules for this turn. Otherwise the whole reply
is replaced with a safe message that offers the salon's phone number.
Amounts typed by the user are deliberately NOT allowed (strict guard).
"""

import json
import logging
import os
from collections.abc import Iterable
from decimal import Decimal

from app.business_rules import SALON_POLICIES, find_chf_amounts

logger = logging.getLogger(__name__)

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "salon_knowledge.json")
PHONE = SALON_POLICIES["contact"]["phone"]

SAFE_MESSAGES = {
    "en": (
        "I'd rather not quote a price I can't confirm. "
        f"Please call us at {PHONE} and we'll give you the exact figure."
    ),
}


def _load_kb_prices() -> frozenset[Decimal]:
    with open(_DATA_PATH, encoding="utf-8") as f:
        entries = json.load(f)
    prices: set[Decimal] = set()
    for entry in entries:
        prices.update(find_chf_amounts(entry.get("answer", "")))
        prices.update(find_chf_amounts(entry.get("question", "")))
    return frozenset(prices)


KB_PRICES = _load_kb_prices()


def check_reply(reply: str, extra_allowed: Iterable[Decimal] = ()) -> tuple[bool, list[Decimal]]:
    """(ok, unknown amounts): ok is False if any CHF amount isn't allowed."""
    allowed = KB_PRICES | frozenset(extra_allowed)
    unknown = [amount for amount in find_chf_amounts(reply) if amount not in allowed]
    return not unknown, unknown


def safe_message(lang: str = "en") -> str:
    return SAFE_MESSAGES.get(lang, SAFE_MESSAGES["en"])


def guard_reply(
    reply: str,
    extra_allowed: Iterable[Decimal] = (),
    session_id: str = "unknown",
    lang: str = "en",
) -> str:
    """Return the reply unchanged, or the safe message if it quotes an unknown price."""
    ok, unknown = check_reply(reply, extra_allowed)
    if ok:
        return reply
    logger.warning(
        f"[{session_id}] Price guard replaced reply (unknown CHF amounts: "
        f"{', '.join(str(a) for a in unknown)})"
    )
    return safe_message(lang)
