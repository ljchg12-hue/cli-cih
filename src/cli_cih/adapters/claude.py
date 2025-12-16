"""Claude CLI adapter for CLI-CIH."""
import asyncio
import os
from typing import AsyncIterator, Optional

from cli_cih.adapters.base import (
    AdapterConfig,
    AdapterError,
    AdapterTimeoutError,
    AIAdapter,
)
from cli_cih.adapters.pty_manager import PTYManager
from cli_cih.utils.text import clean_ansi


class ClaudeAdapter(AIAdapter):
    """Adapter for Claude CLI (Anthropic's claude command)."""

    name = "claude"
    display_name = "Claude"
    color = "bright_blue"
    icon = "🔵"

    def __init__(self, config: Optional[AdapterConfig] = None):
        """Initialize Claude adapter."""
        super().__init__(config)
        self._command = "claude"

    async def is_available(self) -> bool:
        """Check if Claude CLI is available."""
        return await PTYManager.check_command_exists(self._command)

    async def get_version(self) -> str:
        """Get Claude CLI version."""
        version = await PTYManager.get_command_version(self._command, "--version")
        return version or "unknown"

    async def send(self, prompt: str) -> AsyncIterator[str]:
        """Send a prompt to Claude CLI and stream response."""
        if not await self.is_available():
            raise AdapterError("Claude CLI를 사용할 수 없습니다")

        env = os.environ.copy()
        env['TERM'] = 'dumb'
        env['NO_COLOR'] = '1'

        try:
            process = await asyncio.create_subprocess_exec(
                self._command,
                "-p", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            while True:
                chunk = await process.stdout.read(1024)
                if not chunk:
                    break
                text = chunk.decode('utf-8', errors='ignore')
                clean_chunk = clean_ansi(text)
                if clean_chunk:
                    yield clean_chunk

            await process.wait()

        except asyncio.TimeoutError:
            raise AdapterTimeoutError("Claude CLI 응답 시간 초과")
        except Exception as e:
            raise AdapterError(f"Claude CLI 오류: {e}")

    async def send_interactive(self, prompt: str) -> AsyncIterator[str]:
        """Send a prompt in interactive mode."""
        async for chunk in self.send(prompt):
            yield chunk
