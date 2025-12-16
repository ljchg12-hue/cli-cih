"""Gemini CLI adapter for CLI-CIH."""

import asyncio
from typing import AsyncIterator, Optional

import pexpect
from pexpect import EOF, TIMEOUT

from cli_cih.adapters.base import (
    AdapterConfig,
    AdapterError,
    AdapterTimeoutError,
    AIAdapter,
)
from cli_cih.adapters.pty_manager import PTYManager
from cli_cih.utils.text import clean_ansi


class GeminiAdapter(AIAdapter):
    """Adapter for Gemini CLI (Google's gemini command)."""

    name = "gemini"
    display_name = "Gemini"
    color = "bright_yellow"
    icon = "🟡"

    # Patterns to filter from stderr/output
    SKIP_PATTERNS = [
        '[ERROR]',
        '[STARTUP]',
        'YOLO mode',
        'Loaded cached',
        'Recording metric',
        'StartupProfiler',
        'ImportProcessor',
        'duration:',
        'phase:',
        'Initializing',
        'Loading model',
        'Warning:',
        'Deprecation',
    ]

    def __init__(self, config: Optional[AdapterConfig] = None):
        """Initialize Gemini adapter."""
        super().__init__(config)
        self._command = "gemini"
        # Alternative fast wrapper if available
        self._fast_command = "gemini-fast"

    async def is_available(self) -> bool:
        """Check if Gemini CLI is available.

        Returns:
            True if gemini command exists in PATH.
        """
        # Check for fast wrapper first, then regular command
        if await PTYManager.check_command_exists(self._fast_command):
            return True
        return await PTYManager.check_command_exists(self._command)

    async def get_version(self) -> str:
        """Get Gemini CLI version.

        Returns:
            Version string.
        """
        # Try fast wrapper first
        if await PTYManager.check_command_exists(self._fast_command):
            version = await PTYManager.get_command_version(self._fast_command, "--version")
            if version:
                return f"{version} (fast)"

        version = await PTYManager.get_command_version(self._command, "--version")
        return version or "unknown"

    async def _get_active_command(self) -> str:
        """Get the command to use (prefer fast wrapper)."""
        if await PTYManager.check_command_exists(self._fast_command):
            return self._fast_command
        return self._command

    async def send(self, prompt: str) -> AsyncIterator[str]:
        """Send a prompt to Gemini CLI and stream response.

        Filters out stderr noise (ERROR, STARTUP, metrics, etc.)

        Args:
            prompt: The prompt to send.

        Yields:
            Response chunks as they arrive.
        """
        if not await self.is_available():
            raise AdapterError("Gemini CLI를 사용할 수 없습니다. 설치: npm install -g @google/gemini-cli")

        command = await self._get_active_command()
        args = [prompt]

        try:
            process = pexpect.spawn(
                command,
                args,
                encoding="utf-8",
                timeout=self.config.timeout,
            )

            collected = []
            while True:
                try:
                    chunk = process.read_nonblocking(size=1024, timeout=0.1)
                    if chunk:
                        clean_chunk = clean_ansi(chunk)
                        if clean_chunk:
                            # Filter out stderr/noise patterns
                            if not self._should_skip(clean_chunk):
                                collected.append(clean_chunk)
                                yield clean_chunk
                except TIMEOUT:
                    if not process.isalive():
                        break
                    await asyncio.sleep(0.05)
                except EOF:
                    break

            process.close()

            # If nothing was collected, yield error message
            if not collected:
                yield "[Gemini 응답 없음]"

        except pexpect.ExceptionPexpect as e:
            raise AdapterError(f"Gemini CLI 오류: {e}")
        except asyncio.TimeoutError:
            raise AdapterTimeoutError(f"Gemini CLI 응답 시간 초과 ({self.config.timeout}초)")

    def _should_skip(self, text: str) -> bool:
        """Check if text should be filtered out.

        Args:
            text: Text to check.

        Returns:
            True if text matches skip patterns.
        """
        for pattern in self.SKIP_PATTERNS:
            if pattern in text:
                return True
        return False
