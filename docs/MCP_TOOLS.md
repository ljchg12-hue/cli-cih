# CLI-CIH MCP Tools Reference

This document provides comprehensive documentation for all MCP (Model Context Protocol) tools provided by CLI-CIH.

## Overview

CLI-CIH provides 17 MCP tools for multi-AI orchestration, conversation management, and Docker MCP Gateway integration.

### Response Format

All tools return a standardized response format:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "metadata": {
    "duration_ms": 150,
    "ai_used": ["claude", "gemini"]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the operation succeeded |
| `data` | object | Result data (null on error) |
| `error` | string | Error message (null on success) |
| `metadata` | object | Additional info (duration, AI used, etc.) |

---

## Core Tools

### cih_quick

Quick single AI response for simple questions.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `prompt` | string | required | User question |
| `ai` | string | `"claude"` | AI to use (claude/codex/gemini/ollama) |
| `timeout` | int | `60` | Timeout in seconds |

**Example:**

```python
result = await cih_quick("What is Python?", ai="claude")
# Returns:
# {
#   "success": true,
#   "data": {"response": "Python is a...", "ai": "claude"},
#   "metadata": {"duration_ms": 1200, "ai_used": ["claude"]}
# }
```

**Fallback Behavior:** If the primary AI fails, automatically falls back to Ollama.

---

### cih_analyze

Analyze a prompt to determine optimal AI routing.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `prompt` | string | required | Prompt to analyze |

**Response Data:**

| Field | Description |
|-------|-------------|
| `task_type` | Detected task type (code/debug/design/research/explain/general/simple_chat) |
| `complexity` | Complexity score (0.0-1.0) |
| `complexity_level` | Human-readable level (low/medium/high) |
| `keywords` | Extracted keywords (up to 5) |
| `requires_multi_ai` | Whether multi-AI discussion is recommended |
| `suggested_rounds` | Suggested discussion rounds |
| `suggested_ai_count` | Suggested number of AIs |
| `recommendation` | Recommended tool to use |

**Example:**

```python
result = await cih_analyze("Design a microservices architecture")
# Returns task analysis with design type, high complexity
```

---

### cih_discuss

Multi-AI discussion - collect and synthesize responses from multiple AIs.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `prompt` | string | required | Discussion topic/question |
| `ais` | list[str] | auto | AIs to participate (auto-selected if omitted) |
| `max_rounds` | int | `2` | Maximum discussion rounds |
| `include_synthesis` | bool | `True` | Include synthesis of responses |
| `timeout` | int | `90` | Per-AI timeout in seconds |

**Response Data:**

| Field | Description |
|-------|-------------|
| `prompt` | Original prompt |
| `task_type` | Detected task type |
| `complexity` | Complexity score |
| `participating_ais` | List of AIs that participated |
| `responses` | Dict of AI responses `{ai_name: {response, success}}` |
| `synthesis` | Combined analysis (if include_synthesis=True) |
| `errors` | Any errors encountered |

**Smart Behavior:**
- Automatically analyzes prompt complexity
- Simple questions redirect to `cih_quick`
- Complex questions trigger multi-AI discussion
- Synthesis uses Claude by default

---

### cih_compare

Compare AI responses side-by-side.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `prompt` | string | required | Question to compare |
| `ais` | list[str] | `["claude", "codex", "gemini"]` | AIs to compare |
| `timeout` | int | `90` | Per-AI timeout |

**Note:** Wrapper around `cih_discuss` with `mode: "comparison"` in response.

---

### cih_smart

Smart routing - automatically selects best AI based on task type.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `prompt` | string | required | User question |
| `task_type` | string | auto | Force specific task type |
| `timeout` | int | `90` | Timeout in seconds |

**Routing Rules:**

| Task Type | Selected AI | Reason |
|-----------|-------------|--------|
| `code` | Codex | Code-specialized |
| `debug` | Codex | Debugging expertise |
| `design` | Claude | Architecture/design focus |
| `research` | Gemini | Search/research capabilities |
| `explain` | Claude | Clear explanations |
| `general` | Claude | Broad knowledge |

**Response Data:**

```json
{
  "response": "...",
  "selected_ai": "codex",
  "task_type": "code",
  "routing_reason": "Code-specialized"
}
```

---

### cih_status

Check AI availability and system status.

**Parameters:** None

**Response Data:**

```json
{
  "ais": {
    "claude": {"available": true, "version": "1.0.0", "path": "/usr/bin/claude"},
    "codex": {"available": true, "version": "2.0.0", "path": "/usr/bin/codex"},
    "gemini": {"available": false, "path": "/usr/bin/gemini"},
    "copilot": {"available": false, "path": "/usr/bin/copilot"},
    "ollama": {"available": true, "endpoint": "http://localhost:11434", "models": ["llama3.1", "codellama"]}
  },
  "summary": {
    "total_ais": 5,
    "available": 3,
    "ready": true
  }
}
```

---

## History & Stats Tools

### cih_history

Query conversation history.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `limit` | int | `10` | Maximum results |
| `search` | string | null | Search query (optional) |

**Response Data:**

```json
{
  "conversations": [
    {
      "id": "session-abc123",
      "query": "What is Python?",
      "task_type": "general",
      "participating_ais": ["claude"],
      "rounds": 1,
      "status": "completed",
      "created_at": "2024-01-01T10:00:00"
    }
  ],
  "count": 1
}
```

---

### cih_history_detail

Get detailed view of a specific session.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `session_id` | string | required | Session ID |
| `format` | string | `"json"` | Output format (json/md/txt) |

**Response Data (JSON format):**

```json
{
  "id": "session-abc123",
  "query": "Original question",
  "task_type": "general",
  "participating_ais": ["claude", "gemini"],
  "rounds": 2,
  "status": "completed",
  "messages": [
    {"sender": "claude", "content": "...", "round": 1},
    {"sender": "gemini", "content": "...", "round": 1}
  ],
  "result": {
    "summary": "Final synthesis...",
    "consensus": true
  }
}
```

---

### cih_models

Get detailed AI model information.

**Parameters:** None

**Response Data:**

```json
{
  "models": {
    "claude": {"available": true, "type": "cloud", "version": "1.0.0"},
    "codex": {"available": true, "type": "cloud", "version": "2.0.0"},
    "gemini": {"available": true, "type": "cloud", "version": "1.5.0"},
    "copilot": {"available": false, "type": "cloud"},
    "ollama": {
      "available": true,
      "type": "local",
      "endpoint": "http://localhost:11434",
      "models": [
        {"name": "llama3.1:70b", "size": 40, "modified": "2024-01-01"},
        {"name": "codellama:13b", "size": 8, "modified": "2024-01-01"}
      ],
      "model_count": 5
    }
  }
}
```

---

### cih_stats

Get usage statistics.

**Parameters:** None

**Response Data:**

```json
{
  "total_sessions": 150,
  "ai_usage": {
    "claude": 80,
    "codex": 45,
    "gemini": 50,
    "ollama": 25
  },
  "task_types": {
    "code": 40,
    "general": 60,
    "design": 20,
    "research": 30
  },
  "avg_rounds_per_session": 1.8
}
```

---

## Docker Gateway Tools

These tools interact with Docker MCP Gateway for accessing containerized MCP servers.

### cih_gateway_status

Check Docker MCP Gateway connection status.

**Parameters:** None

**Response Data:**

```json
{
  "enabled": true,
  "connected": true,
  "gateway_url": "http://localhost:8811",
  "server_count": 15,
  "servers": ["server1", "server2", ...],
  "tool_counts_sample": {"server1": 5, "server2": 3},
  "health": {"status": "healthy"}
}
```

**Note:** Returns error if `DOCKER_GATEWAY_ENABLED=false`.

---

### cih_gateway_find

Search for MCP servers in Docker Gateway.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `query` | string | required | Search query |
| `limit` | int | `10` | Maximum results |

**Response Data:**

```json
{
  "results": [
    {"name": "filesystem", "description": "File system operations"},
    {"name": "github", "description": "GitHub API integration"}
  ]
}
```

---

### cih_gateway_tools

List tools available on a specific MCP server.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `server` | string | required | Server name |

**Response Data:**

```json
{
  "server": "filesystem",
  "tools": [
    {"name": "read_file", "description": "Read file contents"},
    {"name": "write_file", "description": "Write to file"}
  ]
}
```

---

### cih_gateway_exec

Execute a tool on a Docker Gateway MCP server.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `server` | string | required | Server name |
| `tool` | string | required | Tool name |
| `arguments` | dict | `{}` | Tool arguments |
| `timeout` | float | `60.0` | Timeout in seconds |

**Response Data:**

```json
{
  "server": "filesystem",
  "tool": "read_file",
  "result": {"content": "File contents here..."}
}
```

---

### cih_gateway_multi_exec

Execute multiple tools in parallel.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `calls` | list[dict] | required | List of call specs |
| `timeout` | float | `60.0` | Per-call timeout |

**Call Spec Format:**

```json
[
  {"server": "server1", "tool": "tool1", "arguments": {"arg": "value"}},
  {"server": "server2", "tool": "tool2", "arguments": {}}
]
```

**Response Data:**

```json
{
  "total": 2,
  "succeeded": 2,
  "failed": 0,
  "results": [
    {"server": "server1", "tool": "tool1", "success": true, "result": {...}},
    {"server": "server2", "tool": "tool2", "success": true, "result": {...}}
  ]
}
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_BIN` | auto-detected | Path to Claude CLI |
| `CODEX_BIN` | auto-detected | Path to Codex CLI |
| `GEMINI_BIN` | auto-detected | Path to Gemini CLI |
| `COPILOT_BIN` | auto-detected | Path to Copilot CLI |
| `OLLAMA_ENDPOINT` | `http://localhost:11434` | Ollama API endpoint |
| `DOCKER_GATEWAY_URL` | `http://localhost:8811` | Docker Gateway URL |
| `DOCKER_GATEWAY_ENABLED` | `true` | Enable Gateway integration |

### Claude Desktop Configuration

Add to `~/.config/claude-desktop/config.json`:

```json
{
  "mcpServers": {
    "cli-cih": {
      "command": "python",
      "args": ["-m", "cli_cih.mcp"],
      "env": {
        "DOCKER_GATEWAY_URL": "http://localhost:8811"
      }
    }
  }
}
```

### Running as Standalone Server

```bash
# Using Python module
python -m cli_cih.mcp

# Using entry point
cli-cih-mcp
```

---

## Error Handling

All tools handle errors consistently:

```json
{
  "success": false,
  "data": null,
  "error": "Detailed error message",
  "metadata": {}
}
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Unknown AI: xxx` | Invalid AI name | Use claude/codex/gemini/ollama |
| `Timeout after Xs` | Operation timeout | Increase timeout parameter |
| `Docker Gateway disabled` | Gateway not enabled | Set `DOCKER_GATEWAY_ENABLED=true` |
| `Command not found` | CLI not installed | Install required CLI tool |

---

## Best Practices

1. **Use `cih_analyze` first** for complex questions to understand task type
2. **Use `cih_smart`** for automatic AI routing on single questions
3. **Use `cih_discuss`** for multi-perspective answers on complex topics
4. **Use `cih_quick`** for simple, fast responses
5. **Monitor with `cih_status`** to ensure AI availability
6. **Check `cih_stats`** periodically for usage patterns
