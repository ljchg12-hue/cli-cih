"""Logging configuration for CLI-CIH."""

import logging
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

# Default log directory
DEFAULT_LOG_DIR = Path.home() / ".local" / "share" / "cli-cih" / "logs"


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
    console: Console | None = None,
) -> None:
    """Set up logging configuration.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional file path for logging.
        console: Rich console instance for output.
    """
    # Create log directory if logging to file
    if log_file:
        log_path = Path(log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        # Default log file
        DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = str(DEFAULT_LOG_DIR / "cli-cih.log")

    # Create handlers
    handlers = []

    # Rich console handler (for terminal output)
    rich_handler = RichHandler(
        console=console or Console(stderr=True),
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        tracebacks_show_locals=False,
        markup=True,
    )
    rich_handler.setLevel(logging.WARNING)  # Only warnings and above to console
    handlers.append(rich_handler)

    # File handler (for detailed logs)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        handlers=handlers,
        force=True,
    )

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name (usually __name__).

    Returns:
        Logger instance.
    """
    return logging.getLogger(name)


class ContextLogger:
    """Logger with context information for debugging."""

    def __init__(self, name: str):
        """Initialize context logger.

        Args:
            name: Logger name.
        """
        self._logger = logging.getLogger(name)
        self._context: dict = {}

    def set_context(self, **kwargs) -> None:
        """Set context information."""
        self._context.update(kwargs)

    def clear_context(self) -> None:
        """Clear context information."""
        self._context.clear()

    def _format_message(self, message: str) -> str:
        """Format message with context."""
        if self._context:
            ctx_str = " | ".join(f"{k}={v}" for k, v in self._context.items())
            return f"[{ctx_str}] {message}"
        return message

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._logger.debug(self._format_message(message), **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._logger.info(self._format_message(message), **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._logger.warning(self._format_message(message), **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self._logger.error(self._format_message(message), **kwargs)

    def exception(self, message: str, **kwargs) -> None:
        """Log exception with traceback."""
        self._logger.exception(self._format_message(message), **kwargs)


def log_adapter_call(
    adapter_name: str,
    method: str,
    success: bool,
    duration_ms: float,
    error: str | None = None,
) -> None:
    """Log an adapter call for analytics.

    Args:
        adapter_name: Name of the adapter.
        method: Method called.
        success: Whether the call succeeded.
        duration_ms: Duration in milliseconds.
        error: Error message if failed.
    """
    logger = get_logger("cli_cih.adapters")

    if success:
        logger.debug(f"Adapter call: {adapter_name}.{method} - SUCCESS ({duration_ms:.0f}ms)")
    else:
        logger.warning(
            f"Adapter call: {adapter_name}.{method} - FAILED ({duration_ms:.0f}ms): {error}"
        )


def log_discussion_event(
    event_type: str,
    details: dict | None = None,
) -> None:
    """Log a discussion event for analytics.

    Args:
        event_type: Type of event (round_start, ai_response, etc.).
        details: Additional event details.
    """
    logger = get_logger("cli_cih.discussion")
    logger.debug(f"Discussion event: {event_type} - {details or {}}")
