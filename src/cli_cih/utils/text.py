"""Text processing utilities for CLI-CIH."""

import re

# ANSI 코드 제거 정규식 (모듈 로드 시 1회 컴파일)
ANSI_ESCAPE_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def clean_ansi(text: str) -> str:
    """Remove ANSI escape codes from text.

    Args:
        text: Text containing ANSI escape codes.

    Returns:
        Text with ANSI codes removed.
    """
    return ANSI_ESCAPE_PATTERN.sub("", text)


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """Truncate text to specified length.

    Args:
        text: Text to truncate.
        max_length: Maximum length before truncation.
        suffix: Suffix to add when truncated.

    Returns:
        Truncated text with suffix if needed.
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + suffix
