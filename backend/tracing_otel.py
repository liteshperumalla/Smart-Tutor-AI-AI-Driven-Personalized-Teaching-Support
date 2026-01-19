"""
OpenTelemetry Distributed Tracing Integration
Provides end-to-end request tracing with OpenTelemetry

Features:
- Automatic FastAPI instrumentation
- Auto-instrumentation for common libraries (requests, psycopg2, redis)
- Custom spans for business logic
- Trace context propagation
- Integration with Jaeger, Zipkin, or any OTLP-compatible backend
- Metrics and logs correlation
"""

import logging
import os
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION, DEPLOYMENT_ENVIRONMENT
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.boto3sqs import Boto3SQSInstrumentor
    from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.propagate import set_global_textmap, extract, inject
    from opentelemetry.propagators.b3 import B3MultiFormat
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased, ParentBasedTraceIdRatio

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.warning("OpenTelemetry SDK not installed. Tracing will be disabled.")
    trace = None


class OpenTelemetryConfig:
    """Configuration for OpenTelemetry tracing"""

    def __init__(
        self,
        service_name: str = "smart-ai-tutor-backend",
        service_version: str = "1.0.0",
        environment: str = "development",
        enabled: bool = True,
        sampling_rate: float = 1.0,
        otlp_endpoint: str = None,
        auto_instrument: bool = True,
    ):
        """
        Initialize OpenTelemetry configuration

        Args:
            service_name: Name of the service
            service_version: Version of the service
            environment: Deployment environment (dev/staging/production)
            enabled: Enable/disable tracing
            sampling_rate: Sample rate (0.0 to 1.0, where 1.0 = 100%)
            otlp_endpoint: OTLP collector endpoint (default: localhost:4317)
            auto_instrument: Auto-instrument common libraries
        """
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        self.enabled = enabled and OTEL_AVAILABLE
        self.sampling_rate = sampling_rate
        self.otlp_endpoint = otlp_endpoint or os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "otel-collector.monitoring.svc.cluster.local:4317"
        )
        self.auto_instrument = auto_instrument
        self.tracer = None

        if self.enabled:
            self._setup_tracing()

    def _setup_tracing(self):
        """Set up OpenTelemetry tracing"""
        try:
            # Create resource with service metadata
            resource = Resource.create({
                SERVICE_NAME: self.service_name,
                SERVICE_VERSION: self.service_version,
                DEPLOYMENT_ENVIRONMENT: self.environment,
                "service.namespace": "smart-ai-tutor",
                "service.instance.id": os.getenv("HOSTNAME", "localhost"),
            })

            # Create tracer provider with sampling
            if self.sampling_rate < 1.0:
                sampler = ParentBasedTraceIdRatio(self.sampling_rate)
            else:
                sampler = None  # Sample all

            provider = TracerProvider(
                resource=resource,
                sampler=sampler,
            )

            # Set up OTLP exporter
            otlp_exporter = OTLPSpanExporter(
                endpoint=self.otlp_endpoint,
                insecure=True,  # Use TLS in production
            )

            # Add batch span processor
            span_processor = BatchSpanProcessor(
                otlp_exporter,
                max_queue_size=2048,
                max_export_batch_size=512,
                schedule_delay_millis=5000,
            )
            provider.add_span_processor(span_processor)

            # Set as global tracer provider
            trace.set_tracer_provider(provider)

            # Set up B3 propagator for compatibility
            set_global_textmap(B3MultiFormat())

            # Get tracer
            self.tracer = trace.get_tracer(
                instrumenting_module_name=self.service_name,
                instrumenting_library_version=self.service_version,
            )

            logger.info(
                f"OpenTelemetry tracing enabled: {self.service_name} "
                f"(endpoint: {self.otlp_endpoint}, sampling: {self.sampling_rate})"
            )

            # Auto-instrument libraries
            if self.auto_instrument:
                self._auto_instrument()

        except Exception as e:
            logger.error(f"Failed to set up OpenTelemetry: {e}", exc_info=True)
            self.enabled = False

    def _auto_instrument(self):
        """Auto-instrument common libraries"""
        try:
            # HTTP requests
            RequestsInstrumentor().instrument()
            logger.info("OpenTelemetry: Instrumented requests library")

            # PostgreSQL
            Psycopg2Instrumentor().instrument()
            logger.info("OpenTelemetry: Instrumented psycopg2")

            # Redis
            RedisInstrumentor().instrument()
            logger.info("OpenTelemetry: Instrumented redis")

            # AWS SDK (Boto3)
            BotocoreInstrumentor().instrument()
            logger.info("OpenTelemetry: Instrumented botocore/boto3")

        except Exception as e:
            logger.warning(f"Failed to auto-instrument libraries: {e}")


# Global configuration
_otel_config: Optional[OpenTelemetryConfig] = None


def init_tracing(
    service_name: str = "smart-ai-tutor-backend",
    service_version: str = "1.0.0",
    environment: str = None,
    enabled: bool = True,
    sampling_rate: float = 1.0,
    otlp_endpoint: str = None,
) -> OpenTelemetryConfig:
    """
    Initialize OpenTelemetry distributed tracing

    Args:
        service_name: Service name for traces
        service_version: Service version
        environment: Deployment environment
        enabled: Enable tracing
        sampling_rate: Sampling rate (0.0 to 1.0)
        otlp_endpoint: OTLP collector endpoint

    Returns:
        OpenTelemetryConfig instance
    """
    global _otel_config

    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development")

    _otel_config = OpenTelemetryConfig(
        service_name=service_name,
        service_version=service_version,
        environment=environment,
        enabled=enabled,
        sampling_rate=sampling_rate,
        otlp_endpoint=otlp_endpoint,
    )

    return _otel_config


def get_tracer():
    """Get the global tracer instance"""
    if _otel_config and _otel_config.tracer:
        return _otel_config.tracer
    elif OTEL_AVAILABLE:
        return trace.get_tracer(__name__)
    return None


def instrument_fastapi(app):
    """
    Instrument FastAPI application with OpenTelemetry

    Usage:
        app = FastAPI()
        instrument_fastapi(app)
    """
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available, skipping instrumentation")
        return

    try:
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/health,/metrics",  # Don't trace health checks
            tracer_provider=trace.get_tracer_provider(),
        )
        logger.info("FastAPI instrumented with OpenTelemetry")

    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {e}", exc_info=True)


@contextmanager
def trace_span(
    name: str,
    attributes: dict = None,
    set_status_on_exception: bool = True,
):
    """
    Context manager to create a custom span

    Usage:
        with trace_span("database_query", {"table": "users", "operation": "select"}):
            result = db.query(...)
    """
    if not OTEL_AVAILABLE or not _otel_config or not _otel_config.enabled:
        yield None
        return

    tracer = get_tracer()
    if not tracer:
        yield None
        return

    span = tracer.start_span(name)

    try:
        # Set attributes
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        # Make span current
        ctx = trace.set_span_in_context(span)
        token = None

        yield span

    except Exception as e:
        # Record exception
        span.record_exception(e)
        if set_status_on_exception:
            span.set_status(Status(StatusCode.ERROR, str(e)))
        raise

    finally:
        span.end()


def add_span_attribute(key: str, value):
    """
    Add attribute to current span

    Usage:
        add_span_attribute("user.id", user_id)
        add_span_attribute("cache.hit", True)
    """
    if not OTEL_AVAILABLE or not _otel_config or not _otel_config.enabled:
        return

    try:
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.set_attribute(key, value)
    except Exception as e:
        logger.debug(f"Failed to add span attribute: {e}")


def add_span_event(name: str, attributes: dict = None):
    """
    Add event to current span

    Usage:
        add_span_event("cache_miss", {"key": cache_key})
        add_span_event("retry_attempt", {"attempt": 2, "reason": "timeout"})
    """
    if not OTEL_AVAILABLE or not _otel_config or not _otel_config.enabled:
        return

    try:
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.add_event(name, attributes or {})
    except Exception as e:
        logger.debug(f"Failed to add span event: {e}")


def record_exception(exception: Exception):
    """
    Record exception in current span

    Usage:
        try:
            risky_operation()
        except Exception as e:
            record_exception(e)
            raise
    """
    if not OTEL_AVAILABLE or not _otel_config or not _otel_config.enabled:
        return

    try:
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.record_exception(exception)
            current_span.set_status(Status(StatusCode.ERROR, str(exception)))
    except Exception as e:
        logger.debug(f"Failed to record exception: {e}")


def set_span_status(status_code: str, description: str = None):
    """
    Set status of current span

    Usage:
        set_span_status("OK")
        set_span_status("ERROR", "Database connection failed")
    """
    if not OTEL_AVAILABLE or not _otel_config or not _otel_config.enabled:
        return

    try:
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            code = StatusCode.OK if status_code == "OK" else StatusCode.ERROR
            current_span.set_status(Status(code, description))
    except Exception as e:
        logger.debug(f"Failed to set span status: {e}")


# Decorators for common operations

def trace_function(name: str = None, attributes: dict = None):
    """
    Decorator to trace a function

    Usage:
        @trace_function(name="process_payment", attributes={"service": "stripe"})
        def process_payment(amount):
            ...
    """
    def decorator(func):
        import functools

        span_name = name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not OTEL_AVAILABLE or not _otel_config or not _otel_config.enabled:
                return func(*args, **kwargs)

            with trace_span(span_name, attributes):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def trace_async_function(name: str = None, attributes: dict = None):
    """
    Decorator to trace an async function

    Usage:
        @trace_async_function(name="fetch_user_data")
        async def fetch_user_data(user_id):
            ...
    """
    def decorator(func):
        import functools

        span_name = name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not OTEL_AVAILABLE or not _otel_config or not _otel_config.enabled:
                return await func(*args, **kwargs)

            with trace_span(span_name, attributes):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


# Context propagation utilities

def get_trace_context():
    """
    Get current trace context for propagation

    Returns:
        dict: Trace context headers
    """
    if not OTEL_AVAILABLE:
        return {}

    carrier = {}
    inject(carrier)
    return carrier


def set_trace_context(context: dict):
    """
    Set trace context from propagated headers

    Args:
        context: Trace context dict (e.g., from HTTP headers)
    """
    if not OTEL_AVAILABLE or not context:
        return

    try:
        extract(context)
    except Exception as e:
        logger.debug(f"Failed to extract trace context: {e}")


# Health check
def get_tracing_health() -> dict:
    """Get tracing health status"""
    if not OTEL_AVAILABLE:
        return {
            "status": "not_available",
            "message": "OpenTelemetry SDK not installed",
            "provider": "opentelemetry",
        }

    if not _otel_config or not _otel_config.enabled:
        return {
            "status": "disabled",
            "message": "Tracing is disabled",
            "provider": "opentelemetry",
        }

    return {
        "status": "enabled",
        "provider": "opentelemetry",
        "service_name": _otel_config.service_name,
        "service_version": _otel_config.service_version,
        "environment": _otel_config.environment,
        "sampling_rate": _otel_config.sampling_rate,
        "otlp_endpoint": _otel_config.otlp_endpoint,
    }
