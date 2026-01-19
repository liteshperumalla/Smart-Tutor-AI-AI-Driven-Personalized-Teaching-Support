"""
Circuit Breaker Pattern Implementation
Prevents cascading failures when calling external services

Implements the Circuit Breaker pattern with three states:
- CLOSED: Normal operation, requests pass through
- OPEN: Failures exceeded threshold, reject requests immediately
- HALF_OPEN: Test if service recovered

Based on Michael Nygard's Release It! pattern
"""

import time
import logging
from enum import Enum
from typing import Callable, Any, Optional, Dict
from functools import wraps
from threading import Lock
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreakerOpenError(CircuitBreakerError):
    """Circuit is open, rejecting requests"""
    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker for '{service_name}' is OPEN. "
            f"Retry after {retry_after:.1f} seconds."
        )


class CircuitBreaker:
    """
    Circuit Breaker implementation for external service calls

    Usage:
        breaker = CircuitBreaker(
            name="bedrock-service",
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=BedrockError
        )

        @breaker
        def call_bedrock():
            return bedrock_client.invoke_model(...)
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        success_threshold: int = 2,
    ):
        """
        Initialize circuit breaker

        Args:
            name: Service name for logging
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open
            expected_exception: Exception type to catch
            success_threshold: Successes needed in half-open to close circuit
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = Lock()

        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"failure_threshold={failure_threshold}, "
            f"recovery_timeout={recovery_timeout}s"
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        with self._lock:
            # Check if we should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")

            return self._state

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self._last_failure_time is None:
            return False

        return (time.time() - self._last_failure_time) >= self.recovery_timeout

    def _on_success(self):
        """Handle successful call"""
        with self._lock:
            self._failure_count = 0

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.debug(
                    f"Circuit breaker '{self.name}' success in HALF_OPEN: "
                    f"{self._success_count}/{self.success_threshold}"
                )

                if self._success_count >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._success_count = 0
                    logger.info(f"Circuit breaker '{self.name}' transitioned to CLOSED")

    def _on_failure(self):
        """Handle failed call"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            logger.warning(
                f"Circuit breaker '{self.name}' failure: "
                f"{self._failure_count}/{self.failure_threshold}"
            )

            if self._state == CircuitState.HALF_OPEN:
                # Single failure in half-open reopens circuit
                self._state = CircuitState.OPEN
                self._failure_count = 0
                logger.error(f"Circuit breaker '{self.name}' reopened from HALF_OPEN")

            elif self._failure_count >= self.failure_threshold:
                # Too many failures, open circuit
                self._state = CircuitState.OPEN
                logger.error(
                    f"Circuit breaker '{self.name}' OPENED after "
                    f"{self._failure_count} failures"
                )

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Original exception from function
        """
        current_state = self.state

        if current_state == CircuitState.OPEN:
            retry_after = self.recovery_timeout - (time.time() - self._last_failure_time)
            raise CircuitBreakerOpenError(self.name, max(0, retry_after))

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise

    def __call__(self, func: Callable) -> Callable:
        """
        Decorator to wrap function with circuit breaker

        Usage:
            @circuit_breaker
            def my_function():
                ...
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)

        return wrapper

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
                "last_failure_time": datetime.fromtimestamp(self._last_failure_time).isoformat()
                if self._last_failure_time else None,
            }

    def reset(self):
        """Manually reset circuit breaker to CLOSED state"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            logger.info(f"Circuit breaker '{self.name}' manually reset to CLOSED")


class CircuitBreakerRegistry:
    """
    Global registry for circuit breakers
    Allows centralized management and monitoring
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._breakers: Dict[str, CircuitBreaker] = {}
        return cls._instance

    def register(self, breaker: CircuitBreaker):
        """Register a circuit breaker"""
        self._breakers[breaker.name] = breaker
        logger.info(f"Registered circuit breaker: {breaker.name}")

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        return self._breakers.get(name)

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers"""
        return {
            name: breaker.get_stats()
            for name, breaker in self._breakers.items()
        }

    def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self._breakers.values():
            breaker.reset()
        logger.info("All circuit breakers reset")


# Global registry instance
circuit_breaker_registry = CircuitBreakerRegistry()


# Convenience function to create and register circuit breaker
def create_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception,
    success_threshold: int = 2,
    register: bool = True,
) -> CircuitBreaker:
    """
    Create a circuit breaker and optionally register it

    Args:
        name: Service name
        failure_threshold: Failures before opening
        recovery_timeout: Seconds before half-open attempt
        expected_exception: Exception type to catch
        success_threshold: Successes needed to close from half-open
        register: Whether to register in global registry

    Returns:
        CircuitBreaker instance
    """
    breaker = CircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=expected_exception,
        success_threshold=success_threshold,
    )

    if register:
        circuit_breaker_registry.register(breaker)

    return breaker


# Pre-configured circuit breakers for common services
bedrock_circuit_breaker = create_circuit_breaker(
    name="bedrock",
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=Exception,  # Catch all Bedrock exceptions
)

serpapi_circuit_breaker = create_circuit_breaker(
    name="serpapi",
    failure_threshold=3,
    recovery_timeout=30,
    expected_exception=Exception,
)

redis_circuit_breaker = create_circuit_breaker(
    name="redis",
    failure_threshold=3,
    recovery_timeout=10,
    expected_exception=Exception,
)

postgres_circuit_breaker = create_circuit_breaker(
    name="postgres",
    failure_threshold=5,
    recovery_timeout=30,
    expected_exception=Exception,
)

dynamodb_circuit_breaker = create_circuit_breaker(
    name="dynamodb",
    failure_threshold=5,
    recovery_timeout=30,
    expected_exception=Exception,
)
