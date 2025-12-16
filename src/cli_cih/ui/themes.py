"""Color themes and styling for CLI-CIH."""

from typing import TypedDict


class ThemeColors(TypedDict):
    """Theme color definitions."""

    primary: str
    secondary: str
    success: str
    warning: str
    error: str
    info: str
    dim: str


# AI-specific colors
AI_COLORS: dict[str, str] = {
    "claude": "bright_blue",
    "codex": "bright_green",
    "gemini": "bright_yellow",
    "ollama": "bright_magenta",
}

# Main theme
THEME: ThemeColors = {
    "primary": "cyan",
    "secondary": "white",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "info": "blue",
    "dim": "dim",
}

# Prompt styles for different contexts
PROMPT_STYLES: dict[str, str] = {
    "default": "cyan bold",
    "waiting": "yellow",
    "error": "red bold",
    "success": "green bold",
}

# Panel border styles
PANEL_STYLES: dict[str, str] = {
    "default": "cyan",
    "ai_response": "bright_blue",
    "error": "red",
    "warning": "yellow",
    "info": "blue",
    "success": "green",
}


def get_ai_color(ai_name: str) -> str:
    """Get color for a specific AI.

    Args:
        ai_name: Name of the AI.

    Returns:
        Rich color string.
    """
    return AI_COLORS.get(ai_name.lower(), "white")


def get_ai_style(ai_name: str) -> str:
    """Get full style string for an AI.

    Args:
        ai_name: Name of the AI.

    Returns:
        Rich style string.
    """
    color = get_ai_color(ai_name)
    return f"bold {color}"
