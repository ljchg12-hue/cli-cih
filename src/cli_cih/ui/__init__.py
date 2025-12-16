"""UI module for CLI-CIH."""

from cli_cih.ui.panels import (
    create_ai_panel,
    create_ai_response_panel,
    create_ai_selection_panel,
    create_ai_switch_panel,
    create_consensus_panel,
    create_discussion_header,
    create_discussion_help_panel,
    create_error_panel,
    create_help_panel,
    create_round_header,
    create_solo_header,
    create_status_panel,
    create_synthesis_panel,
    create_task_info_panel,
)
from cli_cih.ui.renderer import get_console, render_ai_response
from cli_cih.ui.streaming import StreamingDisplay, ThinkingIndicator
from cli_cih.ui.themes import AI_COLORS, THEME

__all__ = [
    "get_console",
    "render_ai_response",
    "create_ai_panel",
    "create_status_panel",
    "create_solo_header",
    "create_help_panel",
    "create_ai_switch_panel",
    "create_error_panel",
    "create_discussion_header",
    "create_discussion_help_panel",
    "create_round_header",
    "create_task_info_panel",
    "create_ai_selection_panel",
    "create_ai_response_panel",
    "create_consensus_panel",
    "create_synthesis_panel",
    "StreamingDisplay",
    "ThinkingIndicator",
    "AI_COLORS",
    "THEME",
]
