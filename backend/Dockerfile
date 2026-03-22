# syntax=docker/dockerfile:1.4
# Backend Dockerfile
FROM python:3.11-slim

# SECURITY: Create non-root user for running the application
RUN groupadd -r appuser && useradd -r -g appuser -u 1001 appuser

# Set working directory
WORKDIR /app

# Install system dependencies (as root)
# NOTE: default-jdk, golang-go, nodejs, typescript are only needed for code execution
# (ENABLE_CODE_EXECUTION=true). Excluded here to keep the image under 1GB.
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy only backend dependency manifest
COPY backend/requirements.txt ./requirements.txt

# Install Python dependencies (as root).
# Use PyTorch CPU index as primary so torch resolves to CPU wheels instead of CUDA builds.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --use-deprecated=legacy-resolver \
      --index-url https://download.pytorch.org/whl/cpu \
      --extra-index-url https://pypi.org/simple \
      -r requirements.txt

# Download RAG dependencies (as root) - use BuildKit cache mount for nltk data
RUN --mount=type=cache,target=/usr/local/share/nltk_data \
    python -c "import nltk; nltk.download('punkt', download_dir='/usr/local/share/nltk_data'); nltk.download('punkt_tab', download_dir='/usr/local/share/nltk_data')"

# Set HuggingFace / model cache to a writable directory inside /app
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/huggingface
ENV HOME=/app

# Copy only backend application code with proper ownership
COPY --chown=appuser:appuser backend/ ./backend/
# Some modules are imported from repository root (e.g., `from utils import ...`)
COPY --chown=appuser:appuser utils.py ./utils.py
# Bundle the production evaluation dataset used by the scheduled RAG workflow.
COPY --chown=appuser:appuser Evaluation_files/evaluation_data.jsonl ./Evaluation_files/evaluation_data.jsonl
COPY --chown=appuser:appuser Evaluation_files/evaluation_1_data.jsonl ./Evaluation_files/evaluation_1_data.jsonl

# Create necessary directories with proper ownership
RUN mkdir -p Evaluation_files logs user_data previous_chats quiz_results persisted_index chroma_db keys data .cache .cache/huggingface && \
    chown -R appuser:appuser /app

# SECURITY: Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check (runs as appuser)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# Run the application as non-root user
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
