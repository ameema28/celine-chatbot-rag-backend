# Celine Esthetique AI Backend — Deployment Guide

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

The API serves the demo itself at `GET /` (for example http://127.0.0.1:8000/). Served this way the page calls the API on its own origin, so CORS is not involved. Its Content-Security-Policy (`connect-src 'self'`) also means the `?api=` override only works on a copy of `demo.html` served from elsewhere, as below.

To open `demo.html` from another server instead: CORS only allows the origins in `CORS_ALLOW_ORIGINS` (default: localhost ports 3000, 5173 and 5500). A page opened directly from disk (`file://`) sends `Origin: null` and is blocked, so serve the demo:

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

The image installs CPU-only torch, bakes in the embedding model (no download at start-up), runs as a non-root user (uid 1000) and listens on `$PORT` (default 7860). Sessions go to `/tmp/sessions.db` by default.

```bash
# Run the image directly (offline fallback mode without a key)
docker run -p 8000:7860 celine-ai-backend:latest
```

### 2.2 Run with Docker Compose

```bash
# .env is optional: without it the API runs in offline fallback mode
docker compose up -d
```

The API and the demo page will be available at `http://localhost:8000`. Compose sets `PORT=8000` and keeps sessions in the named volume `celine-sessions` (`/home/user/data/sessions.db`), so they survive container restarts.

### 2.3 View Logs

```bash
docker compose logs -f celine-ai
```

### 2.4 Stop

```bash
docker compose down
```

---

## 3. Session Storage

Sessions are stored in **SQLite** (`sessions.db`), with an in-memory copy as a fallback if SQLite fails. There is no other session store. The in-memory copy drops sessions unused for `SESSION_TTL_MINUTES` (default 60) and keeps at most `SESSION_MEMORY_MAX_SESSIONS` (default 1000); SQLite is not affected.

---

## 3a. Google Cloud Run (public demo)

The same image runs on Cloud Run unchanged. Cloud Run sets `PORT=8080` and the container listens on it. Visitors open the service URL and get the demo page at `/`, which calls the API on the same origin.

### Service settings

| Setting | Value | Why |
|:---|:---|:---|
| Maximum instances | **1** | The rate limiter, the in-memory session copy and the SQLite file all live in one process. More instances would mean separate limits and separate sessions. |
| Minimum instances | **0** | Scale to zero when idle. The first request after an idle period waits for a cold start (see below). |
| Container port | 8080 (Cloud Run default) | The app reads `$PORT`. Do not set `PORT` yourself. |
| Memory | 1 GiB (recommended) | Measured locally: 400.7 MiB after one chat (`docker stats`). Cloud Run's `/tmp` is in memory and counts against this limit. Not yet measured on Cloud Run. |
| CPU | 1 | Single uvicorn worker. |
| Authentication | Allow unauthenticated invocations | Visitors must be able to open the page. The API has no auth of its own. |
| Request timeout | Default | Enough for `/api/ai/chat` and `/api/ai/chat/stream`. |

### Environment variables and secrets

| Name | Set as | Value |
|:---|:---|:---|
| `GROQ_API_KEY` | **Secret Manager** secret, exposed to the service as an environment variable | Your Groq key. The service's runtime service account needs the Secret Manager Secret Accessor role on that secret. Never put the key in a plain env var or in the image. |
| `TRUST_PROXY` | Env var | `true` |
| `TRUST_PROXY_HOPS` | Env var (optional) | `1` (default): the client IP is the right-most `X-Forwarded-For` entry, which Google's front end appends. Entries to its left are client-supplied and ignored. Use `2` if an external HTTPS load balancer sits in front of the service. |
| `CORS_ALLOW_ORIGINS` | Env var | The service URL, e.g. `https://<service>-<hash>.<region>.run.app` (or your custom domain). The demo at `/` is same-origin, so this only matters for other browser callers. |
| `SESSIONS_DB_PATH` | Env var (optional) | `/tmp/sessions.db` (already the image default) |
| `GROQ_MODEL_NAME` | Env var (optional) | Default `openai/gpt-oss-20b`. Change it if Groq stops serving that model (a new revision picks it up). |
| `RAG_MAX_L2_DISTANCE` | Not set | Default `1.20` |

### Health, cold start and what resets

- **`GET /health`** needs no auth and is not rate limited. `llm_ready` only means a usable-looking key is set (not missing, not a `your_...` placeholder, at least 20 characters), not that Groq accepted it. Use `fallback_used` in a `/api/ai/chat` reply to confirm the live model. Uvicorn opens the port only after the app (and the embedding model) has loaded, so the default TCP startup probe already waits for a ready app; `/health` can also be used as an HTTP startup probe.
- **Cold start:** measured locally at 10.9 s from `docker run` to the first `/health` 200 (this PC, image already on disk). On Cloud Run a cold start also includes starting the instance and loading the image; it is **not measured yet**.
- **Scale to zero:** with minimum instances 0, an idle service is shut down, and the next visitor waits for a cold start.
- **Sessions reset:** sessions are SQLite in `/tmp`, which is in memory and belongs to one instance. They are **lost on every restart, new revision or scale to zero**. A visitor's old `session_id` then simply has no history.
- **Rate limit:** 10 requests per minute per client IP, in memory, for one instance. `/`, `/health`, `/docs`, `/redoc`, `/openapi.json` and CORS preflights are not counted.
- **No auth:** anyone with the URL can chat. Anyone who has a `session_id` can continue that session.

### Post-deploy smoke check

`scripts/smoke_check.py` (Python stdlib only, no API key) checks a deployed URL. It writes a JSON summary to `--out`, which must be outside the repository.

```bash
python scripts/smoke_check.py --url https://<service-url> --out ../_facts/celine_smoke.json
```

What it checks:
- `/health` and the demo page at `/`.
- One English and one French `/api/ai/chat`, both expecting `fallback_used=false`. The French reply is printed for you to read; its language is not checked automatically.
- One `/api/ai/chat/stream`.
- A price-guard question ("CHF 30" for a manicure; the knowledge base says CHF 45).
- The rate limit, sending empty messages that cost no LLM call.
- Whether spoofed `X-Forwarded-For` entries get around the rate limit.

It makes about 4 live LLM calls per run and takes about 2.5 minutes (two waits of 61 s for fresh rate-limit windows). `--skip-rate-limit` skips the last two checks.

### Latency benchmark

`scripts/benchmark.py` (stdlib only, no API key) sends one warm-up request, which is excluded from the stats, then N sequential `/api/ai/chat` requests, each in a new session. It prints p50, p95 and max (nearest-rank), plus the fallback, 429 and error counts.

```bash
python scripts/benchmark.py --url https://<service-url> -n 20 --out ../_facts/celine_benchmark.json
```

- **Pacing:** requests are spaced 6.5 s apart, so one client stays under 10 requests/minute (about 2.5 minutes for N=20). Wait 60 s after the smoke check before starting.
- **Two timings:** client times include your network; `response_time_ms` from the server is LLM time only.
- **Exit status:** the script exits non-zero unless every measured request returned 200.

### Retrieval evaluation (no LLM)

`scripts/eval_retrieval.py` runs every question in `data/eval/retrieval_eval.jsonl` through the app's own retrieval path. It calls `build_turn()`, which applies the French glossary, FAISS search, the 1.20 cutoff and the top-3 limit, and makes no LLM call.

It reports:
- hit@1, hit@3 and MRR@3, overall and split by English/French and normal/hard;
- the off-topic rejection rate (questions that get no context at all);
- the misses.

Results go to `--out`, which must be outside the repository. `tests/test_retrieval_eval.py` fails if any metric drops below the measured floors (first set on 2026-11-07, raised to the 2026-11-08 values; they are only ever raised).

```bash
python scripts/eval_retrieval.py --out ../_facts/celine_retrieval_eval.json
```

The questions are written by the project author (paraphrases, typos, follow-ups, off-topic questions), not taken from real visitors, so the scores describe this set only.

### Checking the client IP the rate limiter sees

Not yet verified on Cloud Run: whether the right-most `X-Forwarded-For` entry is the visitor's IP or a Google address. After `scripts/smoke_check.py` triggers a 429, the service log has a line `Rate limit exceeded for IP: <ip>`. Compare `<ip>` with your own public IP:
- If it matches, the setting is correct.
- If it is a Google address, all visitors share one limit. The setting is still not spoofable, but set `TRUST_PROXY_HOPS=2`.

---

## 4. GitHub Actions CI/CD

A workflow is provided in `.github/workflows/ci.yml`.

**What it does:**
- Triggers on push and pull request to `main` or `master`
- Installs Python 3.11, `requirements.txt` and `requirements-dev.txt` (pip cached)
- Runs `ruff check app/ tests/ scripts/` (blocking)
- Runs the full pytest suite with a coverage gate (`--cov-fail-under=94`)
- Needs **no API key**: the tests mock Groq, so CI makes no paid LLM calls

**Run the same checks locally:**

```bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check app/ tests/ scripts/
pytest tests/ -p no:cacheprovider --cov=app --cov-report=term-missing --cov-fail-under=94
```

---

## 5. Environment Variables Reference

| Variable | Required | Default | Purpose |
|:---|:---|:---|:---|
| `GROQ_API_KEY` | Yes (for live LLM) | — | Groq Cloud API key |
| `GROQ_MODEL_NAME` | No | `openai/gpt-oss-20b` | Groq model ID |
| `EMBEDDING_MODEL_NAME` | No | `all-MiniLM-L6-v2` | HuggingFace embedding model |
| `CORS_ALLOW_ORIGINS` | No | localhost:3000, :5173, :5500, 127.0.0.1:5500 | Comma-separated browser origins allowed to call the API |
| `RAG_MAX_L2_DISTANCE` | No | `1.20` | FAISS relevance cutoff (squared L2; lower is stricter) |
| `SESSIONS_DB_PATH` | No | `./sessions.db` (Docker image: `/tmp/sessions.db`) | SQLite session file |
| `SESSION_TTL_MINUTES` | No | `60` | In-memory session copy: drop sessions unused for this many minutes |
| `SESSION_MEMORY_MAX_SESSIONS` | No | `1000` | In-memory session copy: maximum sessions kept (least recently used dropped first) |
| `TRUST_PROXY` | No | `false` | Take the client IP for rate limiting from `X-Forwarded-For` (only behind a proxy that appends it) |
| `TRUST_PROXY_HOPS` | No | `1` | With `TRUST_PROXY=true`: use the entry this many places from the right (1 = right-most); entries further left are ignored |
| `PORT` | No | `7860` (Docker image) | Port the container listens on; Cloud Run sets it to 8080 |
| `PROJECT_NAME` | No | `Celine Esthetique Luxury AI Backend` | App display name |
| `VERSION` | No | `1.0.0` | App version |

---

## 6. Production Checklist

For the Cloud Run demo (section 3a):

| # | Item | Status |
|:---|:---|:---|
| 1 | GitHub Actions pipeline is green on the deployed commit | [ ] |
| 2 | `GROQ_API_KEY` stored in Secret Manager and exposed to the service; no key in env vars or the image | [ ] |
| 3 | Service settings as in 3a: max instances 1, `TRUST_PROXY=true`, `CORS_ALLOW_ORIGINS` set to the service URL | [ ] |
| 4 | `GET /health` returns 200 with `llm_ready: true` | [ ] |
| 5 | `scripts/smoke_check.py` passes (live English and French chat, stream, price guard, rate limit) | [ ] |
| 6 | Rate-limit IP checked in the logs ("Checking the client IP the rate limiter sees") | [ ] |
| 7 | Demo page checked on desktop and a phone | [ ] |

For a local or Compose run: `.env` is optional (offline fallback without a key), `docker compose up -d`, then the same `/health` and chat checks.

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
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

With `TRUST_PROXY=true` the app uses the right-most `X-Forwarded-For` entry, which is the one nginx appends (`$proxy_add_x_forwarded_for`). This nginx snippet has not been tested here.

---

## 8. Troubleshooting

| Issue | Solution |
|:---|:---|
| `sessions.db` locked | Stop the container, delete `sessions.db`, restart |
| FAISS index not found | Ensure `data/salon_knowledge.json` exists and is valid JSON |
| Groq 400 error | Check model ID at console.groq.com/docs/deprecations |
| Slow first response | The Docker image already bakes in the embedding model; the first request after scale-to-zero waits for a cold start |
| `fallback_used: true` on a deployed service | Check the logs for `GROQ_API_KEY loaded: no`, `AUTH ERROR` or `API ERROR (404)` (model no longer served; change `GROQ_MODEL_NAME`) |

---

**Author:** Ameema Rashid — AI Lead & Backend Developer  
**Client:** Celine Esthetique, Lausanne, Switzerland  
**Internship:** TechNexus Virtual University
