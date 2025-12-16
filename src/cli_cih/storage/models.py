"""Database models for CLI-CIH history storage."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    """Status of a discussion session."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class SenderType(str, Enum):
    """Type of message sender."""

    USER = "user"
    AI = "ai"
    SYSTEM = "system"


@dataclass
class HistoryMessage:
    """A message in the conversation history."""

    id: str
    session_id: str
    sender_type: SenderType
    sender_id: str  # e.g., 'claude', 'gemini', 'user'
    content: str
    created_at: datetime = field(default_factory=datetime.now)
    round_num: int = 0
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        session_id: str,
        sender_type: SenderType,
        sender_id: str,
        content: str,
        round_num: int = 0,
        metadata: dict | None = None,
    ) -> "HistoryMessage":
        """Create a new message with generated ID."""
        return cls(
            id=str(uuid.uuid4()),
            session_id=session_id,
            sender_type=sender_type,
            sender_id=sender_id,
            content=content,
            round_num=round_num,
            metadata=metadata or {},
        )


@dataclass
class SessionResult:
    """Final result of a discussion session."""

    id: str
    session_id: str
    summary: str
    key_points: list[str] = field(default_factory=list)
    consensus_reached: bool = False
    confidence: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(
        cls,
        session_id: str,
        summary: str,
        key_points: list[str] | None = None,
        consensus_reached: bool = False,
        confidence: float = 0.0,
    ) -> "SessionResult":
        """Create a new result with generated ID."""
        return cls(
            id=str(uuid.uuid4()),
            session_id=session_id,
            summary=summary,
            key_points=key_points or [],
            consensus_reached=consensus_reached,
            confidence=confidence,
        )


@dataclass
class Session:
    """A discussion session."""

    id: str
    user_query: str
    task_type: str
    participating_ais: list[str]
    total_rounds: int = 0
    status: SessionStatus = SessionStatus.IN_PROGRESS
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    messages: list[HistoryMessage] = field(default_factory=list)
    result: SessionResult | None = None

    @classmethod
    def create(
        cls,
        user_query: str,
        task_type: str = "general",
        participating_ais: list[str] | None = None,
    ) -> "Session":
        """Create a new session with generated ID."""
        return cls(
            id=str(uuid.uuid4()),
            user_query=user_query,
            task_type=task_type,
            participating_ais=participating_ais or [],
        )

    def add_message(
        self,
        sender_type: SenderType,
        sender_id: str,
        content: str,
        round_num: int = 0,
        metadata: dict | None = None,
    ) -> HistoryMessage:
        """Add a message to the session."""
        message = HistoryMessage.create(
            session_id=self.id,
            sender_type=sender_type,
            sender_id=sender_id,
            content=content,
            round_num=round_num,
            metadata=metadata,
        )
        self.messages.append(message)
        self.updated_at = datetime.now()
        return message

    def set_result(
        self,
        summary: str,
        key_points: list[str] | None = None,
        consensus_reached: bool = False,
        confidence: float = 0.0,
    ) -> SessionResult:
        """Set the session result."""
        self.result = SessionResult.create(
            session_id=self.id,
            summary=summary,
            key_points=key_points,
            consensus_reached=consensus_reached,
            confidence=confidence,
        )
        self.status = SessionStatus.COMPLETED
        self.updated_at = datetime.now()
        return self.result

    def mark_error(self, error_message: str = "") -> None:
        """Mark session as errored."""
        self.status = SessionStatus.ERROR
        self.updated_at = datetime.now()
        if error_message:
            self.add_message(SenderType.SYSTEM, "system", f"Error: {error_message}")

    def mark_cancelled(self) -> None:
        """Mark session as cancelled."""
        self.status = SessionStatus.CANCELLED
        self.updated_at = datetime.now()

    @property
    def duration_seconds(self) -> float:
        """Get session duration in seconds."""
        return (self.updated_at - self.created_at).total_seconds()

    @property
    def summary_text(self) -> str:
        """Get a brief summary for display."""
        query_preview = (
            self.user_query[:50] + "..." if len(self.user_query) > 50 else self.user_query
        )
        return f"{query_preview} ({len(self.participating_ais)} AIs, {self.total_rounds} rounds)"
