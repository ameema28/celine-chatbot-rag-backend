import os
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# ── Graceful Firebase import ──
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    logger.warning("firebase-admin not installed. Firestore session store disabled.")

_firebase_initialized = False
_db = None


def _init_firebase():
    """Initialize Firebase Admin SDK if credentials are present.""""
    global _firebase_initialized, _db
    if _firebase_initialized:
        return _db

    project_id = os.getenv("FIREBASE_PROJECT_ID")
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")

    if not project_id or not service_account_path:
        return None

    if not os.path.exists(service_account_path):
        logger.warning(f"Firebase service account not found at: {service_account_path}")
        return None

    try:
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred, {"projectId": project_id})
        _db = firestore.client()
        _firebase_initialized = True
        logger.info("Firebase Firestore session store initialized successfully.")
        return _db
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
        return None


def save_session_firestore(session_id: str, history: List[Dict[str, str]]) -> bool:
    """Save session history to Firestore. Returns True on success.""""
    db = _init_firebase()
    if not db:
        return False

    try:
        db.collection("chatHistory").document(session_id).set({
            "session_id": session_id,
            "history": history,
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        return True
    except Exception as e:
        logger.error(f"Firestore save error [{session_id}]: {e}")
        return False


def load_session_firestore(session_id: str) -> Optional[List[Dict[str, str]]]:
    """Load session history from Firestore. Returns None if not found or on error.""""
    db = _init_firebase()
    if not db:
        return None

    try:
        doc = db.collection("chatHistory").document(session_id).get()
        if doc.exists:
            data = doc.to_dict()
            return data.get("history", [])
        return None
    except Exception as e:
        logger.error(f"Firestore load error [{session_id}]: {e}")
        return None
