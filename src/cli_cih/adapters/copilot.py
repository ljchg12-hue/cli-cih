"""GitHub Copilot CLI adapter for CLI-CIH.

Uses GitHub Copilot CLI with -p (prompt) flag for non-interactive mode.
"""

import asyncio
import os
import re
from collections.abc import AsyncIterator

from cli_cih.adapters.base import (
    AdapterConfig,
    AdapterError,
    AdapterTimeoutError,
    AIAdapter,
)
from cli_cih.adapters.pty_manager import PTYManager

import pexpect
from pexpect import EOF, TIMEOUT


class CopilotAdapter(AIAdapter):
    """Adapter for GitHub Copilot CLI.

    Uses -p (prompt) flag for non-interactive mode with --allow-all for auto-approval.
    """

    name = "copilot"
    display_name = "Copilot"
    color = "bright_cyan"
    icon = "🔷"

    # Patterns to filter from output
    SKIP_PATTERNS = [
        'Total usage',
        'Total duration',
        'Total code changes',
        'Usage by model',
        'Premium request',
        'input,',
        'output,',
        'cache read',
        'lines added',
        'lines removed',
    ]

    def __init__(self, config: AdapterConfig | None = None):
        """Initialize Copilot adapter."""
        super().__init__(config)
        self._command = "copilot"
        self._detected_model: str | None = None

    async def _check_availability(self) -> bool:
        """Check if Copilot CLI is available.

        Returns:
            True if copilot command exists in PATH.
        """
        return await PTYManager.check_command_exists(self._command)

    async def get_version(self) -> str:
        """Get Copilot CLI version.

        Returns:
            Version string.
        """
        version = await PTYManager.get_command_version(self._command, "--version")
        return version or "unknown"

    async def send(self, prompt: str) -> AsyncIterator[str]:
        """Send a prompt to Copilot CLI and stream response.

        Uses -p flag for non-interactive mode.

        Args:
            prompt: The prompt to send.

        Yields:
            Response chunks as they arrive.
        """
        if not await self.is_available():
            raise AdapterError("Copilot CLI를 사용할 수 없습니다. 설치: npm install -g @github/copilot")

        # Inherit environment
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"

        try:
            # Use -p for non-interactive mode, --allow-all for auto-approval
            process = pexpect.spawn(
                self._command,
                ["-p", prompt, "--allow-all"],
                encoding="utf-8",
                timeout=self.config.timeout,
                env=env,
            )

            collected_response = []
            buffer = ""

            while True:
                try:
                    chunk = process.read_nonblocking(size=4096, timeout=0.5)
                    if chunk:
                        buffer += chunk
                except TIMEOUT:
                    if not process.isalive():
                        break
                    await asyncio.sleep(0.1)
                except EOF:
                    break

            process.close()

            # Process the collected output
            lines = buffer.split('\n')
            response_lines = []

            for line in lines:
                # Skip status/usage lines
                if self._should_skip(line):
                    # Try to extract model from usage line
                    model_match = re.search(r'(\w+-\w+-[\d.]+)', line)
                    if model_match:
                        self._detected_model = model_match.group(1)
                    continue

                # Clean ANSI codes
                clean_line = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line)
                clean_line = clean_line.strip()

                if clean_line:
                    response_lines.append(clean_line)

            if response_lines:
                response = '\n'.join(response_lines)
                collected_response.append(response)
                yield response
            else:
                model_info = f" (Model: {self._detected_model})" if self._detected_model else ""
                yield f"[Copilot 응답 없음{model_info}]"

        except pexpect.ExceptionPexpect as e:
            raise AdapterError(f"Copilot CLI 오류: {e}") from e
        except asyncio.TimeoutError as err:
            raise AdapterTimeoutError(f"Copilot CLI 응답 시간 초과 ({self.config.timeout}초)") from err

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

    def get_detected_model(self) -> str | None:
        """Get the last detected model name.

        Returns:
            Model name if detected, None otherwise.
        """
        return self._detected_model
