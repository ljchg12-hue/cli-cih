"""Tests for utils/text module."""

import pytest
from cli_cih.utils.text import clean_ansi, truncate_text, ANSI_ESCAPE_PATTERN


class TestCleanAnsi:
    """Tests for clean_ansi function."""

    def test_clean_ansi_removes_color_codes(self):
        """Should remove ANSI color codes."""
        colored = "\x1b[31mRed text\x1b[0m"
        result = clean_ansi(colored)
        assert result == "Red text"

    def test_clean_ansi_removes_bold(self):
        """Should remove bold formatting."""
        bold = "\x1b[1mBold text\x1b[0m"
        result = clean_ansi(bold)
        assert result == "Bold text"

    def test_clean_ansi_removes_multiple_codes(self):
        """Should remove multiple ANSI codes."""
        formatted = "\x1b[1m\x1b[31mBold Red\x1b[0m Normal"
        result = clean_ansi(formatted)
        assert result == "Bold Red Normal"

    def test_clean_ansi_preserves_plain_text(self):
        """Should not modify plain text."""
        plain = "Hello World"
        result = clean_ansi(plain)
        assert result == "Hello World"

    def test_clean_ansi_empty_string(self):
        """Should handle empty string."""
        result = clean_ansi("")
        assert result == ""

    def test_clean_ansi_cursor_movement(self):
        """Should remove cursor movement codes."""
        cursor = "\x1b[2J\x1b[HHello"
        result = clean_ansi(cursor)
        assert result == "Hello"


class TestTruncateText:
    """Tests for truncate_text function."""

    def test_truncate_short_text_unchanged(self):
        """Short text should not be truncated."""
        text = "Short"
        result = truncate_text(text, max_length=100)
        assert result == "Short"

    def test_truncate_exact_length_unchanged(self):
        """Text exactly at max_length should not be truncated."""
        text = "Exactly ten"
        result = truncate_text(text, max_length=11)
        assert result == "Exactly ten"

    def test_truncate_long_text(self):
        """Long text should be truncated with suffix."""
        text = "This is a very long text that needs truncation"
        result = truncate_text(text, max_length=20)
        assert len(result) == 23  # 20 + "..."
        assert result.endswith("...")

    def test_truncate_custom_suffix(self):
        """Should use custom suffix."""
        text = "Long text here"
        result = truncate_text(text, max_length=5, suffix=">>")
        assert result.endswith(">>")

    def test_truncate_empty_string(self):
        """Should handle empty string."""
        result = truncate_text("", max_length=100)
        assert result == ""


class TestAnsiPattern:
    """Tests for ANSI_ESCAPE_PATTERN."""

    def test_pattern_compiled(self):
        """Pattern should be pre-compiled."""
        assert ANSI_ESCAPE_PATTERN is not None
        assert hasattr(ANSI_ESCAPE_PATTERN, 'sub')

    def test_pattern_matches_colors(self):
        """Pattern should match color codes."""
        text = "\x1b[31m"
        assert ANSI_ESCAPE_PATTERN.search(text) is not None

    def test_pattern_no_match_plain_text(self):
        """Pattern should not match plain text."""
        text = "Hello World"
        assert ANSI_ESCAPE_PATTERN.search(text) is None
