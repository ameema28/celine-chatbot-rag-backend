import logging
import uuid
from typing import List, Dict, Optional
from fastapi import FastAPI
from pydantic import BaseModel, Field
from app.config import settings
from app.services.rag_service import generate_rag_response

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

SESSION_MEMORY = {}

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

@app.on_event("startup")
async def startup_validation():
    logger.info("Starting " + settings.PROJECT_NAME + " v" + settings.VERSION)
    if not settings.GROQ_API_KEY:
        logger.critical("GROQ_API_KEY missing. Offline mode active.")
    else:
        logger.info("GROQ_API_KEY loaded")
        logger.info("Model: " + settings.GROQ_MODEL_NAME)

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = Field(None, description="Existing session ID")

class ChatResponse(BaseModel):
    reply: str
    intent: str
    session_id: str
    fallback_used: bool
    retrieved_context: List[dict]

@app.post("/api/ai/chat", response_model=ChatResponse)
def ai_chat_endpoint(payload: ChatRequest):
    session_id = payload.session_id or "cel-" + uuid.uuid4().hex[:12]
    history = SESSION_MEMORY.get(session_id, [])[-12:]

    logger.info("Query: " + payload.message[:60])

    response_data = generate_rag_response(
        user_query=payload.message,
        session_id=session_id,
        history=history
    )

    history.append({"role": "user", "content": payload.message})
    history.append({"role": "assistant", "content": response_data["reply"]})
    SESSION_MEMORY[session_id] = history

    if response_data.get("fallback_used"):
        logger.warning("OFFLINE FALLBACK")
    else:
        logger.info("Live LLM response")

    return ChatResponse(
        reply=response_data["reply"],
        intent=response_data["intent"],
        session_id=session_id,
        fallback_used=response_data["fallback_used"],
        retrieved_context=response_data["retrieved_context"]
    )