# app/business_rules.py
"""
Salon Business Rules Engine
- VIP: 10% off
- First-time: 15% off
- Cancellation: 24 hours notice
- Deposit: Luxury services = 20%
"""

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

def calculate_price(base_price: float, is_vip: bool = False, is_first_time: bool = False) -> dict:
    discount = 0
    discount_label = None
    
    if is_vip:
        discount = SALON_POLICIES["discounts"]["vip"]["percentage"]
        discount_label = SALON_POLICIES["discounts"]["vip"]["label"]
    elif is_first_time:
        discount = SALON_POLICIES["discounts"]["first_time"]["percentage"]
        discount_label = SALON_POLICIES["discounts"]["first_time"]["label"]
    
    final = base_price * (1 - discount / 100)
    return {
        "base": base_price,
        "discount_percent": discount,
        "discount_label": discount_label,
        "final": round(final, 2)
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

def get_pricing_context() -> str:
    return (
        f"VIP clients receive {SALON_POLICIES['discounts']['vip']['percentage']}% off. "
        f"First-time clients receive {SALON_POLICIES['discounts']['first_time']['percentage']}% off. "
        f"Luxury services require a {int(SALON_POLICIES['deposits']['luxury_rate']*100)}% deposit. "
        f"{get_cancellation_policy()}"
    )