# syntax=docker/dockerfile:1.4
# Backend Dockerfile
FROM python:3.11-slim

# SECURITY: Create non-root user for running the application
RUN groupadd -r appuser && useradd -r -g appuser -u 1001 appuser

# Set working directory
WORKDIR /app

# Install system dependencies (as root)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    nodejs \
    default-jdk \
    golang-go \
    && rm -rf /var/lib/apt/lists/*

# Install TypeScript globally (as root)
RUN npm install -g typescript 2>/dev/null || true

# Copy requirements
COPY requirements.txt .

# Install Python dependencies (as root) - use BuildKit cache mount for pip cache
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --use-deprecated=legacy-resolver -r requirements.txt

# Download RAG dependencies (as root) - use BuildKit cache mount for nltk data
RUN --mount=type=cache,target=/usr/local/share/nltk_data \
    python -c "import nltk; nltk.download('punkt', download_dir='/usr/local/share/nltk_data'); nltk.download('punkt_tab', download_dir='/usr/local/share/nltk_data')"

# Copy application code with proper ownership
COPY --chown=appuser:appuser . .

# Create necessary directories with proper ownership
RUN mkdir -p logs user_data previous_chats quiz_results persisted_index chroma_db keys .cache && \
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
