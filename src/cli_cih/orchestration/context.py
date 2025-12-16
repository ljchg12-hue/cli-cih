"""Shared context management for multi-AI discussions."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Message:
    """A message in the discussion."""

    ai_name: str
    content: str
    round_num: int
    timestamp: datetime = field(default_factory=datetime.now)
    token_count: int = 0

    def __post_init__(self):
        # Rough token estimation (4 chars per token)
        if self.token_count == 0:
            self.token_count = len(self.content) // 4


class SharedContext:
    """Manages shared context for multi-AI discussions.

    This class maintains the conversation history and provides
    methods to build prompts for each AI based on the current context.
    """

    def __init__(
        self,
        original_prompt: str,
        max_tokens: int = 8000,
        max_history_per_ai: int = 5,
    ):
        """Initialize shared context.

        Args:
            original_prompt: The original user prompt.
            max_tokens: Maximum tokens to include in context.
            max_history_per_ai: Max messages to keep per AI.
        """
        self.original_prompt = original_prompt
        self.max_tokens = max_tokens
        self.max_history_per_ai = max_history_per_ai

        self.messages: list[Message] = []
        self.ai_message_counts: dict[str, int] = defaultdict(int)
        self.current_round = 0
        self.consensus_reached = False
        self.key_points: list[str] = []

    def add_message(self, ai_name: str, content: str, round_num: int) -> Message:
        """Add a message to the context.

        Args:
            ai_name: Name of the AI.
            content: Message content.
            round_num: Current round number.

        Returns:
            The created Message.
        """
        message = Message(
            ai_name=ai_name,
            content=content,
            round_num=round_num,
        )
        self.messages.append(message)
        self.ai_message_counts[ai_name] += 1
        self.current_round = max(self.current_round, round_num)

        # Extract key points (simple heuristic)
        self._extract_key_points(content)

        return message

    def _extract_key_points(self, content: str) -> None:
        """Extract key points from content."""
        # Simple heuristic: look for numbered points or bullet points
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line and (
                line[0].isdigit()
                or line.startswith("-")
                or line.startswith("*")
                or line.startswith("•")
            ):
                # Limit to first 100 chars
                point = line[:100]
                if point not in self.key_points:
                    self.key_points.append(point)
                    # Keep only last 20 key points
                    if len(self.key_points) > 20:
                        self.key_points.pop(0)

    def add_key_point(self, point: str) -> None:
        """Add a key point to the context.

        Args:
            point: Key point to add.
        """
        if point and point not in self.key_points:
            self.key_points.append(point[:100])
            # Keep only last 20 key points
            if len(self.key_points) > 20:
                self.key_points.pop(0)

    def get_messages_for_round(self, round_num: int) -> list[Message]:
        """Get all messages for a specific round."""
        return [m for m in self.messages if m.round_num == round_num]

    def get_messages_by_ai(self, ai_name: str) -> list[Message]:
        """Get all messages from a specific AI."""
        return [m for m in self.messages if m.ai_name == ai_name]

    def get_recent_messages(self, count: int = 10) -> list[Message]:
        """Get the most recent messages."""
        return self.messages[-count:]

    def build_prompt_for(
        self,
        ai_name: str,
        is_first_round: bool = False,
    ) -> str:
        """Build a prompt for a specific AI.

        Args:
            ai_name: Name of the AI to build prompt for.
            is_first_round: Whether this is the first round.

        Returns:
            Prompt string.
        """
        parts = []

        # System context
        parts.append("You are participating in a collaborative AI discussion.")
        parts.append("Multiple AIs are working together to help the user.")
        parts.append("Be concise but thorough. Build on others' ideas.")
        parts.append("If you agree, say so briefly and add value.")
        parts.append("If you disagree, explain why constructively.")
        parts.append("")

        # Original question
        parts.append(f"USER'S QUESTION: {self.original_prompt}")
        parts.append("")

        if is_first_round:
            parts.append("This is the first round. Share your initial thoughts.")
        else:
            # Include discussion history
            parts.append("DISCUSSION SO FAR:")
            parts.append("")

            # Get recent messages, prioritizing other AIs
            recent = self._get_context_messages(ai_name)
            for msg in recent:
                prefix = f"[{msg.ai_name.upper()}]"
                # Truncate long messages
                content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
                parts.append(f"{prefix} {content}")
                parts.append("")

            # Add key points if available
            if self.key_points:
                parts.append("KEY POINTS IDENTIFIED:")
                for point in self.key_points[-5:]:
                    parts.append(f"  {point}")
                parts.append("")

            parts.append(f"Now it's your turn ({ai_name}). Respond to the discussion.")
            parts.append("Add new insights or build on what others have said.")

        return "\n".join(parts)

    def _get_context_messages(self, current_ai: str) -> list[Message]:
        """Get messages to include in context, respecting token limits."""
        # Start with most recent messages
        messages = []
        token_count = 0

        for msg in reversed(self.messages):
            msg_tokens = msg.token_count
            if token_count + msg_tokens > self.max_tokens // 2:
                break
            messages.insert(0, msg)
            token_count += msg_tokens

        return messages

    def get_all_content(self) -> str:
        """Get all discussion content as a single string."""
        parts = [f"Original Question: {self.original_prompt}\n"]

        current_round = 0
        for msg in self.messages:
            if msg.round_num != current_round:
                current_round = msg.round_num
                parts.append(f"\n--- Round {current_round} ---\n")
            parts.append(f"[{msg.ai_name.upper()}]: {msg.content}\n")

        return "".join(parts)

    def get_summary(self) -> dict:
        """Get a summary of the discussion."""
        ai_contributions = {}
        for ai_name, count in self.ai_message_counts.items():
            messages = self.get_messages_by_ai(ai_name)
            total_tokens = sum(m.token_count for m in messages)
            ai_contributions[ai_name] = {
                "message_count": count,
                "total_tokens": total_tokens,
            }

        return {
            "original_prompt": self.original_prompt[:100],
            "total_messages": len(self.messages),
            "total_rounds": self.current_round,
            "ai_contributions": ai_contributions,
            "key_points_count": len(self.key_points),
            "consensus_reached": self.consensus_reached,
        }
