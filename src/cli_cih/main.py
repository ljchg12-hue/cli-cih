"""Main entry point for CLI-CIH."""

import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console

from cli_cih import __version__
from cli_cih.cli.commands import history_app, models_app
from cli_cih.cli.interactive import start_discussion_mode, start_interactive_mode
from cli_cih.utils.logging import setup_logging

app = typer.Typer(
    name="cli-cih",
    help="Multi-AI Collaboration CLI Tool - Interactive terminal interface",
    add_completion=False,
    no_args_is_help=False,
)

# Register subcommands
app.add_typer(models_app, name="models")
app.add_typer(history_app, name="history")

# Initialize logging
setup_logging()

console = Console()


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"[bold cyan]cli-cih[/bold cyan] version [green]{__version__}[/green]")
        raise typer.Exit()


@app.command("ask")
def ask_command(
    question: str = typer.Argument(..., help="Question to ask the AI"),
    ai: Optional[str] = typer.Option(
        None,
        "--ai",
        "-a",
        help="Specify AI to use (claude, codex, gemini, ollama)",
    ),
) -> None:
    """Ask a question to an AI directly."""
    asyncio.run(quick_query(question, ai))


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
    solo: Optional[str] = typer.Option(
        None,
        "--solo",
        "-s",
        help="Start solo mode with specific AI (claude, codex, gemini, ollama)",
    ),
) -> None:
    """CLI-CIH: Multi-AI Collaboration Tool.

    Run without arguments for multi-AI discussion mode.
    Use 'cih --solo claude' to chat with a specific AI.
    Use 'cih ask "question"' for quick queries.
    Use 'cih models' to manage AI adapters.
    Use 'cih history' to view conversation history.
    """
    if ctx.invoked_subcommand is not None:
        return

    # Solo mode with specific AI
    if solo:
        start_interactive_mode(ai_name=solo)
        return

    # Check if there's a positional argument that looks like a question
    # (for backwards compatibility with 'cih "question"')
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-") and sys.argv[1] not in ["models", "ask"]:
        # Treat first arg as a question
        question = sys.argv[1]
        ai = None
        # Check for --ai flag
        for i, arg in enumerate(sys.argv[2:], start=2):
            if arg in ("--ai", "-a") and i + 1 < len(sys.argv):
                ai = sys.argv[i + 1]
                break
        asyncio.run(quick_query(question, ai))
    else:
        # Default: Multi-AI discussion mode
        start_discussion_mode()


async def quick_query(question: str, ai_name: Optional[str] = None) -> None:
    """Execute a quick query to an AI.

    Args:
        question: The question to ask.
        ai_name: Optional AI name to use.
    """
    from cli_cih.adapters import AdapterError, get_adapter, get_all_adapters

    # Determine which AI to use
    if ai_name:
        try:
            adapter = get_adapter(ai_name)
        except ValueError as e:
            console.print(f"[red]오류: {e}[/red]")
            return
    else:
        # Find first available adapter
        adapter = None
        for a in get_all_adapters():
            if await a.is_available():
                adapter = a
                break

        if adapter is None:
            console.print("[red]사용 가능한 AI가 없습니다![/red]")
            console.print("[dim]설치: claude, codex, gemini 또는 ollama serve 실행[/dim]")
            return

    console.print(f"\n[dim]Using:[/dim] [{adapter.color}]{adapter.icon} {adapter.display_name}[/{adapter.color}]")
    console.print(f"[dim]Question:[/dim] {question}\n")

    try:
        # Check availability
        if not await adapter.is_available():
            console.print(f"[red]{adapter.display_name}을(를) 사용할 수 없습니다[/red]")
            return

        # Stream response
        console.print(f"[{adapter.color}]{adapter.display_name}:[/{adapter.color}] ", end="")
        async for chunk in adapter.send(question):
            console.print(chunk, end="")
        console.print("\n")

    except AdapterError as e:
        console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    app()
