"""Discussion manager for multi-AI conversations."""

import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

from cli_cih.adapters import AdapterError, AIAdapter
from cli_cih.orchestration.context import SharedContext
from cli_cih.orchestration.task_analyzer import Task


@dataclass
class DiscussionConfig:
    """Configuration for a discussion."""

    max_rounds: int = 5
    consensus_threshold: float = 0.7
    timeout_per_ai: int = 60
    enable_consensus_check: bool = True
    min_response_length: int = 50


@dataclass
class DiscussionState:
    """Current state of a discussion."""

    current_round: int = 0
    is_complete: bool = False
    consensus_reached: bool = False
    error: Optional[str] = None
    ai_responses: dict[str, list[str]] = field(default_factory=dict)


class DiscussionEvent:
    """Base class for discussion events."""
    pass


@dataclass
class RoundStartEvent(DiscussionEvent):
    """Emitted when a round starts."""
    round_num: int
    max_rounds: int


@dataclass
class RoundEndEvent(DiscussionEvent):
    """Emitted when a round ends."""
    round_num: int


@dataclass
class AITurnStartEvent(DiscussionEvent):
    """Emitted when an AI's turn starts."""
    ai_name: str
    ai_icon: str
    ai_color: str


@dataclass
class AIChunkEvent(DiscussionEvent):
    """Emitted for each chunk of AI response."""
    ai_name: str
    chunk: str


@dataclass
class AITurnEndEvent(DiscussionEvent):
    """Emitted when an AI's turn ends."""
    ai_name: str
    full_response: str


@dataclass
class AIErrorEvent(DiscussionEvent):
    """Emitted when an AI encounters an error."""
    ai_name: str
    error: str


@dataclass
class ConsensusCheckEvent(DiscussionEvent):
    """Emitted when checking for consensus."""
    round_num: int
    consensus_reached: bool


@dataclass
class DiscussionCompleteEvent(DiscussionEvent):
    """Emitted when discussion is complete."""
    total_rounds: int
    consensus_reached: bool


class DiscussionManager:
    """Manages multi-AI discussions."""

    def __init__(self, config: Optional[DiscussionConfig] = None):
        """Initialize discussion manager.

        Args:
            config: Discussion configuration.
        """
        self.config = config or DiscussionConfig()
        self.state = DiscussionState()

    async def run(
        self,
        task: Task,
        adapters: list[AIAdapter],
        context: Optional[SharedContext] = None,
    ) -> AsyncIterator[DiscussionEvent]:
        """Run a multi-AI discussion.

        Args:
            task: The task to discuss.
            adapters: List of AI adapters to use.
            context: Optional shared context.

        Yields:
            Discussion events as they occur.
        """
        # Initialize context
        if context is None:
            context = SharedContext(task.prompt)

        # Reset state
        self.state = DiscussionState()

        # Use task's suggested rounds or config max
        max_rounds = min(task.suggested_rounds, self.config.max_rounds)

        # Main discussion loop
        for round_num in range(1, max_rounds + 1):
            self.state.current_round = round_num
            yield RoundStartEvent(round_num, max_rounds)

            # Each AI takes a turn
            for adapter in adapters:
                ai_name = adapter.name

                # Build prompt for this AI
                is_first_round = (round_num == 1)
                prompt = context.build_prompt_for(ai_name, is_first_round)

                yield AITurnStartEvent(
                    ai_name=adapter.display_name,
                    ai_icon=adapter.icon,
                    ai_color=adapter.color,
                )

                # Get AI response
                try:
                    response_chunks = []
                    async for chunk in adapter.send(prompt):
                        response_chunks.append(chunk)
                        yield AIChunkEvent(ai_name=adapter.display_name, chunk=chunk)

                    full_response = "".join(response_chunks)

                    # Add to context
                    context.add_message(ai_name, full_response, round_num)

                    # Track in state
                    if ai_name not in self.state.ai_responses:
                        self.state.ai_responses[ai_name] = []
                    self.state.ai_responses[ai_name].append(full_response)

                    yield AITurnEndEvent(
                        ai_name=adapter.display_name,
                        full_response=full_response,
                    )

                except AdapterError as e:
                    yield AIErrorEvent(ai_name=adapter.display_name, error=str(e))
                    continue

                except asyncio.TimeoutError:
                    yield AIErrorEvent(
                        ai_name=adapter.display_name,
                        error=f"Timeout after {self.config.timeout_per_ai}s",
                    )
                    continue

            yield RoundEndEvent(round_num)

            # Check for consensus after round (except first round)
            if self.config.enable_consensus_check and round_num > 1:
                consensus = await self._check_consensus(context)
                yield ConsensusCheckEvent(round_num, consensus)

                if consensus:
                    self.state.consensus_reached = True
                    context.consensus_reached = True
                    break

        # Discussion complete
        self.state.is_complete = True
        yield DiscussionCompleteEvent(
            total_rounds=self.state.current_round,
            consensus_reached=self.state.consensus_reached,
        )

    async def _check_consensus(self, context: SharedContext) -> bool:
        """Check if AIs have reached consensus.

        This is a simple heuristic check. In production,
        you might use an AI to analyze consensus.

        Args:
            context: The shared context.

        Returns:
            True if consensus seems reached.
        """
        # Simple heuristic: check for agreement phrases in recent messages
        agreement_phrases = [
            "agree", "동의", "맞습니다", "correct", "좋은 의견", "good point",
            "build on", "추가하면", "덧붙이면", "adding to",
        ]

        recent_messages = context.get_recent_messages(4)
        if len(recent_messages) < 2:
            return False

        agreement_count = 0
        for msg in recent_messages:
            content_lower = msg.content.lower()
            for phrase in agreement_phrases:
                if phrase in content_lower:
                    agreement_count += 1
                    break

        # If most recent messages show agreement
        consensus_ratio = agreement_count / len(recent_messages)
        return consensus_ratio >= self.config.consensus_threshold

    def get_discussion_summary(self) -> dict:
        """Get summary of the discussion."""
        return {
            "total_rounds": self.state.current_round,
            "is_complete": self.state.is_complete,
            "consensus_reached": self.state.consensus_reached,
            "ai_count": len(self.state.ai_responses),
            "error": self.state.error,
        }
