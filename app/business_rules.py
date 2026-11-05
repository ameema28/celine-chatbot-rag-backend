import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

SALON_POLICIES = {
    "discounts": {
        "vip": {"percentage": 10, "label": "VIP Client"},
        "first_time": {"percentage": 15, "label": "First-Time Client"}
    },
    "cancellation": {
        "notice_hours": 24,
        "policy_text": "Appointments can be rescheduled or canceled free of charge up to 24 hours before the appointment time."
    },
    "deposits": {
        "luxury_rate": 0.20,
        "standard_rate": 0.00,
        "luxury_services": [
            "Head Spa Japanese", "Eyelash extensions", "Full body wax",
            "Babyboomer installation", "Semi-permanent varnish", "Gel application"
        ]
    },
    "contact": {
        "phone": "+41 78 949 40 39",
        "address": "Cheneau-de-Bourg Street, Billens Stairs 1, 1003 Lausanne, Switzerland"
    }
}


_CENT = Decimal("0.01")

# "CHF 45", "CHF 45.50", "CHF 45,50", ranges "CHF 35-50", and "45 CHF".
_CHF_PATTERN = re.compile(
    r"CHF\s*(\d+(?:[.,]\d{1,2})?)(?:\s*[-–]\s*(\d+(?:[.,]\d{1,2})?))?"
    r"|(\d+(?:[.,]\d{1,2})?)\s*CHF",
    re.IGNORECASE,
)

_VIP_PATTERN = re.compile(r"\bvip\b", re.IGNORECASE)
_FIRST_TIME_PATTERN = re.compile(
    r"first[\s-]?time|first visit|new (?:client|customer)|never been"
    r"|premi[eè]re (?:fois|visite)|nouveau client|nouvelle cliente",
    re.IGNORECASE,
)


def money(value) -> Decimal:
    """Exact decimal amount rounded half-up to the centime."""
    return Decimal(str(value)).quantize(_CENT, rounding=ROUND_HALF_UP)


def calculate_price(base_price: float, is_vip: bool = False, is_first_time: bool = False) -> dict:
    """Apply one discount. VIP wins over first-time (they never stack)."""
    discount = 0
    discount_label = None

    if is_vip:
        discount = SALON_POLICIES["discounts"]["vip"]["percentage"]
        discount_label = SALON_POLICIES["discounts"]["vip"]["label"]
    elif is_first_time:
        discount = SALON_POLICIES["discounts"]["first_time"]["percentage"]
        discount_label = SALON_POLICIES["discounts"]["first_time"]["label"]

    final = money(Decimal(str(base_price)) * (Decimal(100 - discount) / Decimal(100)))
    return {
        "base": base_price,
        "discount_percent": discount,
        "discount_label": discount_label,
        "final": float(final)
    }


def get_deposit_info(service_name: str) -> dict:
    luxury_list = SALON_POLICIES["deposits"]["luxury_services"]
    is_luxury = any(lux.lower() in service_name.lower() for lux in luxury_list)
    rate = SALON_POLICIES["deposits"]["luxury_rate"] if is_luxury else SALON_POLICIES["deposits"]["standard_rate"]

    return {
        "required": is_luxury,
        "rate": rate,
        "rate_percent": int(rate * 100),
        "text": f"A {int(rate*100)}% deposit is required for this luxury service." if is_luxury else "No deposit required for this service."
    }


def get_cancellation_policy() -> str:
    return SALON_POLICIES["cancellation"]["policy_text"]


def find_chf_amounts(text: str) -> list[Decimal]:
    """Every CHF amount in the text (both ends of a range), as Decimals."""
    amounts = []
    for m in _CHF_PATTERN.finditer(text or ""):
        for group in m.groups():
            if group:
                amounts.append(money(group.replace(",", ".")))
    return amounts


def detect_client_status(text: str) -> tuple[bool, bool]:
    """(mentions VIP, mentions first-time) from keyword rules, English and French."""
    text = text or ""
    return bool(_VIP_PATTERN.search(text)), bool(_FIRST_TIME_PATTERN.search(text))


@dataclass(frozen=True)
class PriceItem:
    """One listed price in a knowledge-base entry."""

    service: str
    base: Decimal
    deposit_rate: Decimal  # from get_deposit_info(); 0 when no deposit is required

    @property
    def deposit(self) -> Decimal | None:
        """Deposit on the listed price, or None when not required."""
        return money(self.base * self.deposit_rate) if self.deposit_rate > 0 else None


def _clean_service_name(prefix: str) -> str:
    name = re.split(r"[,;:.()]", prefix)[-1]
    name = re.split(r"\b(?:includes?|including|offers?|features?)\b", name)[-1]
    name = re.sub(r"^\s*(?:and|or|the)\s+", "", name.strip(), flags=re.IGNORECASE)
    return name.strip()


def price_items_from_entry(entry: dict) -> list[PriceItem]:
    """(service, price) pairs from an entry's answer text.

    Two formats exist in the data: list items "Name (CHF 45, 45 min)" and
    detail entries "Price: CHF 45." whose service is the entry itself.
    """
    def rate(name: str) -> Decimal:
        return Decimal(str(get_deposit_info(name)["rate"]))

    answer = entry.get("answer", "")
    items: list[PriceItem] = []
    rest = answer
    for m in re.finditer(r"\(([^()]*CHF[^()]*)\)", answer):
        name = _clean_service_name(answer[: m.start()])
        for amount in find_chf_amounts(m.group(1)):
            items.append(PriceItem(name, amount, rate(name)))
        rest = rest.replace(m.group(0), " ", 1)

    entry_name = " ".join(
        [entry.get("question", ""), entry.get("id", "").replace("_", " "), answer.split(". ")[0]]
    )
    label = entry.get("question", "").rstrip("?").strip() or entry.get("id", "")
    for amount in find_chf_amounts(rest):
        items.append(PriceItem(label, amount, rate(entry_name)))

    unique: list[PriceItem] = []
    for item in items:
        if item not in unique:
            unique.append(item)
    return unique