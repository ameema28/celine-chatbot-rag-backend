FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

WORKDIR /app

# Runtime dependencies only (requirements-dev.txt is never installed).
# CPU-only torch first, from the PyTorch CPU index only (no extra index for the
# other packages), in its own layer so rebuilds reuse it. The torch==2.3.1 pin
# in requirements.txt is then already satisfied by 2.3.1+cpu, so pip keeps it.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.3.1
COPY requirements.txt .
RUN pip install -r requirements.txt

# Non-root user with uid 1000 (Hugging Face Spaces runs containers as uid 1000).
# /home/user/data is a writable mount point for the docker-compose sessions volume.
RUN useradd --create-home --uid 1000 user \
 && mkdir -p /home/user/data \
 && chown user:user /home/user/data
USER user

# Writable model cache and SQLite path. /tmp is reset on every restart.
ENV HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface \
    SESSIONS_DB_PATH=/tmp/sessions.db \
    PORT=7860

# Bake the embedding model into the image (no runtime download).
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# The model is baked in, so no Hugging Face Hub calls at start-up.
# Changing EMBEDDING_MODEL_NAME at runtime therefore fails instead of downloading.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

# Application code stays owned by root: read-only for the runtime user.
COPY --chown=root:root . .

EXPOSE 7860

# Single worker: the rate limiter and in-memory session copy are per process.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
