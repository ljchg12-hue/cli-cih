"""Panel components for CLI-CIH UI."""

from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cli_cih.ui.themes import AI_COLORS

if TYPE_CHECKING:
    from cli_cih.adapters import AIAdapter


def create_ai_panel(
    ai_name: str,
    content: str,
    subtitle: str | None = None,
) -> Panel:
    """Create a styled panel for AI response.

    Args:
        ai_name: Name of the AI.
        content: Panel content.
        subtitle: Optional subtitle.

    Returns:
        Styled Rich Panel.
    """
    color = AI_COLORS.get(ai_name.lower(), "white")

    title = Text()
    title.append(ai_name.upper(), style=f"bold {color}")

    return Panel(
        content,
        title=title,
        subtitle=subtitle,
        border_style=color,
        padding=(0, 1),
    )


def create_status_panel(
    active_ais: list[str],
    mode: str = "free_discussion",
    current_round: int = 0,
    max_rounds: int = 7,
) -> Panel:
    """Create a status panel showing current state.

    Args:
        active_ais: List of active AI names.
        mode: Current collaboration mode.
        current_round: Current round number.
        max_rounds: Maximum rounds.

    Returns:
        Status Panel.
    """
    table = Table.grid(padding=(0, 2))
    table.add_column("Label", style="dim")
    table.add_column("Value")

    # Active AIs
    ai_text = Text()
    for i, ai in enumerate(active_ais):
        if i > 0:
            ai_text.append(" | ", style="dim")
        color = AI_COLORS.get(ai.lower(), "white")
        ai_text.append(ai.upper(), style=color)

    table.add_row("AIs:", ai_text)
    table.add_row("Mode:", mode.replace("_", " ").title())
    table.add_row("Round:", f"{current_round}/{max_rounds}")

    return Panel(
        table,
        title="[bold cyan]Status[/bold cyan]",
        border_style="dim",
    )


def create_help_panel() -> Panel:
    """Create help panel with commands.

    Returns:
        Help Panel.
    """
    help_text = """
[bold]Commands:[/bold]
  /help, /h      Show help
  /clear, /c     Clear screen
  /switch <ai>   Switch AI (claude, codex, gemini, ollama)
  /models        Show AI status
  /exit, /q      Exit

[bold]Keyboard:[/bold]
  Ctrl+C         Cancel
  Ctrl+D         Exit
  Up/Down        History
"""
    return Panel(
        help_text.strip(),
        title="[bold cyan]Help[/bold cyan]",
        border_style="cyan",
    )


def create_welcome_panel(version: str) -> Panel:
    """Create welcome panel.

    Args:
        version: Application version.

    Returns:
        Welcome Panel.
    """
    welcome_text = Text()
    welcome_text.append("CLI-CIH", style="bold cyan")
    welcome_text.append(f" v{version}\n\n", style="dim")
    welcome_text.append("Multi-AI Collaboration Tool\n", style="")
    welcome_text.append("\nType ", style="dim")
    welcome_text.append("/help", style="yellow")
    welcome_text.append(" for commands", style="dim")

    return Panel(
        welcome_text,
        border_style="cyan",
        padding=(1, 2),
    )


def create_solo_header(
    version: str,
    ai_name: str,
    ai_icon: str,
) -> Panel:
    """Create header for solo AI mode.

    Args:
        version: Application version.
        ai_name: Active AI name.
        ai_icon: AI icon.

    Returns:
        Header Panel.
    """
    color = AI_COLORS.get(ai_name.lower(), "white")

    header = Text()
    header.append("🤖 CLI-CIH", style="bold cyan")
    header.append(f" v{version}\n", style="dim")
    header.append("─" * 50 + "\n", style="dim")
    header.append("Active AI: ", style="dim")
    header.append(f"{ai_icon} {ai_name.title()}\n", style=f"bold {color}")
    header.append("Mode: ", style="dim")
    header.append("Single AI", style="white")
    header.append(" | Type ", style="dim")
    header.append("/help", style="yellow")
    header.append(" or ", style="dim")
    header.append("Ctrl+D", style="yellow")
    header.append(" to quit", style="dim")

    return Panel(
        header,
        border_style="cyan",
        padding=(0, 2),
    )


def create_ai_switch_panel(old_ai: str, new_ai: str) -> Panel:
    """Create panel showing AI switch.

    Args:
        old_ai: Previous AI name.
        new_ai: New AI name.

    Returns:
        Switch notification Panel.
    """
    old_color = AI_COLORS.get(old_ai.lower(), "white")
    new_color = AI_COLORS.get(new_ai.lower(), "white")

    content = Text()
    content.append("Switched from ", style="dim")
    content.append(old_ai.title(), style=old_color)
    content.append(" → ", style="dim")
    content.append(new_ai.title(), style=f"bold {new_color}")

    return Panel(
        content,
        border_style="green",
        padding=(0, 1),
    )


def create_error_panel(message: str, title: str = "Error") -> Panel:
    """Create error panel.

    Args:
        message: Error message.
        title: Panel title.

    Returns:
        Error Panel.
    """
    return Panel(
        Text(message, style="red"),
        title=f"[bold red]{title}[/bold red]",
        border_style="red",
        padding=(0, 1),
    )


def create_user_message_display(message: str) -> Text:
    """Create styled user message display.

    Args:
        message: User's message.

    Returns:
        Styled Text object.
    """
    display = Text()
    display.append("You: ", style="bold bright_white")
    display.append(message, style="white")
    return display


def create_discussion_header(
    version: str,
    ai_count: int = 0,
) -> Panel:
    """Create header for discussion mode.

    Args:
        version: Application version.
        ai_count: Number of participating AIs.

    Returns:
        Header Panel.
    """
    header = Text()
    header.append("🤖 CLI-CIH", style="bold cyan")
    header.append(f" v{version}\n", style="dim")
    header.append("─" * 50 + "\n", style="dim")
    header.append("Mode: ", style="dim")
    header.append("Multi-AI Discussion", style="bold yellow")
    if ai_count > 0:
        header.append(f" ({ai_count} AIs)", style="dim")
    header.append("\n", style="dim")
    header.append("Type ", style="dim")
    header.append("/help", style="yellow")
    header.append(" or ", style="dim")
    header.append("Ctrl+D", style="yellow")
    header.append(" to quit", style="dim")

    return Panel(
        header,
        border_style="cyan",
        padding=(0, 2),
    )


def create_round_header(
    round_num: int,
    max_rounds: int,
) -> Text:
    """Create header for a discussion round.

    Args:
        round_num: Current round number.
        max_rounds: Maximum rounds.

    Returns:
        Styled Text for round header.
    """
    header = Text()
    header.append("\n")
    header.append("━" * 20, style="dim yellow")
    header.append(f" Round {round_num}/{max_rounds} ", style="bold yellow")
    header.append("━" * 20, style="dim yellow")
    header.append("\n")
    return header


def create_task_info_panel(
    task_type: str,
    complexity: float,
    keywords: list[str],
) -> Panel:
    """Create panel showing task analysis.

    Args:
        task_type: Type of the task.
        complexity: Task complexity (0-1).
        keywords: Extracted keywords.

    Returns:
        Task info Panel.
    """
    table = Table.grid(padding=(0, 2))
    table.add_column("Label", style="dim")
    table.add_column("Value")

    table.add_row("Type:", task_type.title())
    table.add_row("Complexity:", f"{complexity:.0%}")
    if keywords:
        table.add_row("Keywords:", ", ".join(keywords[:5]))

    return Panel(
        table,
        title="[bold cyan]📋 Task Analysis[/bold cyan]",
        border_style="dim cyan",
        padding=(0, 1),
    )


def create_ai_selection_panel(
    adapters: "list[AIAdapter]",
    explanation: str,
) -> Panel:
    """Create panel showing selected AIs.

    Args:
        adapters: Selected AI adapters.
        explanation: Selection explanation.

    Returns:
        AI selection Panel.
    """
    content = Text()
    content.append("Selected AIs:\n", style="dim")

    for adapter in adapters:
        color = AI_COLORS.get(adapter.name.lower(), "white")
        content.append(f"  {adapter.icon} ", style=color)
        content.append(adapter.display_name, style=f"bold {color}")
        content.append("\n")

    if explanation:
        content.append("\n")
        content.append(explanation, style="dim")

    return Panel(
        content,
        title="[bold cyan]🎯 AI Selection[/bold cyan]",
        border_style="dim cyan",
        padding=(0, 1),
    )


def create_ai_response_panel(
    ai_name: str,
    ai_icon: str,
    content: str,
) -> Panel:
    """Create panel for AI response in discussion.

    Args:
        ai_name: Name of the AI.
        ai_icon: AI icon.
        content: Response content.

    Returns:
        AI response Panel.
    """
    color = AI_COLORS.get(ai_name.lower(), "white")

    title = Text()
    title.append(f"{ai_icon} ", style=color)
    title.append(ai_name, style=f"bold {color}")

    return Panel(
        content,
        title=title,
        border_style=color,
        padding=(0, 1),
    )


def create_consensus_panel(
    round_num: int,
    reached: bool,
) -> Panel:
    """Create panel showing consensus status.

    Args:
        round_num: Round when consensus was checked.
        reached: Whether consensus was reached.

    Returns:
        Consensus Panel.
    """
    if reached:
        content = Text()
        content.append("✅ ", style="green")
        content.append("Consensus reached at round ", style="green")
        content.append(str(round_num), style="bold green")
        border = "green"
    else:
        content = Text()
        content.append("💬 ", style="yellow")
        content.append("Discussion continues...", style="yellow")
        border = "yellow"

    return Panel(
        content,
        border_style=border,
        padding=(0, 1),
    )


def create_synthesis_panel(
    summary: str,
    key_points: list[str],
    recommendations: list[str],
    total_rounds: int,
    total_messages: int,
    consensus_reached: bool,
    ai_contributions: dict[str, int],
) -> Panel:
    """Create panel showing discussion synthesis.

    Args:
        summary: Discussion summary.
        key_points: Key points from discussion.
        recommendations: Extracted recommendations.
        total_rounds: Total rounds completed.
        total_messages: Total messages exchanged.
        consensus_reached: Whether consensus was reached.
        ai_contributions: Message count per AI.

    Returns:
        Synthesis Panel.
    """
    content = Text()

    # Summary
    content.append("📝 Summary\n", style="bold cyan")
    content.append(summary + "\n\n", style="white")

    # Stats
    content.append("📊 Statistics\n", style="bold cyan")
    content.append(f"  Rounds: {total_rounds}\n", style="dim")
    content.append(f"  Messages: {total_messages}\n", style="dim")
    consensus_status = "✅ Yes" if consensus_reached else "❌ No"
    content.append(f"  Consensus: {consensus_status}\n", style="dim")

    # AI contributions
    if ai_contributions:
        content.append("\n🤖 AI Contributions\n", style="bold cyan")
        for ai_name, count in ai_contributions.items():
            color = AI_COLORS.get(ai_name.lower(), "white")
            content.append(f"  {ai_name}: ", style=color)
            content.append(f"{count} messages\n", style="dim")

    # Key points
    if key_points:
        content.append("\n💡 Key Points\n", style="bold cyan")
        for i, point in enumerate(key_points[:5], 1):
            content.append(f"  {i}. {point}\n", style="white")

    # Recommendations
    if recommendations:
        content.append("\n📌 Recommendations\n", style="bold cyan")
        for rec in recommendations[:3]:
            content.append(f"  • {rec}\n", style="white")

    return Panel(
        content,
        title="[bold cyan]📊 Discussion Results[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )


def create_discussion_help_panel() -> Panel:
    """Create help panel for discussion mode.

    Returns:
        Help Panel.
    """
    help_text = """
[bold]Commands:[/bold]
  /help, /h      Show help
  /clear, /c     Clear screen
  /solo <ai>     Switch to solo mode
  /models        Show AI status
  /exit, /q      Exit

[bold]Keyboard:[/bold]
  Ctrl+C         Cancel current
  Ctrl+D         Exit
  Up/Down        History

[bold]Discussion Mode:[/bold]
  Enter a question and multiple AIs will
  discuss and provide collaborative answers.
"""
    return Panel(
        help_text.strip(),
        title="[bold cyan]Help[/bold cyan]",
        border_style="cyan",
    )
