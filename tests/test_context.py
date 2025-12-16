"""Tests for SharedContext module."""

import pytest
from datetime import datetime
from cli_cih.orchestration.context import SharedContext, Message


class TestMessage:
    """Tests for Message dataclass."""

    def test_message_creation(self):
        """Message should be created with required fields."""
        msg = Message(
            ai_name="claude",
            content="Test response",
            round_num=1,
        )
        assert msg.ai_name == "claude"
        assert msg.content == "Test response"
        assert msg.round_num == 1
        assert isinstance(msg.timestamp, datetime)

    def test_message_auto_token_count(self):
        """Message should auto-calculate token count."""
        content = "A" * 100  # 100 chars
        msg = Message(ai_name="test", content=content, round_num=1)
        # Rough estimation: 4 chars per token
        assert msg.token_count == 25

    def test_message_explicit_token_count(self):
        """Explicit token count should be used if provided."""
        msg = Message(
            ai_name="test",
            content="test",
            round_num=1,
            token_count=50
        )
        assert msg.token_count == 50


class TestSharedContext:
    """Tests for SharedContext."""

    @pytest.fixture
    def context(self):
        return SharedContext(original_prompt="Test question")

    def test_context_initialization(self, context):
        """Context should initialize with correct defaults."""
        assert context.original_prompt == "Test question"
        assert context.messages == []
        assert context.current_round == 0
        assert context.consensus_reached is False

    def test_add_message(self, context):
        """Adding message should work correctly."""
        msg = context.add_message("claude", "Test response", round_num=1)

        assert len(context.messages) == 1
        assert msg.ai_name == "claude"
        assert msg.content == "Test response"
        assert context.current_round == 1
        assert context.ai_message_counts["claude"] == 1

    def test_add_multiple_messages(self, context):
        """Adding multiple messages should track correctly."""
        context.add_message("claude", "Response 1", round_num=1)
        context.add_message("codex", "Response 2", round_num=1)
        context.add_message("claude", "Response 3", round_num=2)

        assert len(context.messages) == 3
        assert context.ai_message_counts["claude"] == 2
        assert context.ai_message_counts["codex"] == 1
        assert context.current_round == 2

    def test_add_key_point(self, context):
        """add_key_point should add points correctly."""
        context.add_key_point("Important point 1")
        context.add_key_point("Important point 2")

        assert len(context.key_points) == 2
        assert "Important point 1" in context.key_points
        assert "Important point 2" in context.key_points

    def test_add_key_point_no_duplicates(self, context):
        """add_key_point should not add duplicates."""
        context.add_key_point("Same point")
        context.add_key_point("Same point")

        assert len(context.key_points) == 1

    def test_add_key_point_truncates_long_points(self, context):
        """add_key_point should truncate points over 100 chars."""
        long_point = "A" * 150
        context.add_key_point(long_point)

        assert len(context.key_points[0]) == 100

    def test_add_key_point_limit(self, context):
        """key_points should be limited to 20 items."""
        for i in range(25):
            context.add_key_point(f"Point {i}")

        assert len(context.key_points) == 20
        # First 5 should be removed
        assert "Point 0" not in context.key_points
        assert "Point 24" in context.key_points


class TestSharedContextQueries:
    """Tests for SharedContext query methods."""

    @pytest.fixture
    def context_with_messages(self):
        context = SharedContext(original_prompt="Test")
        context.add_message("claude", "Round 1 Claude", round_num=1)
        context.add_message("codex", "Round 1 Codex", round_num=1)
        context.add_message("claude", "Round 2 Claude", round_num=2)
        context.add_message("gemini", "Round 2 Gemini", round_num=2)
        return context

    def test_get_messages_for_round(self, context_with_messages):
        """get_messages_for_round should return correct messages."""
        round_1 = context_with_messages.get_messages_for_round(1)
        assert len(round_1) == 2
        assert all(m.round_num == 1 for m in round_1)

        round_2 = context_with_messages.get_messages_for_round(2)
        assert len(round_2) == 2
        assert all(m.round_num == 2 for m in round_2)

    def test_get_messages_by_ai(self, context_with_messages):
        """get_messages_by_ai should return correct messages."""
        claude_msgs = context_with_messages.get_messages_by_ai("claude")
        assert len(claude_msgs) == 2
        assert all(m.ai_name == "claude" for m in claude_msgs)

    def test_get_recent_messages(self, context_with_messages):
        """get_recent_messages should return most recent messages."""
        recent = context_with_messages.get_recent_messages(2)
        assert len(recent) == 2
        assert recent[0].content == "Round 2 Claude"
        assert recent[1].content == "Round 2 Gemini"


class TestSharedContextPromptBuilding:
    """Tests for prompt building."""

    @pytest.fixture
    def context(self):
        return SharedContext(original_prompt="What is Python?")

    def test_build_prompt_first_round(self, context):
        """First round prompt should include original question."""
        prompt = context.build_prompt_for("claude", is_first_round=True)

        assert "What is Python?" in prompt
        assert "first round" in prompt.lower()

    def test_build_prompt_subsequent_round(self, context):
        """Subsequent round prompt should include discussion history."""
        context.add_message("gemini", "Python is a programming language", round_num=1)
        prompt = context.build_prompt_for("claude", is_first_round=False)

        assert "What is Python?" in prompt
        assert "DISCUSSION SO FAR" in prompt
        assert "GEMINI" in prompt


class TestSharedContextSummary:
    """Tests for context summary."""

    @pytest.fixture
    def context_with_data(self):
        context = SharedContext(original_prompt="Test question")
        context.add_message("claude", "Response 1", round_num=1)
        context.add_message("codex", "Response 2", round_num=1)
        context.add_key_point("Key point 1")
        return context

    def test_get_summary(self, context_with_data):
        """get_summary should return correct summary."""
        summary = context_with_data.get_summary()

        assert "original_prompt" in summary
        assert summary["total_messages"] == 2
        assert summary["total_rounds"] == 1
        assert "ai_contributions" in summary
        assert "claude" in summary["ai_contributions"]
        assert "codex" in summary["ai_contributions"]
        assert summary["key_points_count"] == 1

    def test_get_all_content(self, context_with_data):
        """get_all_content should return formatted content."""
        content = context_with_data.get_all_content()

        assert "Original Question:" in content
        assert "[CLAUDE]:" in content
        assert "[CODEX]:" in content
        assert "Round 1" in content
