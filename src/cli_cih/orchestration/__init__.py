"""Orchestration module for CLI-CIH Multi-AI Discussion System.

This module provides the core functionality for coordinating
multiple AI assistants in collaborative discussions.
"""

from cli_cih.orchestration.ai_selector import AIScore, AISelector
from cli_cih.orchestration.approval import (
    Action,
    ActionType,
    AIVote,
    ApprovalEngine,
    ApprovalResult,
    ApprovalStatus,
    ImportanceLevel,
)
from cli_cih.orchestration.conflict import (
    Conflict,
    ConflictResolver,
    ConflictSeverity,
    Opinion,
    Resolution,
    ResolutionType,
    VotedOption,
)
from cli_cih.orchestration.context import Message, SharedContext
from cli_cih.orchestration.coordinator import (
    AIChunkEvent,
    AIEndEvent,
    AIsSelectedEvent,
    AIStartEvent,
    ApprovalRequestedEvent,
    ApprovalResultEvent,
    ConflictDetectedEvent,
    ConflictResolvedEvent,
    ConsensusReachedEvent,
    Coordinator,
    Event,
    ResultEvent,
    RoundEndEvent,
    RoundStartEvent,
    TaskAnalyzedEvent,
)
from cli_cih.orchestration.discussion import DiscussionConfig, DiscussionManager
from cli_cih.orchestration.synthesizer import SynthesisResult, Synthesizer
from cli_cih.orchestration.task_analyzer import Task, TaskAnalyzer, TaskType

__all__ = [
    # Context
    "SharedContext",
    "Message",
    # Task Analysis
    "TaskAnalyzer",
    "Task",
    "TaskType",
    # AI Selection
    "AISelector",
    "AIScore",
    # Discussion
    "DiscussionManager",
    "DiscussionConfig",
    # Synthesis
    "Synthesizer",
    "SynthesisResult",
    # Coordination
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
    # Conflict Resolution
    "ConflictResolver",
    "Conflict",
    "ConflictSeverity",
    "Resolution",
    "ResolutionType",
    "Opinion",
    "VotedOption",
    # Approval
    "ApprovalEngine",
    "Action",
    "ActionType",
    "ApprovalResult",
    "ApprovalStatus",
    "ImportanceLevel",
    "AIVote",
]
