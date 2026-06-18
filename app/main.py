from fastapi import FastAPI
from pydantic import BaseModel
from app.config import settings
from app.services.rag_service import generate_rag_response

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION
)

class ChatRequest(BaseModel):
    message: str

@app.post("/api/ai/chat")
def ai_chat_endpoint(payload: ChatRequest):
    # Call our live RAG logic engine directly without security constraints
    response_data = generate_rag_response(payload.message)
    return response_data