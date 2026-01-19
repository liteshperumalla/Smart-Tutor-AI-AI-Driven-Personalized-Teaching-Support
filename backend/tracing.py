"""
AWS X-Ray Distributed Tracing Integration
Provides end-to-end request tracing across microservices

Features:
- Automatic FastAPI instrumentation
- Custom subsegments for business logic
- Trace context propagation
- Integration with AWS services (Bedrock, DynamoDB, S3)
- Performance metrics and annotations
"""

import logging
import functools
from typing import Callable, Any, Optional, Dict
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Try to import X-Ray SDK
try:
    from aws_xray_sdk.core import xray_recorder, patch_all
    from aws_xray_sdk.ext.flask.middleware import XRayMiddleware
    from aws_xray_sdk.core.context import Context
    XRAY_AVAILABLE = True
except ImportError:
    XRAY_AVAILABLE = False
    logger.warning("AWS X-Ray SDK not installed. Tracing will be disabled.")
    # Create no-op decorators
    xray_recorder = None


class TracingConfig:
    """Configuration for X-Ray tracing"""

    def __init__(
        self,
        service_name: str = "smart-ai-tutor",
        enabled: bool = True,
        sampling_rate: float = 1.0,
        patch_libraries: bool = True,
    ):
        """
        Initialize tracing configuration

        Args:
            service_name: Name of the service for tracing
            enabled: Enable/disable tracing
            sampling_rate: Sample rate (0.0 to 1.0, where 1.0 = 100%)
            patch_libraries: Auto-patch AWS SDK and other libraries
        """
        self.service_name = service_name
        self.enabled = enabled and XRAY_AVAILABLE
        self.sampling_rate = sampling_rate
        self.patch_libraries = patch_libraries

        if self.enabled:
            self._configure_xray()

    def _configure_xray(self):
        """Configure X-Ray recorder"""
        try:
            # Configure service name
            xray_recorder.configure(
                service=self.service_name,
                sampling=True,
                context_missing='LOG_ERROR',
                plugins=('ECSPlugin', 'EC2Plugin'),  # Auto-detect AWS environment
            )

            # Patch AWS SDK and other libraries
            if self.patch_libraries:
                patch_all()
                logger.info("X-Ray: Patched AWS SDK and libraries")

            logger.info(f"X-Ray tracing enabled for service: {self.service_name}")

        except Exception as e:
            logger.error(f"Failed to configure X-Ray: {e}")
            self.enabled = False


# Global tracing config
_tracing_config: Optional[TracingConfig] = None


def init_tracing(
    service_name: str = "smart-ai-tutor",
    enabled: bool = True,
    sampling_rate: float = 1.0,
):
    """
    Initialize distributed tracing

    Args:
        service_name: Service name for traces
        enabled: Enable tracing
        sampling_rate: Sampling rate (0.0 to 1.0)
    """
    global _tracing_config
    _tracing_config = TracingConfig(
        service_name=service_name,
        enabled=enabled,
        sampling_rate=sampling_rate,
    )
    return _tracing_config


def get_tracing_config() -> Optional[TracingConfig]:
    """Get global tracing configuration"""
    return _tracing_config


def instrument_fastapi(app):
    """
    Instrument FastAPI application with X-Ray

    Usage:
        app = FastAPI()
        instrument_fastapi(app)
    """
    if not XRAY_AVAILABLE:
        logger.warning("X-Ray SDK not available, skipping FastAPI instrumentation")
        return

    try:
        # X-Ray middleware for FastAPI
        from aws_xray_sdk.ext.aiohttp.middleware import middleware as xray_middleware

        @app.middleware("http")
        async def xray_fastapi_middleware(request, call_next):
            """X-Ray middleware for FastAPI"""
            # Start a segment for this request
            segment_name = f"{request.method} {request.url.path}"

            try:
                # Begin segment
                segment = xray_recorder.begin_segment(segment_name)

                # Add metadata
                segment.put_metadata('http_method', request.method)
                segment.put_metadata('url', str(request.url))
                segment.put_metadata('headers', dict(request.headers))

                # Process request
                response = await call_next(request)

                # Add response metadata
                segment.put_metadata('status_code', response.status_code)

                # Add annotations for filtering
                segment.put_annotation('method', request.method)
                segment.put_annotation('status', response.status_code)
                segment.put_annotation('path', request.url.path)

                return response

            except Exception as e:
                # Record exception
                if xray_recorder.current_segment():
                    xray_recorder.current_segment().add_exception(e)
                raise

            finally:
                # End segment
                xray_recorder.end_segment()

        logger.info("FastAPI instrumented with X-Ray middleware")

    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {e}")


@contextmanager
def trace_subsegment(name: str, metadata: Optional[Dict[str, Any]] = None):
    """
    Context manager for custom subsegments

    Usage:
        with trace_subsegment("database_query", {"table": "users"}):
            db.query(...)
    """
    if not XRAY_AVAILABLE or not _tracing_config or not _tracing_config.enabled:
        yield
        return

    subsegment = None
    try:
        # Begin subsegment
        subsegment = xray_recorder.begin_subsegment(name)

        # Add metadata
        if metadata:
            for key, value in metadata.items():
                subsegment.put_metadata(key, value)

        yield subsegment

    except Exception as e:
        # Record exception in subsegment
        if subsegment:
            subsegment.add_exception(e)
        raise

    finally:
        # End subsegment
        if subsegment:
            xray_recorder.end_subsegment()


def trace_function(name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
    """
    Decorator to trace a function

    Usage:
        @trace_function(name="bedrock_call", metadata={"model": "claude"})
        def call_bedrock():
            ...
    """
    def decorator(func: Callable) -> Callable:
        function_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not XRAY_AVAILABLE or not _tracing_config or not _tracing_config.enabled:
                return func(*args, **kwargs)

            with trace_subsegment(function_name, metadata):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def trace_async_function(name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
    """
    Decorator to trace an async function

    Usage:
        @trace_async_function(name="async_operation")
        async def my_async_func():
            ...
    """
    def decorator(func: Callable) -> Callable:
        function_name = name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not XRAY_AVAILABLE or not _tracing_config or not _tracing_config.enabled:
                return await func(*args, **kwargs)

            subsegment = None
            try:
                subsegment = xray_recorder.begin_subsegment(function_name)

                if metadata:
                    for key, value in metadata.items():
                        subsegment.put_metadata(key, value)

                result = await func(*args, **kwargs)
                return result

            except Exception as e:
                if subsegment:
                    subsegment.add_exception(e)
                raise

            finally:
                if subsegment:
                    xray_recorder.end_subsegment()

        return wrapper

    return decorator


def add_trace_metadata(key: str, value: Any):
    """
    Add metadata to current segment

    Usage:
        add_trace_metadata("user_id", "123")
    """
    if not XRAY_AVAILABLE or not _tracing_config or not _tracing_config.enabled:
        return

    try:
        segment = xray_recorder.current_segment()
        if segment:
            segment.put_metadata(key, value)
    except Exception as e:
        logger.debug(f"Failed to add trace metadata: {e}")


def add_trace_annotation(key: str, value: str):
    """
    Add annotation to current segment (indexed for search)

    Annotations are indexed and can be used for filtering traces

    Usage:
        add_trace_annotation("user_type", "premium")
    """
    if not XRAY_AVAILABLE or not _tracing_config or not _tracing_config.enabled:
        return

    try:
        segment = xray_recorder.current_segment()
        if segment:
            segment.put_annotation(key, value)
    except Exception as e:
        logger.debug(f"Failed to add trace annotation: {e}")


def record_exception(exception: Exception):
    """
    Record exception in current segment

    Usage:
        try:
            risky_operation()
        except Exception as e:
            record_exception(e)
            raise
    """
    if not XRAY_AVAILABLE or not _tracing_config or not _tracing_config.enabled:
        return

    try:
        segment = xray_recorder.current_segment()
        if segment:
            segment.add_exception(exception)
    except Exception as e:
        logger.debug(f"Failed to record exception in trace: {e}")


class TracedOperation:
    """
    Context manager for traced operations with timing

    Usage:
        with TracedOperation("database_query", user_id="123") as op:
            result = db.query(...)
            op.add_result_metadata({"rows": len(result)})
    """

    def __init__(self, name: str, **metadata):
        self.name = name
        self.metadata = metadata
        self.subsegment = None
        self.start_time = None

    def __enter__(self):
        if not XRAY_AVAILABLE or not _tracing_config or not _tracing_config.enabled:
            return self

        import time
        self.start_time = time.time()

        self.subsegment = xray_recorder.begin_subsegment(self.name)

        # Add initial metadata
        for key, value in self.metadata.items():
            self.subsegment.put_metadata(key, value)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not XRAY_AVAILABLE or not _tracing_config or not _tracing_config.enabled:
            return

        if self.subsegment:
            # Add timing metadata
            if self.start_time:
                import time
                duration = time.time() - self.start_time
                self.subsegment.put_metadata("duration_ms", duration * 1000)

            # Record exception if any
            if exc_val:
                self.subsegment.add_exception(exc_val)

            xray_recorder.end_subsegment()

    def add_metadata(self, key: str, value: Any):
        """Add metadata during operation"""
        if self.subsegment:
            self.subsegment.put_metadata(key, value)

    def add_annotation(self, key: str, value: str):
        """Add annotation during operation"""
        if self.subsegment:
            self.subsegment.put_annotation(key, value)

    def add_result_metadata(self, metadata: Dict[str, Any]):
        """Add result metadata at end of operation"""
        if self.subsegment:
            for key, value in metadata.items():
                self.subsegment.put_metadata(f"result_{key}", value)


# Convenience functions for common operations

@trace_function(name="bedrock_llm_call")
def trace_bedrock_call(func: Callable) -> Callable:
    """Decorator for Bedrock LLM calls"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        add_trace_annotation("service", "bedrock")
        add_trace_annotation("operation_type", "llm_inference")
        return func(*args, **kwargs)
    return wrapper


@trace_function(name="database_operation")
def trace_db_operation(func: Callable) -> Callable:
    """Decorator for database operations"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        add_trace_annotation("service", "database")
        return func(*args, **kwargs)
    return wrapper


@trace_function(name="cache_operation")
def trace_cache_operation(func: Callable) -> Callable:
    """Decorator for cache operations"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        add_trace_annotation("service", "redis")
        return func(*args, **kwargs)
    return wrapper


# Health check for tracing
def get_tracing_health() -> Dict[str, Any]:
    """Get tracing health status"""
    if not XRAY_AVAILABLE:
        return {
            "status": "not_available",
            "message": "X-Ray SDK not installed",
        }

    if not _tracing_config or not _tracing_config.enabled:
        return {
            "status": "disabled",
            "message": "Tracing is disabled",
        }

    return {
        "status": "enabled",
        "service_name": _tracing_config.service_name,
        "sampling_rate": _tracing_config.sampling_rate,
    }
