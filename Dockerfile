FROM python:3.11-slim

WORKDIR /app

# No compiler toolchain needed: every dependency installs from a manylinux wheel.
# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download embedding model so it is baked into the image (no runtime download)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy application code
COPY . .

# Ensure data directory exists
RUN mkdir -p data

EXPOSE 8000

# Run with a single worker; increase --workers in production behind a reverse proxy
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
