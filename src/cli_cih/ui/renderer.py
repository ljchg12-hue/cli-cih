"""Rich console rendering for CLI-CIH."""


from rich.console import Console, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from cli_cih.ui.themes import AI_COLORS

# Singleton console instance
_console: Console | None = None


def get_console() -> Console:
    """Get the singleton Console instance.

    Returns:
        Rich Console instance.
    """
    global _console
    if _console is None:
        _console = Console()
    return _console


def render_ai_response(
    ai_name: str,
    content: str,
    is_markdown: bool = True,
) -> None:
    """Render an AI response with appropriate styling.

    Args:
        ai_name: Name of the AI (claude, codex, gemini, ollama).
        content: The response content.
        is_markdown: Whether to render content as markdown.
    """
    console = get_console()
    color = AI_COLORS.get(ai_name.lower(), "white")

    # Create title
    title = Text()
    title.append(ai_name.upper(), style=f"bold {color}")

    # Render content
    rendered_content: RenderableType
    if is_markdown:
        rendered_content = Markdown(content)
    else:
        rendered_content = Text(content)

    # Create and print panel
    panel = Panel(
        rendered_content,
        title=title,
        border_style=color,
        padding=(0, 1),
    )
    console.print(panel)


def render_thinking(ai_name: str) -> None:
    """Show thinking indicator for an AI.

    Args:
        ai_name: Name of the AI.
    """
    console = get_console()
    color = AI_COLORS.get(ai_name.lower(), "white")
    console.print(f"[{color}]{ai_name.upper()}[/{color}] [dim]is thinking...[/dim]")


def render_error(message: str) -> None:
    """Render an error message.

    Args:
        message: Error message to display.
    """
    console = get_console()
    console.print(f"[bold red]Error:[/bold red] {message}")


def render_warning(message: str) -> None:
    """Render a warning message.

    Args:
        message: Warning message to display.
    """
    console = get_console()
    console.print(f"[bold yellow]Warning:[/bold yellow] {message}")


def render_success(message: str) -> None:
    """Render a success message.

    Args:
        message: Success message to display.
    """
    console = get_console()
    console.print(f"[bold green]Success:[/bold green] {message}")


def render_info(message: str) -> None:
    """Render an info message.

    Args:
        message: Info message to display.
    """
    console = get_console()
    console.print(f"[bold cyan]Info:[/bold cyan] {message}")
