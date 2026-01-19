"""
Retry Policy with Exponential Backoff
Complements Circuit Breaker for resilient external service calls

Implements:
- Exponential backoff with jitter
- Configurable retry attempts
- Timeout management
- Fallback mechanisms
"""

import time
import random
import logging
from typing import Callable, Any, Optional, TypeVar, Type
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted"""
    pass


class RetryPolicy:
    """
    Retry policy with exponential backoff

    Usage:
        retry = RetryPolicy(
            max_attempts=3,
            base_delay=1.0,
            max_delay=30.0,
            exponential_base=2,
            jitter=True
        )

        @retry
        def unstable_function():
            ...
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        exceptions: tuple = (Exception,),
        fallback: Optional[Callable] = None,
    ):
        """
        Initialize retry policy

        Args:
            max_attempts: Maximum retry attempts (1 = no retry)
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff (2 = double each time)
            jitter: Add random jitter to prevent thundering herd
            exceptions: Tuple of exceptions to retry on
            fallback: Fallback function to call if all retries fail
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.exceptions = exceptions
        self.fallback = fallback

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt with exponential backoff and jitter

        Delay = min(base_delay * (exponential_base ^ attempt), max_delay)
        With jitter: random.uniform(0, delay)

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )

        if self.jitter:
            # Full jitter: random between 0 and calculated delay
            delay = random.uniform(0, delay)

        return delay

    def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with retry logic

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            RetryExhaustedError: If all retries exhausted
            Exception: Last exception if fallback not provided
        """
        last_exception = None

        for attempt in range(self.max_attempts):
            try:
                result = func(*args, **kwargs)
                if attempt > 0:
                    logger.info(
                        f"Function '{func.__name__}' succeeded on attempt {attempt + 1}"
                    )
                return result

            except self.exceptions as e:
                last_exception = e

                if attempt < self.max_attempts - 1:
                    # Calculate delay for next attempt
                    delay = self._calculate_delay(attempt)

                    logger.warning(
                        f"Function '{func.__name__}' failed on attempt {attempt + 1}/{self.max_attempts}. "
                        f"Retrying in {delay:.2f}s. Error: {e}"
                    )

                    time.sleep(delay)
                else:
                    logger.error(
                        f"Function '{func.__name__}' failed after {self.max_attempts} attempts. "
                        f"Last error: {e}"
                    )

        # All retries exhausted
        if self.fallback:
            logger.info(f"Calling fallback for '{func.__name__}'")
            try:
                return self.fallback(*args, **kwargs)
            except Exception as fallback_error:
                logger.error(f"Fallback failed: {fallback_error}")
                raise RetryExhaustedError(
                    f"All {self.max_attempts} attempts failed and fallback failed"
                ) from last_exception

        raise RetryExhaustedError(
            f"All {self.max_attempts} attempts failed"
        ) from last_exception

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        Decorator to wrap function with retry logic

        Usage:
            @retry_policy
            def my_function():
                ...
        """
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return self.execute(func, *args, **kwargs)

        return wrapper


# Convenience decorators for common scenarios

def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,),
    fallback: Optional[Callable] = None,
):
    """
    Decorator for retry with exponential backoff

    Usage:
        @retry_with_backoff(max_attempts=5, base_delay=2.0)
        def call_external_api():
            ...
    """
    return RetryPolicy(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exceptions=exceptions,
        fallback=fallback,
    )


def retry_on_timeout(
    max_attempts: int = 3,
    base_delay: float = 2.0,
    timeout_exception: Type[Exception] = TimeoutError,
):
    """
    Retry specifically for timeout errors

    Usage:
        @retry_on_timeout(max_attempts=5)
        def slow_operation():
            ...
    """
    return RetryPolicy(
        max_attempts=max_attempts,
        base_delay=base_delay,
        exceptions=(timeout_exception,),
    )


# Pre-configured retry policies for common services

bedrock_retry = RetryPolicy(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
    exceptions=(Exception,),  # Retry all exceptions
)

serpapi_retry = RetryPolicy(
    max_attempts=3,
    base_delay=2.0,
    max_delay=20.0,
    exponential_base=2.0,
    jitter=True,
    exceptions=(Exception,),
)

database_retry = RetryPolicy(
    max_attempts=5,
    base_delay=0.5,
    max_delay=10.0,
    exponential_base=2.0,
    jitter=True,
    exceptions=(Exception,),  # Retry connection errors
)

redis_retry = RetryPolicy(
    max_attempts=3,
    base_delay=0.5,
    max_delay=5.0,
    exponential_base=2.0,
    jitter=True,
    exceptions=(Exception,),
)


# Combined Circuit Breaker + Retry Pattern

def with_circuit_breaker_and_retry(
    circuit_breaker,
    retry_policy,
):
    """
    Combine circuit breaker and retry for maximum resilience

    Usage:
        from backend.circuit_breaker import bedrock_circuit_breaker
        from backend.retry_policy import bedrock_retry

        @with_circuit_breaker_and_retry(bedrock_circuit_breaker, bedrock_retry)
        def call_bedrock():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Circuit breaker wraps retry logic
            # If circuit is open, fail fast without retrying
            return circuit_breaker.call(
                retry_policy.execute,
                func,
                *args,
                **kwargs
            )
        return wrapper
    return decorator


# Timeout decorator

class TimeoutError(Exception):
    """Raised when operation times out"""
    pass


def timeout(seconds: float):
    """
    Timeout decorator using signal (Unix only)

    Usage:
        @timeout(30.0)
        def long_running_operation():
            ...
    """
    import signal

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Operation timed out after {seconds} seconds")

            # Set signal handler
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(seconds))

            try:
                result = func(*args, **kwargs)
            finally:
                # Reset alarm
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            return result

        return wrapper

    return decorator


# Async retry for async functions

import asyncio
from typing import Awaitable


class AsyncRetryPolicy:
    """Async version of RetryPolicy for async functions"""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        exceptions: tuple = (Exception,),
        fallback: Optional[Callable] = None,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.exceptions = exceptions
        self.fallback = fallback

    def _calculate_delay(self, attempt: int) -> float:
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        if self.jitter:
            delay = random.uniform(0, delay)
        return delay

    async def execute(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Execute async function with retry logic"""
        last_exception = None

        for attempt in range(self.max_attempts):
            try:
                result = await func(*args, **kwargs)
                if attempt > 0:
                    logger.info(
                        f"Async function '{func.__name__}' succeeded on attempt {attempt + 1}"
                    )
                return result

            except self.exceptions as e:
                last_exception = e

                if attempt < self.max_attempts - 1:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Async function '{func.__name__}' failed on attempt {attempt + 1}/{self.max_attempts}. "
                        f"Retrying in {delay:.2f}s. Error: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Async function '{func.__name__}' failed after {self.max_attempts} attempts. "
                        f"Last error: {e}"
                    )

        if self.fallback:
            logger.info(f"Calling async fallback for '{func.__name__}'")
            try:
                return await self.fallback(*args, **kwargs)
            except Exception as fallback_error:
                logger.error(f"Async fallback failed: {fallback_error}")
                raise RetryExhaustedError(
                    f"All {self.max_attempts} attempts failed and fallback failed"
                ) from last_exception

        raise RetryExhaustedError(
            f"All {self.max_attempts} attempts failed"
        ) from last_exception

    def __call__(self, func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await self.execute(func, *args, **kwargs)
        return wrapper
