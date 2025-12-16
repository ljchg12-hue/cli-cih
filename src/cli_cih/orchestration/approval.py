"""Approval system for multi-AI actions."""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ImportanceLevel(str, Enum):
    """Importance levels for actions."""

    LOW = "low"  # Auto-approved
    MEDIUM = "medium"  # Notification, can auto-approve
    HIGH = "high"  # Requires explicit approval
    CRITICAL = "critical"  # Must confirm with details


class ActionType(str, Enum):
    """Types of actions that can be performed."""

    FILE_CREATE = "file_create"
    FILE_MODIFY = "file_modify"
    FILE_DELETE = "file_delete"
    COMMAND_EXECUTE = "command_execute"
    API_CALL = "api_call"
    CONFIG_CHANGE = "config_change"
    INSTALL_PACKAGE = "install_package"
    SUGGESTION = "suggestion"


class ApprovalStatus(str, Enum):
    """Status of approval request."""

    AUTO_APPROVED = "auto_approved"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    PENDING = "pending"


@dataclass
class AIVote:
    """An AI's vote on an action."""

    ai_name: str
    ai_icon: str
    approves: bool
    confidence: float  # 0.0 to 1.0
    reasoning: str = ""


@dataclass
class Action:
    """Represents an action proposed by AIs."""

    action_type: ActionType
    description: str
    details: dict[str, Any] = field(default_factory=dict)

    # Action specifics
    files_to_create: list[str] = field(default_factory=list)
    files_to_modify: list[str] = field(default_factory=list)
    files_to_delete: list[str] = field(default_factory=list)
    commands_to_execute: list[str] = field(default_factory=list)

    # Flags
    modifies_files: bool = False
    executes_commands: bool = False
    has_destructive_operation: bool = False
    reversible: bool = True

    # AI consensus
    ai_votes: list[AIVote] = field(default_factory=list)

    @property
    def total_confidence(self) -> float:
        """Calculate total confidence from AI votes."""
        if not self.ai_votes:
            return 0.0
        approving = [v for v in self.ai_votes if v.approves]
        if not approving:
            return 0.0
        return sum(v.confidence for v in approving) / len(self.ai_votes)

    @property
    def approval_ratio(self) -> float:
        """Calculate ratio of approving AIs."""
        if not self.ai_votes:
            return 0.0
        approving = len([v for v in self.ai_votes if v.approves])
        return approving / len(self.ai_votes)


@dataclass
class ApprovalResult:
    """Result of an approval request."""

    status: ApprovalStatus
    action: Action
    user_feedback: str = ""
    modifications: dict[str, Any] = field(default_factory=dict)


# Dangerous patterns in commands
DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\brm\s+.*\*",
    r"\bsudo\b",
    r"\bchmod\s+777\b",
    r"\bdrop\s+database\b",
    r"\btruncate\b",
    r"\bformat\b",
    r"\bfdisk\b",
    r">\s*/dev/",
    r"\bdd\s+if=",
]

# Sensitive file patterns
SENSITIVE_FILES = [
    r"\.env",
    r"\.git/",
    r"\.ssh/",
    r"credentials",
    r"secrets?\.ya?ml",
    r"config\.ya?ml",
    r"package-lock\.json",
    r"yarn\.lock",
]


class ApprovalEngine:
    """Engine for managing action approvals."""

    def __init__(
        self,
        auto_approve_low: bool = True,
        auto_approve_medium: bool = False,
    ):
        """Initialize approval engine.

        Args:
            auto_approve_low: Auto-approve low importance actions.
            auto_approve_medium: Auto-approve medium importance actions.
        """
        self.auto_approve_low = auto_approve_low
        self.auto_approve_medium = auto_approve_medium
        self._approval_callback: (
            Callable[[Action, ImportanceLevel], Awaitable[ApprovalResult]] | None
        ) = None

    def set_approval_callback(
        self,
        callback: Callable[[Action, ImportanceLevel], Awaitable[ApprovalResult]],
    ) -> None:
        """Set the callback for approval UI.

        Args:
            callback: Async function that shows approval UI and returns result.
        """
        self._approval_callback = callback

    def calculate_importance(self, action: Action) -> ImportanceLevel:
        """Calculate importance level of an action.

        Args:
            action: The action to evaluate.

        Returns:
            ImportanceLevel indicating required approval level.
        """
        score: float = 0

        # File operations
        if action.modifies_files:
            score += 2

        if action.files_to_create:
            score += len(action.files_to_create) * 0.5

        if action.files_to_modify:
            score += len(action.files_to_modify) * 1
            # Check for sensitive files
            for f in action.files_to_modify:
                if self._is_sensitive_file(f):
                    score += 2

        if action.files_to_delete:
            score += len(action.files_to_delete) * 2

        # Command execution
        if action.executes_commands:
            score += 2
            # Check for dangerous commands
            for cmd in action.commands_to_execute:
                if self._is_dangerous_command(cmd):
                    score += 3

        # Destructive operations
        if action.has_destructive_operation:
            score += 3

        # Reversibility
        if not action.reversible:
            score += 2

        # AI consensus factor
        if action.ai_votes:
            # Low consensus increases importance
            if action.approval_ratio < 0.5:
                score += 2
            elif action.approval_ratio < 0.8:
                score += 1

        # Determine level
        if score <= 1:
            return ImportanceLevel.LOW
        elif score <= 3:
            return ImportanceLevel.MEDIUM
        elif score <= 5:
            return ImportanceLevel.HIGH
        else:
            return ImportanceLevel.CRITICAL

    def _is_sensitive_file(self, filepath: str) -> bool:
        """Check if file is sensitive."""
        filepath_lower = filepath.lower()
        for pattern in SENSITIVE_FILES:
            if re.search(pattern, filepath_lower, re.IGNORECASE):
                return True
        return False

    def _is_dangerous_command(self, command: str) -> bool:
        """Check if command is dangerous."""
        command_lower = command.lower()
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, command_lower, re.IGNORECASE):
                return True
        return False

    async def request_approval(self, action: Action) -> ApprovalResult:
        """Request approval for an action.

        Args:
            action: The action requiring approval.

        Returns:
            ApprovalResult with status and any modifications.
        """
        importance = self.calculate_importance(action)

        # Auto-approve if configured
        if importance == ImportanceLevel.LOW and self.auto_approve_low:
            return ApprovalResult(
                status=ApprovalStatus.AUTO_APPROVED,
                action=action,
            )

        if importance == ImportanceLevel.MEDIUM and self.auto_approve_medium:
            return ApprovalResult(
                status=ApprovalStatus.AUTO_APPROVED,
                action=action,
            )

        # Use callback if available
        if self._approval_callback:
            return await self._approval_callback(action, importance)

        # Default: require approval for HIGH and CRITICAL
        if importance in (ImportanceLevel.HIGH, ImportanceLevel.CRITICAL):
            return ApprovalResult(
                status=ApprovalStatus.PENDING,
                action=action,
            )

        # Auto-approve others
        return ApprovalResult(
            status=ApprovalStatus.AUTO_APPROVED,
            action=action,
        )

    def extract_actions_from_response(self, ai_response: str) -> list[Action]:
        """Extract proposed actions from an AI response.

        Args:
            ai_response: The AI's response text.

        Returns:
            List of detected actions.
        """
        actions = []

        # Detect file creation
        file_create_patterns = [
            r"create\s+(?:file|files?)?\s*[:\s]+([^\n]+)",
            r"생성[:\s]+([^\n]+)",
            r"```[\w]*\n.*?```",  # Code blocks might indicate file content
        ]

        files_to_create = []
        for pattern in file_create_patterns[:2]:
            matches = re.findall(pattern, ai_response, re.IGNORECASE)
            files_to_create.extend(matches)

        if files_to_create:
            actions.append(
                Action(
                    action_type=ActionType.FILE_CREATE,
                    description="Create files",
                    files_to_create=files_to_create[:10],  # Limit
                    modifies_files=True,
                    reversible=True,
                )
            )

        # Detect command execution
        command_patterns = [
            r"run[:\s]+`([^`]+)`",
            r"execute[:\s]+`([^`]+)`",
            r"실행[:\s]+`([^`]+)`",
            r"```(?:bash|sh|shell)\n([^`]+)```",
        ]

        commands = []
        for pattern in command_patterns:
            matches = re.findall(pattern, ai_response, re.IGNORECASE)
            commands.extend(matches)

        if commands:
            action = Action(
                action_type=ActionType.COMMAND_EXECUTE,
                description="Execute commands",
                commands_to_execute=commands[:10],
                executes_commands=True,
                reversible=False,  # Commands are not reversible
            )

            # Check for destructive commands
            for cmd in commands:
                if self._is_dangerous_command(cmd):
                    action.has_destructive_operation = True
                    break

            actions.append(action)

        # Detect package installation
        install_patterns = [
            r"npm\s+install\s+([^\n]+)",
            r"pip\s+install\s+([^\n]+)",
            r"yarn\s+add\s+([^\n]+)",
        ]

        for pattern in install_patterns:
            matches = re.findall(pattern, ai_response, re.IGNORECASE)
            if matches:
                actions.append(
                    Action(
                        action_type=ActionType.INSTALL_PACKAGE,
                        description=f"Install packages: {', '.join(matches[:5])}",
                        executes_commands=True,
                        reversible=True,
                        commands_to_execute=[f"Install: {m}" for m in matches[:5]],
                    )
                )
                break

        return actions

    def create_action_from_context(
        self,
        description: str,
        ai_votes: list[AIVote],
        **kwargs: Any,
    ) -> Action:
        """Create an action with AI votes.

        Args:
            description: Action description.
            ai_votes: Votes from participating AIs.
            **kwargs: Additional action parameters.

        Returns:
            Configured Action.
        """
        action_type = kwargs.pop("action_type", ActionType.SUGGESTION)

        action = Action(
            action_type=action_type,
            description=description,
            ai_votes=ai_votes,
            **kwargs,
        )

        # Set flags based on type
        if action_type in (ActionType.FILE_CREATE, ActionType.FILE_MODIFY, ActionType.FILE_DELETE):
            action.modifies_files = True

        if action_type == ActionType.FILE_DELETE:
            action.has_destructive_operation = True
            action.reversible = False

        if action_type == ActionType.COMMAND_EXECUTE:
            action.executes_commands = True
            action.reversible = False

        return action

    def format_action_summary(self, action: Action) -> str:
        """Format action summary for display.

        Args:
            action: The action to summarize.

        Returns:
            Formatted summary string.
        """
        lines = []
        lines.append(f"Action: {action.action_type.value}")
        lines.append(f"Description: {action.description}")

        if action.files_to_create:
            lines.append(f"Files to create: {len(action.files_to_create)}")
            for f in action.files_to_create[:5]:
                lines.append(f"  - {f}")

        if action.files_to_modify:
            lines.append(f"Files to modify: {len(action.files_to_modify)}")
            for f in action.files_to_modify[:5]:
                lines.append(f"  - {f}")

        if action.files_to_delete:
            lines.append(f"Files to delete: {len(action.files_to_delete)}")
            for f in action.files_to_delete[:5]:
                lines.append(f"  - {f}")

        if action.commands_to_execute:
            lines.append(f"Commands: {len(action.commands_to_execute)}")
            for c in action.commands_to_execute[:5]:
                lines.append(f"  $ {c}")

        lines.append(f"AI Approval: {action.approval_ratio:.0%}")
        lines.append(f"Confidence: {action.total_confidence:.0%}")

        return "\n".join(lines)
