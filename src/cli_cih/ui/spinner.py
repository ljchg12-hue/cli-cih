"""Loading indicator utilities for CLI-CIH."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import TracebackType

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text


class LoadingIndicator:
    """Async context manager for showing loading state."""

    def __init__(
        self,
        message: str = "처리 중...",
        spinner: str = "dots",
        console: Console | None = None,
    ):
        """Initialize loading indicator.

        Args:
            message: Message to display while loading.
            spinner: Spinner style (dots, line, arc, etc.).
            console: Rich console instance.
        """
        self.message = message
        self.spinner_name = spinner
        self.console = console or Console()
        self._live: Live | None = None
        self._active = False

    async def __aenter__(self) -> "LoadingIndicator":
        """Start the loading indicator."""
        self._active = True
        spinner = Spinner(self.spinner_name, text=self.message)
        self._live = Live(spinner, console=self.console, refresh_per_second=10)
        self._live.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Stop the loading indicator."""
        self._active = False
        if self._live:
            self._live.stop()
            # Clear the spinner line
            self.console.print(" " * len(self.message) + "  ", end="\r")

    def update(self, message: str) -> None:
        """Update the loading message.

        Args:
            message: New message to display.
        """
        self.message = message
        if self._live and self._active:
            spinner = Spinner(self.spinner_name, text=message)
            self._live.update(spinner)


@asynccontextmanager
async def loading(
    message: str = "처리 중...",
    spinner: str = "dots",
    console: Console | None = None,
) -> AsyncIterator[LoadingIndicator]:
    """Async context manager for showing a loading spinner.

    Usage:
        async with loading("AI 응답 대기 중..."):
            result = await some_async_operation()

    Args:
        message: Message to display.
        spinner: Spinner style.
        console: Rich console instance.

    Yields:
        LoadingIndicator instance.
    """
    indicator = LoadingIndicator(message, spinner, console)
    try:
        await indicator.__aenter__()
        yield indicator
    finally:
        await indicator.__aexit__(None, None, None)


class ProgressTracker:
    """Track progress through multiple steps."""

    def __init__(
        self,
        total_steps: int,
        console: Console | None = None,
    ):
        """Initialize progress tracker.

        Args:
            total_steps: Total number of steps.
            console: Rich console instance.
        """
        self.total_steps = total_steps
        self.current_step = 0
        self.console = console or Console()
        self._completed_ais: list[str] = []

    def step_complete(self, ai_name: str) -> None:
        """Mark a step as complete.

        Args:
            ai_name: Name of the AI that completed.
        """
        self.current_step += 1
        self._completed_ais.append(ai_name)

    def get_status(self) -> str:
        """Get current status string.

        Returns:
            Status string like "2/4 완료 (Claude, Gemini)"
        """
        if not self._completed_ais:
            return f"0/{self.total_steps} 진행 중..."

        completed = ", ".join(self._completed_ais)
        return f"{self.current_step}/{self.total_steps} 완료 ({completed})"

    def render(self) -> Text:
        """Render progress as Rich Text.

        Returns:
            Rich Text object.
        """
        text = Text()
        text.append(f"[{self.current_step}/{self.total_steps}] ", style="bold")

        for i, ai in enumerate(self._completed_ais):
            if i > 0:
                text.append(", ")
            text.append(ai, style="green")
            text.append(" ✓", style="green")

        remaining = self.total_steps - self.current_step
        if remaining > 0:
            if self._completed_ais:
                text.append(" | ", style="dim")
            text.append(f"{remaining}개 대기중", style="dim")

        return text
