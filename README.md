# Celine Esthétique — Luxury AI Concierge Backend

A production-grade FastAPI backend powering the conversational AI assistant for **Celine Esthétique** (Lausanne, Switzerland). Uses a local FAISS vector database with HuggingFace embeddings and Groq Cloud LLM for premium, context-grounded salon responses.

---

## 📅 Progress Logs

### Phase 1: Foundation & Local Vector Database *(17 June 2026)*
- Created modular FastAPI project structure with virtual environment
- Populated curated salon knowledge base (`salon_knowledge.json`) with 12 entries
- Implemented local text embedding pipeline using HuggingFace `all-MiniLM-L6-v2`
- Built FAISS vector index for semantic similarity search

### Phase 2: RAG Pipeline Integration & Fallback Logic *(18 June 2026)*
- Connected FAISS retrieval to live API endpoint (`POST /api/ai/chat`)
- Built intent tracking engine (`service_nails`, `service_eyes`, `general_salon_info`)
- Implemented Groq Cloud SDK integration with specific exception handling
- Added defensive `try-except` fallback returning structured JSON on failure
- Fixed startup `.env` resolution to be CWD-independent using `pathlib`
- Resolved Groq model decommission bug (`llama3-70b-8192` → `llama-3.3-70b-versatile`)

### Phase 3: Luxury Persona, Session Memory & High-Fidelity RAG *(19 June 2026)*
- **Luxury Persona System Prompt:** Engineered elegant, five-star spa tone with bilingual support (English/French), strict context grounding, booking CTAs, and graceful reception handoff (+41 78 949 40 39)
- **High-Fidelity FAISS Injection:** Upgraded `top_k=2` → `top_k=3` with structured category/question/answer formatting
- **Session Memory Arrays:** In-memory `SESSION_MEMORY` keyed by `session_id` (`cel-&lt;hex&gt;`), retains last 6 exchanges (12 messages), injects full history into LLM message array for contextual continuity
- **Expanded Intent Classification:** `service_nails`, `service_eyes`, `service_waxing`, `service_head_spa`, `intent_booking`, `intent_pricing`, `intent_shop`
- **Production Logging:** Per-session trace logging with `[{session_id}]` identifiers

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|:---|:---|:---|
| Framework | FastAPI + Uvicorn | REST API server |
| Embeddings | HuggingFace `sentence-transformers` (`all-MiniLM-L6-v2`) | Local semantic encoding |
| Vector Index | FAISS (Facebook AI Similarity Search) | Offline similarity search |
| LLM | Groq Cloud SDK (`llama-3.3-70b-versatile`) | Live inference |
| Config | Pydantic Settings + python-dotenv | Robust `.env` management |
| Session Store | In-memory Python `dict` | Conversational history |

---

## 🚀 Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env in project root
# GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# GROQ_MODEL_NAME=llama-3.3-70b-versatile
# EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2

# 4. Run server
uvicorn app.main:app --reload

Test: Open http://127.0.0.1:8000/docs → POST /api/ai/chat → Try it out

API Endpoints
Table
Method	Endpoint	Description
POST	/api/ai/chat	AI concierge with session memory

Request:
JSON
{
  "message": "What nail services do you offer?",
  "session_id": "cel-a1b2c3d4e5f6"
}

Response:
JSON
{
  "reply": "Good day. At Celine Esthétique, we offer premium nail care services...",
  "intent": "service_nails",
  "session_id": "cel-a1b2c3d4e5f6",
  "fallback_used": false,
  "retrieved_context": [...]
}

Project Structure

celine-ai/
├── .env                          # Secrets (not tracked)
├── requirements.txt
├── README.md
├── salon_knowledge.json          # 12 curated salon entries
│
├── app/
│   ├── main.py                   # FastAPI app + session memory
│   ├── config.py                 # Pydantic settings (absolute .env path)
│   ├── database.py               # FAISS singleton
│   └── services/
│       └── rag_service.py        # Luxury RAG + intent classifier
│
└── tests/
    └── test_rag.py

Notes
Do not commit .env — it contains secrets.
In-memory session store resets on server restart. For production, migrate to Redis.
FAISS index rebuilds from salon_knowledge.json on every boot.
If Groq returns 400, verify model ID at console.groq.com/docs/deprecations.

Author: Ameema Rashid
AI Backend Engineer — TechNexus Virtual University Internship
Client: Celine Esthétique, Lausanne, Switzerland