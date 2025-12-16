"""Interactive mode for CLI-CIH - Single AI and Multi-AI conversation interface."""

import asyncio
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.text import Text

from cli_cih import __version__
from cli_cih.adapters import AdapterError, AIAdapter, get_adapter, get_all_adapters
from cli_cih.orchestration import (
    AIChunkEvent,
    AIEndEvent,
    AIsSelectedEvent,
    AIStartEvent,
    Conflict,
    ConflictDetectedEvent,
    ConflictResolvedEvent,
    ConsensusReachedEvent,
    Coordinator,
    Resolution,
    ResolutionType,
    ResultEvent,
    RoundEndEvent,
    RoundStartEvent,
    TaskAnalyzedEvent,
)
from cli_cih.ui.approval_prompt import ConflictPrompt
from cli_cih.ui.panels import (
    create_ai_selection_panel,
    create_ai_switch_panel,
    create_consensus_panel,
    create_discussion_header,
    create_discussion_help_panel,
    create_error_panel,
    create_help_panel,
    create_round_header,
    create_solo_header,
    create_synthesis_panel,
    create_task_info_panel,
)
from cli_cih.ui.spinner import loading
from cli_cih.ui.streaming import StreamingDisplay
from cli_cih.ui.themes import AI_COLORS

# Prompt styles (prompt_toolkit uses ANSI color names)
USER_PROMPT_STYLE = Style.from_dict(
    {
        "prompt": "bold ansiwhite",
    }
)


def get_history_path() -> Path:
    """Get path for command history file."""
    config_dir = Path.home() / ".config" / "cli-cih"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "history"


def get_console() -> Console:
    """Get or create console instance."""
    return Console()


class InteractiveSession:
    """Manages an interactive conversation session with an AI."""

    def __init__(
        self,
        ai_name: str | None = None,
        console: Console | None = None,
    ):
        """Initialize interactive session.

        Args:
            ai_name: Name of AI to use (defaults to first available).
            console: Rich console instance.
        """
        self.console = console or get_console()
        self.ai_name = ai_name
        self.adapter: AIAdapter | None = None
        self.session: PromptSession | None = None
        self._running = False
        self._interrupted = False

    async def initialize(self) -> bool:
        """Initialize the session with an AI adapter.

        Uses parallel checking for faster adapter discovery.

        Returns:
            True if initialization successful.
        """
        # Get adapter
        if self.ai_name:
            try:
                self.adapter = get_adapter(self.ai_name)
            except ValueError as e:
                self.console.print(create_error_panel(str(e)))
                return False
        else:
            # Find first available adapter using parallel checking
            async with loading("AI 확인 중...", console=self.console):
                all_adapters = get_all_adapters()
                available = await Coordinator.check_adapters_parallel(all_adapters)

            if available:
                self.adapter = available[0]
                self.ai_name = self.adapter.name

        if self.adapter is None:
            self.console.print(
                create_error_panel(
                    "No AI adapters available!\nInstall: claude, codex, gemini or start ollama"
                )
            )
            return False

        # Check availability (uses cache from parallel check)
        if not await self.adapter.is_available():
            self.console.print(
                create_error_panel(f"{self.adapter.display_name}을(를) 사용할 수 없습니다")
            )
            return False

        # Setup prompt session
        history_path = get_history_path()
        self.session = PromptSession(
            history=FileHistory(str(history_path)),
            style=USER_PROMPT_STYLE,
        )

        return True

    def show_header(self) -> None:
        """Display the session header."""
        header = create_solo_header(
            version=__version__,
            ai_name=self.adapter.display_name,
            ai_icon=self.adapter.icon,
        )
        self.console.print(header)
        self.console.print()

    async def switch_ai(self, new_ai_name: str) -> bool:
        """Switch to a different AI.

        Args:
            new_ai_name: Name of the new AI.

        Returns:
            True if switch successful.
        """
        try:
            new_adapter = get_adapter(new_ai_name)
        except ValueError as e:
            self.console.print(f"[red]오류: {e}[/red]")
            return False

        if not await new_adapter.is_available():
            self.console.print(f"[red]{new_adapter.display_name}을(를) 사용할 수 없습니다[/red]")
            return False

        old_name = self.adapter.name
        self.adapter = new_adapter
        self.ai_name = new_ai_name

        self.console.print(create_ai_switch_panel(old_name, new_ai_name))
        return True

    async def handle_command(self, command: str) -> str | None:
        """Handle slash commands.

        Args:
            command: Command string.

        Returns:
            'exit' to exit, 'continue' to skip response, None otherwise.
        """
        cmd = command.lower().strip()
        parts = cmd.split(maxsplit=1)
        base_cmd = parts[0]
        arg = parts[1] if len(parts) > 1 else None

        if base_cmd in ("/exit", "/quit", "/q"):
            return "exit"

        elif base_cmd in ("/help", "/h"):
            self.console.print(create_help_panel())
            return "continue"

        elif base_cmd in ("/clear", "/c"):
            self.console.clear()
            self.show_header()
            return "continue"

        elif base_cmd == "/switch":
            if not arg:
                self.console.print("[yellow]Usage: /switch <ai_name>[/yellow]")
                self.console.print("[dim]Available: claude, codex, gemini, ollama[/dim]")
            else:
                await self.switch_ai(arg)
            return "continue"

        elif base_cmd == "/models":
            await self._show_models()
            return "continue"

        return None

    async def _show_models(self) -> None:
        """Show available models status using parallel checking."""
        from rich.table import Table

        table = Table(show_header=True, header_style="bold")
        table.add_column("AI", style="bold")
        table.add_column("Status")

        # Use parallel checking for faster status display
        all_adapters = get_all_adapters()
        async with loading("상태 확인 중...", console=self.console):
            available_adapters = await Coordinator.check_adapters_parallel(all_adapters)

        available_names = {a.name for a in available_adapters}
        for adapter in all_adapters:
            available = adapter.name in available_names
            status = "[green]✅ Available[/green]" if available else "[red]❌ Unavailable[/red]"
            current = " [cyan](current)[/cyan]" if adapter.name == self.ai_name else ""
            ai_label = f"[{adapter.color}]{adapter.icon} {adapter.display_name}"
            ai_label += f"[/{adapter.color}]{current}"
            table.add_row(ai_label, status)

        self.console.print(table)

    async def send_message(self, message: str) -> None:
        """Send a message to the AI and display response.

        Args:
            message: User's message.
        """
        self._interrupted = False

        streamer = StreamingDisplay(
            console=self.console,
            ai_name=self.adapter.display_name,
            ai_icon=self.adapter.icon,
        )

        try:
            # Stream with interrupt support
            await self._stream_with_interrupt(streamer, message)
        except AdapterError as e:
            self.console.print(f"[red]오류: {e}[/red]")

    async def _stream_with_interrupt(
        self,
        streamer: StreamingDisplay,
        message: str,
    ) -> None:
        """Stream response with Ctrl+C interrupt support.

        Args:
            streamer: Streaming display handler.
            message: User's message.
        """

        async def stream_task():
            try:
                await streamer.stream_response(self.adapter.send(message))
            except asyncio.CancelledError:
                pass

        task = asyncio.create_task(stream_task())

        try:
            await task
        except asyncio.CancelledError:
            self._interrupted = True
            self.console.print("\n[dim]⚡ Response interrupted (Ctrl+C)[/dim]")

    async def run(self) -> None:
        """Run the interactive session loop."""
        if not await self.initialize():
            return

        self.show_header()
        self._running = True

        while self._running:
            try:
                # Get user input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.session.prompt(
                        [("class:prompt", "You: ")],
                    ),
                )
                user_input = user_input.strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    result = await self.handle_command(user_input)
                    if result == "exit":
                        break
                    elif result == "continue":
                        continue

                # Send to AI
                await self.send_message(user_input)
                self.console.print()  # Blank line after response

            except KeyboardInterrupt:
                if self._interrupted:
                    self.console.print()  # Just newline if already interrupted
                else:
                    self.console.print("\n[dim]Cancelled (press again to exit)[/dim]")
                self._interrupted = False
                continue

            except EOFError:
                break

            except Exception as e:
                self.console.print(f"[red]오류: {e}[/red]")
                continue

        self.console.print("\n[cyan]Goodbye![/cyan]")


def start_interactive_mode(ai_name: str | None = None) -> None:
    """Start the interactive CLI mode.

    Args:
        ai_name: Optional AI name to use.
    """
    session = InteractiveSession(ai_name=ai_name)
    asyncio.run(session.run())


# Legacy function for backward compatibility
def start_solo_mode(ai_name: str) -> None:
    """Start solo mode with specific AI.

    Args:
        ai_name: AI to use.
    """
    start_interactive_mode(ai_name=ai_name)


class DiscussionSession:
    """Manages a multi-AI discussion session."""

    def __init__(
        self,
        console: Console | None = None,
        min_ais: int = 2,
        max_ais: int = 4,
    ):
        """Initialize discussion session.

        Args:
            console: Rich console instance.
            min_ais: Minimum number of AIs.
            max_ais: Maximum number of AIs.
        """
        self.console = console or get_console()
        self.coordinator = Coordinator(min_ais=min_ais, max_ais=max_ais)
        self.conflict_prompt = ConflictPrompt(console=self.console)
        self.session: PromptSession | None = None
        self._running = False
        self._available_adapters: list[AIAdapter] = []
        self._current_ai_buffer = ""
        self._interrupted = False

        # Set up conflict resolution callback
        self.coordinator.set_conflict_callback(self._handle_conflict)

    async def initialize(self) -> bool:
        """Initialize the discussion session.

        Uses parallel checking for faster adapter discovery.

        Returns:
            True if initialization successful.
        """
        # Find available adapters using parallel checking
        async with loading("AI 확인 중...", console=self.console):
            all_adapters = get_all_adapters()
            self._available_adapters = await Coordinator.check_adapters_parallel(all_adapters)

        if len(self._available_adapters) < 2:
            self.console.print(
                create_error_panel(
                    f"Need at least 2 AIs for discussion mode!\n"
                    f"Found: {len(self._available_adapters)}\n"
                    "Install: claude, codex, gemini or start ollama"
                )
            )
            return False

        # Setup prompt session
        history_path = get_history_path()
        self.session = PromptSession(
            history=FileHistory(str(history_path)),
            style=USER_PROMPT_STYLE,
        )

        return True

    def show_header(self) -> None:
        """Display the discussion header."""
        header = create_discussion_header(
            version=__version__,
            ai_count=len(self._available_adapters),
        )
        self.console.print(header)
        self.console.print()

    async def handle_command(self, command: str) -> str | None:
        """Handle slash commands.

        Args:
            command: Command string.

        Returns:
            'exit' to exit, 'continue' to skip, 'solo:name' to switch mode, None otherwise.
        """
        cmd = command.lower().strip()
        parts = cmd.split(maxsplit=1)
        base_cmd = parts[0]
        arg = parts[1] if len(parts) > 1 else None

        if base_cmd in ("/exit", "/quit", "/q"):
            return "exit"

        elif base_cmd in ("/help", "/h"):
            self.console.print(create_discussion_help_panel())
            return "continue"

        elif base_cmd in ("/clear", "/c"):
            self.console.clear()
            self.show_header()
            return "continue"

        elif base_cmd == "/solo":
            if not arg:
                self.console.print("[yellow]Usage: /solo <ai_name>[/yellow]")
                self.console.print("[dim]Available: claude, codex, gemini, ollama[/dim]")
                return "continue"
            return f"solo:{arg}"

        elif base_cmd == "/models":
            await self._show_models()
            return "continue"

        return None

    async def _show_models(self) -> None:
        """Show available models status using parallel checking."""
        from rich.table import Table

        table = Table(show_header=True, header_style="bold")
        table.add_column("AI", style="bold")
        table.add_column("Status")
        table.add_column("In Discussion")

        # Use parallel checking for faster status display
        all_adapters = get_all_adapters()
        async with loading("상태 확인 중...", console=self.console):
            available_adapters = await Coordinator.check_adapters_parallel(all_adapters)

        available_names = {a.name for a in available_adapters}
        in_discussion_names = {a.name for a in self._available_adapters}
        for adapter in all_adapters:
            available = adapter.name in available_names
            status = "[green]✅ Available[/green]" if available else "[red]❌ Unavailable[/red]"
            in_discussion = "✓" if adapter.name in in_discussion_names else ""
            table.add_row(
                f"[{adapter.color}]{adapter.icon} {adapter.display_name}[/{adapter.color}]",
                status,
                in_discussion,
            )

        self.console.print(table)

    async def _handle_conflict(
        self,
        conflict: Conflict,
        resolution: Resolution,
    ) -> str:
        """Handle conflict resolution through UI.

        Args:
            conflict: The detected conflict.
            resolution: The proposed resolution.

        Returns:
            User's choice or 'more' for more discussion.
        """
        return await self.conflict_prompt.show_conflict_prompt(conflict, resolution)

    async def run_discussion(self, user_input: str) -> None:
        """Run a multi-AI discussion on user input.

        Args:
            user_input: User's question/topic.
        """
        self.console.print()
        self._interrupted = False

        try:
            await self._run_discussion_with_interrupt(user_input)
        except asyncio.CancelledError:
            self._interrupted = True
            self.console.print("\n[dim]⚡ Discussion interrupted (Ctrl+C)[/dim]")

    async def _run_discussion_with_interrupt(self, user_input: str) -> None:
        """Run discussion with interrupt support."""
        async for event in self.coordinator.process(user_input, self._available_adapters):
            # Check for interrupt
            if self._interrupted:
                break
            # Handle different event types
            if isinstance(event, TaskAnalyzedEvent):
                # Show task analysis
                panel = create_task_info_panel(
                    task_type=event.task.task_type.value,
                    complexity=event.task.complexity,
                    keywords=event.task.keywords,
                )
                self.console.print(panel)

            elif isinstance(event, AIsSelectedEvent):
                # Show selected AIs
                panel = create_ai_selection_panel(
                    adapters=event.adapters,
                    explanation=event.explanation,
                )
                self.console.print(panel)
                self.console.print()

            elif isinstance(event, RoundStartEvent):
                # Show round header
                header = create_round_header(event.round_num, event.max_rounds)
                self.console.print(header)

            elif isinstance(event, AIStartEvent):
                # Start AI response with streaming display
                self._current_ai_buffer = ""
                color = AI_COLORS.get(event.ai_name.lower(), "white")
                header = Text()
                header.append(f"\n{event.ai_icon} ", style=color)
                header.append(event.ai_name, style=f"bold {color}")
                header.append(": ", style="dim")
                self.console.print(header, end="")

            elif isinstance(event, AIChunkEvent):
                # Stream AI response chunk
                self._current_ai_buffer += event.chunk
                self.console.print(event.chunk, end="", highlight=False)

            elif isinstance(event, AIEndEvent):
                # Complete AI response
                self.console.print()  # Newline after response

            elif isinstance(event, RoundEndEvent):
                # Round completed
                self.console.print()

            elif isinstance(event, ConsensusReachedEvent):
                # Show consensus notification
                panel = create_consensus_panel(event.round_num, reached=True)
                self.console.print(panel)

            elif isinstance(event, ConflictDetectedEvent):
                # Show conflict detection (UI will be handled by callback)
                self.console.print()
                self.console.print("[yellow]⚡ AI opinions differ on this topic...[/yellow]")

            elif isinstance(event, ConflictResolvedEvent):
                # Show conflict resolution result
                if event.user_choice:
                    self.console.print(f"[green]✓ User selected: {event.user_choice}[/green]")
                elif event.resolution.type == ResolutionType.AUTO_RESOLVED:
                    self.console.print(f"[dim]Auto-resolved: {event.resolution.winner}[/dim]")

            elif isinstance(event, ResultEvent):
                # Show final synthesis (skip for simple chat)
                result = event.result
                # 간단한 대화 (1라운드, 1메시지)면 패널 표시 안 함
                if result.total_rounds == 1 and result.total_messages == 1:
                    continue
                panel = create_synthesis_panel(
                    summary=result.summary,
                    key_points=result.key_points,
                    recommendations=result.recommendations,
                    total_rounds=result.total_rounds,
                    total_messages=result.total_messages,
                    consensus_reached=result.consensus_reached,
                    ai_contributions=result.ai_contributions,
                )
                self.console.print(panel)

    async def run(self) -> None:
        """Run the discussion session loop."""
        if not await self.initialize():
            return

        self.show_header()
        self._running = True

        while self._running:
            try:
                # Get user input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.session.prompt(
                        [("class:prompt", "You: ")],
                    ),
                )
                user_input = user_input.strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    result = await self.handle_command(user_input)
                    if result == "exit":
                        break
                    elif result == "continue":
                        continue
                    elif result and result.startswith("solo:"):
                        # Switch to solo mode
                        ai_name = result.split(":", 1)[1]
                        self.console.print(
                            f"\n[cyan]Switching to solo mode with {ai_name}...[/cyan]\n"
                        )
                        solo_session = InteractiveSession(ai_name=ai_name, console=self.console)
                        await solo_session.run()
                        # After returning from solo, show header again
                        self.show_header()
                        continue

                # Run multi-AI discussion
                await self.run_discussion(user_input)
                self.console.print()  # Blank line after discussion

            except KeyboardInterrupt:
                if self._interrupted:
                    self.console.print()  # Just newline if already interrupted
                else:
                    self.console.print("\n[dim]Discussion cancelled (press again to exit)[/dim]")
                self._interrupted = False
                continue

            except EOFError:
                break

            except Exception as e:
                self.console.print(f"[red]오류: {e}[/red]")
                import traceback

                traceback.print_exc()
                continue

        self.console.print("\n[cyan]Goodbye![/cyan]")


def start_discussion_mode() -> None:
    """Start the multi-AI discussion mode."""
    session = DiscussionSession()
    asyncio.run(session.run())


if __name__ == "__main__":
    start_discussion_mode()
