"""Lightweight English/French handling (no dependency).

Only English and French are needed, so a small deterministic word/accent
heuristic is used instead of a language-detection library.

The salon data and the embedding model (all-MiniLM-L6-v2) are English-only,
so French questions are also searched with English glossary terms.
"""

import re
import unicodedata

_FR_ACCENTS = re.compile(r"[àâçéèêëîïôûùüÿœæ]", re.IGNORECASE)

_FR_WORDS = {
    "bonjour", "bonsoir", "salut", "merci", "combien", "coute", "prix", "tarif", "tarifs",
    "vous", "nous", "votre", "vos", "quel", "quelle", "quels", "quelles", "est-ce",
    "rendez-vous", "horaires", "ou", "je", "suis", "une", "des", "pour", "avec", "le",
    "la", "les", "du", "au", "aux", "et", "se", "trouve", "sont", "cils", "ongles",
    "manucure", "epilation", "annulation", "reserver", "acompte", "reduction", "plait",
    "mon", "ma", "mes", "est", "fois", "premiere", "jambes", "visage", "sourcils",
}
_EN_WORDS = {
    "the", "is", "are", "what", "how", "much", "you", "your", "do", "does", "i", "my",
    "a", "an", "for", "with", "and", "price", "hello", "hi", "please", "can", "book",
    "where", "when", "it", "of", "to", "in", "me", "this", "time", "first",
}

# French salon terms -> English search terms (keys are accent-free, lowercase).
FR_EN_GLOSSARY = {
    "manucure": "manicure",
    "pedicure": "pedicure",
    "ongle": "nails",
    "vernis": "varnish",
    "semi-permanent": "semi-permanent varnish",
    "cils": "eyelash",
    "extension": "extensions",
    "rehaussement": "eyelash lift",
    "teinture": "tinting",
    "sourcil": "eyebrow",
    "epilation": "wax",
    "cire": "wax",
    "jambe": "leg",
    "complete": "full",
    "demi": "half",
    "aisselle": "armpit",
    "maillot": "bikini",
    "levre": "upper lip",
    "menton": "chin",
    "visage": "face",
    "corps": "body",
    "cuir chevelu": "scalp",
    "japonais": "japanese",
    "tete": "head spa",
    "prix": "price",
    "tarif": "price",
    "combien": "price",
    "coute": "price",
    "horaire": "opening hours",
    "ouverture": "opening hours",
    "adresse": "address location",
    "ou se trouve": "where is the salon located",
    "situe": "located",
    "annulation": "cancellation policy",
    "annuler": "cancel",
    "rendez-vous": "book appointment",
    "reserver": "book",
    "reservation": "booking",
    "acompte": "deposit",
    "reduction": "discount",
    "remise": "discount",
    "premiere fois": "first time",
    "produit": "products",
    "creme": "cream",
    "paiement": "payment",
}

LANGUAGE_NAMES = {"en": "English", "fr": "French"}


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z]+(?:-[a-z]+)*", _normalize(text))


def detect_language(text: str) -> str:
    """'fr' or 'en' (default 'en')."""
    words = _words(text)
    fr = sum(1 for w in words if w in _FR_WORDS) + (1 if _FR_ACCENTS.search(text or "") else 0)
    en = sum(1 for w in words if w in _EN_WORDS)
    return "fr" if fr > en and fr >= 1 else "en"


def to_english_query(text: str) -> str:
    """English search terms for the French salon words in the text ('' if none)."""
    normalized = _normalize(text)
    terms: list[str] = []
    for fr_term in sorted(FR_EN_GLOSSARY, key=len, reverse=True):
        if re.search(rf"\b{re.escape(fr_term)}s?\b", normalized):
            for word in FR_EN_GLOSSARY[fr_term].split():
                if word not in terms:
                    terms.append(word)
    return " ".join(terms)
