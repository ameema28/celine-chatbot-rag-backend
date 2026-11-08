import base64
import hashlib
import logging
import re
import time
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app import llm
from app.config import settings
from app.database import vector_db
from app.services.rag_service import generate_rag_response
from app.services.streaming_service import generate_streaming_rag_response
from app.session_store import load_session, save_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# In-memory session copy, least recently used first; bounded by _evict_sessions().
SESSION_MEMORY: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
SESSION_LAST_USED: dict[str, float] = {}


def _now() -> float:
    return time.monotonic()


def _touch_session(session_id: str):
    SESSION_MEMORY.move_to_end(session_id)
    SESSION_LAST_USED[session_id] = _now()


def _evict_sessions():
    """Drop in-memory sessions idle longer than SESSION_TTL_MINUTES, then the least
    recently used ones above SESSION_MEMORY_MAX_SESSIONS. SQLite is not touched."""
    cutoff = _now() - settings.SESSION_TTL_MINUTES * 60
    for session_id in [s for s, used in SESSION_LAST_USED.items() if used < cutoff]:
        SESSION_MEMORY.pop(session_id, None)
        del SESSION_LAST_USED[session_id]
    while len(SESSION_MEMORY) > settings.SESSION_MEMORY_MAX_SESSIONS:
        session_id, _ = SESSION_MEMORY.popitem(last=False)
        SESSION_LAST_USED.pop(session_id, None)

# Rate Limiting Middleware: max 10 requests per minute per IP
RATE_LIMIT_STORE: dict[str, list[float]] = {}


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
    logger.info(f"FAISS index: {vector_db.index.ntotal} knowledge base entries")
    # Never log any part of the key itself, only whether live mode is possible.
    if llm.groq_key_usable():
        logger.info("GROQ_API_KEY loaded: yes")
        logger.info(f"Model: {settings.GROQ_MODEL_NAME}")
    else:
        logger.warning("GROQ_API_KEY loaded: no")
    logger.info("Streaming: ENABLED")
    logger.info("Business Rules: ENABLED")
    logger.info("CORS: ENABLED")
    logger.info("SQLite Sessions: ENABLED")
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
    description="AI concierge for Celine Esthetique salon. RAG with FAISS, Groq LLM, session memory, business rules, CHF price guard and SSE streaming.",
    contact={
        "name": "Ameema Rashid — AI Lead",
        "email": "ameema.rashid@technexusvu.com"
    },
    lifespan=lifespan
)

# Preflights, the demo page and health/docs routes are never rate limited.
RATE_LIMIT_EXEMPT_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}

# demo.html is served at GET / with its API base switched to the page's own origin.
DEMO_PAGE_PATH = Path(__file__).resolve().parent.parent / "demo.html"
DEMO_LOCAL_API_META = '<meta name="celine-api-base" content="http://127.0.0.1:8000">'
DEMO_SAME_ORIGIN_META = '<meta name="celine-api-base" content="">'


def _load_demo_page() -> str:
    html = DEMO_PAGE_PATH.read_text(encoding="utf-8")
    if DEMO_LOCAL_API_META not in html:
        raise RuntimeError("demo.html is missing the celine-api-base meta tag")
    return html.replace(DEMO_LOCAL_API_META, DEMO_SAME_ORIGIN_META)


DEMO_PAGE_HTML = _load_demo_page()


def _csp_hash(html: str, tag: str) -> str:
    """CSP source for the page's single inline <script> or <style> block."""
    blocks = re.findall(rf"<{tag}>(.*?)</{tag}>", html, flags=re.DOTALL)
    if len(blocks) != 1:
        raise RuntimeError(f"demo.html must have exactly one inline <{tag}> block")
    digest = hashlib.sha256(blocks[0].encode("utf-8")).digest()
    return f"'sha256-{base64.b64encode(digest).decode()}'"


# The served page calls only its own origin; ?api= overrides are for the file
# served from elsewhere (python -m http.server), not for this page.
DEMO_PAGE_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; "
        f"script-src {_csp_hash(DEMO_PAGE_HTML, 'script')}; "
        f"style-src {_csp_hash(DEMO_PAGE_HTML, 'style')}; "
        "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


def _client_ip(request: Request) -> str:
    """Client IP for rate limiting.

    With TRUST_PROXY=true: the X-Forwarded-For entry TRUST_PROXY_HOPS places from
    the right (default 1 = right-most, the one the trusted proxy appended). Entries
    to its left are client-supplied and ignored. If the header has fewer entries
    than that, or TRUST_PROXY is off, the socket peer is used.
    """
    if settings.TRUST_PROXY:
        joined = ",".join(request.headers.getlist("x-forwarded-for"))
        entries = [entry.strip() for entry in joined.split(",") if entry.strip()]
        hops = settings.TRUST_PROXY_HOPS
        if len(entries) >= hops:
            return entries[-hops]
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in RATE_LIMIT_EXEMPT_PATHS:
        return await call_next(request)

    client_ip = _client_ip(request)
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
            content={"detail": "Rate limit exceeded. Max 10 requests per minute."},
            headers={"Retry-After": "60"},
        )

    RATE_LIMIT_STORE[client_ip].append(now)
    response = await call_next(request)
    return response


# CORS: only the configured origins (CORS_ALLOW_ORIGINS). No cookies are used.
# Added after the rate limiter so it is the outer layer: 429 responses still
# carry CORS headers and browsers see the real status.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=["X-Session-Id"],
)


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    """Unexpected errors return the same JSON shape as other errors ({"detail": ...})."""
    logger.error(f"Unhandled error on {request.url.path}: {type(exc).__name__}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500, description="User message to the AI concierge.")
    session_id: str | None = Field(None, description="Existing session ID for memory continuity. Omit to start a new session.")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="AI-generated response text.")
    intent: str = Field(..., description="Classified intent tag (e.g., service_nails, intent_pricing).")
    session_id: str = Field(..., description="Session identifier for continuity.")
    fallback_used: bool = Field(..., description="True if the offline fallback was used instead of live LLM.")
    response_time_ms: int = Field(..., description="LLM inference time in milliseconds (0 if fallback).")
    retrieved_context: list[dict] = Field(..., description="FAISS-retrieved knowledge base chunks.")


def _persist_session(session_id: str, history: list[dict[str, str]]):
    """Save to SQLite; the in-memory copy is the fallback if SQLite fails."""
    SESSION_MEMORY[session_id] = history
    _touch_session(session_id)
    _evict_sessions()

    try:
        save_session(session_id, history)
    except Exception as e:  # noqa: BLE001 - a storage failure must never break a reply
        logger.error(f"SQLite save failed [{session_id}]: {e}")


def _load_session(session_id: str) -> list[dict[str, str]] | None:
    """Load from SQLite, else from the in-memory copy."""
    try:
        hist = load_session(session_id)
        if hist is not None:
            return hist
    except Exception as e:  # noqa: BLE001 - fall back to the in-memory copy on any storage error
        logger.error(f"SQLite load failed [{session_id}]: {e}")

    _evict_sessions()
    if session_id not in SESSION_MEMORY:
        return None
    _touch_session(session_id)
    return SESSION_MEMORY[session_id]


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

    logger.info(f"[{session_id}] Query received (len={len(payload.message)})")

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


def _sse_event(text: str) -> str:
    """One SSE event; multi-line text becomes several data: lines (SSE spec)."""
    return "".join(f"data: {line}\n" for line in text.split("\n")) + "\n"


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

    logger.info(f"[STREAM] [{session_id}] Query received (len={len(payload.message)})")
    start_time = time.time()

    async def event_generator():
        full_response = []
        async for token in generate_streaming_rag_response(
            payload.message, session_id, history
        ):
            full_response.append(token)
            yield _sse_event(token)

        complete_reply = "".join(full_response)
        history.append({"role": "user", "content": payload.message})
        history.append({"role": "assistant", "content": complete_reply})

        _persist_session(session_id, history)

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"[STREAM] [{session_id}] Completed in {elapsed_ms}ms")

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "X-Session-Id": session_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
def demo_page():
    """The chat demo page; it calls the API on this same origin."""
    return HTMLResponse(DEMO_PAGE_HTML, headers=DEMO_PAGE_HEADERS)


@app.get("/health", tags=["System"], summary="Health and status check")
def health_check():
    """Returns server health, model info, and LLM readiness status."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "model": settings.GROQ_MODEL_NAME,
        "llm_ready": llm.groq_key_usable(),
        "session_store": "sqlite",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }