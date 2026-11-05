# Celine Esthetique AI Backend — Deployment Guide

## Phase 7: Production Deployment, Containerization & CI/CD

---

## 1. Local Development (Existing)

```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate       # macOS/Linux

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for interactive Swagger UI.

### Demo page

CORS only allows the origins in `CORS_ALLOW_ORIGINS` (default: localhost ports 3000, 5173 and 5500). A page opened directly from disk (`file://`) sends `Origin: null` and is blocked, so serve the demo:

```bash
python -m http.server 5500
# then open http://localhost:5500/demo.html
# another API host: http://localhost:5500/demo.html?api=https://your-api-host
```

---

## 2. Docker Deployment (Recommended for Production)

### 2.1 Build the Image

```bash
docker build -t celine-ai-backend:latest .
```

### 2.2 Run with Docker Compose

```bash
# Ensure .env is present in project root
docker-compose up -d
```

The API will be available at `http://localhost:8000`.

### 2.3 View Logs

```bash
docker-compose logs -f celine-ai
```

### 2.4 Stop

```bash
docker-compose down
```

---

## 3. Session Storage

Sessions are stored in **SQLite** (`sessions.db`), with an in-memory copy as a fallback if SQLite fails. There is no other session store.

---

## 4. GitHub Actions CI/CD

A workflow is provided in `.github/workflows/ci.yml`.

**What it does:**
- Triggers on every push / PR to `main` or `master`
- Installs Python 3.11 and caches pip dependencies
- Runs the full pytest suite (`tests/test_chatbot.py` + `tests/test_rag.py`)
- Runs optional linting with `ruff`

**Setup:**
1. Push the `.github/workflows/ci.yml` file to your repository.
2. Go to **GitHub Repo > Actions** to view pipeline runs.
3. (Optional) Add repository secrets if you need encrypted env vars during CI.

---

## 5. Environment Variables Reference

| Variable | Required | Default | Purpose |
|:---|:---|:---|:---|
| `GROQ_API_KEY` | Yes (for live LLM) | — | Groq Cloud API key |
| `GROQ_MODEL_NAME` | No | `openai/gpt-oss-20b` | Groq model ID |
| `EMBEDDING_MODEL_NAME` | No | `all-MiniLM-L6-v2` | HuggingFace embedding model |
| `CORS_ALLOW_ORIGINS` | No | localhost:3000, :5173, :5500, 127.0.0.1:5500 | Comma-separated browser origins allowed to call the API |
| `RAG_MAX_L2_DISTANCE` | No | `1.20` | FAISS relevance cutoff (squared L2; lower is stricter) |
| `SESSIONS_DB_PATH` | No | `./sessions.db` | SQLite session file |
| `TRUST_PROXY` | No | `false` | Use the first `X-Forwarded-For` entry as client IP for rate limiting (only behind a trusted proxy) |
| `PROJECT_NAME` | No | `Celine Esthetique Luxury AI Backend` | App display name |
| `VERSION` | No | `1.0.0` | App version |

---

## 6. Production Checklist

| # | Item | Status |
|:---|:---|:---|
| 1 | `.env` created and secrets filled | [ ] |
| 2 | `docker-compose up` runs without errors | [ ] |
| 3 | Health check `GET /health` returns 200 | [ ] |
| 4 | `POST /api/ai/chat` returns valid JSON | [ ] |
| 5 | `POST /api/ai/chat/stream` returns SSE stream | [ ] |
| 6 | pytest suite passes (`pytest tests/ -v`) | [ ] |
| 7 | Rate limiting tested (11th request returns 429) | [ ] |
| 8 | CORS enabled for frontend origin | [ ] |
| 9 | GitHub Actions pipeline is green | [ ] |

---

## 7. Reverse Proxy (Nginx) — Advanced

For production behind a domain:

```nginx
server {
    listen 80;
    server_name api.celine-esthetique.ch;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 8. Troubleshooting

| Issue | Solution |
|:---|:---|
| `sessions.db` locked | Stop the container, delete `sessions.db`, restart |
| FAISS index not found | Ensure `data/salon_knowledge.json` exists and is valid JSON |
| Groq 400 error | Check model ID at console.groq.com/docs/deprecations |
| Slow first response | The embedding model downloads on first boot; pre-bake it in Dockerfile |

---

**Author:** Ameema Rashid — AI Lead & Backend Developer  
**Client:** Celine Esthetique, Lausanne, Switzerland  
**Internship:** TechNexus Virtual University
