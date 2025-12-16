"""Base adapter interface for AI integrations."""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, ClassVar, Optional


class AdapterError(Exception):
    """Base exception for adapter errors."""

    pass


class AdapterTimeoutError(AdapterError):
    """Raised when an adapter operation times out."""

    pass


class AdapterNotAvailableError(AdapterError):
    """Raised when an adapter is not available."""

    pass


class AdapterConnectionError(AdapterError):
    """Raised when connection to the adapter fails."""

    pass


class AdapterRateLimitError(AdapterError):
    """Raised when rate limited by the service."""

    pass


@dataclass
class AdapterConfig:
    """Configuration for an adapter."""

    timeout: int = 60
    max_tokens: int = 4096
    model: Optional[str] = None
    endpoint: Optional[str] = None
    max_retries: int = 3
    retry_delay: float = 1.0
    extra: dict = field(default_factory=dict)


@dataclass
class AdapterResponse:
    """Response from an adapter."""

    content: str
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    elapsed_time: Optional[float] = None
    raw_response: Optional[dict] = None


class AIAdapter(ABC):
    """Abstract base class for AI adapters.

    All AI adapters must implement this interface to provide
    a consistent way to interact with different AI services.
    """

    # Adapter identification
    name: str = "base"
    display_name: str = "Base Adapter"
    color: str = "white"
    icon: str = "🤖"

    # Availability cache (shared across all instances)
    _availability_cache: ClassVar[dict[str, tuple[bool, float]]] = {}
    CACHE_TTL: ClassVar[float] = 30.0  # 30초 캐시

    def __init__(self, config: Optional[AdapterConfig] = None):
        """Initialize the adapter.

        Args:
            config: Optional adapter configuration.
        """
        self.config = config or AdapterConfig()
        self._is_initialized = False

    async def is_available(self) -> bool:
        """Check if this adapter is available (with caching).

        Returns:
            True if the adapter can be used, False otherwise.
        """
        cache_key = self.name
        now = time.time()

        # Check cache
        if cache_key in self._availability_cache:
            cached_result, cached_time = self._availability_cache[cache_key]
            if now - cached_time < self.CACHE_TTL:
                return cached_result

        # Cache miss - perform actual check
        result = await self._check_availability()
        self._availability_cache[cache_key] = (result, now)
        return result

    @abstractmethod
    async def _check_availability(self) -> bool:
        """Perform actual availability check.

        Subclasses must implement this method.

        Returns:
            True if the adapter can be used, False otherwise.
        """
        pass

    @classmethod
    def clear_availability_cache(cls) -> None:
        """Clear the availability cache for all adapters."""
        cls._availability_cache.clear()

    @classmethod
    def invalidate_cache(cls, adapter_name: str) -> None:
        """Invalidate cache for a specific adapter.

        Args:
            adapter_name: Name of the adapter to invalidate.
        """
        cls._availability_cache.pop(adapter_name, None)

    @abstractmethod
    async def send(self, prompt: str) -> AsyncIterator[str]:
        """Send a prompt and yield streaming response chunks.

        Args:
            prompt: The prompt to send to the AI.

        Yields:
            String chunks of the response as they arrive.

        Raises:
            AdapterError: If the request fails.
            AdapterTimeoutError: If the request times out.
        """
        yield ""

    @abstractmethod
    async def get_version(self) -> str:
        """Get the version of the underlying AI tool/service.

        Returns:
            Version string.
        """
        pass

    async def send_and_wait(self, prompt: str) -> AdapterResponse:
        """Send a prompt and wait for the complete response.

        Args:
            prompt: The prompt to send.

        Returns:
            Complete AdapterResponse.
        """
        import time

        start_time = time.time()
        chunks: list[str] = []

        async for chunk in self.send(prompt):
            chunks.append(chunk)

        elapsed = time.time() - start_time
        content = "".join(chunks)

        return AdapterResponse(
            content=content,
            elapsed_time=elapsed,
        )

    async def health_check(self) -> dict:
        """Perform a health check on the adapter.

        Returns:
            Dict with status information.
        """
        try:
            available = await self.is_available()
            version = await self.get_version() if available else "N/A"
            return {
                "name": self.name,
                "display_name": self.display_name,
                "available": available,
                "version": version,
                "status": "ok" if available else "unavailable",
            }
        except Exception as e:
            return {
                "name": self.name,
                "display_name": self.display_name,
                "available": False,
                "version": "N/A",
                "status": "error",
                "error": str(e),
            }

    async def _retry_operation(
        self,
        operation: Callable[..., Any],
        *args,
        operation_name: str = "operation",
        **kwargs,
    ) -> Any:
        """Execute an operation with retry logic.

        Args:
            operation: The async callable to execute.
            *args: Positional arguments for the operation.
            operation_name: Name for logging purposes.
            **kwargs: Keyword arguments for the operation.

        Returns:
            Result of the operation.

        Raises:
            AdapterError: If all retries fail.
        """
        logger = logging.getLogger(f"cli_cih.adapters.{self.name}")
        last_error: Optional[Exception] = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return await operation(*args, **kwargs)

            except (AdapterTimeoutError, AdapterConnectionError) as e:
                last_error = e
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"[{self.display_name}] {operation_name} failed (attempt {attempt + 1}/"
                        f"{self.config.max_retries + 1}): {e}. Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"[{self.display_name}] {operation_name} failed after "
                        f"{self.config.max_retries + 1} attempts: {e}"
                    )

            except AdapterRateLimitError as e:
                last_error = e
                # Wait longer for rate limits
                delay = min(30.0, self.config.retry_delay * (3 ** attempt))
                logger.warning(
                    f"[{self.display_name}] Rate limited. Waiting {delay:.1f}s..."
                )
                await asyncio.sleep(delay)

            except AdapterError:
                # Don't retry other adapter errors
                raise

            except Exception as e:
                # Convert unexpected errors to AdapterError
                logger.exception(f"[{self.display_name}] Unexpected error in {operation_name}")
                raise AdapterError(f"Unexpected error: {e}") from e

        # All retries exhausted
        raise last_error or AdapterError("Operation failed")

    def _format_error(self, error: Exception) -> str:
        """Format an error for user display.

        Args:
            error: The exception.

        Returns:
            User-friendly error message.
        """
        error_msg = str(error).lower()

        if "connection" in error_msg or "connect" in error_msg:
            return f"{self.display_name} is not reachable. Check your connection."

        if "timeout" in error_msg:
            return f"{self.display_name} is taking too long to respond."

        if "rate limit" in error_msg or "too many" in error_msg:
            return f"{self.display_name} is rate limiting requests. Please wait."

        if "auth" in error_msg or "key" in error_msg or "token" in error_msg:
            return f"{self.display_name} authentication failed. Check your credentials."

        if "not found" in error_msg or "not installed" in error_msg:
            return f"{self.display_name} is not installed or not found."

        return f"{self.display_name} error: {error}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
