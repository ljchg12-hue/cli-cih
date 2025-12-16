"""MCP-specific exception classes for CLI-CIH."""


class MCPError(Exception):
    """MCP 기본 예외."""

    pass


class MCPTimeoutError(MCPError):
    """MCP 타임아웃 예외."""

    pass


class MCPValidationError(MCPError):
    """MCP 입력 검증 예외."""

    pass


class MCPAdapterError(MCPError):
    """MCP 어댑터 호출 예외."""

    pass


class MCPGatewayError(MCPError):
    """Docker Gateway 연결 예외."""

    pass
