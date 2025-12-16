"""Streaming display components for CLI-CIH."""

import asyncio
import re
from collections.abc import AsyncIterator

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from cli_cih.ui.themes import AI_COLORS


class StreamingDisplay:
    """Display streaming AI responses with real-time updates."""

    def __init__(
        self,
        console: Console,
        ai_name: str,
        ai_icon: str = "🤖",
        show_panel: bool = False,
    ):
        """Initialize streaming display.

        Args:
            console: Rich console instance.
            ai_name: Name of the AI.
            ai_icon: Icon for the AI.
            show_panel: Whether to wrap in a panel.
        """
        self.console = console
        self.ai_name = ai_name
        self.ai_icon = ai_icon
        self.ai_color = AI_COLORS.get(ai_name.lower(), "white")
        self.show_panel = show_panel
        self._buffer = ""
        self._is_code_block = False

    def _create_header(self) -> Text:
        """Create AI response header."""
        header = Text()
        header.append(f"{self.ai_icon} ", style=self.ai_color)
        header.append(self.ai_name, style=f"bold {self.ai_color}")
        header.append(": ", style="dim")
        return header

    async def stream_response(
        self,
        chunks: AsyncIterator[str],
        use_live: bool = False,
    ) -> str:
        """Stream and display response chunks.

        Args:
            chunks: Async iterator of response chunks.
            use_live: Use Rich Live for smooth updates.

        Returns:
            Complete response text.
        """
        self._buffer = ""

        if use_live:
            return await self._stream_with_live(chunks)
        else:
            return await self._stream_simple(chunks)

    async def _stream_simple(self, chunks: AsyncIterator[str]) -> str:
        """Simple streaming without Live component."""
        # Print header
        header = self._create_header()
        self.console.print(header, end="")

        async for chunk in chunks:
            self._buffer += chunk
            # Print chunk directly
            self.console.print(chunk, end="", highlight=False)

        # Final newline
        self.console.print()
        return self._buffer

    async def _stream_with_live(self, chunks: AsyncIterator[str]) -> str:
        """Streaming with Rich Live for smooth markdown rendering."""
        header = self._create_header()

        with Live(
            header,
            console=self.console,
            refresh_per_second=10,
            transient=False,
        ) as live:
            async for chunk in chunks:
                self._buffer += chunk

                # Create display with header and content
                display = Text()
                display.append(f"{self.ai_icon} ", style=self.ai_color)
                display.append(self.ai_name, style=f"bold {self.ai_color}")
                display.append(": ", style="dim")
                display.append(self._buffer)

                live.update(display)

        return self._buffer


class ThinkingIndicator:
    """Display thinking/loading indicator."""

    def __init__(
        self,
        console: Console,
        ai_name: str,
        ai_icon: str = "🤖",
    ):
        """Initialize thinking indicator.

        Args:
            console: Rich console instance.
            ai_name: Name of the AI.
            ai_icon: Icon for the AI.
        """
        self.console = console
        self.ai_name = ai_name
        self.ai_icon = ai_icon
        self.ai_color = AI_COLORS.get(ai_name.lower(), "white")
        self._live: Live | None = None

    def start(self) -> None:
        """Start showing thinking indicator."""
        spinner = Spinner("dots", text=Text(f" {self.ai_name} is thinking...", style="dim"))
        self._live = Live(
            spinner,
            console=self.console,
            refresh_per_second=10,
            transient=True,
        )
        self._live.start()

    def stop(self) -> None:
        """Stop thinking indicator."""
        if self._live:
            self._live.stop()
            self._live = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.stop()
        return False


def detect_code_blocks(text: str) -> list[tuple[str, bool]]:
    """Detect code blocks in text.

    Args:
        text: Text to analyze.

    Returns:
        List of (content, is_code) tuples.
    """
    parts = []
    pattern = r"```(\w*)\n(.*?)```"

    last_end = 0
    for match in re.finditer(pattern, text, re.DOTALL):
        # Add text before code block
        if match.start() > last_end:
            parts.append((text[last_end : match.start()], False))

        # Add code block (language hint not used in simple detection)
        code = match.group(2)
        parts.append((code, True))
        last_end = match.end()

    # Add remaining text
    if last_end < len(text):
        parts.append((text[last_end:], False))

    return parts if parts else [(text, False)]


async def stream_with_typing_effect(
    console: Console,
    text: str,
    delay: float = 0.01,
) -> None:
    """Display text with typing effect.

    Args:
        console: Rich console.
        text: Text to display.
        delay: Delay between characters.
    """
    for char in text:
        console.print(char, end="", highlight=False)
        await asyncio.sleep(delay)
    console.print()
