# CLI-CIH

**Multi-AI Collaboration CLI Tool** - An interactive terminal interface for orchestrating multiple AI assistants.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/cli-cih.svg)](https://badge.fury.io/py/cli-cih)

## Features

- **Multi-AI Orchestration**: Seamlessly work with Claude, Codex, Gemini, and Ollama
- **Discussion Modes**: Free Discussion, Round Robin, Expert Panel for structured AI collaboration
- **Consensus System**: AI voting and agreement detection for group decisions
- **Rich Terminal UI**: Beautiful colored panels with AI-specific styling
- **Conversation History**: SQLite-based history with search and export
- **Smart Retry Logic**: Exponential backoff and circuit breaker patterns
- **Solo Mode**: Direct chat with a single AI assistant

## Installation

### From PyPI (Recommended)

```bash
pip install cli-cih
```

### From Source

```bash
git clone https://github.com/cli-cih/cli-cih.git
cd cli-cih
pip install -e .
```

### Development Installation

```bash
pip install -e ".[dev]"
```

## Quick Start

```bash
# Multi-AI discussion mode (default)
cih

# Solo mode with specific AI
cih --solo claude
cih -s gemini

# Quick question
cih ask "What is Python?"
cih ask "Explain async/await" --ai claude

# Check available AIs
cih models status

# View history
cih history list
```

## Commands Reference

### Main Commands

| Command | Description |
|---------|-------------|
| `cih` | Start multi-AI discussion mode |
| `cih --solo <ai>` | Start solo mode with specific AI |
| `cih ask "<question>"` | Quick question to first available AI |
| `cih ask "<question>" --ai <name>` | Quick question to specific AI |
| `cih --version` | Show version |
| `cih --help` | Show help |

### Models Commands

| Command | Description |
|---------|-------------|
| `cih models status` | Show all AI adapters status |
| `cih models check <name>` | Check specific adapter |
| `cih models test <name>` | Test adapter with sample query |

### History Commands

| Command | Description |
|---------|-------------|
| `cih history list` | List recent sessions |
| `cih history show <id>` | Show session details |
| `cih history search "<query>"` | Search conversations |
| `cih history export <id>` | Export session (md/json/txt) |
| `cih history stats` | Show usage statistics |
| `cih history clear` | Clear all history |

## Interactive Mode Commands

When in interactive mode, use these commands:

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/mode <mode>` | Change discussion mode |
| `/add <ai>` | Add AI to discussion |
| `/remove <ai>` | Remove AI from discussion |
| `/vote` | Start voting on current topic |
| `/clear` | Clear conversation |
| `/exit` or `/quit` | Exit interactive mode |

## Discussion Modes

| Mode | Description |
|------|-------------|
| `free` | Free discussion - all AIs respond naturally |
| `round` | Round robin - AIs take turns in order |
| `expert` | Expert panel - task-specific AI selection |

## Configuration

Configuration file: `~/.config/cli-cih/config.yaml`

```yaml
# Default settings
default_ai: claude
collaboration_mode: free_discussion
max_rounds: 7
consensus_threshold: 0.6

# AI-specific colors
ai_colors:
  claude: bright_blue
  codex: bright_green
  gemini: bright_yellow
  ollama: bright_magenta

# Timeout settings (seconds)
timeout:
  default: 60
  claude: 90
  ollama: 120

# Retry configuration
retry:
  max_retries: 3
  base_delay: 1.0
  max_delay: 30.0
```

## Supported AI Backends

| AI | Requirement | Description |
|----|-------------|-------------|
| Claude | `claude` CLI installed | Anthropic Claude via Claude Code |
| Codex | `codex` CLI installed | OpenAI Codex CLI |
| Gemini | `gemini` CLI installed | Google Gemini CLI |
| Ollama | Ollama server running | Local LLM models |

### Setting Up AI Backends

```bash
# Claude - Install Claude Code
# https://claude.ai/code

# Codex - Install OpenAI Codex CLI
npm install -g @openai/codex

# Gemini - Install Gemini CLI
# https://gemini.google.com/cli

# Ollama - Install and run Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
ollama pull llama3.1
```

## Architecture

```
cli-cih/
├── src/cli_cih/
│   ├── adapters/              # AI backend adapters
│   │   ├── base.py            # Abstract adapter interface
│   │   ├── claude.py          # Claude adapter
│   │   ├── codex.py           # Codex adapter
│   │   ├── gemini.py          # Gemini adapter
│   │   └── ollama.py          # Ollama adapter
│   ├── orchestration/         # Multi-AI orchestration
│   │   ├── ai_selector.py     # AI selection & scoring
│   │   ├── task_analyzer.py   # Task type detection
│   │   ├── context.py         # Shared discussion context
│   │   ├── coordinator.py     # Discussion coordinator
│   │   ├── discussion.py      # Discussion session
│   │   ├── conflict.py        # Conflict detection
│   │   └── synthesizer.py     # Response synthesis
│   ├── cli/                   # CLI interface
│   │   ├── commands.py        # Typer subcommands
│   │   ├── interactive.py     # Interactive mode
│   │   └── app.py             # CLI app entry
│   ├── mcp/                   # MCP server
│   │   └── server.py          # FastMCP server implementation
│   ├── storage/               # Data persistence
│   │   ├── history.py         # SQLite history
│   │   └── models.py          # Data models
│   ├── ui/                    # Terminal UI
│   │   ├── panels.py          # Rich panels
│   │   ├── themes.py          # Color themes
│   │   └── streaming.py       # Streaming output
│   ├── utils/                 # Utilities
│   │   ├── logging.py         # Logging setup
│   │   ├── retry.py           # Retry & circuit breaker
│   │   └── text.py            # Text utilities
│   └── main.py                # Entry point
└── tests/                     # Test suite (168+ tests)
```

## Examples

### Multi-AI Discussion

```bash
$ cih
╭─ CLI-CIH Multi-AI Discussion ─╮
│ Available AIs: Claude, Gemini │
│ Mode: Free Discussion         │
╰───────────────────────────────╯

You: What are the best practices for API design?

╭─ Claude ────────────────────────────────────╮
│ Here are key REST API design practices:     │
│ 1. Use meaningful resource names            │
│ 2. Version your API...                      │
╰─────────────────────────────────────────────╯

╭─ Gemini ────────────────────────────────────╮
│ Building on Claude's points, I'd add:       │
│ 1. Consistent error handling                │
│ 2. Rate limiting...                         │
╰─────────────────────────────────────────────╯
```

### Solo Mode

```bash
$ cih --solo claude
╭─ Solo Mode: Claude ─╮
╰─────────────────────╯

You: Explain Python decorators

Claude: Decorators are a powerful feature...
```

### Export Conversation

```bash
$ cih history export abc123 --format md > conversation.md
```

## MCP Server

CLI-CIH provides an MCP (Model Context Protocol) server for integration with Claude Desktop and other MCP-compatible applications.

### Available Tools (17 total)

| Tool | Category | Description |
|------|----------|-------------|
| `cih_quick` | Core | Quick single AI response |
| `cih_analyze` | Core | Analyze prompt for optimal routing |
| `cih_discuss` | Core | Multi-AI discussion with synthesis |
| `cih_compare` | Core | Compare responses from multiple AIs |
| `cih_smart` | Core | Smart routing based on task type |
| `cih_status` | Core | Check AI availability |
| `cih_history` | History | Query conversation history |
| `cih_history_detail` | History | Get session details |
| `cih_models` | Info | List available AI models |
| `cih_stats` | Info | Usage statistics |
| `cih_gateway_status` | Gateway | Docker Gateway connection status |
| `cih_gateway_find` | Gateway | Search MCP servers |
| `cih_gateway_tools` | Gateway | List server tools |
| `cih_gateway_exec` | Gateway | Execute MCP tool |
| `cih_gateway_multi_exec` | Gateway | Execute multiple tools in parallel |

### Response Format

All tools return a standardized response:

```json
{
  "success": true,
  "data": { "response": "..." },
  "error": null,
  "metadata": { "duration_ms": 150, "ai_used": ["claude"] }
}
```

### Configuration (Claude Desktop)

Add to `~/.config/claude-desktop/config.json`:

```json
{
  "mcpServers": {
    "cli-cih": {
      "command": "python",
      "args": ["-m", "cli_cih.mcp"],
      "env": {
        "DOCKER_GATEWAY_URL": "http://localhost:8811",
        "DOCKER_GATEWAY_ENABLED": "true"
      }
    }
  }
}
```

### Using with uv

```json
{
  "mcpServers": {
    "cli-cih": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/cli-cih", "python", "-m", "cli_cih.mcp"]
    }
  }
}
```

### Documentation

See [docs/MCP_TOOLS.md](docs/MCP_TOOLS.md) for complete tool documentation.

## Development

### Running Tests

```bash
# All tests
pytest tests/

# With coverage
pytest tests/ --cov=cli_cih

# Specific test
pytest tests/test_adapters.py -v
```

### Code Quality

```bash
# Linting
ruff check src/

# Type checking
mypy src/cli_cih/

# Format
ruff format src/
```

## Troubleshooting

### Common Issues

**AI not available**
```bash
# Check AI status
cih models status

# Test specific AI
cih models test claude
```

**Connection timeout**
```bash
# Increase timeout in config
timeout:
  claude: 120
```

**Rate limiting**
The tool automatically handles rate limits with exponential backoff.
Wait a moment and retry.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new features
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Rich](https://rich.readthedocs.io/) - Terminal formatting
- [Prompt Toolkit](https://python-prompt-toolkit.readthedocs.io/) - Interactive input
