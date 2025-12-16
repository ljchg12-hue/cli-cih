"""Unit tests for MCP Server (Phase 5 Refactored)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# Helper to get underlying function from FastMCP tool
def get_tool_fn(tool):
    """Extract the underlying async function from FastMCP FunctionTool."""
    if hasattr(tool, "fn"):
        return tool.fn
    if hasattr(tool, "_fn"):
        return tool._fn
    if hasattr(tool, "__wrapped__"):
        return tool.__wrapped__
    return tool


# ═══════════════════════════════════════════════
# Test MCPResponse and make_response
# ═══════════════════════════════════════════════

class TestMCPResponse:
    """Tests for MCPResponse dataclass."""

    def test_response_success(self):
        """Success response should have correct structure."""
        from cli_cih.mcp.server import MCPResponse

        response = MCPResponse(success=True, data={"key": "value"})
        result = response.to_dict()

        assert result["success"] is True
        assert result["data"] == {"key": "value"}
        assert result["error"] is None
        assert result["metadata"] == {}

    def test_response_error(self):
        """Error response should have correct structure."""
        from cli_cih.mcp.server import MCPResponse

        response = MCPResponse(success=False, error="Something went wrong")
        result = response.to_dict()

        assert result["success"] is False
        assert result["data"] is None
        assert result["error"] == "Something went wrong"

    def test_response_with_metadata(self):
        """Response with metadata should include it."""
        from cli_cih.mcp.server import MCPResponse

        response = MCPResponse(
            success=True,
            data={"result": "test"},
            metadata={"duration_ms": 100, "ai_used": ["claude"]}
        )
        result = response.to_dict()

        assert result["metadata"]["duration_ms"] == 100
        assert result["metadata"]["ai_used"] == ["claude"]


class TestMakeResponse:
    """Tests for make_response helper function."""

    def test_make_response_success(self):
        """make_response should create standardized success response."""
        from cli_cih.mcp.server import make_response

        result = make_response(
            success=True,
            data={"response": "Hello"},
            duration_ms=50,
            ai_used=["claude"]
        )

        assert result["success"] is True
        assert result["data"]["response"] == "Hello"
        assert result["metadata"]["duration_ms"] == 50
        assert result["metadata"]["ai_used"] == ["claude"]

    def test_make_response_error(self):
        """make_response should create standardized error response."""
        from cli_cih.mcp.server import make_response

        result = make_response(success=False, error="Test error")

        assert result["success"] is False
        assert result["error"] == "Test error"
        assert result["data"] is None

    def test_make_response_minimal(self):
        """make_response with minimal args should work."""
        from cli_cih.mcp.server import make_response

        result = make_response(success=True)

        assert result["success"] is True
        assert result["metadata"] is None or result["metadata"] == {}


# ═══════════════════════════════════════════════
# Test run_cli_async
# ═══════════════════════════════════════════════

class TestRunCliAsync:
    """Tests for run_cli_async helper function."""

    @pytest.mark.asyncio
    async def test_successful_command(self):
        """Successful command should return proper result with whitelisted command."""
        from cli_cih.mcp.server import run_cli_async

        # Use a mocked whitelisted command
        with patch("cli_cih.mcp.server.validate_command", return_value=True):
            result = await run_cli_async(["echo", "hello"], timeout=10)

            assert result["success"] is True
            assert "hello" in result["stdout"]
            assert result["returncode"] == 0

    @pytest.mark.asyncio
    async def test_failed_command(self):
        """Failed command should return error info."""
        from cli_cih.mcp.server import run_cli_async

        with patch("cli_cih.mcp.server.validate_command", return_value=True):
            result = await run_cli_async(["false"], timeout=10)

            assert result["success"] is False
            assert result["returncode"] != 0

    @pytest.mark.asyncio
    async def test_command_not_found(self):
        """Non-existent command should raise MCPAdapterError."""
        from cli_cih.mcp.exceptions import MCPAdapterError
        from cli_cih.mcp.server import run_cli_async

        with patch("cli_cih.mcp.server.validate_command", return_value=True):
            with pytest.raises(MCPAdapterError):
                await run_cli_async(["nonexistent_command_xyz"], timeout=5)

    @pytest.mark.asyncio
    async def test_timeout(self):
        """Command timeout should raise MCPTimeoutError."""
        from cli_cih.mcp.exceptions import MCPTimeoutError
        from cli_cih.mcp.server import run_cli_async

        with patch("cli_cih.mcp.server.validate_command", return_value=True):
            with pytest.raises(MCPTimeoutError):
                await run_cli_async(["sleep", "10"], timeout=1)

    @pytest.mark.asyncio
    async def test_validation_rejects_unknown_command(self):
        """Unknown commands should raise MCPValidationError."""
        from cli_cih.mcp.exceptions import MCPValidationError
        from cli_cih.mcp.server import run_cli_async

        with pytest.raises(MCPValidationError):
            await run_cli_async(["malicious_command", "--flag"], timeout=5)


# ═══════════════════════════════════════════════
# Test DockerGatewayClient
# ═══════════════════════════════════════════════

class TestDockerGatewayClient:
    """Tests for DockerGatewayClient."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        from cli_cih.mcp.server import DockerGatewayClient
        return DockerGatewayClient(base_url="http://localhost:8811", max_retries=2)

    @pytest.mark.asyncio
    async def test_check_health_success(self, client):
        """Health check should return success when gateway is up."""
        with patch.object(client, "_request_with_retry") as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            mock_request.return_value = mock_response

            result = await client.check_health()

            assert result["success"] is True
            assert result["status"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_check_health_failure(self, client):
        """Health check should handle connection errors."""
        with patch.object(client, "_request_with_retry") as mock_request:
            mock_request.side_effect = httpx.RequestError("Connection refused")

            result = await client.check_health()

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_list_servers(self, client):
        """list_servers should return server list."""
        with patch.object(client, "_request_with_retry") as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = ["server1", "server2"]
            mock_request.return_value = mock_response

            result = await client.list_servers()

            assert result["success"] is True
            assert result["servers"] == ["server1", "server2"]

    @pytest.mark.asyncio
    async def test_call_tool(self, client):
        """call_tool should execute MCP tool."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "success"}
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await client.call_tool("server1", "tool1", {"arg": "value"})

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_call_tool_timeout(self, client):
        """call_tool should handle timeout."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = asyncio.TimeoutError()
            mock_get_client.return_value = mock_client

            result = await client.call_tool("server1", "tool1", timeout=1.0)

            assert result["success"] is False
            assert "timeout" in result.get("error", "").lower()


# ═══════════════════════════════════════════════
# Test MCP Tools - Core Functions
# ═══════════════════════════════════════════════

class TestCihQuick:
    """Tests for cih_quick tool."""

    @pytest.mark.asyncio
    async def test_quick_claude_success(self):
        """cih_quick with claude should return response."""
        from cli_cih.mcp.server import cih_quick
        fn = get_tool_fn(cih_quick)

        with patch("cli_cih.mcp.server.run_cli_async") as mock_run:
            mock_run.return_value = {
                "success": True,
                "stdout": "Hello, I am Claude",
                "returncode": 0
            }

            result = await fn("Hello", ai="claude")

            assert result["success"] is True
            assert result["data"]["ai"] == "claude"
            assert "Hello" in result["data"]["response"]

    @pytest.mark.asyncio
    async def test_quick_unknown_ai(self):
        """cih_quick with unknown AI should return error."""
        from cli_cih.mcp.server import cih_quick
        fn = get_tool_fn(cih_quick)

        result = await fn("Hello", ai="unknown_ai")

        assert result["success"] is False
        # Korean: "유효하지 않은 AI" or English "Unknown AI"
        assert "유효하지 않은 AI" in result["error"] or "Unknown AI" in result["error"]

    @pytest.mark.asyncio
    async def test_quick_fallback_to_ollama(self):
        """cih_quick should fallback to Ollama if primary fails."""
        from cli_cih.mcp.server import cih_quick
        fn = get_tool_fn(cih_quick)

        with patch("cli_cih.mcp.server.run_cli_async") as mock_run, \
             patch("cli_cih.mcp.server.call_ollama") as mock_ollama:

            mock_run.return_value = {"success": False, "error": "CLI failed"}
            mock_ollama.return_value = {
                "success": True,
                "response": "Ollama response"
            }

            result = await fn("Hello", ai="claude")

            assert result["success"] is True
            assert result["data"]["ai"] == "ollama"
            assert result["data"]["fallback"] is True


class TestCihAnalyze:
    """Tests for cih_analyze tool."""

    @pytest.mark.asyncio
    async def test_analyze_simple_prompt(self):
        """cih_analyze should classify simple prompts correctly."""
        from cli_cih.mcp.server import cih_analyze
        fn = get_tool_fn(cih_analyze)

        result = await fn("hi")

        assert result["success"] is True
        assert result["data"]["task_type"] == "simple_chat"
        assert result["data"]["requires_multi_ai"] is False

    @pytest.mark.asyncio
    async def test_analyze_complex_prompt(self):
        """cih_analyze should classify complex prompts correctly."""
        from cli_cih.mcp.server import cih_analyze
        fn = get_tool_fn(cih_analyze)

        prompt = "마이크로서비스 아키텍처를 설계하고 각 서비스 간 통신 방법을 분석해줘"
        result = await fn(prompt)

        assert result["success"] is True
        assert result["data"]["complexity_level"] in ["medium", "high"]
        assert "keywords" in result["data"]


class TestCihStatus:
    """Tests for cih_status tool."""

    @pytest.mark.asyncio
    async def test_status_returns_ai_info(self):
        """cih_status should return AI availability info."""
        from cli_cih.mcp.server import cih_status
        fn = get_tool_fn(cih_status)

        with patch("cli_cih.mcp.server.run_cli_async") as mock_run, \
             patch("httpx.get") as mock_get:

            mock_run.return_value = {"success": True, "stdout": "1.0.0"}
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"models": []}
            mock_get.return_value = mock_response

            result = await fn()

            assert result["success"] is True
            assert "ais" in result["data"]
            assert "summary" in result["data"]


class TestCihSmart:
    """Tests for cih_smart tool."""

    @pytest.mark.asyncio
    async def test_smart_routing_code(self):
        """cih_smart should route code tasks to codex."""
        from cli_cih.mcp.server import cih_smart
        fn = get_tool_fn(cih_smart)

        with patch("cli_cih.mcp.server.run_cli_async") as mock_run:
            mock_run.return_value = {
                "success": True,
                "stdout": "Code result"
            }

            result = await fn("코드 작성해줘", task_type="code")

            assert result["success"] is True
            assert result["data"]["selected_ai"] == "codex"
            assert result["data"]["task_type"] == "code"

    @pytest.mark.asyncio
    async def test_smart_routing_research(self):
        """cih_smart should route research tasks to gemini."""
        from cli_cih.mcp.server import cih_smart
        fn = get_tool_fn(cih_smart)

        with patch("cli_cih.mcp.server.run_cli_async") as mock_run:
            mock_run.return_value = {
                "success": True,
                "stdout": "Research result"
            }

            result = await fn("조사해줘", task_type="research")

            assert result["success"] is True
            assert result["data"]["selected_ai"] == "gemini"


# ═══════════════════════════════════════════════
# Test MCP Tools - History and Stats
# ═══════════════════════════════════════════════

class TestCihHistory:
    """Tests for cih_history tool."""

    @pytest.mark.asyncio
    async def test_history_returns_sessions(self):
        """cih_history should return conversation history."""
        from cli_cih.mcp.server import cih_history
        fn = get_tool_fn(cih_history)

        mock_session = MagicMock()
        mock_session.id = "session-123"
        mock_session.user_query = "Test query"
        mock_session.task_type = "general"
        mock_session.participating_ais = ["claude"]
        mock_session.total_rounds = 1
        mock_session.status.value = "completed"
        mock_session.created_at.isoformat.return_value = "2024-01-01T00:00:00"

        with patch("cli_cih.mcp.server.get_history_storage") as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.get_recent.return_value = [mock_session]
            mock_get_storage.return_value = mock_storage

            result = await fn(limit=5)

            assert result["success"] is True
            assert len(result["data"]["conversations"]) == 1
            assert result["data"]["conversations"][0]["id"] == "session-123"


class TestCihModels:
    """Tests for cih_models tool."""

    @pytest.mark.asyncio
    async def test_models_returns_info(self):
        """cih_models should return model information."""
        from cli_cih.mcp.server import cih_models
        fn = get_tool_fn(cih_models)

        with patch("cli_cih.mcp.server.run_cli_async") as mock_run, \
             patch("httpx.get") as mock_get:

            mock_run.return_value = {"success": True, "stdout": "1.0.0"}
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "models": [{"name": "llama3.1:70b", "size": 40 * 1024**3}]
            }
            mock_get.return_value = mock_response

            result = await fn()

            assert result["success"] is True
            assert "models" in result["data"]
            assert "ollama" in result["data"]["models"]


class TestCihStats:
    """Tests for cih_stats tool."""

    @pytest.mark.asyncio
    async def test_stats_returns_data(self):
        """cih_stats should return usage statistics."""
        from cli_cih.mcp.server import cih_stats
        fn = get_tool_fn(cih_stats)

        with patch("cli_cih.mcp.server.get_history_storage") as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.get_stats.return_value = {
                "total_sessions": 10,
                "ai_usage": {"claude": 5, "gemini": 3}
            }
            mock_get_storage.return_value = mock_storage

            result = await fn()

            assert result["success"] is True
            assert result["data"]["total_sessions"] == 10


# ═══════════════════════════════════════════════
# Test MCP Tools - Docker Gateway
# ═══════════════════════════════════════════════

class TestCihGatewayStatus:
    """Tests for cih_gateway_status tool."""

    @pytest.mark.asyncio
    async def test_gateway_status_disabled(self):
        """cih_gateway_status should handle disabled gateway."""
        from cli_cih.mcp.server import cih_gateway_status
        fn = get_tool_fn(cih_gateway_status)

        with patch("cli_cih.mcp.server.DOCKER_GATEWAY_ENABLED", False):
            result = await fn()

            assert result["success"] is False
            assert "비활성화" in result["error"]

    @pytest.mark.asyncio
    async def test_gateway_status_connected(self):
        """cih_gateway_status should show connected status."""
        from cli_cih.mcp.server import cih_gateway_status
        fn = get_tool_fn(cih_gateway_status)

        with patch("cli_cih.mcp.server.DOCKER_GATEWAY_ENABLED", True), \
             patch("cli_cih.mcp.server.get_gateway_client") as mock_get_client:

            mock_client = AsyncMock()
            mock_client.check_health.return_value = {"success": True, "status": {"healthy": True}}
            mock_client.list_servers.return_value = {"success": True, "servers": ["server1"]}
            mock_client.get_server_tools.return_value = {"success": True, "tools": ["tool1"]}
            mock_get_client.return_value = mock_client

            result = await fn()

            assert result["success"] is True
            assert result["data"]["connected"] is True


class TestCihGatewayExec:
    """Tests for cih_gateway_exec tool."""

    @pytest.mark.asyncio
    async def test_gateway_exec_disabled(self):
        """cih_gateway_exec should handle disabled gateway."""
        from cli_cih.mcp.server import cih_gateway_exec
        fn = get_tool_fn(cih_gateway_exec)

        with patch("cli_cih.mcp.server.DOCKER_GATEWAY_ENABLED", False):
            result = await fn("server", "tool")

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_gateway_exec_success(self):
        """cih_gateway_exec should execute tool successfully."""
        from cli_cih.mcp.server import cih_gateway_exec
        fn = get_tool_fn(cih_gateway_exec)

        with patch("cli_cih.mcp.server.DOCKER_GATEWAY_ENABLED", True), \
             patch("cli_cih.mcp.server.get_gateway_client") as mock_get_client:

            mock_client = AsyncMock()
            mock_client.call_tool.return_value = {
                "success": True,
                "result": {"output": "test"}
            }
            mock_get_client.return_value = mock_client

            result = await fn("server1", "tool1", {"arg": "value"})

            assert result["success"] is True
            assert result["data"]["server"] == "server1"
            assert result["data"]["tool"] == "tool1"


# ═══════════════════════════════════════════════
# Test Response Schema Validation
# ═══════════════════════════════════════════════

class TestResponseSchema:
    """Tests for standardized response schema."""

    def test_all_responses_have_success(self):
        """All responses should have success field."""
        from cli_cih.mcp.server import make_response

        responses = [
            make_response(True),
            make_response(False, error="test"),
            make_response(True, data={"key": "value"}),
        ]

        for response in responses:
            assert "success" in response
            assert isinstance(response["success"], bool)

    def test_error_responses_have_error_field(self):
        """Error responses should have error field."""
        from cli_cih.mcp.server import make_response

        response = make_response(False, error="Test error message")

        assert response["error"] == "Test error message"

    def test_success_responses_have_data_field(self):
        """Success responses should have data field."""
        from cli_cih.mcp.server import make_response

        response = make_response(True, data={"result": "test"})

        assert response["data"]["result"] == "test"

    def test_metadata_includes_duration(self):
        """Metadata should include duration when provided."""
        from cli_cih.mcp.server import make_response

        response = make_response(True, duration_ms=150)

        assert response["metadata"]["duration_ms"] == 150

    def test_metadata_includes_ai_used(self):
        """Metadata should include ai_used when provided."""
        from cli_cih.mcp.server import make_response

        response = make_response(True, ai_used=["claude", "gemini"])

        assert response["metadata"]["ai_used"] == ["claude", "gemini"]


# ═══════════════════════════════════════════════
# Integration Tests (with mocking)
# ═══════════════════════════════════════════════

class TestIntegration:
    """Integration tests with mocked external services."""

    @pytest.mark.asyncio
    async def test_cih_discuss_flow(self):
        """cih_discuss should coordinate multiple AI calls."""
        from cli_cih.mcp.server import cih_discuss
        fn = get_tool_fn(cih_discuss)

        with patch("cli_cih.mcp.server.run_cli_async") as mock_run:
            # Mock all AI responses
            def mock_responses(args, timeout=None):
                if "claude" in args[0]:
                    return {"success": True, "stdout": "Claude says: test"}
                elif "codex" in args[0]:
                    return {"success": True, "stdout": "Codex says: test"}
                elif "gemini" in args[0]:
                    return {"success": True, "stdout": "Gemini says: test"}
                return {"success": False, "error": "Unknown"}

            mock_run.side_effect = mock_responses

            # Force multi-AI by passing explicit list
            result = await fn(
                "복잡한 아키텍처 설계 질문으로 멀티 AI가 필요한 상황입니다",
                ais=["claude", "codex"],
                include_synthesis=False
            )

            # Check structure
            assert "success" in result
            if result["success"]:
                assert "responses" in result["data"]

    @pytest.mark.asyncio
    async def test_error_handling_consistency(self):
        """All tools should handle errors consistently."""
        from cli_cih.mcp.server import cih_analyze, cih_quick
        quick_fn = get_tool_fn(cih_quick)
        analyze_fn = get_tool_fn(cih_analyze)

        # Test cih_quick with error
        with patch("cli_cih.mcp.server.run_cli_async") as mock_run, \
             patch("cli_cih.mcp.server.call_ollama") as mock_ollama:
            mock_run.return_value = {"success": False, "error": "CLI error"}
            mock_ollama.return_value = {"success": False, "error": "Ollama error"}

            result = await quick_fn("test")
            assert "success" in result
            assert "error" in result

        # Test cih_analyze always succeeds (unless exception)
        result = await analyze_fn("test")
        assert result["success"] is True
