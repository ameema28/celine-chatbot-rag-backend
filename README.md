# Celine Esthetique — Luxury AI Concierge Backend

A production-grade FastAPI backend powering the conversational AI assistant for **Celine Esthetique** (Lausanne, Switzerland). Uses a local FAISS vector database with HuggingFace embeddings and Groq Cloud LLM for premium, context-grounded salon responses.

---

## Progress Logs

### Phase 1: Foundation & Local Vector Database *(17 June 2026)*
- Created modular FastAPI project structure with virtual environment
- Populated curated salon knowledge base with 12 entries
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
- **Streaming SSE Endpoint:** Implemented `/api/ai/chat/stream` with Server-Sent Events for real-time token delivery from Groq LLM
- **Business Rules Engine:** Created `business_rules.py` with salon policies:
  - VIP clients: 10% discount
  - First-time clients: 15% discount
  - Cancellation: 24-hour notice policy
  - Luxury services: 20% deposit required
- **Dynamic Context Injection:** Business rules automatically injected into LLM prompt when intent is `intent_pricing` or `intent_booking`
- **Performance Monitoring:** Added response time tracking with alerts when inference exceeds 4-second target
- **Firebase Prep:** Added optional Firestore configuration fields with graceful fallback to in-memory session store
- **API Expansion:** Maintained backward compatibility with existing `/api/ai/chat` while adding streaming endpoint

### Phase 5: Production Hardening & Expanded Dataset *(23 June 2026)*
- **Expanded Dataset:** Grew `salon_knowledge.json` from 12 to 50 entries covering all 30+ salon services with realistic CHF pricing, durations, and aftercare instructions
- **CORS Middleware:** Added `CORSMiddleware` to enable React.js frontend integration (Mehwish/Sibgha)
- **SQLite Session Persistence:** Replaced pure in-memory store with SQLite `sessions.db` so conversation history survives server restarts
- **Health Check Endpoint:** Added `GET /health` for deployment monitoring and uptime verification
- **Code Cleanup:** Removed all emoji characters from log messages and production code for professional presentation
- **Conversation Disambiguation:** Enhanced system prompt to instruct LLM to use conversation history for understanding vague follow-up queries

### Phase 6: Testing, Rate Limiting & Frontend Demo *(24 June 2026)*
- **pytest Automated Test Suite:** Created `tests/test_chatbot.py` with 7 comprehensive tests (health, chat, intent classification, session memory, streaming, validation) — all passing
- **Rate Limiting Middleware:** Added `app/main.py` middleware enforcing max 10 requests/minute per IP with 429 responses
- **HTML Chat Demo:** Created `demo.html` for live browser-based interaction with the AI concierge
- **French Language Validation:** Verified bilingual persona responds elegantly in French to French-language queries
- **Test Infrastructure:** Added `tests/conftest.py` and `tests/__init__.py` for proper pytest path resolution

### Phase 7: Production Deployment, Containerization & CI/CD *(25 June 2026)*
- **Docker Containerization:** Created `Dockerfile` with multi-stage build optimization, pre-baked embedding model, and `.dockerignore`
- **Docker Compose:** Added `docker-compose.yml` with health checks, volume persistence for `sessions.db`, and restart policy
- **Firebase Firestore Integration:** Built `app/firebase_session_store.py` with graceful fallback — automatically uses Firestore when `FIREBASE_PROJECT_ID` and service account are configured; falls back to SQLite otherwise
- **Unified Session Persistence Layer:** Refactored `main.py` with `_persist_session()` and `_load_session()` that prioritize Firebase > SQLite > In-memory
- **Memory Leak Prevention:** Added `_cleanup_rate_limit_store()` to prevent unbounded growth of `RATE_LIMIT_STORE` dict in long-running production instances
- **GitHub Actions CI/CD:** Created `.github/workflows/ci.yml` with Python 3.11, pip caching, pytest execution, and optional `ruff` linting
- **Enhanced OpenAPI Documentation:** Enriched FastAPI metadata with descriptions, contact info, license, and endpoint tags for auto-generated Swagger UI
- **Fixed Package Structure:** Added proper `app/__init__.py` and `app/services/__init__.py` for correct Python package resolution
- **Fixed RAG Tests:** Rewrote `tests/test_rag.py` to align with production `generate_rag_response()` API instead of legacy `RAGService` class
- **Deployment Guide:** Authored `DEPLOYMENT.md` with Docker, Firebase, CI/CD, Nginx reverse proxy, and troubleshooting sections
- **Environment Template:** Added `.env.example` for safe onboarding of new developers without exposing secrets

---

## Tech Stack

| Layer | Technology | Purpose |
|:---|:---|:---|
| Framework | FastAPI + Uvicorn | REST API server |
| Embeddings | HuggingFace `sentence-transformers` (`all-MiniLM-L6-v2`) | Local semantic encoding |
| Vector Index | FAISS (Facebook AI Similarity Search) | Offline similarity search |
| LLM | Groq Cloud SDK (`llama-3.3-70b-versatile`) | Live inference |
| Config | Pydantic Settings + python-dotenv | Robust `.env` management |
| Session Store | SQLite (`sessions.db`) + optional Firebase Firestore | Persistent conversational history |
| Business Logic | Python module (`business_rules.py`) | Salon policies engine |
| Testing | pytest + httpx | Automated API testing |
| Containerization | Docker + Docker Compose | Production deployment |
| CI/CD | GitHub Actions | Automated testing pipeline |

---

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env in project root (see .env.example)
# GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# GROQ_MODEL_NAME=llama-3.3-70b-versatile
# EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2

# 4. Run server
uvicorn app.main:app --reload
```

**Test:** Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) → `POST /api/ai/chat` → Try it out

**Demo:** Open `demo.html` in your browser for a live chat interface

---

## Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f celine-ai

# Stop
docker-compose down
```

See `DEPLOYMENT.md` for full production deployment instructions.

---

## API Endpoints

| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/health` | Server health check and status |
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
  "reply": "Good day. At Celine Esthetique, we offer premium nail care services...",
  "intent": "service_nails",
  "session_id": "cel-a1b2c3d4e5f6",
  "fallback_used": false,
  "response_time_ms": 1234,
  "retrieved_context": [
    {
      "id": "srv_nail_care",
      "category": "Nail Care",
      "question": "What nail care treatments do you offer?",
      "answer": "Our premium nail care services include Manicure (CHF 45, 45 min)..."
    }
  ]
}
```

---

## Project Structure

```
celine-ai/
├── .env                          # Secrets (not tracked)
├── .env.example                  # Template for new developers
├── .gitignore                    # Production-grade ignore rules
├── requirements.txt
├── README.md
├── demo.html                     # Browser chat demo
├── DEPLOYMENT.md                 # Production deployment guide
├── Dockerfile                    # Container image definition
├── docker-compose.yml            # Multi-service orchestration
├── sessions.db                   # SQLite session persistence (auto-created, not tracked)
│
├── .github/
│   └── workflows/
│       └── ci.yml                # GitHub Actions CI/CD pipeline
│
├── data/
│   └── salon_knowledge.json      # 50 curated salon entries with CHF pricing
│
├── app/
│   ├── __init__.py               # Package marker
│   ├── main.py                   # FastAPI app + CORS + health + streaming + rate limiting + Firebase bridge
│   ├── config.py                 # Pydantic settings (absolute .env path)
│   ├── database.py               # FAISS singleton
│   ├── business_rules.py         # Salon policies (discounts, cancellation, deposits)
│   ├── session_store.py          # SQLite session persistence
│   ├── firebase_session_store.py # Firebase Firestore session persistence (optional)
│   └── services/
│       ├── __init__.py           # Package marker
│       ├── rag_service.py        # Luxury RAG + intent + business rules
│       └── streaming_service.py  # SSE streaming generator
│
└── tests/
    ├── __init__.py
    ├── conftest.py               # pytest path configuration
    ├── test_chatbot.py           # 7 automated API tests
    └── test_rag.py               # RAG unit tests (vector search + service pipeline)
```

---

## Environment Variables

| Variable | Required | Default | Description |
|:---|:---|:---|:---|
| `GROQ_API_KEY` | Yes (for live LLM) | — | Groq Cloud API key |
| `GROQ_MODEL_NAME` | No | `llama-3.3-70b-versatile` | Groq model ID |
| `EMBEDDING_MODEL_NAME` | No | `all-MiniLM-L6-v2` | HuggingFace embedding model |
| `FIREBASE_PROJECT_ID` | No | — | Firebase project (optional) |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | No | — | Service account JSON path (optional) |
| `PROJECT_NAME` | No | `Celine Esthetique Luxury AI Backend` | App display name |
| `VERSION` | No | `1.0.0` | App version |

---

## Testing

```bash
# Run all automated tests
pytest tests/ -v
```

**Test coverage:**
- Health check endpoint
- Standard chat endpoint
- Intent classification (nails, pricing, booking, head spa)
- Session memory continuity
- Streaming SSE endpoint
- Message length validation
- Empty message rejection
- Vector database semantic search
- RAG service schema validation
- History-aware response generation

---

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/ci.yml`) automatically:
1. Installs Python 3.11 and dependencies on every push/PR
2. Caches pip packages for faster builds
3. Runs the full pytest suite
4. Runs optional linting with `ruff`

**Status badge:** Add the following to your repo README after first run:
```markdown
![CI](https://github.com/<your-username>/celine-ai/actions/workflows/ci.yml/badge.svg)
```

---

## Notes

- **Do not commit `.env`** — it contains secrets.
- **Do not commit `sessions.db`** — local SQLite database (added to `.gitignore`).
- SQLite session store persists across server restarts. For production, configure Firebase Firestore via `.env`.
- FAISS index rebuilds from `data/salon_knowledge.json` on every boot.
- If Groq returns 400, verify model ID at [console.groq.com/docs/deprecations](https://console.groq.com/docs/deprecations).
- Streaming endpoint (`/api/ai/chat/stream`) returns `text/event-stream` for real-time frontend display.
- Rate limiting: 10 requests per minute per IP address.
- Docker image pre-downloads the embedding model to eliminate cold-start latency.

---

## Author

**Ameema Rashid** — AI Lead & AI Backend Developer
TechNexus Virtual University Internship
**Client:** Celine Esthetique, Lausanne, Switzerland
