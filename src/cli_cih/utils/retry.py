"""Retry utilities for error handling."""

import asyncio
import functools
import logging
import random
from typing import Any, Callable, Optional, TypeVar

from cli_cih.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_on: Optional[tuple[type[Exception], ...]] = None,
    ):
        """Initialize retry config.

        Args:
            max_retries: Maximum number of retry attempts.
            base_delay: Initial delay between retries (seconds).
            max_delay: Maximum delay between retries (seconds).
            exponential_base: Base for exponential backoff.
            jitter: Whether to add random jitter to delays.
            retry_on: Tuple of exception types to retry on.
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_on = retry_on or (Exception,)


def calculate_delay(
    attempt: int,
    config: RetryConfig,
) -> float:
    """Calculate delay for a retry attempt.

    Args:
        attempt: Current attempt number (0-indexed).
        config: Retry configuration.

    Returns:
        Delay in seconds.
    """
    delay = min(
        config.base_delay * (config.exponential_base ** attempt),
        config.max_delay,
    )

    if config.jitter:
        # Add random jitter (0% to 25% of delay)
        jitter = delay * random.uniform(0, 0.25)
        delay += jitter

    return delay


async def retry_async(
    func: Callable[..., Any],
    *args,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
    **kwargs,
) -> Any:
    """Execute an async function with retry logic.

    Args:
        func: Async function to execute.
        *args: Positional arguments for the function.
        config: Retry configuration.
        on_retry: Optional callback called on each retry.
        **kwargs: Keyword arguments for the function.

    Returns:
        Result of the function.

    Raises:
        The last exception if all retries fail.
    """
    config = config or RetryConfig()
    last_exception: Optional[Exception] = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)

        except config.retry_on as e:
            last_exception = e

            if attempt < config.max_retries:
                delay = calculate_delay(attempt, config)

                logger.warning(
                    f"Retry {attempt + 1}/{config.max_retries} for {func.__name__}: "
                    f"{type(e).__name__}: {e}. Waiting {delay:.1f}s..."
                )

                if on_retry:
                    on_retry(attempt + 1, e)

                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"All {config.max_retries} retries failed for {func.__name__}: "
                    f"{type(e).__name__}: {e}"
                )

    raise last_exception  # type: ignore


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    retry_on: Optional[tuple[type[Exception], ...]] = None,
) -> Callable:
    """Decorator to add retry logic to an async function.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay between retries.
        retry_on: Exception types to retry on.

    Returns:
        Decorator function.
    """
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        retry_on=retry_on,
    )

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            return await retry_async(func, *args, config=config, **kwargs)

        return wrapper

    return decorator


class CircuitBreaker:
    """Circuit breaker for preventing cascading failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_requests: int = 1,
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit.
            recovery_timeout: Time to wait before trying again (seconds).
            half_open_requests: Requests to allow in half-open state.
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests

        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = "closed"  # closed, open, half_open
        self._half_open_count = 0

    @property
    def state(self) -> str:
        """Get current circuit state."""
        return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self._state == "open"

    def record_success(self) -> None:
        """Record a successful call."""
        if self._state == "half_open":
            self._state = "closed"
            self._failure_count = 0
            logger.info("Circuit breaker closed after successful recovery")
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        import time

        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = "open"
            logger.warning(f"Circuit breaker opened after {self._failure_count} failures")

    def can_execute(self) -> bool:
        """Check if a call can be executed.

        Returns:
            True if call can proceed, False otherwise.
        """
        import time

        if self._state == "closed":
            return True

        if self._state == "open":
            # Check if recovery timeout has passed
            if self._last_failure_time is None:
                return True

            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = "half_open"
                self._half_open_count = 0
                logger.info("Circuit breaker entering half-open state")
                return True

            return False

        if self._state == "half_open":
            if self._half_open_count < self.half_open_requests:
                self._half_open_count += 1
                return True
            return False

        return True

    async def execute(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs,
    ) -> Any:
        """Execute a function with circuit breaker protection.

        Args:
            func: Async function to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Function result.

        Raises:
            CircuitBreakerOpenError: If circuit is open.
            The original exception if the function fails.
        """
        if not self.can_execute():
            raise CircuitBreakerOpenError(
                f"Circuit breaker is open. Wait {self.recovery_timeout}s before retrying."
            )

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result

        except Exception as e:
            self.record_failure()
            raise


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


def format_error_message(error: Exception, adapter_name: str = "") -> str:
    """Format a user-friendly error message.

    Args:
        error: The exception.
        adapter_name: Optional adapter name for context.

    Returns:
        Formatted error message.
    """
    error_type = type(error).__name__
    error_msg = str(error)

    # Common error patterns
    if "connection" in error_msg.lower() or "connect" in error_msg.lower():
        return f"Connection failed{' to ' + adapter_name if adapter_name else ''}. Check your network connection."

    if "timeout" in error_msg.lower():
        return f"Request timed out{' for ' + adapter_name if adapter_name else ''}. The service may be slow or unavailable."

    if "authentication" in error_msg.lower() or "auth" in error_msg.lower() or "api key" in error_msg.lower():
        return f"Authentication failed{' for ' + adapter_name if adapter_name else ''}. Check your API key or credentials."

    if "rate limit" in error_msg.lower() or "too many requests" in error_msg.lower():
        return f"Rate limited{' by ' + adapter_name if adapter_name else ''}. Please wait before trying again."

    if "not found" in error_msg.lower():
        return f"Resource not found{' on ' + adapter_name if adapter_name else ''}. Check that the service is properly installed."

    # Default: Include error type and message
    prefix = f"[{adapter_name}] " if adapter_name else ""
    return f"{prefix}{error_type}: {error_msg}"
