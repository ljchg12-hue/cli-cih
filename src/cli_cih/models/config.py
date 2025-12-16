"""Configuration models for CLI-CIH."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CollaborationMode(str, Enum):
    """Collaboration modes for AI interaction."""

    FREE_DISCUSSION = "free_discussion"
    ROUND_ROBIN = "round_robin"
    EXPERT_PANEL = "expert_panel"


class AIConfig(BaseModel):
    """Configuration for a single AI."""

    name: str
    enabled: bool = True
    color: str = "white"
    endpoint: Optional[str] = None
    model: Optional[str] = None
    timeout: int = 60
    max_tokens: int = 4096


class Config(BaseModel):
    """Main configuration model."""

    version: str = "1.0.0"

    # Default settings
    default_ai: str = "claude"
    collaboration_mode: CollaborationMode = CollaborationMode.FREE_DISCUSSION
    max_rounds: int = Field(default=7, ge=1, le=20)

    # AI configurations
    ais: dict[str, AIConfig] = Field(default_factory=lambda: {
        "claude": AIConfig(
            name="claude",
            color="bright_blue",
            endpoint="cli",
        ),
        "codex": AIConfig(
            name="codex",
            color="bright_green",
            endpoint="cli",
        ),
        "gemini": AIConfig(
            name="gemini",
            color="bright_yellow",
            endpoint="cli",
        ),
        "ollama": AIConfig(
            name="ollama",
            color="bright_magenta",
            endpoint="http://localhost:11434",
        ),
    })

    # UI settings
    show_thinking: bool = True
    show_timestamps: bool = False
    compact_mode: bool = False
    show_loading_spinner: bool = True

    # History settings
    save_history: bool = True
    max_history_items: int = 1000

    # Performance settings
    availability_cache_ttl: float = Field(
        default=30.0, ge=5.0, le=300.0,
        description="TTL for adapter availability cache in seconds"
    )
    parallel_check_timeout: float = Field(
        default=5.0, ge=1.0, le=30.0,
        description="Timeout for parallel adapter availability checks"
    )
    enable_graceful_degradation: bool = Field(
        default=True, description="Fallback to next AI on error"
    )

    class Config:
        """Pydantic config."""

        use_enum_values = True
