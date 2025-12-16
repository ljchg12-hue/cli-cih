"""Integration tests for CLI-CIH.

Tests the complete flow from adapters through discussion to history storage.
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Test imports
from cli_cih import __version__
from cli_cih.adapters import (
    AIAdapter,
    AdapterConfig,
    AdapterResponse,
    AdapterError,
    AdapterTimeoutError,
    AdapterNotAvailableError,
    AdapterConnectionError,
    AdapterRateLimitError,
    get_adapter,
    get_all_adapters,
    ADAPTERS,
    ClaudeAdapter,
    CodexAdapter,
    GeminiAdapter,
    OllamaAdapter,
)
from cli_cih.storage.models import (
    Session,
    HistoryMessage,
    SessionResult,
    SessionStatus,
    SenderType,
)
from cli_cih.storage.history import HistoryStorage
from cli_cih.utils.retry import (
    RetryConfig,
    retry_async,
    with_retry,
    CircuitBreaker,
    CircuitBreakerOpenError,
    format_error_message,
    calculate_delay,
)
from cli_cih.utils.logging import setup_logging, get_logger


class TestVersion:
    """Test version information."""

    def test_version_exists(self):
        """Version should be defined."""
        assert __version__ is not None
        assert isinstance(__version__, str)

    def test_version_format(self):
        """Version should follow semantic versioning."""
        parts = __version__.split(".")
        assert len(parts) >= 2
        assert all(part.isdigit() for part in parts[:2])


class TestAdapterRegistry:
    """Test adapter registry functionality."""

    def test_all_adapters_registered(self):
        """All expected adapters should be registered."""
        assert "claude" in ADAPTERS
        assert "codex" in ADAPTERS
        assert "gemini" in ADAPTERS
        assert "ollama" in ADAPTERS

    def test_get_adapter_valid(self):
        """Should return adapter instance for valid name."""
        adapter = get_adapter("claude")
        assert isinstance(adapter, ClaudeAdapter)

        adapter = get_adapter("CLAUDE")  # Case insensitive
        assert isinstance(adapter, ClaudeAdapter)

    def test_get_adapter_invalid(self):
        """Should raise ValueError for invalid adapter name."""
        with pytest.raises(ValueError) as exc:
            get_adapter("nonexistent")
        assert "Unknown adapter" in str(exc.value)

    def test_get_all_adapters(self):
        """Should return all adapter instances."""
        adapters = get_all_adapters()
        assert len(adapters) == 4
        assert all(isinstance(a, AIAdapter) for a in adapters)


class TestAdapterConfig:
    """Test adapter configuration."""

    def test_default_config(self):
        """Default config should have sensible values."""
        config = AdapterConfig()
        assert config.timeout == 60
        assert config.max_tokens == 4096
        assert config.max_retries == 3
        assert config.retry_delay == 1.0

    def test_custom_config(self):
        """Custom config values should be applied."""
        config = AdapterConfig(
            timeout=120,
            max_tokens=8192,
            model="custom-model",
            max_retries=5,
        )
        assert config.timeout == 120
        assert config.max_tokens == 8192
        assert config.model == "custom-model"
        assert config.max_retries == 5


class TestAdapterBase:
    """Test base adapter functionality."""

    def test_adapter_attributes(self):
        """Adapters should have required attributes."""
        for adapter_cls in ADAPTERS.values():
            adapter = adapter_cls()
            assert hasattr(adapter, "name")
            assert hasattr(adapter, "display_name")
            assert hasattr(adapter, "color")
            assert hasattr(adapter, "icon")

    def test_adapter_config_initialization(self):
        """Adapters should initialize with config."""
        config = AdapterConfig(timeout=90)
        adapter = ClaudeAdapter(config=config)
        assert adapter.config.timeout == 90

    def test_format_error_connection(self):
        """Error formatting for connection errors."""
        adapter = ClaudeAdapter()
        msg = adapter._format_error(Exception("connection refused"))
        assert "not reachable" in msg.lower() or "connection" in msg.lower()

    def test_format_error_timeout(self):
        """Error formatting for timeout errors."""
        adapter = ClaudeAdapter()
        msg = adapter._format_error(Exception("request timeout"))
        assert "timeout" in msg.lower() or "long" in msg.lower()


class TestAdapterResponse:
    """Test adapter response dataclass."""

    def test_response_creation(self):
        """Response should be created with required fields."""
        response = AdapterResponse(content="Hello, world!")
        assert response.content == "Hello, world!"
        assert response.model is None
        assert response.tokens_used is None

    def test_response_with_metadata(self):
        """Response should include metadata."""
        response = AdapterResponse(
            content="Test response",
            model="gpt-4",
            tokens_used=100,
            elapsed_time=1.5,
        )
        assert response.model == "gpt-4"
        assert response.tokens_used == 100
        assert response.elapsed_time == 1.5


class TestHistoryModels:
    """Test history data models."""

    def test_session_creation(self):
        """Session should be created with required fields."""
        session = Session(
            id="test-123",
            user_query="Test query",
            task_type="general",
            participating_ais=["claude", "gemini"],
        )
        assert session.id == "test-123"
        assert session.user_query == "Test query"
        assert session.status == SessionStatus.IN_PROGRESS
        assert len(session.participating_ais) == 2

    def test_session_add_message(self):
        """Session should track messages."""
        session = Session(
            id="test-123",
            user_query="Test",
            task_type="general",
            participating_ais=["claude"],
        )
        session.add_message(
            sender_type=SenderType.AI,
            sender_id="claude",
            content="Response text",
        )
        assert len(session.messages) == 1
        assert session.messages[0].sender_id == "claude"
        assert session.messages[0].content == "Response text"

    def test_session_set_result(self):
        """Session should store result."""
        session = Session(
            id="test-123",
            user_query="Test",
            task_type="general",
            participating_ais=["claude"],
        )
        session.set_result(
            summary="The answer is 42",
            consensus_reached=True,
            confidence=0.95,
        )
        assert session.result is not None
        assert session.result.summary == "The answer is 42"
        assert session.result.consensus_reached is True
        assert session.status == SessionStatus.COMPLETED

    def test_session_mark_error(self):
        """Session should handle error state."""
        session = Session(
            id="test-123",
            user_query="Test",
            task_type="general",
            participating_ais=["claude"],
        )
        session.mark_error("Connection failed")
        assert session.status == SessionStatus.ERROR
        # Error is stored as a system message
        assert len(session.messages) == 1
        assert "Connection failed" in session.messages[0].content

    def test_history_message_creation(self):
        """HistoryMessage should store message data."""
        msg = HistoryMessage(
            id="msg-001",
            session_id="session-001",
            sender_type=SenderType.USER,
            sender_id="user",
            content="Hello!",
            round_num=1,
        )
        assert msg.sender_id == "user"
        assert msg.sender_type == SenderType.USER
        assert msg.content == "Hello!"


class TestHistoryStorage:
    """Test history storage operations."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def storage(self, temp_db):
        """Create storage with temp database."""
        return HistoryStorage(db_path=temp_db)

    @pytest.mark.asyncio
    async def test_save_and_get_session(self, storage):
        """Should save and retrieve session."""
        session = Session(
            id="test-save-001",
            user_query="Test query for save",
            task_type="testing",
            participating_ais=["claude"],
        )
        session.add_message(SenderType.USER, "user", "User message")
        session.add_message(SenderType.AI, "claude", "AI response")
        session.set_result("Final answer", consensus_reached=True, confidence=0.9)

        # Save
        session_id = await storage.save_session(session)
        assert session_id == "test-save-001"

        # Retrieve
        retrieved = await storage.get_session(session_id)
        assert retrieved is not None
        assert retrieved.id == session_id
        assert retrieved.user_query == "Test query for save"
        assert len(retrieved.messages) == 2
        assert retrieved.result is not None

    @pytest.mark.asyncio
    async def test_get_recent(self, storage):
        """Should retrieve recent sessions."""
        # Create multiple sessions
        for i in range(5):
            session = Session(
                id=f"recent-{i}",
                user_query=f"Query {i}",
                task_type="test",
                participating_ais=["claude"],
            )
            await storage.save_session(session)

        recent = await storage.get_recent(limit=3)
        assert len(recent) == 3

    @pytest.mark.asyncio
    async def test_search(self, storage):
        """Should search sessions by query."""
        session = Session(
            id="search-test",
            user_query="Python programming language",
            task_type="coding",
            participating_ais=["claude"],
        )
        await storage.save_session(session)

        results = await storage.search("Python")
        assert len(results) >= 1
        assert any(s.id == "search-test" for s in results)

    @pytest.mark.asyncio
    async def test_delete_session(self, storage):
        """Should delete session."""
        session = Session(
            id="delete-test",
            user_query="To be deleted",
            task_type="test",
            participating_ais=["claude"],
        )
        await storage.save_session(session)

        success = await storage.delete_session("delete-test")
        assert success is True

        retrieved = await storage.get_session("delete-test")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_export_markdown(self, storage):
        """Should export session as markdown."""
        session = Session(
            id="export-md",
            user_query="Export test",
            task_type="test",
            participating_ais=["claude"],
        )
        session.add_message(SenderType.USER, "user", "Hello")
        session.add_message(SenderType.AI, "claude", "Hi there!")
        await storage.save_session(session)

        md = await storage.export_session("export-md", format="md")
        assert md is not None
        assert "Export test" in md
        assert "Hello" in md
        assert "Hi there!" in md

    @pytest.mark.asyncio
    async def test_export_json(self, storage):
        """Should export session as JSON."""
        session = Session(
            id="export-json",
            user_query="JSON test",
            task_type="test",
            participating_ais=["claude"],
        )
        await storage.save_session(session)

        json_str = await storage.export_session("export-json", format="json")
        assert json_str is not None
        import json
        data = json.loads(json_str)
        assert data["id"] == "export-json"

    @pytest.mark.asyncio
    async def test_get_stats(self, storage):
        """Should return statistics."""
        # Add some sessions
        for i in range(3):
            session = Session(
                id=f"stats-{i}",
                user_query=f"Stats query {i}",
                task_type="test",
                participating_ais=["claude", "gemini"],
            )
            if i == 2:
                session.set_result("Answer", True, 0.8)
            await storage.save_session(session)

        stats = await storage.get_stats()
        assert "total_sessions" in stats
        assert stats["total_sessions"] >= 3


class TestRetryUtilities:
    """Test retry and error handling utilities."""

    def test_retry_config_defaults(self):
        """RetryConfig should have sensible defaults."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0
        assert config.jitter is True

    def test_calculate_delay_exponential(self):
        """Delay should grow exponentially."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)

        delay0 = calculate_delay(0, config)
        delay1 = calculate_delay(1, config)
        delay2 = calculate_delay(2, config)

        assert delay0 == 1.0
        assert delay1 == 2.0
        assert delay2 == 4.0

    def test_calculate_delay_max_cap(self):
        """Delay should be capped at max_delay."""
        config = RetryConfig(base_delay=10.0, max_delay=15.0, jitter=False)
        delay = calculate_delay(5, config)  # Would be 320 without cap
        assert delay == 15.0

    @pytest.mark.asyncio
    async def test_retry_async_success(self):
        """Should succeed on first try."""
        async def success_func():
            return "success"

        result = await retry_async(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_async_eventual_success(self):
        """Should retry and eventually succeed."""
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        config = RetryConfig(
            max_retries=3,
            base_delay=0.01,
            retry_on=(ConnectionError,),
        )
        result = await retry_async(flaky_func, config=config)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_async_all_failures(self):
        """Should raise after all retries exhausted."""
        async def always_fail():
            raise ConnectionError("Always fails")

        config = RetryConfig(
            max_retries=2,
            base_delay=0.01,
            retry_on=(ConnectionError,),
        )

        with pytest.raises(ConnectionError):
            await retry_async(always_fail, config=config)


class TestCircuitBreaker:
    """Test circuit breaker pattern."""

    def test_initial_state_closed(self):
        """Circuit should start closed."""
        cb = CircuitBreaker()
        assert cb.state == "closed"
        assert cb.can_execute() is True

    def test_opens_after_failures(self):
        """Circuit should open after failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)

        for _ in range(3):
            cb.record_failure()

        assert cb.state == "open"
        assert cb.can_execute() is False

    def test_success_resets_failures(self):
        """Success should reset failure count."""
        cb = CircuitBreaker(failure_threshold=5)

        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"

        cb.record_success()
        # Failure count should be reset
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_execute_with_circuit_breaker(self):
        """Should execute function when circuit closed."""
        cb = CircuitBreaker()

        async def success_func():
            return "result"

        result = await cb.execute(success_func)
        assert result == "result"

    @pytest.mark.asyncio
    async def test_execute_raises_when_open(self):
        """Should raise when circuit is open."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        cb.record_failure()  # Opens circuit

        async def any_func():
            return "result"

        with pytest.raises(CircuitBreakerOpenError):
            await cb.execute(any_func)


class TestErrorFormatting:
    """Test error message formatting."""

    def test_connection_error(self):
        """Should format connection errors."""
        msg = format_error_message(Exception("connection refused"), "Claude")
        assert "connection" in msg.lower()

    def test_timeout_error(self):
        """Should format timeout errors."""
        msg = format_error_message(Exception("request timeout"), "Gemini")
        assert "timeout" in msg.lower() or "slow" in msg.lower()

    def test_auth_error(self):
        """Should format authentication errors."""
        msg = format_error_message(Exception("authentication failed"), "Codex")
        assert "authentication" in msg.lower() or "credential" in msg.lower()

    def test_rate_limit_error(self):
        """Should format rate limit errors."""
        msg = format_error_message(Exception("rate limit exceeded"))
        assert "rate" in msg.lower() or "wait" in msg.lower()

    def test_generic_error(self):
        """Should format generic errors."""
        msg = format_error_message(ValueError("Something went wrong"), "Test")
        assert "ValueError" in msg
        assert "Something went wrong" in msg


class TestLogging:
    """Test logging utilities."""

    def test_get_logger(self):
        """Should return logger instance."""
        logger = get_logger("test.module")
        assert logger is not None
        assert logger.name == "test.module"

    def test_setup_logging(self):
        """Should configure logging without errors."""
        # Should not raise
        setup_logging(level="DEBUG")


class TestExceptionHierarchy:
    """Test exception class hierarchy."""

    def test_adapter_error_base(self):
        """AdapterError should be base exception."""
        assert issubclass(AdapterTimeoutError, AdapterError)
        assert issubclass(AdapterNotAvailableError, AdapterError)
        assert issubclass(AdapterConnectionError, AdapterError)
        assert issubclass(AdapterRateLimitError, AdapterError)

    def test_exception_messages(self):
        """Exceptions should preserve messages."""
        msg = "Custom error message"
        err = AdapterTimeoutError(msg)
        assert str(err) == msg


class TestWithRetryDecorator:
    """Test retry decorator."""

    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """Decorated function should work normally."""
        @with_retry(max_retries=1, base_delay=0.01)
        async def decorated_func():
            return "decorated"

        result = await decorated_func()
        assert result == "decorated"

    @pytest.mark.asyncio
    async def test_decorator_retry(self):
        """Decorated function should retry on failure."""
        call_count = 0

        @with_retry(max_retries=2, base_delay=0.01, retry_on=(ValueError,))
        async def flaky_decorated():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry me")
            return "success"

        result = await flaky_decorated()
        assert result == "success"
        assert call_count == 2


class TestSessionStatus:
    """Test session status enum."""

    def test_status_values(self):
        """All expected status values should exist."""
        assert SessionStatus.IN_PROGRESS is not None
        assert SessionStatus.COMPLETED is not None
        assert SessionStatus.CANCELLED is not None
        assert SessionStatus.ERROR is not None


class TestSenderType:
    """Test sender type enum."""

    def test_sender_types(self):
        """All expected sender types should exist."""
        assert SenderType.USER is not None
        assert SenderType.AI is not None
        assert SenderType.SYSTEM is not None


# Integration test combining multiple components
class TestEndToEndFlow:
    """End-to-end integration tests."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_full_session_flow(self, temp_db):
        """Test complete session from creation to export."""
        storage = HistoryStorage(db_path=temp_db)

        # 1. Create session
        session = Session(
            id="e2e-test-001",
            user_query="What is the meaning of life?",
            task_type="philosophy",
            participating_ais=["claude", "gemini"],
        )

        # 2. Add conversation
        session.add_message(SenderType.USER, "user", "What is the meaning of life?")
        session.add_message(
            SenderType.AI,
            "claude",
            "The meaning of life is a profound question...",
            round_num=1,
        )
        session.add_message(
            SenderType.AI,
            "gemini",
            "I agree with Claude, and would add...",
            round_num=1,
        )

        # 3. Set result with consensus
        session.set_result(
            summary="Life's meaning is subjective and personal.",
            consensus_reached=True,
            confidence=0.85,
        )

        # 4. Save to storage
        await storage.save_session(session)

        # 5. Verify retrieval
        retrieved = await storage.get_session("e2e-test-001")
        assert retrieved is not None
        assert retrieved.status == SessionStatus.COMPLETED
        assert len(retrieved.messages) == 3
        assert retrieved.result.consensus_reached is True

        # 6. Verify search
        results = await storage.search("meaning of life")
        assert len(results) >= 1

        # 7. Verify export
        md_export = await storage.export_session("e2e-test-001", "md")
        assert "meaning of life" in md_export.lower()
        assert "claude" in md_export.lower()

        # 8. Verify stats
        stats = await storage.get_stats()
        assert stats["total_sessions"] >= 1

    @pytest.mark.asyncio
    async def test_error_recovery_flow(self, temp_db):
        """Test error handling in session flow."""
        storage = HistoryStorage(db_path=temp_db)

        # Create session that will fail
        session = Session(
            id="error-test-001",
            user_query="Test error handling",
            task_type="test",
            participating_ais=["claude"],
        )

        # Mark as error
        session.mark_error("Simulated connection failure")

        await storage.save_session(session)

        # Verify error state is preserved
        retrieved = await storage.get_session("error-test-001")
        assert retrieved.status == SessionStatus.ERROR
        # Error message is stored in a system message
        assert len(retrieved.messages) >= 1
        assert any("connection failure" in m.content.lower() for m in retrieved.messages)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
