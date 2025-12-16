"""Codex CLI adapter for CLI-CIH."""

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


class CodexAdapter(AIAdapter):
    """Adapter for Codex CLI (OpenAI's codex command)."""

    name = "codex"
    display_name = "Codex"
    color = "bright_green"
    icon = "🟢"

    def __init__(self, config: Optional[AdapterConfig] = None):
        """Initialize Codex adapter."""
        super().__init__(config)
        self._command = "codex"

    async def _check_availability(self) -> bool:
        """Check if Codex CLI is available.

        Returns:
            True if codex command exists in PATH.
        """
        return await PTYManager.check_command_exists(self._command)

    async def get_version(self) -> str:
        """Get Codex CLI version.

        Returns:
            Version string.
        """
        version = await PTYManager.get_command_version(self._command, "--version")
        return version or "unknown"

    async def send(self, prompt: str) -> AsyncIterator[str]:
        """Send a prompt to Codex CLI and stream response.

        Uses subprocess with exec --skip-git-repo-check for non-interactive mode.

        Args:
            prompt: The prompt to send.

        Yields:
            Response chunks as they arrive.
        """
        if not await self.is_available():
            raise AdapterError("Codex CLI를 사용할 수 없습니다. 설치: npm install -g @openai/codex")

        # Non-interactive environment variables
        env = os.environ.copy()
        env['TERM'] = 'dumb'  # Disable terminal features
        env['NO_COLOR'] = '1'  # Disable color output
        env['CI'] = '1'  # CI mode (non-interactive)
        env['FORCE_COLOR'] = '0'  # Force no color
        env['CODEX_QUIET'] = '1'  # Quiet mode

        try:
            # Use exec --skip-git-repo-check for non-interactive execution
            proc = await asyncio.create_subprocess_exec(
                self._command,
                'exec',  # exec subcommand
                '--skip-git-repo-check',  # Skip git repo check
                prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            # Read streaming output
            buffer = ""
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        proc.stdout.read(1024),
                        timeout=1.0
                    )
                    if not chunk:
                        break
                    decoded = chunk.decode('utf-8', errors='ignore')
                    clean_chunk = clean_ansi(decoded)
                    if clean_chunk:
                        yield clean_chunk
                        buffer += clean_chunk
                except asyncio.TimeoutError:
                    # Check if process is still running
                    if proc.returncode is not None:
                        break
                    continue

            # Wait for process to finish
            await asyncio.wait_for(proc.wait(), timeout=5.0)

            # Only show error if no output was produced
            if not buffer:
                stderr = await proc.stderr.read()
                if stderr:
                    error_msg = stderr.decode('utf-8', errors='ignore').strip()
                    # Filter out cursor/terminal errors
                    if error_msg and 'cursor' not in error_msg.lower():
                        yield f"[Codex 경고: {error_msg}]"

        except asyncio.TimeoutError:
            raise AdapterTimeoutError(f"Codex CLI 응답 시간 초과 ({self.config.timeout}초)")
        except Exception as e:
            raise AdapterError(f"Codex CLI 오류: {e}")

    async def send_fallback(self, prompt: str) -> AsyncIterator[str]:
        """Fallback method using simple subprocess without streaming.

        Args:
            prompt: The prompt to send.

        Yields:
            Response as single chunk.
        """
        env = os.environ.copy()
        env['TERM'] = 'dumb'
        env['NO_COLOR'] = '1'

        try:
            proc = await asyncio.create_subprocess_exec(
                self._command,
                prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout
            )

            if stdout:
                result = clean_ansi(stdout.decode('utf-8', errors='ignore'))
                if result:
                    yield result

            if stderr and not stdout:
                yield f"[Codex 에러: {stderr.decode('utf-8', errors='ignore')}]"

        except asyncio.TimeoutError:
            yield '[Codex 응답 시간 초과]'
        except Exception as e:
            yield f'[Codex 에러: {e}]'
