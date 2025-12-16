# Changelog

All notable changes to CLI-CIH will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
