# app/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.config import settings
from app.services.rag_service import RAGService

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION
)

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    intent: str
    retrieved_context: list

@app.get("/")
def read_root():
    return {"status": "online", "system": settings.PROJECT_NAME, "version": settings.VERSION}

@app.post("/api/ai/chat", response_model=ChatResponse)
async def ai_chat_endpoint(payload: ChatRequest):
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message string cannot be empty.")
    
    try:
        result = RAGService.process_query(payload.message)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal AI Pipeline Error: {str(e)}")