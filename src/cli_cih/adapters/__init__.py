"""AI Adapters for CLI-CIH.

This module provides adapters for various AI CLI tools and services.
"""

from cli_cih.adapters.base import (
    AdapterConfig,
    AdapterConnectionError,
    AdapterError,
    AdapterNotAvailableError,
    AdapterRateLimitError,
    AdapterResponse,
    AdapterTimeoutError,
    AIAdapter,
)
from cli_cih.adapters.claude import ClaudeAdapter
from cli_cih.adapters.codex import CodexAdapter
from cli_cih.adapters.copilot import CopilotAdapter
from cli_cih.adapters.gemini import GeminiAdapter
from cli_cih.adapters.glm import GLMAdapter
from cli_cih.adapters.ollama import OllamaAdapter

__all__ = [
    # Base
    "AIAdapter",
    "AdapterConfig",
    "AdapterResponse",
    # Errors
    "AdapterError",
    "AdapterTimeoutError",
    "AdapterNotAvailableError",
    "AdapterConnectionError",
    "AdapterRateLimitError",
    # Adapters
    "ClaudeAdapter",
    "CodexAdapter",
    "CopilotAdapter",
    "GeminiAdapter",
    "GLMAdapter",
    "OllamaAdapter",
    # Functions
    "get_adapter",
    "get_all_adapters",
    "ADAPTERS",
]

# Adapter registry
ADAPTERS: dict[str, type[AIAdapter]] = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "copilot": CopilotAdapter,
    "gemini": GeminiAdapter,
    "glm": GLMAdapter,
    "ollama": OllamaAdapter,
}


def get_adapter(name: str) -> AIAdapter:
    """Get an adapter instance by name.

    Args:
        name: Adapter name (claude, codex, gemini, ollama).

    Returns:
        AIAdapter instance.

    Raises:
        ValueError: If adapter name is unknown.
    """
    adapter_class = ADAPTERS.get(name.lower())
    if adapter_class is None:
        raise ValueError(f"Unknown adapter: {name}. Available: {list(ADAPTERS.keys())}")
    return adapter_class()


def get_all_adapters() -> list[AIAdapter]:
    """Get instances of all available adapters.

    Returns:
        List of AIAdapter instances.
    """
    return [adapter_class() for adapter_class in ADAPTERS.values()]
