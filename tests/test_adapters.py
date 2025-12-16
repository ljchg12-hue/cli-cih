"""Unit tests for AI adapters."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from cli_cih.adapters import (
    AIAdapter,
    AdapterConfig,
    AdapterResponse,
    AdapterError,
    AdapterTimeoutError,
    AdapterNotAvailableError,
    AdapterConnectionError,
    AdapterRateLimitError,
    ClaudeAdapter,
    CodexAdapter,
    GeminiAdapter,
    OllamaAdapter,
    get_adapter,
    get_all_adapters,
    ADAPTERS,
)


class TestClaudeAdapter:
    """Tests for Claude adapter."""

    def test_adapter_attributes(self):
        """Claude adapter should have correct attributes."""
        adapter = ClaudeAdapter()
        assert adapter.name == "claude"
        assert adapter.display_name == "Claude"
        assert adapter.color == "bright_blue"
        assert adapter.icon == "🔵"

    def test_config_initialization(self):
        """Adapter should initialize with config."""
        config = AdapterConfig(timeout=120, max_tokens=8192)
        adapter = ClaudeAdapter(config=config)
        assert adapter.config.timeout == 120
        assert adapter.config.max_tokens == 8192

    @pytest.mark.asyncio
    async def test_health_check_unavailable(self):
        """Health check should handle unavailable state."""
        adapter = ClaudeAdapter()
        with patch.object(adapter, "is_available", return_value=False):
            health = await adapter.health_check()
            assert health["available"] is False
            assert health["status"] == "unavailable"


class TestCodexAdapter:
    """Tests for Codex adapter."""

    def test_adapter_attributes(self):
        """Codex adapter should have correct attributes."""
        adapter = CodexAdapter()
        assert adapter.name == "codex"
        assert adapter.display_name == "Codex"
        assert adapter.color == "bright_green"
        assert adapter.icon == "🟢"


class TestGeminiAdapter:
    """Tests for Gemini adapter."""

    def test_adapter_attributes(self):
        """Gemini adapter should have correct attributes."""
        adapter = GeminiAdapter()
        assert adapter.name == "gemini"
        assert adapter.display_name == "Gemini"
        assert adapter.color == "bright_yellow"
        assert adapter.icon == "🟡"


class TestOllamaAdapter:
    """Tests for Ollama adapter."""

    def test_adapter_attributes(self):
        """Ollama adapter should have correct attributes."""
        adapter = OllamaAdapter()
        assert adapter.name == "ollama"
        assert adapter.display_name == "Ollama"
        assert adapter.color == "bright_magenta"
        assert adapter.icon == "🟣"


class TestAdapterFactory:
    """Test adapter factory functions."""

    def test_get_adapter_claude(self):
        """Should return Claude adapter."""
        adapter = get_adapter("claude")
        assert isinstance(adapter, ClaudeAdapter)

    def test_get_adapter_codex(self):
        """Should return Codex adapter."""
        adapter = get_adapter("codex")
        assert isinstance(adapter, CodexAdapter)

    def test_get_adapter_gemini(self):
        """Should return Gemini adapter."""
        adapter = get_adapter("gemini")
        assert isinstance(adapter, GeminiAdapter)

    def test_get_adapter_ollama(self):
        """Should return Ollama adapter."""
        adapter = get_adapter("ollama")
        assert isinstance(adapter, OllamaAdapter)

    def test_get_adapter_case_insensitive(self):
        """Should handle case insensitive names."""
        assert isinstance(get_adapter("CLAUDE"), ClaudeAdapter)
        assert isinstance(get_adapter("Claude"), ClaudeAdapter)
        assert isinstance(get_adapter("cLaUdE"), ClaudeAdapter)

    def test_get_adapter_invalid(self):
        """Should raise for invalid adapter name."""
        with pytest.raises(ValueError) as exc:
            get_adapter("invalid")
        assert "Unknown adapter" in str(exc.value)
        assert "invalid" in str(exc.value)

    def test_get_all_adapters(self):
        """Should return all adapters."""
        adapters = get_all_adapters()
        assert len(adapters) == 4
        names = {a.name for a in adapters}
        assert names == {"claude", "codex", "gemini", "ollama"}


class TestAdapterConfig:
    """Test adapter configuration."""

    def test_default_values(self):
        """Config should have sensible defaults."""
        config = AdapterConfig()
        assert config.timeout == 60
        assert config.max_tokens == 4096
        assert config.model is None
        assert config.endpoint is None
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.extra == {}

    def test_custom_values(self):
        """Config should accept custom values."""
        config = AdapterConfig(
            timeout=120,
            max_tokens=16384,
            model="gpt-4",
            endpoint="http://custom.api",
            max_retries=5,
            retry_delay=2.0,
            extra={"custom": "value"},
        )
        assert config.timeout == 120
        assert config.max_tokens == 16384
        assert config.model == "gpt-4"
        assert config.endpoint == "http://custom.api"
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.extra["custom"] == "value"


class TestAdapterResponse:
    """Test adapter response dataclass."""

    def test_minimal_response(self):
        """Response should work with just content."""
        response = AdapterResponse(content="Hello")
        assert response.content == "Hello"
        assert response.model is None
        assert response.tokens_used is None
        assert response.elapsed_time is None
        assert response.raw_response is None

    def test_full_response(self):
        """Response should accept all fields."""
        response = AdapterResponse(
            content="Test content",
            model="claude-3",
            tokens_used=100,
            elapsed_time=1.5,
            raw_response={"raw": "data"},
        )
        assert response.content == "Test content"
        assert response.model == "claude-3"
        assert response.tokens_used == 100
        assert response.elapsed_time == 1.5
        assert response.raw_response == {"raw": "data"}


class TestAdapterErrors:
    """Test adapter error classes."""

    def test_base_error(self):
        """AdapterError should be base class."""
        err = AdapterError("Base error")
        assert str(err) == "Base error"

    def test_timeout_error(self):
        """AdapterTimeoutError should inherit from AdapterError."""
        err = AdapterTimeoutError("Timeout!")
        assert isinstance(err, AdapterError)
        assert str(err) == "Timeout!"

    def test_not_available_error(self):
        """AdapterNotAvailableError should inherit from AdapterError."""
        err = AdapterNotAvailableError("Not available")
        assert isinstance(err, AdapterError)

    def test_connection_error(self):
        """AdapterConnectionError should inherit from AdapterError."""
        err = AdapterConnectionError("Connection failed")
        assert isinstance(err, AdapterError)

    def test_rate_limit_error(self):
        """AdapterRateLimitError should inherit from AdapterError."""
        err = AdapterRateLimitError("Rate limited")
        assert isinstance(err, AdapterError)


class TestAdapterRepr:
    """Test adapter string representation."""

    def test_claude_repr(self):
        """Claude adapter repr should be informative."""
        adapter = ClaudeAdapter()
        assert "ClaudeAdapter" in repr(adapter)
        assert "claude" in repr(adapter)

    def test_codex_repr(self):
        """Codex adapter repr should be informative."""
        adapter = CodexAdapter()
        assert "CodexAdapter" in repr(adapter)


class TestAdapterRegistry:
    """Test adapter registry."""

    def test_registry_contains_all(self):
        """Registry should contain all adapters."""
        assert "claude" in ADAPTERS
        assert "codex" in ADAPTERS
        assert "gemini" in ADAPTERS
        assert "ollama" in ADAPTERS

    def test_registry_values_are_classes(self):
        """Registry values should be adapter classes."""
        for name, cls in ADAPTERS.items():
            assert issubclass(cls, AIAdapter)


class TestAdapterSendAndWait:
    """Test send_and_wait method."""

    @pytest.mark.asyncio
    async def test_send_and_wait_combines_chunks(self):
        """send_and_wait should combine streaming chunks."""
        adapter = ClaudeAdapter()

        async def mock_send(prompt):
            yield "Hello, "
            yield "world!"

        with patch.object(adapter, "send", mock_send):
            response = await adapter.send_and_wait("test")
            assert response.content == "Hello, world!"
            assert response.elapsed_time is not None


class TestAdapterHealthCheck:
    """Test health check method."""

    @pytest.mark.asyncio
    async def test_health_check_available(self):
        """Health check should report available status."""
        adapter = ClaudeAdapter()

        with patch.object(adapter, "is_available", return_value=True):
            with patch.object(adapter, "get_version", return_value="1.0.0"):
                health = await adapter.health_check()

                assert health["name"] == "claude"
                assert health["available"] is True
                assert health["version"] == "1.0.0"
                assert health["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_check_error(self):
        """Health check should handle errors."""
        adapter = ClaudeAdapter()

        with patch.object(
            adapter, "is_available", side_effect=Exception("Check failed")
        ):
            health = await adapter.health_check()

            assert health["available"] is False
            assert health["status"] == "error"
            assert "error" in health


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
