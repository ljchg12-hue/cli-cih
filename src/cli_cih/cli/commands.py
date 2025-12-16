"""CLI commands for CLI-CIH."""

import asyncio
from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table

from cli_cih.ui.renderer import get_console

console = get_console()


def cmd_config() -> None:
    """Open configuration editor."""
    console.print("[yellow]Configuration editor coming soon...[/yellow]")


def cmd_history() -> None:
    """Show conversation history."""
    asyncio.run(_show_history_list())


async def _show_history_list(limit: int = 10) -> None:
    """Show recent history list."""
    from cli_cih.storage import get_history_storage

    storage = get_history_storage()
    sessions = await storage.get_recent(limit=limit)

    if not sessions:
        console.print("[dim]No conversation history found.[/dim]")
        return

    console.print("\n[bold cyan]Recent Conversations[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Date", width=16)
    table.add_column("Query", width=40)
    table.add_column("AIs", width=20)
    table.add_column("Status", width=12)

    for session in sessions:
        # Short ID
        short_id = session.id[:8]

        # Date
        date_str = session.created_at.strftime("%Y-%m-%d %H:%M")

        # Query preview
        query = (
            session.user_query[:37] + "..." if len(session.user_query) > 40 else session.user_query
        )

        # AIs
        ais = ", ".join(session.participating_ais[:3])
        if len(session.participating_ais) > 3:
            ais += f" +{len(session.participating_ais) - 3}"

        # Status
        status_colors = {
            "completed": "green",
            "in_progress": "yellow",
            "cancelled": "dim",
            "error": "red",
        }
        status_color = status_colors.get(session.status.value, "white")
        status = f"[{status_color}]{session.status.value}[/{status_color}]"

        table.add_row(short_id, date_str, query, ais, status)

    console.print(table)
    console.print("\n[dim]Use 'cih history show <id>' to view details[/dim]\n")


def cmd_clear() -> None:
    """Clear the terminal screen."""
    console.clear()


def cmd_help() -> None:
    """Show help information."""
    help_text = """
[bold cyan]CLI-CIH Commands[/bold cyan]

[bold]Interactive Mode Commands:[/bold]
  /help, /h      Show this help
  /clear, /c     Clear screen
  /history       Show conversation history
  /config        Open configuration
  /models        Show AI status
  /exit, /q      Exit interactive mode

[bold]AI Selection:[/bold]
  @claude        Use Claude AI
  @codex         Use Codex AI
  @gemini        Use Gemini AI
  @ollama        Use Ollama (local)
  @all           Ask all AIs

[bold]Collaboration Modes:[/bold]
  /mode free     Free discussion (default)
  /mode round    Round robin
  /mode expert   Expert panel

[bold]Keyboard Shortcuts:[/bold]
  Ctrl+C         Cancel current operation
  Ctrl+D         Exit interactive mode
  Up/Down        Navigate history
"""
    console.print(help_text)


async def cmd_models_status() -> None:
    """Show status of all AI adapters."""
    from cli_cih.adapters import get_all_adapters

    console.print("\n[bold cyan]AI Models Status[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("AI", style="bold")
    table.add_column("Status")
    table.add_column("Version")

    adapters = get_all_adapters()

    for adapter in adapters:
        health = await adapter.health_check()
        status_icon = "✅" if health["available"] else "❌"
        status_text = (
            "[green]Available[/green]" if health["available"] else "[red]Unavailable[/red]"
        )
        version = health.get("version", "N/A")

        table.add_row(
            f"[{adapter.color}]{adapter.icon} {adapter.display_name}[/{adapter.color}]",
            f"{status_icon} {status_text}",
            version,
        )

    console.print(table)
    console.print()


def handle_slash_command(command: str) -> bool:
    """Handle slash commands in interactive mode.

    Args:
        command: The command string (with or without /)

    Returns:
        True if command was handled, False otherwise.
    """
    cmd = command.lower().strip()

    if cmd in ("/help", "/h", "help"):
        cmd_help()
        return True
    elif cmd in ("/clear", "/c", "clear"):
        cmd_clear()
        return True
    elif cmd in ("/history", "history"):
        cmd_history()
        return True
    elif cmd in ("/config", "config"):
        cmd_config()
        return True
    elif cmd in ("/models", "/status", "models", "status"):
        asyncio.run(cmd_models_status())
        return True
    elif cmd in ("/exit", "/q", "/quit", "exit", "quit"):
        raise typer.Exit()

    return False


# ============================================================
# Typer subcommands for 'cih models'
# ============================================================

models_app = typer.Typer(
    name="models",
    help="Manage and inspect AI models/adapters",
)


@models_app.command("list")
def models_list() -> None:
    """List all available AI adapters."""
    from cli_cih.adapters import ADAPTERS

    console.print("\n[bold cyan]Available AI Adapters[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name", style="bold")
    table.add_column("Display Name")
    table.add_column("Color")

    for name, adapter_class in ADAPTERS.items():
        adapter = adapter_class()
        table.add_row(
            name,
            f"{adapter.icon} {adapter.display_name}",
            f"[{adapter.color}]{adapter.color}[/{adapter.color}]",
        )

    console.print(table)
    console.print()


@models_app.command("test")
def models_test(
    ai_name: str = typer.Argument(
        ..., help="AI adapter name to test (claude, codex, gemini, ollama)"
    ),
) -> None:
    """Test connection to a specific AI adapter."""
    from cli_cih.adapters import AdapterError, get_adapter

    console.print(f"\n[cyan]Testing {ai_name} adapter...[/cyan]\n")

    try:
        adapter = get_adapter(ai_name)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from None

    async def run_test() -> bool:
        # Check availability
        available = await adapter.is_available()
        if available:
            console.print(f"[green]✅ {adapter.display_name} is available[/green]")
        else:
            console.print(f"[red]❌ {adapter.display_name} is not available[/red]")
            return False

        # Get version
        version = await adapter.get_version()
        console.print(f"[dim]Version: {version}[/dim]")

        # Quick test query
        console.print("\n[dim]Sending test query...[/dim]")
        try:
            response_chunks = []
            async for chunk in adapter.send("Say 'Hello from CLI-CIH!' in exactly those words."):
                response_chunks.append(chunk)
                # Show streaming indicator
                if len(response_chunks) == 1:
                    console.print(f"[{adapter.color}]Response: [/{adapter.color}]", end="")

            response = "".join(response_chunks)
            console.print(f"[{adapter.color}]{response.strip()}[/{adapter.color}]")
            console.print("\n[green]✅ Test passed![/green]")
            return True

        except AdapterError as e:
            console.print(f"[red]Test failed: {e}[/red]")
            return False

    success = asyncio.run(run_test())
    console.print()

    if not success:
        raise typer.Exit(1)


@models_app.command("status")
def models_status() -> None:
    """Show status of all AI adapters."""
    asyncio.run(cmd_models_status())


# ============================================================
# Typer subcommands for 'cih history'
# ============================================================

history_app = typer.Typer(
    name="history",
    help="View and manage conversation history",
)


@history_app.callback(invoke_without_command=True)
def history_callback(ctx: typer.Context) -> None:
    """Show recent conversation history."""
    if ctx.invoked_subcommand is None:
        asyncio.run(_show_history_list())


@history_app.command("list")
def history_list(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of sessions to show"),
) -> None:
    """List recent conversation sessions."""
    asyncio.run(_show_history_list(limit=limit))


@history_app.command("show")
def history_show(
    session_id: str = typer.Argument(..., help="Session ID (full or partial)"),
) -> None:
    """Show details of a specific conversation session."""
    asyncio.run(_show_session_detail(session_id))


async def _show_session_detail(session_id: str) -> None:
    """Show session details."""
    from cli_cih.storage import get_history_storage

    storage = get_history_storage()

    # Try to find session by partial ID
    sessions = await storage.get_recent(limit=100)
    session = None

    for s in sessions:
        if s.id.startswith(session_id) or s.id == session_id:
            session = await storage.get_session(s.id)
            break

    if not session:
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)

    # Display session details
    console.print()
    console.print(
        Panel(
            f"[bold]{session.user_query}[/bold]",
            title="[cyan]Question[/cyan]",
            border_style="cyan",
        )
    )

    console.print()
    console.print(f"[dim]ID:[/dim] {session.id}")
    console.print(f"[dim]Date:[/dim] {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    console.print(f"[dim]AIs:[/dim] {', '.join(session.participating_ais)}")
    console.print(f"[dim]Rounds:[/dim] {session.total_rounds}")
    console.print(f"[dim]Status:[/dim] {session.status.value}")
    console.print()

    # Display messages
    if session.messages:
        console.print("[bold]Discussion:[/bold]")
        console.print()

        current_round = 0
        for msg in session.messages:
            if msg.round_num != current_round:
                current_round = msg.round_num
                console.print(f"[dim]--- Round {current_round} ---[/dim]")

            if msg.sender_type.value == "ai":
                ai_colors = {
                    "claude": "blue",
                    "gemini": "yellow",
                    "codex": "green",
                    "ollama": "magenta",
                }
                color = ai_colors.get(msg.sender_id.lower(), "white")
                truncated = msg.content[:200]
                ellipsis = "..." if len(msg.content) > 200 else ""
                console.print(
                    f"[{color}][{msg.sender_id.upper()}][/{color}] {truncated}{ellipsis}"
                )
            elif msg.sender_type.value == "user":
                console.print(f"[bold][USER][/bold] {msg.content}")
            else:
                console.print(f"[dim]{msg.content}[/dim]")

        console.print()

    # Display result
    if session.result:
        console.print(
            Panel(
                session.result.summary,
                title="[green]Result[/green]",
                border_style="green",
            )
        )

        if session.result.key_points:
            console.print()
            console.print("[bold]Key Points:[/bold]")
            for point in session.result.key_points:
                console.print(f"  • {point}")

    console.print()


@history_app.command("search")
def history_search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum results"),
) -> None:
    """Search conversation history."""
    asyncio.run(_search_history(query, limit))


async def _search_history(query: str, limit: int) -> None:
    """Search history."""
    from cli_cih.storage import get_history_storage

    storage = get_history_storage()
    sessions = await storage.search(query, limit=limit)

    if not sessions:
        console.print(f"[dim]No results found for: {query}[/dim]")
        return

    console.print(f"\n[bold cyan]Search Results for '{query}'[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Date", width=16)
    table.add_column("Query", width=50)
    table.add_column("Status", width=12)

    for session in sessions:
        short_id = session.id[:8]
        date_str = session.created_at.strftime("%Y-%m-%d %H:%M")
        query_text = (
            session.user_query[:47] + "..." if len(session.user_query) > 50 else session.user_query
        )

        status_colors = {
            "completed": "green",
            "in_progress": "yellow",
            "cancelled": "dim",
            "error": "red",
        }
        status_color = status_colors.get(session.status.value, "white")
        status = f"[{status_color}]{session.status.value}[/{status_color}]"

        table.add_row(short_id, date_str, query_text, status)

    console.print(table)
    console.print()


@history_app.command("export")
def history_export(
    session_id: str = typer.Argument(..., help="Session ID to export"),
    format: str = typer.Option("md", "--format", "-f", help="Export format (md, json, txt)"),
    output: str | None = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Export a conversation session."""
    asyncio.run(_export_session(session_id, format, output))


async def _export_session(session_id: str, format: str, output: str | None) -> None:
    """Export session."""
    from cli_cih.storage import get_history_storage

    storage = get_history_storage()

    # Find session
    sessions = await storage.get_recent(limit=100)
    full_id = None

    for s in sessions:
        if s.id.startswith(session_id) or s.id == session_id:
            full_id = s.id
            break

    if not full_id:
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)

    # Export
    content = await storage.export_session(full_id, format=format)

    if not content:
        console.print("[red]Failed to export session[/red]")
        raise typer.Exit(1)

    # Output
    if output:
        output_path = Path(output).expanduser()
        output_path.write_text(content, encoding="utf-8")
        console.print(f"[green]Exported to: {output_path}[/green]")
    else:
        console.print(content)


@history_app.command("stats")
def history_stats() -> None:
    """Show history statistics."""
    asyncio.run(_show_history_stats())


async def _show_history_stats() -> None:
    """Show history stats."""
    from cli_cih.storage import get_history_storage

    storage = get_history_storage()
    stats = await storage.get_stats()

    console.print("\n[bold cyan]History Statistics[/bold cyan]\n")

    console.print(f"Total sessions: {stats['total_sessions']}")
    console.print(f"Completed sessions: {stats['completed_sessions']}")
    console.print(f"Total messages: {stats['total_messages']}")
    console.print(f"Database: {stats['db_path']}")

    if stats["ai_usage"]:
        console.print("\n[bold]AI Usage:[/bold]")
        for ai, count in sorted(stats["ai_usage"].items(), key=lambda x: -x[1]):
            console.print(f"  {ai}: {count} sessions")

    console.print()


@history_app.command("clear")
def history_clear(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Clear all conversation history."""
    if not force:
        confirm = typer.confirm("Are you sure you want to delete all history?")
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            raise typer.Abort()

    asyncio.run(_clear_history())


async def _clear_history() -> None:
    """Clear all history."""
    from cli_cih.storage import get_history_storage

    storage = get_history_storage()

    # Get all sessions and delete them
    sessions = await storage.get_recent(limit=1000)
    deleted = 0

    for session in sessions:
        if await storage.delete_session(session.id):
            deleted += 1

    console.print(f"[green]Deleted {deleted} sessions[/green]")
