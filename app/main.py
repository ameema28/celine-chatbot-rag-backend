import logging
import uuid
import time
from typing import List, Dict, Optional
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from app.config import settings
from app.services.rag_service import generate_rag_response
from app.services.streaming_service import generate_streaming_rag_response
from app.session_store import save_session, load_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

SESSION_MEMORY: Dict[str, List[Dict[str, str]]] = {}

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiting Middleware: max 10 requests per minute per IP
RATE_LIMIT_STORE: Dict[str, List[float]] = {}

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Safely get client IP (request.client can be None in testing)
    if request.client:
        client_ip = request.client.host
    else:
        client_ip = request.headers.get("x-forwarded-for", "unknown")
    
    now = time.time()
    
    # Clean old entries (older than 60 seconds)
    if client_ip in RATE_LIMIT_STORE:
        RATE_LIMIT_STORE[client_ip] = [
            t for t in RATE_LIMIT_STORE[client_ip] if now - t < 60
        ]
    else:
        RATE_LIMIT_STORE[client_ip] = []
    
    # Check limit
    if len(RATE_LIMIT_STORE[client_ip]) >= 10:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Max 10 requests per minute."}
        )
    
    RATE_LIMIT_STORE[client_ip].append(now)
    response = await call_next(request)
    return response

@app.on_event("startup")
async def startup_validation():
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    if not settings.GROQ_API_KEY:
        logger.critical("GROQ_API_KEY missing. Offline mode active.")
    else:
        masked = f"{settings.GROQ_API_KEY[:8]}...{settings.GROQ_API_KEY[-4:]}"
        logger.info(f"GROQ_API_KEY loaded: {masked}")
        logger.info(f"Model: {settings.GROQ_MODEL_NAME}")
        logger.info("Streaming: ENABLED")
        logger.info("Business Rules: ENABLED")
        logger.info("CORS: ENABLED")
        logger.info("SQLite Sessions: ENABLED")
        logger.info("Rate Limiting: ENABLED")

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = Field(None, description="Existing session ID for memory continuity")

class ChatResponse(BaseModel):
    reply: str
    intent: str
    session_id: str
    fallback_used: bool
    response_time_ms: int
    retrieved_context: List[dict]

@app.post("/api/ai/chat", response_model=ChatResponse)
def ai_chat_endpoint(payload: ChatRequest):
    session_id = payload.session_id or f"cel-{uuid.uuid4().hex[:12]}"

    history = load_session(session_id) or SESSION_MEMORY.get(session_id, [])
    history = history[-12:]

    logger.info(f"[{session_id}] Query: '{payload.message[:60]}...'")

    response_data = generate_rag_response(
        user_query=payload.message,
        session_id=session_id,
        history=history
    )

    history.append({"role": "user", "content": payload.message})
    history.append({"role": "assistant", "content": response_data["reply"]})

    save_session(session_id, history)
    SESSION_MEMORY[session_id] = history

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

@app.post("/api/ai/chat/stream")
async def ai_chat_stream_endpoint(payload: ChatRequest):
    session_id = payload.session_id or f"cel-{uuid.uuid4().hex[:12]}"

    history = load_session(session_id) or SESSION_MEMORY.get(session_id, [])
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

        save_session(session_id, history)
        SESSION_MEMORY[session_id] = history

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

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "model": settings.GROQ_MODEL_NAME,
        "llm_ready": bool(settings.GROQ_API_KEY),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }