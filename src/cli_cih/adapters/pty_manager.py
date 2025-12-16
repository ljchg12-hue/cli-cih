"""PTY session management for CLI-based AI tools."""

import asyncio
import shutil
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pexpect
from pexpect import EOF, TIMEOUT


@dataclass
class PTYConfig:
    """Configuration for PTY session."""

    command: str
    args: list[str]
    timeout: int = 60
    encoding: str = "utf-8"
    prompt_pattern: str | None = None
    end_patterns: list[str] = None

    def __post_init__(self):
        if self.end_patterns is None:
            self.end_patterns = []


class PTYSession:
    """Manages a PTY session for interactive CLI tools.

    This class provides async-friendly interaction with CLI tools
    that require a pseudo-terminal (PTY) for proper operation.
    """

    def __init__(self, config: PTYConfig):
        """Initialize PTY session.

        Args:
            config: PTY configuration.
        """
        self.config = config
        self._process: pexpect.spawn | None = None
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        """Check if the session is running."""
        return self._process is not None and self._process.isalive()

    async def start(self) -> bool:
        """Start the PTY session.

        Returns:
            True if started successfully.
        """
        async with self._lock:
            if self.is_running:
                return True

            try:
                cmd = self.config.command
                args = self.config.args

                self._process = pexpect.spawn(
                    cmd,
                    args,
                    encoding=self.config.encoding,
                    timeout=self.config.timeout,
                )
                return True
            except Exception:
                self._process = None
                return False

    async def stop(self) -> None:
        """Stop the PTY session."""
        async with self._lock:
            if self._process is not None:
                try:
                    self._process.close(force=True)
                except Exception:
                    pass
                finally:
                    self._process = None

    async def send_and_stream(
        self,
        text: str,
        end_patterns: list[str] | None = None,
    ) -> AsyncIterator[str]:
        """Send text and stream the response.

        Args:
            text: Text to send.
            end_patterns: Patterns that indicate end of response.

        Yields:
            Response chunks as they arrive.
        """
        if not self.is_running:
            raise RuntimeError("PTY session not running")

        patterns = end_patterns or self.config.end_patterns or [pexpect.EOF]

        # Send the input
        self._process.sendline(text)

        # Buffer for accumulating output
        buffer = ""

        while True:
            try:
                # Read available data
                chunk = self._process.read_nonblocking(size=1024, timeout=0.1)
                if chunk:
                    buffer += chunk
                    yield chunk
            except TIMEOUT:
                # Check for end patterns in buffer
                for pattern in patterns:
                    if isinstance(pattern, str) and pattern in buffer:
                        return
                await asyncio.sleep(0.05)
            except EOF:
                return


class PTYManager:
    """Manager for creating and handling PTY sessions."""

    @staticmethod
    def find_executable(name: str) -> str | None:
        """Find an executable in PATH.

        Args:
            name: Executable name.

        Returns:
            Full path if found, None otherwise.
        """
        return shutil.which(name)

    @staticmethod
    async def run_command(
        command: str,
        args: list[str] | None = None,
        timeout: int = 60,
    ) -> AsyncIterator[str]:
        """Run a command and stream its output.

        Args:
            command: Command to run.
            args: Command arguments.
            timeout: Timeout in seconds.

        Yields:
            Output chunks as they arrive.
        """
        args = args or []

        try:
            process = pexpect.spawn(
                command,
                args,
                encoding="utf-8",
                timeout=timeout,
            )

            while True:
                try:
                    chunk = process.read_nonblocking(size=1024, timeout=0.1)
                    if chunk:
                        yield chunk
                except TIMEOUT:
                    if not process.isalive():
                        break
                    await asyncio.sleep(0.05)
                except EOF:
                    break

        except Exception as e:
            yield f"\n[Error: {e}]\n"

    @staticmethod
    async def run_and_capture(
        command: str,
        args: list[str] | None = None,
        timeout: int = 30,
    ) -> tuple[str, int]:
        """Run a command and capture all output.

        Args:
            command: Command to run.
            args: Command arguments.
            timeout: Timeout in seconds.

        Returns:
            Tuple of (output, exit_code).
        """
        args = args or []
        output_chunks: list[str] = []

        async for chunk in PTYManager.run_command(command, args, timeout):
            output_chunks.append(chunk)

        output = "".join(output_chunks)
        return output, 0

    @staticmethod
    async def check_command_exists(command: str) -> bool:
        """Check if a command exists in PATH.

        Args:
            command: Command name.

        Returns:
            True if command exists.
        """
        return PTYManager.find_executable(command) is not None

    @staticmethod
    async def get_command_version(
        command: str,
        version_arg: str = "--version",
    ) -> str | None:
        """Get the version of a command.

        Args:
            command: Command name.
            version_arg: Argument to get version.

        Returns:
            Version string or None.
        """
        if not await PTYManager.check_command_exists(command):
            return None

        try:
            output, _ = await PTYManager.run_and_capture(
                command,
                [version_arg],
                timeout=10,
            )
            # Extract first line as version
            lines = output.strip().split("\n")
            return lines[0] if lines else None
        except Exception:
            return None
