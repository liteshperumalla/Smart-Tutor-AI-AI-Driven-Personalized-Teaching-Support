"""
Prometheus metrics instrumentation for Smart AI Tutor backend.

Provides:
- HTTP request metrics (count, duration, status codes)
- RAG-specific metrics (query latency, cache hits, retrieval quality, cost tracking)
- Database connection pool metrics
- Redis cache metrics
- Custom application metrics
"""

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
)
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)

# Create a custom registry to avoid conflicts
REGISTRY = CollectorRegistry(auto_describe=True)

# ============================================================================
# HTTP Request Metrics
# ============================================================================

# Total HTTP requests by method, endpoint, and status
http_requests_total = Counter(
    name="http_requests_total",
    documentation="Total HTTP requests",
    labelnames=["method", "endpoint", "status"],
    registry=REGISTRY,
)

# HTTP request duration histogram
http_request_duration_seconds = Histogram(
    name="http_request_duration_seconds",
    documentation="HTTP request latency in seconds",
    labelnames=["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

# Active HTTP requests gauge
http_requests_in_progress = Gauge(
    name="http_requests_in_progress",
    documentation="Number of HTTP requests currently being processed",
    labelnames=["method", "endpoint"],
    registry=REGISTRY,
)

# HTTP response size
http_response_size_bytes = Summary(
    name="http_response_size_bytes",
    documentation="HTTP response size in bytes",
    labelnames=["method", "endpoint"],
    registry=REGISTRY,
)

# ============================================================================
# RAG Application Metrics
# ============================================================================

# RAG query total count
rag_query_total = Counter(
    name="rag_query_total",
    documentation="Total number of RAG queries processed",
    labelnames=["query_type", "status"],  # query_type: chat, research, quiz; status: success, error
    registry=REGISTRY,
)

# RAG query duration
rag_query_duration_seconds = Histogram(
    name="rag_query_duration_seconds",
    documentation="RAG query latency in seconds",
    labelnames=["query_type"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 30.0),
    registry=REGISTRY,
)

# RAG retrieval metrics
rag_retrieval_recall_at_3 = Gauge(
    name="rag_retrieval_recall_at_3",
    documentation="RAG retrieval recall@3 metric (0-1)",
    registry=REGISTRY,
)

rag_retrieval_precision_at_3 = Gauge(
    name="rag_retrieval_precision_at_3",
    documentation="RAG retrieval precision@3 metric (0-1)",
    registry=REGISTRY,
)

# RAG cache metrics
rag_cache_hits_total = Counter(
    name="rag_cache_hits_total",
    documentation="Total number of RAG cache hits",
    labelnames=["cache_type"],  # cache_type: embedding, query_result
    registry=REGISTRY,
)

rag_cache_misses_total = Counter(
    name="rag_cache_misses_total",
    documentation="Total number of RAG cache misses",
    labelnames=["cache_type"],
    registry=REGISTRY,
)

# RAG embedding metrics
rag_embedding_requests_total = Counter(
    name="rag_embedding_requests_total",
    documentation="Total embedding generation requests",
    labelnames=["model", "status"],  # model: bedrock-titan, huggingface-*; status: success, error
    registry=REGISTRY,
)

rag_embedding_duration_seconds = Histogram(
    name="rag_embedding_duration_seconds",
    documentation="Embedding generation duration in seconds",
    labelnames=["model"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
    registry=REGISTRY,
)

rag_embedding_errors_total = Counter(
    name="rag_embedding_errors_total",
    documentation="Total embedding generation errors",
    labelnames=["model", "error_type"],
    registry=REGISTRY,
)

# RAG cost tracking
rag_total_cost_dollars = Counter(
    name="rag_total_cost_dollars",
    documentation="Total RAG operational cost in USD",
    labelnames=["service"],  # service: bedrock_embedding, bedrock_llm, langfuse
    registry=REGISTRY,
)

rag_tokens_processed_total = Counter(
    name="rag_tokens_processed_total",
    documentation="Total tokens processed",
    labelnames=["service", "token_type"],  # token_type: input, output
    registry=REGISTRY,
)

# ============================================================================
# Database Metrics
# ============================================================================

# Database connection pool
db_connection_pool_size = Gauge(
    name="db_connection_pool_size",
    documentation="Current database connection pool size",
    labelnames=["pool"],  # pool: postgres, dynamodb
    registry=REGISTRY,
)

db_connection_pool_active = Gauge(
    name="db_connection_pool_active",
    documentation="Active database connections",
    labelnames=["pool"],
    registry=REGISTRY,
)

db_connection_pool_idle = Gauge(
    name="db_connection_pool_idle",
    documentation="Idle database connections",
    labelnames=["pool"],
    registry=REGISTRY,
)

# Database query metrics
db_query_duration_seconds = Histogram(
    name="db_query_duration_seconds",
    documentation="Database query duration in seconds",
    labelnames=["database", "operation"],  # operation: select, insert, update, delete
    buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0),
    registry=REGISTRY,
)

db_query_errors_total = Counter(
    name="db_query_errors_total",
    documentation="Total database query errors",
    labelnames=["database", "error_type"],
    registry=REGISTRY,
)

# ============================================================================
# Redis Cache Metrics
# ============================================================================

redis_cache_operations_total = Counter(
    name="redis_cache_operations_total",
    documentation="Total Redis cache operations",
    labelnames=["operation", "status"],  # operation: get, set, delete; status: success, error
    registry=REGISTRY,
)

redis_cache_operation_duration_seconds = Histogram(
    name="redis_cache_operation_duration_seconds",
    documentation="Redis operation duration in seconds",
    labelnames=["operation"],
    buckets=(0.0001, 0.001, 0.01, 0.05, 0.1, 0.5, 1.0),
    registry=REGISTRY,
)

# ============================================================================
# LLM Call Metrics (LLMOps)
# ============================================================================

# Total LLM generation requests by model and status
llm_requests_total = Counter(
    name="llm_requests_total",
    documentation="Total LLM generation requests",
    labelnames=["model", "status"],   # status: success, error
    registry=REGISTRY,
)

# LLM end-to-end generation latency (wall-clock: prompt submit → stream complete)
llm_latency_seconds = Histogram(
    name="llm_latency_seconds",
    documentation="LLM generation latency in seconds (prompt-submit to stream-complete)",
    labelnames=["model"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0),
    registry=REGISTRY,
)

# Token counters (output approximated from char count; input tracked separately if available)
llm_tokens_total = Counter(
    name="llm_tokens_total",
    documentation="Approximate tokens generated by LLM calls",
    labelnames=["model", "token_type"],   # token_type: output
    registry=REGISTRY,
)

# User satisfaction votes from message feedback (thumbs up / thumbs down)
llm_satisfaction_total = Counter(
    name="llm_satisfaction_total",
    documentation="User satisfaction votes on LLM responses",
    labelnames=["vote"],   # vote: thumbs_up, thumbs_down
    registry=REGISTRY,
)

# ============================================================================
# Application Info
# ============================================================================

app_info = Info(
    name="smart_ai_tutor_app",
    documentation="Smart AI Tutor application information",
    registry=REGISTRY,
)

# Set application info (call this on startup)
def set_app_info(version: str, environment: str):
    """Set application metadata for Prometheus."""
    app_info.info({
        "version": version,
        "environment": environment,
        "application": "smart-ai-tutor",
        "component": "backend-api",
    })


# ============================================================================
# Prometheus Metrics Middleware
# ============================================================================

class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware to automatically instrument HTTP requests with Prometheus metrics.

    Tracks:
    - Request count by method, endpoint, and status code
    - Request duration by method and endpoint
    - Active requests gauge
    - Response size
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        logger.info("Prometheus metrics middleware initialized")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract endpoint from request
        endpoint = request.url.path
        method = request.method

        # Skip metrics endpoint itself to avoid recursion
        if endpoint == "/metrics":
            return await call_next(request)

        # Increment in-progress requests
        http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()

        # Track request start time
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)

            # Track request duration
            duration = time.time() - start_time
            http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

            # Track total requests by status code
            status_code = response.status_code
            http_requests_total.labels(method=method, endpoint=endpoint, status=status_code).inc()

            # Track response size if available
            if hasattr(response, "body") and response.body:
                response_size = len(response.body)
                http_response_size_bytes.labels(method=method, endpoint=endpoint).observe(response_size)

            return response

        except Exception as e:
            # Track request duration even on error
            duration = time.time() - start_time
            http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

            # Track error with 500 status
            http_requests_total.labels(method=method, endpoint=endpoint, status=500).inc()

            logger.error(f"Error processing request {method} {endpoint}: {e}")
            raise

        finally:
            # Decrement in-progress requests
            http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()


# ============================================================================
# Helper Functions for Custom Metrics
# ============================================================================

def track_rag_query(query_type: str, duration: float, status: str = "success"):
    """Track a RAG query execution."""
    rag_query_total.labels(query_type=query_type, status=status).inc()
    rag_query_duration_seconds.labels(query_type=query_type).observe(duration)


def track_cache_hit(cache_type: str = "query_result"):
    """Track a cache hit."""
    rag_cache_hits_total.labels(cache_type=cache_type).inc()


def track_cache_miss(cache_type: str = "query_result"):
    """Track a cache miss."""
    rag_cache_misses_total.labels(cache_type=cache_type).inc()


def track_embedding_request(model: str, duration: float, status: str = "success"):
    """Track an embedding generation request."""
    rag_embedding_requests_total.labels(model=model, status=status).inc()
    rag_embedding_duration_seconds.labels(model=model).observe(duration)


def track_embedding_error(model: str, error_type: str):
    """Track an embedding generation error."""
    rag_embedding_errors_total.labels(model=model, error_type=error_type).inc()


def track_rag_cost(service: str, cost_dollars: float):
    """Track RAG operational cost."""
    rag_total_cost_dollars.labels(service=service).inc(cost_dollars)


def track_tokens(service: str, input_tokens: int = 0, output_tokens: int = 0):
    """Track token usage."""
    if input_tokens > 0:
        rag_tokens_processed_total.labels(service=service, token_type="input").inc(input_tokens)
    if output_tokens > 0:
        rag_tokens_processed_total.labels(service=service, token_type="output").inc(output_tokens)


def track_db_query(database: str, operation: str, duration: float):
    """Track a database query execution."""
    db_query_duration_seconds.labels(database=database, operation=operation).observe(duration)


def track_db_error(database: str, error_type: str):
    """Track a database error."""
    db_query_errors_total.labels(database=database, error_type=error_type).inc()


def update_db_pool_metrics(pool: str, size: int, active: int, idle: int):
    """Update database connection pool metrics."""
    db_connection_pool_size.labels(pool=pool).set(size)
    db_connection_pool_active.labels(pool=pool).set(active)
    db_connection_pool_idle.labels(pool=pool).set(idle)


def track_redis_operation(operation: str, duration: float, status: str = "success"):
    """Track a Redis cache operation."""
    redis_cache_operations_total.labels(operation=operation, status=status).inc()
    redis_cache_operation_duration_seconds.labels(operation=operation).observe(duration)


def update_retrieval_quality(recall_at_3: Optional[float] = None, precision_at_3: Optional[float] = None):
    """Update RAG retrieval quality metrics."""
    if recall_at_3 is not None:
        rag_retrieval_recall_at_3.set(recall_at_3)
    if precision_at_3 is not None:
        rag_retrieval_precision_at_3.set(precision_at_3)


def track_llm_call(model: str, latency_seconds: float, output_chars: int, status: str = "success"):
    """Track an LLM generation call (called from LLMOps logger)."""
    llm_requests_total.labels(model=model, status=status).inc()
    llm_latency_seconds.labels(model=model).observe(latency_seconds)
    approx_tokens = max(1, output_chars // 4)
    llm_tokens_total.labels(model=model, token_type="output").inc(approx_tokens)


def track_llm_satisfaction(vote: str):
    """Track user satisfaction vote (thumbs_up / thumbs_down)."""
    llm_satisfaction_total.labels(vote=vote).inc()


# ============================================================================
# Metrics Endpoint Handler
# ============================================================================

def metrics_handler() -> Response:
    """
    Generate Prometheus metrics in text format.

    Use this as the handler for the /metrics endpoint:

    ```python
    @app.get("/metrics")
    async def metrics():
        return metrics_handler()
    ```
    """
    metrics_data = generate_latest(REGISTRY)
    return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)
