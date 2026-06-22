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
- **Session Memory Arrays:** In-memory `SESSION_MEMORY` keyed by `session_id` (`cel-<hex>`), retains last 6 exchanges (12 messages), injects full history into LLM message array for contextual continuity
- **Expanded Intent Classification:** `service_nails`, `service_eyes`, `service_waxing`, `service_head_spa`, `intent_booking`, `intent_pricing`, `intent_shop`
- **Production Logging:** Per-session trace logging with `[{session_id}]` identifiers

### Phase 4: Streaming, Business Rules & Performance Optimization *(22 June 2026)*
- **Streaming SSE Endpoint:** Implemented `/api/ai/chat/stream` with Server-Sent Events for real-time token delivery from Groq LLM (supervisor requirement)
- **Business Rules Engine:** Created `business_rules.py` with salon policies:
  - VIP clients: 10% discount
  - First-time clients: 15% discount
  - Cancellation: 24-hour notice policy
  - Luxury services: 20% deposit required
- **Dynamic Context Injection:** Business rules automatically injected into LLM prompt when intent is `intent_pricing` or `intent_booking`
- **Performance Monitoring:** Added response time tracking with alerts when inference exceeds 4-second target
- **Firebase Prep:** Added optional Firestore configuration fields with graceful fallback to in-memory session store
- **API Expansion:** Maintained backward compatibility with existing `/api/ai/chat` while adding streaming endpoint

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
```

**Test:** Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) → `POST /api/ai/chat` → Try it out

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/api/ai/chat` | AI concierge with session memory (JSON response) |
| `POST` | `/api/ai/chat/stream` | AI concierge with real-time SSE streaming |

### Request Body (`ChatRequest`)
```json
{
  "message": "What nail services do you offer?",
  "session_id": "cel-a1b2c3d4e5f6"
}
```

### Response Body (`ChatResponse`)
```json
{
  "reply": "Good day. At Celine Esthétique, we offer premium nail care services...",
  "intent": "service_nails",
  "session_id": "cel-a1b2c3d4e5f6",
  "fallback_used": false,
  "response_time_ms": 1234,
  "retrieved_context": [
    {
      "id": "srv_nail_care",
      "category": "Nail Care",
      "question": "What nail care treatments do you offer?",
      "answer": "Our premium nail care services include Manicure, Pedicure, Gel application..."
    }
  ]
}
```

---

## 📁 Project Structure

```
celine-ai/
├── .env                          # Secrets (not tracked)
├── requirements.txt
├── README.md
├── salon_knowledge.json          # 12 curated salon entries
│
├── app/
│   ├── main.py                   # FastAPI app + session memory + streaming
│   ├── config.py                 # Pydantic settings (absolute .env path)
│   ├── database.py               # FAISS singleton
│   ├── business_rules.py         # Salon policies (discounts, cancellation, deposits)
│   └── services/
│       ├── rag_service.py        # Luxury RAG + intent classifier + business rules
│       └── streaming_service.py  # SSE streaming generator
│
└── tests/
    └── test_rag.py
```

---

## 🔐 Environment Variables

| Variable | Required | Default | Description |
|:---|:---|:---|:---|
| `GROQ_API_KEY` | ✅ | — | Groq Cloud API key |
| `GROQ_MODEL_NAME` | ❌ | `llama-3.3-70b-versatile` | Groq model ID |
| `EMBEDDING_MODEL_NAME` | ❌ | `all-MiniLM-L6-v2` | HuggingFace embedding model |
| `FIREBASE_PROJECT_ID` | ❌ | — | Firebase project (optional) |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | ❌ | — | Service account JSON path (optional) |

---

## 📝 Notes

- **Do not commit `.env`** — it contains secrets.
- In-memory session store resets on server restart. For production, migrate to Firebase Firestore.
- FAISS index rebuilds from `salon_knowledge.json` on every boot.
- If Groq returns 400, verify model ID at [console.groq.com/docs/deprecations](https://console.groq.com/docs/deprecations).
- Streaming endpoint (`/api/ai/chat/stream`) returns `text/event-stream` for real-time frontend display.

---

## 👤 Author

**Ameema Rashid** — AI Lead & AI Developer  
TechNexus Virtual University Internship  
**Client:** Celine Esthétique, Lausanne, Switzerland

---