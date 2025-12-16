# Changelog

All notable changes to CLI-CIH will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1] - 2025-12-17

### Fixed
- **Ollama Multi-Instance Conflict** (Critical)
  - Added unique `instance_id` to prevent adapter.name collision
  - Instance-specific cache keys avoid context key overwrite
  - Property decorators for unique display_name per instance

- **Invalid Ollama Model Names**
  - Replaced non-existent `qwen3:32b` → `qwen2.5:32b`
  - Replaced non-existent `llama3.3:70b-instruct-q4_K_M` → `llama3.1:70b`

- **MCP Server Blocking I/O** (Performance)
  - Converted `subprocess.run` → `asyncio.create_subprocess_exec`
  - Converted sync `httpx.get` → async `httpx.AsyncClient`
  - Added proper timeout handling with `asyncio.wait_for`

- **SQLite Foreign Key Enforcement**
  - Added `PRAGMA foreign_keys = ON` in connection setup

- **Pydantic V2 Deprecation Warning**
  - Migrated from deprecated `class Config:` to `ConfigDict`

- **Cache Thread Safety** (Concurrency)
  - Added `threading.Lock` to protect shared availability cache
  - Thread-safe cache read/write/clear operations

### Changed
- HTTP client timeout explicitly set via `httpx.Timeout`
- Test class renamed from `TestRunCliSafe` to `TestRunCliAsync`
- Updated tests to use async mock patterns

### Testing
- 205 tests passing
- All ruff lint checks passing

---

## [1.1.0] - 2025-12-16

### Added
- **MCP Server Enhancement** (17 tools total)
  - `cih_analyze`: Task analysis and AI routing
  - `cih_compare`: Multi-AI response comparison
  - `cih_smart`: Smart routing based on task type
  - `cih_quick`: Fast single AI response
  - `cih_history_detail`: Session detail retrieval
  - `cih_models`: List available models
  - `cih_stats`: Usage statistics

- **Docker Gateway Integration**
  - `cih_gateway_status`: Connection status check
  - `cih_gateway_find`: Search MCP servers
  - `cih_gateway_tools`: List server tools
  - `cih_gateway_exec`: Execute MCP tool
  - `cih_gateway_multi_exec`: Parallel tool execution

- **Standardized Response Schema**
  - All tools return consistent `{success, data, error, metadata}` format
  - Duration tracking in metadata
  - AI source attribution

### Changed
- MCP server architecture refactored for maintainability
- Removed duplicate code across MCP tools
- Improved error handling with proper exception chaining (B904)
- Enhanced type annotations throughout codebase

### Fixed
- Lint issues (ruff): 25+ issues resolved
- Mutable default argument in `cih_compare` (B006)
- Unused imports and variables removed
- Line length violations fixed

### Testing
- 205 tests passing
- Core module coverage: context 90%, task_analyzer 93%, models 92%
- History module coverage: 83%

---

## [1.0.0] - 2025-12-16

### Added
- **Multi-AI Orchestration System**
  - AI Selector with task-based scoring
  - Task Analyzer for automatic task type detection (CODE, DEBUG, DESIGN, RESEARCH, SIMPLE_CHAT, etc.)
  - Shared Context for multi-round discussions
  - Conflict Detection between AI responses
  - Response Synthesizer for consensus building

- **AI Adapters**
  - Claude adapter with Claude Code CLI integration
  - Codex adapter with OpenAI Codex CLI integration
  - Gemini adapter with Google Gemini CLI integration
  - Ollama adapter with multi-model support and Korean language mode

- **CLI Interface**
  - Interactive multi-AI discussion mode
  - Solo mode for single AI conversations
  - Quick question command (`cih ask`)
  - History management commands (list, search, export)
  - Model status and health check commands

- **MCP Server**
  - FastMCP-based server implementation
  - Tools: `cih_discuss`, `cih_ask`, `cih_status`, `cih_history`
  - Claude Desktop integration support

- **Storage**
  - SQLite-based conversation history
  - Markdown and JSON export formats
  - Full-text search capabilities
  - Usage statistics

- **Utilities**
  - Retry mechanism with exponential backoff
  - Circuit breaker pattern for fault tolerance
  - Rich terminal UI with AI-specific themes
  - Streaming output support
  - ANSI text cleaning utilities

- **Testing**
  - 168+ unit and integration tests
  - Test coverage for core modules (36%+)
  - Comprehensive adapter testing
  - Orchestration module testing

### Technical Details
- Python 3.10+ required
- Uses `uv` for dependency management
- Rich terminal formatting
- Async/await throughout

### Korean Language Support
- Korean prompt detection and handling
- Ollama Korean mode for better Korean responses
- Korean UI messages and error handling

## [0.1.0] - Initial Development

### Added
- Basic project structure
- Initial adapter implementations
- Core CLI framework

---

## Notes

### Versioning Strategy
- MAJOR: Breaking API changes
- MINOR: New features, backward compatible
- PATCH: Bug fixes, backward compatible

### Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.
