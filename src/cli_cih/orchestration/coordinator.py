"""Main coordinator for multi-AI discussions."""

from dataclasses import dataclass
from typing import AsyncIterator, Awaitable, Callable, Optional

from cli_cih.adapters import AIAdapter
from cli_cih.orchestration.ai_selector import AISelector
from cli_cih.orchestration.approval import (
    Action,
    ApprovalEngine,
    ApprovalResult,
    ApprovalStatus,
    ImportanceLevel,
)
from cli_cih.orchestration.conflict import (
    Conflict,
    ConflictResolver,
    Resolution,
    ResolutionType,
)
from cli_cih.orchestration.context import SharedContext
from cli_cih.orchestration.discussion import (
    AIChunkEvent,
    AIErrorEvent,
    AITurnEndEvent,
    AITurnStartEvent,
    ConsensusCheckEvent,
    DiscussionCompleteEvent,
    DiscussionConfig,
    DiscussionEvent,
    DiscussionManager,
    RoundEndEvent,
    RoundStartEvent,
)
from cli_cih.orchestration.synthesizer import SynthesisResult, Synthesizer
from cli_cih.orchestration.task_analyzer import Task, TaskAnalyzer

# Re-export discussion events
__all__ = [
    "Coordinator",
    "Event",
    "TaskAnalyzedEvent",
    "AIsSelectedEvent",
    "RoundStartEvent",
    "AIStartEvent",
    "AIChunkEvent",
    "AIEndEvent",
    "RoundEndEvent",
    "ConsensusReachedEvent",
    "ConflictDetectedEvent",
    "ConflictResolvedEvent",
    "ApprovalRequestedEvent",
    "ApprovalResultEvent",
    "ResultEvent",
]


# Base event class
class Event:
    """Base class for coordinator events."""
    pass


@dataclass
class TaskAnalyzedEvent(Event):
    """Emitted when task analysis is complete."""
    task: Task


@dataclass
class AIsSelectedEvent(Event):
    """Emitted when AIs are selected."""
    adapters: list[AIAdapter]
    explanation: str


@dataclass
class AIStartEvent(Event):
    """Emitted when an AI starts responding."""
    ai_name: str
    ai_icon: str
    ai_color: str


@dataclass
class AIEndEvent(Event):
    """Emitted when an AI finishes responding."""
    ai_name: str
    response: str


@dataclass
class ConsensusReachedEvent(Event):
    """Emitted when consensus is reached."""
    round_num: int


@dataclass
class ConflictDetectedEvent(Event):
    """Emitted when AI conflict is detected."""
    conflict: Conflict
    resolution: Resolution


@dataclass
class ConflictResolvedEvent(Event):
    """Emitted when conflict is resolved."""
    conflict: Conflict
    resolution: Resolution
    user_choice: Optional[str] = None


@dataclass
class ApprovalRequestedEvent(Event):
    """Emitted when user approval is needed."""
    action: Action
    importance: ImportanceLevel


@dataclass
class ApprovalResultEvent(Event):
    """Emitted with approval result."""
    result: ApprovalResult


@dataclass
class ResultEvent(Event):
    """Emitted with final results."""
    result: SynthesisResult
    context: SharedContext


class Coordinator:
    """Coordinates multi-AI discussions.

    The coordinator orchestrates the entire discussion process:
    1. Analyze the task
    2. Select appropriate AIs
    3. Run the discussion
    4. Detect and resolve conflicts
    5. Handle approvals if needed
    6. Synthesize results
    """

    def __init__(
        self,
        discussion_config: Optional[DiscussionConfig] = None,
        min_ais: int = 2,
        max_ais: int = 4,
        enable_conflict_detection: bool = True,
        enable_approval: bool = True,
    ):
        """Initialize coordinator.

        Args:
            discussion_config: Configuration for discussions.
            min_ais: Minimum number of AIs to use.
            max_ais: Maximum number of AIs to use.
            enable_conflict_detection: Whether to detect conflicts.
            enable_approval: Whether to request approvals.
        """
        self.analyzer = TaskAnalyzer()
        self.selector = AISelector(min_ais=min_ais, max_ais=max_ais)
        self.discussion = DiscussionManager(discussion_config)
        self.synthesizer = Synthesizer()
        self.conflict_resolver: Optional[ConflictResolver] = None
        self.approval_engine = ApprovalEngine()

        self.enable_conflict_detection = enable_conflict_detection
        self.enable_approval = enable_approval

        self._current_task: Optional[Task] = None
        self._current_adapters: list[AIAdapter] = []
        self._context: Optional[SharedContext] = None
        self._detected_conflict: Optional[Conflict] = None
        self._conflict_resolution: Optional[Resolution] = None

        # Callbacks for interactive conflict/approval handling
        self._conflict_callback: Optional[Callable[[Conflict, Resolution], Awaitable[str]]] = None
        self._approval_callback: Optional[Callable[[Action, ImportanceLevel], Awaitable[ApprovalResult]]] = None

    def set_conflict_callback(
        self,
        callback: Callable[[Conflict, Resolution], Awaitable[str]],
    ) -> None:
        """Set callback for conflict resolution UI.

        Args:
            callback: Async function that handles conflict UI.
        """
        self._conflict_callback = callback

    def set_approval_callback(
        self,
        callback: Callable[[Action, ImportanceLevel], Awaitable[ApprovalResult]],
    ) -> None:
        """Set callback for approval UI.

        Args:
            callback: Async function that handles approval UI.
        """
        self._approval_callback = callback
        self.approval_engine.set_approval_callback(callback)

    async def process(
        self,
        user_input: str,
        available_adapters: Optional[list[AIAdapter]] = None,
    ) -> AsyncIterator[Event]:
        """Process a user input through the full discussion pipeline.

        Args:
            user_input: The user's input/question.
            available_adapters: Optional list of available adapters.

        Yields:
            Events as the discussion progresses.
        """
        from cli_cih.orchestration.task_analyzer import TaskType

        # 1. Analyze the task
        task = self.analyzer.analyze(user_input)
        self._current_task = task

        # ★ Fast path: Simple chat or low complexity - skip task analysis display
        if task.task_type == TaskType.SIMPLE_CHAT or task.complexity < 0.3:
            # 간단한 대화는 토론 없이 즉시 응답!
            async for event in self._fast_single_ai_response(user_input, available_adapters):
                yield event
            return

        # Only show task analysis for complex tasks
        yield TaskAnalyzedEvent(task=task)

        # Initialize conflict resolver with task type
        if self.enable_conflict_detection:
            self.conflict_resolver = ConflictResolver(task_type=task.task_type)

        # 2. Select AIs
        adapters = await self.selector.select(task, available_adapters)
        self._current_adapters = adapters

        if not adapters:
            # No AIs available
            yield AIsSelectedEvent(
                adapters=[],
                explanation="No AI adapters available for this task.",
            )
            return

        explanation = self.selector.get_selection_explanation(task, adapters)
        yield AIsSelectedEvent(adapters=adapters, explanation=explanation)

        # 3. Initialize context
        self._context = SharedContext(user_input)

        # 4. Run discussion with conflict detection
        current_round = 0
        async for event in self.discussion.run(task, adapters, self._context):
            # Convert discussion events to coordinator events
            converted = self._convert_event(event)
            yield converted

            # Track round for conflict detection
            if isinstance(event, RoundEndEvent):
                current_round = event.round_num

                # Check for conflicts after each round (starting from round 2)
                if self.enable_conflict_detection and current_round >= 2:
                    conflict_event = await self._check_for_conflict()
                    if conflict_event:
                        yield conflict_event

                        # If user decision needed, yield resolution event
                        if (self._conflict_resolution and
                            self._conflict_resolution.type == ResolutionType.USER_DECISION):
                            resolution_event = await self._handle_conflict_resolution()
                            if resolution_event:
                                yield resolution_event

        # 5. Synthesize results
        result = await self.synthesizer.synthesize(self._context)
        yield ResultEvent(result=result, context=self._context)

    async def _check_for_conflict(self) -> Optional[ConflictDetectedEvent]:
        """Check for conflicts in the current discussion.

        Returns:
            ConflictDetectedEvent if conflict found, None otherwise.
        """
        if not self.conflict_resolver or not self._context:
            return None

        conflict = self.conflict_resolver.detect_conflict(self._context)

        if conflict:
            self._detected_conflict = conflict
            resolution = await self.conflict_resolver.resolve(conflict)
            self._conflict_resolution = resolution

            return ConflictDetectedEvent(
                conflict=conflict,
                resolution=resolution,
            )

        return None

    async def _handle_conflict_resolution(self) -> Optional[ConflictResolvedEvent]:
        """Handle conflict resolution, potentially with user input.

        Returns:
            ConflictResolvedEvent after resolution.
        """
        if not self._detected_conflict or not self._conflict_resolution:
            return None

        user_choice = None

        # If user decision needed and callback available
        if (self._conflict_resolution.type == ResolutionType.USER_DECISION and
            self._conflict_callback):
            user_choice = await self._conflict_callback(
                self._detected_conflict,
                self._conflict_resolution,
            )

            # Update context with user's decision
            if user_choice and user_choice != 'more':
                self._context.add_key_point(f"User chose: {user_choice}")

        return ConflictResolvedEvent(
            conflict=self._detected_conflict,
            resolution=self._conflict_resolution,
            user_choice=user_choice,
        )

    def _convert_event(self, event: DiscussionEvent) -> Event:
        """Convert discussion event to coordinator event."""
        if isinstance(event, RoundStartEvent):
            return event  # Pass through
        elif isinstance(event, RoundEndEvent):
            return event  # Pass through
        elif isinstance(event, AITurnStartEvent):
            return AIStartEvent(
                ai_name=event.ai_name,
                ai_icon=event.ai_icon,
                ai_color=event.ai_color,
            )
        elif isinstance(event, AIChunkEvent):
            return event  # Pass through
        elif isinstance(event, AITurnEndEvent):
            return AIEndEvent(
                ai_name=event.ai_name,
                response=event.full_response,
            )
        elif isinstance(event, ConsensusCheckEvent):
            if event.consensus_reached:
                return ConsensusReachedEvent(round_num=event.round_num)
            return event  # Pass through
        elif isinstance(event, DiscussionCompleteEvent):
            return event  # Pass through
        else:
            return event  # Pass through unknown events

    async def quick_discussion(
        self,
        user_input: str,
        max_rounds: int = 3,
    ) -> SynthesisResult:
        """Run a quick discussion and return results.

        Args:
            user_input: The user's input.
            max_rounds: Maximum rounds for discussion.

        Returns:
            Synthesis result.
        """
        result = None
        async for event in self.process(user_input):
            if isinstance(event, ResultEvent):
                result = event.result

        return result

    def get_current_state(self) -> dict:
        """Get current coordinator state."""
        return {
            "task": self._current_task,
            "adapters": [a.name for a in self._current_adapters],
            "context_summary": self._context.get_summary() if self._context else None,
        }

    async def _fast_single_ai_response(
        self,
        user_input: str,
        available_adapters: Optional[list[AIAdapter]] = None,
    ) -> AsyncIterator[Event]:
        """Fast path for simple queries using a single AI.

        Args:
            user_input: The user's input.
            available_adapters: Available adapters.

        Yields:
            Events for single AI response.
        """
        from cli_cih.adapters import get_all_adapters

        # Get first available adapter
        if available_adapters is None:
            all_adapters = get_all_adapters()
            available_adapters = []
            for adapter in all_adapters:
                if await adapter.is_available():
                    available_adapters.append(adapter)

        if not available_adapters:
            yield AIsSelectedEvent(
                adapters=[],
                explanation="No AI adapters available.",
            )
            return

        # Use first available adapter for fast response
        adapter = available_adapters[0]
        self._current_adapters = [adapter]

        yield AIsSelectedEvent(
            adapters=[adapter],
            explanation=f"Quick response from {adapter.display_name}",
        )

        # Initialize minimal context
        self._context = SharedContext(user_input)

        # Start single AI response
        yield AIStartEvent(
            ai_name=adapter.display_name,
            ai_icon=adapter.icon,
            ai_color=adapter.color,
        )

        # Stream response
        full_response = ""
        try:
            async for chunk in adapter.send(user_input):
                full_response += chunk
                yield AIChunkEvent(
                    ai_name=adapter.display_name,
                    chunk=chunk,
                )
        except Exception as e:
            yield AIErrorEvent(
                ai_name=adapter.display_name,
                error=str(e),
            )
            return

        yield AIEndEvent(
            ai_name=adapter.display_name,
            response=full_response,
        )

        # Minimal result
        from cli_cih.orchestration.synthesizer import SynthesisResult
        result = SynthesisResult(
            summary=full_response[:200] + "..." if len(full_response) > 200 else full_response,
            key_points=[],
            agreements=[],
            disagreements=[],
            recommendations=[],
            total_rounds=1,
            total_messages=1,
            consensus_reached=True,
            ai_contributions={adapter.name: 100.0},
        )
        yield ResultEvent(result=result, context=self._context)
