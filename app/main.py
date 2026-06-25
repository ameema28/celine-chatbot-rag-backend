import logging
import uuid
import time
from contextlib import asynccontextmanager
from typing import List, Dict, Optional
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from app.config import settings
from app.services.rag_service import generate_rag_response
from app.services.streaming_service import generate_streaming_rag_response
from app.session_store import save_session, load_session

# Phase 7: Firebase Firestore bridge (graceful fallback)
save_session_firestore = None
load_session_firestore = None
FIRESTORE_AVAILABLE = False

try:
    from app.firebase_session_store import save_session_firestore as _save_fs
    from app.firebase_session_store import load_session_firestore as _load_fs
    save_session_firestore = _save_fs
    load_session_firestore = _load_fs
    FIRESTORE_AVAILABLE = True
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

SESSION_MEMORY: Dict[str, List[Dict[str, str]]] = {}

# Rate Limiting Middleware: max 10 requests per minute per IP
RATE_LIMIT_STORE: Dict[str, List[float]] = {}


def _cleanup_rate_limit_store():
    """Prevent unbounded memory growth in rate limit dict."""
    now = time.time()
    cutoff = now - 3600
    stale = [ip for ip, timestamps in RATE_LIMIT_STORE.items() if timestamps and timestamps[-1] < cutoff]
    for ip in stale:
        del RATE_LIMIT_STORE[ip]


def _startup_tasks():
    """Run once at server startup."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    if not settings.GROQ_API_KEY:
        logger.critical("GROQ_API_KEY missing. Offline fallback mode active.")
    else:
        masked = f"{settings.GROQ_API_KEY[:8]}...{settings.GROQ_API_KEY[-4:]}"
        logger.info(f"GROQ_API_KEY loaded: {masked}")
        logger.info(f"Model: {settings.GROQ_MODEL_NAME}")
    logger.info("Streaming: ENABLED")
    logger.info("Business Rules: ENABLED")
    logger.info("CORS: ENABLED")
    logger.info("SQLite Sessions: ENABLED")
    logger.info(f"Firebase Firestore: {'ENABLED' if FIRESTORE_AVAILABLE else 'DISABLED (fallback to SQLite)'}")
    logger.info("Rate Limiting: ENABLED")
    logger.info("Memory Cleanup: ENABLED")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Phase 7: Modern FastAPI lifespan event handler (replaces deprecated on_event)."""
    _startup_tasks()
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-grade AI concierge for Celine Esthetique luxury salon. RAG-powered with FAISS, Groq LLM, session memory, business rules, and real-time SSE streaming.",
    contact={
        "name": "Ameema Rashid — AI Lead",
        "email": "ameema.rashid@technexusvu.com"
    },
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.client:
        client_ip = request.client.host
    else:
        client_ip = request.headers.get("x-forwarded-for", "unknown")

    now = time.time()

    if len(RATE_LIMIT_STORE) % 100 == 0:
        _cleanup_rate_limit_store()

    if client_ip in RATE_LIMIT_STORE:
        RATE_LIMIT_STORE[client_ip] = [
            t for t in RATE_LIMIT_STORE[client_ip] if now - t < 60
        ]
    else:
        RATE_LIMIT_STORE[client_ip] = []

    if len(RATE_LIMIT_STORE[client_ip]) >= 10:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Max 10 requests per minute."}
        )

    RATE_LIMIT_STORE[client_ip].append(now)
    response = await call_next(request)
    return response


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500, description="User message to the AI concierge.")
    session_id: Optional[str] = Field(None, description="Existing session ID for memory continuity. Omit to start a new session.")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="AI-generated response text.")
    intent: str = Field(..., description="Classified intent tag (e.g., service_nails, intent_pricing).")
    session_id: str = Field(..., description="Session identifier for continuity.")
    fallback_used: bool = Field(..., description="True if the offline fallback was used instead of live LLM.")
    response_time_ms: int = Field(..., description="LLM inference time in milliseconds (0 if fallback).")
    retrieved_context: List[dict] = Field(..., description="FAISS-retrieved knowledge base chunks.")


def _persist_session(session_id: str, history: List[Dict[str, str]]):
    """Save to Firebase if available, else SQLite, else in-memory."""
    SESSION_MEMORY[session_id] = history

    if FIRESTORE_AVAILABLE and save_session_firestore is not None:
        ok = save_session_firestore(session_id, history)
        if ok:
            return

    try:
        save_session(session_id, history)
    except Exception as e:
        logger.error(f"SQLite save failed [{session_id}]: {e}")


def _load_session(session_id: str) -> Optional[List[Dict[str, str]]]:
    """Load from Firebase if available, else SQLite, else in-memory."""
    if FIRESTORE_AVAILABLE and load_session_firestore is not None:
        hist = load_session_firestore(session_id)
        if hist is not None:
            return hist

    try:
        hist = load_session(session_id)
        if hist is not None:
            return hist
    except Exception as e:
        logger.error(f"SQLite load failed [{session_id}]: {e}")

    return SESSION_MEMORY.get(session_id)


@app.post("/api/ai/chat", response_model=ChatResponse, tags=["AI Concierge"], summary="Standard chat with JSON response")
def ai_chat_endpoint(payload: ChatRequest):
    """
    Send a message to the AI concierge and receive a structured JSON response.

    - Retrieves relevant salon context from FAISS
    - Classifies intent
    - Injects business rules for pricing/booking queries
    - Maintains session memory across requests
    """
    session_id = payload.session_id or f"cel-{uuid.uuid4().hex[:12]}"

    history = _load_session(session_id) or []
    history = history[-12:]

    logger.info(f"[{session_id}] Query: '{payload.message[:60]}...'")

    response_data = generate_rag_response(
        user_query=payload.message,
        session_id=session_id,
        history=history
    )

    history.append({"role": "user", "content": payload.message})
    history.append({"role": "assistant", "content": response_data["reply"]})

    _persist_session(session_id, history)

    if response_data.get("fallback_used"):
        logger.warning(f"[{session_id}] OFFLINE FALLBACK")
    else:
        logger.info(f"[{session_id}] Live LLM response in {response_data.get('response_time_ms', 0)}ms")

    return ChatResponse(
        reply=response_data["reply"],
        intent=response_data["intent"],
        session_id=session_id,
        fallback_used=response_data["fallback_used"],
        response_time_ms=response_data.get("response_time_ms", 0),
        retrieved_context=response_data["retrieved_context"]
    )


@app.post("/api/ai/chat/stream", tags=["AI Concierge"], summary="Streaming chat with SSE")
async def ai_chat_stream_endpoint(payload: ChatRequest):
    """
    Send a message and receive a real-time Server-Sent Events (SSE) stream.

    Ideal for frontend typing indicators and live token display.
    Stream ends with `data: [DONE]\n\n`.
    """
    session_id = payload.session_id or f"cel-{uuid.uuid4().hex[:12]}"

    history = _load_session(session_id) or []
    history = history[-12:]

    logger.info(f"[STREAM] [{session_id}] Query: '{payload.message[:60]}...'")
    start_time = time.time()

    async def event_generator():
        full_response = []
        async for token in generate_streaming_rag_response(
            payload.message, session_id, history
        ):
            full_response.append(token)
            yield f"data: {token}\n\n"

        complete_reply = "".join(full_response)
        history.append({"role": "user", "content": payload.message})
        history.append({"role": "assistant", "content": complete_reply})

        _persist_session(session_id, history)

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"[STREAM] [{session_id}] Completed in {elapsed_ms}ms")

        yield f"data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "X-Session-Id": session_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@app.get("/health", tags=["System"], summary="Health and status check")
def health_check():
    """Returns server health, model info, and LLM readiness status."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "model": settings.GROQ_MODEL_NAME,
        "llm_ready": bool(settings.GROQ_API_KEY),
        "firebase_ready": FIRESTORE_AVAILABLE,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }