"""Conflict detection and resolution for multi-AI discussions."""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from cli_cih.orchestration.context import SharedContext
from cli_cih.orchestration.task_analyzer import TaskType


class ConflictSeverity(str, Enum):
    """Severity levels for conflicts."""

    LOW = "low"          # Minor disagreement, easily resolved
    MEDIUM = "medium"    # Significant disagreement
    HIGH = "high"        # Strong opposing views
    CRITICAL = "critical"  # Fundamental disagreement requiring user input


class ResolutionType(str, Enum):
    """Types of conflict resolution."""

    AUTO_RESOLVED = "auto_resolved"     # Resolved by weighted voting
    USER_DECISION = "user_decision"     # Requires user choice
    COMPROMISE = "compromise"           # Merged solution
    DEFERRED = "deferred"              # More discussion needed


@dataclass
class Opinion:
    """Represents an AI's opinion on a topic."""

    ai_name: str
    position: str
    confidence: float  # 0.0 to 1.0
    reasoning: str
    supporting_points: list[str] = field(default_factory=list)


@dataclass
class Conflict:
    """Represents a detected conflict between AI opinions."""

    topic: str
    opinions: dict[str, Opinion]
    severity: ConflictSeverity
    round_detected: int
    context_summary: str = ""


@dataclass
class VotedOption:
    """An option with voting weight."""

    position: str
    supporters: list[str]
    weight: float
    reasoning: str


@dataclass
class Resolution:
    """Resolution of a conflict."""

    type: ResolutionType
    winner: Optional[str] = None
    options: list[VotedOption] = field(default_factory=list)
    explanation: str = ""
    confidence: float = 0.0


# AI strength scores by task type
AI_STRENGTHS: dict[str, dict[TaskType, float]] = {
    "claude": {
        TaskType.CODE: 0.9,
        TaskType.DESIGN: 0.95,
        TaskType.ANALYSIS: 0.9,
        TaskType.CREATIVE: 0.85,
        TaskType.RESEARCH: 0.8,
        TaskType.DEBUG: 0.85,
        TaskType.EXPLAIN: 0.95,
        TaskType.GENERAL: 0.9,
        TaskType.SIMPLE_CHAT: 0.9,
    },
    "codex": {
        TaskType.CODE: 0.95,
        TaskType.DESIGN: 0.85,
        TaskType.ANALYSIS: 0.8,
        TaskType.CREATIVE: 0.7,
        TaskType.RESEARCH: 0.7,
        TaskType.DEBUG: 0.9,
        TaskType.EXPLAIN: 0.75,
        TaskType.GENERAL: 0.8,
        TaskType.SIMPLE_CHAT: 0.7,
    },
    "gemini": {
        TaskType.CODE: 0.85,
        TaskType.DESIGN: 0.85,
        TaskType.ANALYSIS: 0.9,
        TaskType.CREATIVE: 0.9,
        TaskType.RESEARCH: 0.95,
        TaskType.DEBUG: 0.8,
        TaskType.EXPLAIN: 0.9,
        TaskType.GENERAL: 0.85,
        TaskType.SIMPLE_CHAT: 0.85,
    },
    "ollama": {
        TaskType.CODE: 0.8,
        TaskType.DESIGN: 0.75,
        TaskType.ANALYSIS: 0.75,
        TaskType.CREATIVE: 0.8,
        TaskType.RESEARCH: 0.7,
        TaskType.DEBUG: 0.75,
        TaskType.EXPLAIN: 0.8,
        TaskType.GENERAL: 0.8,
        TaskType.SIMPLE_CHAT: 0.85,
    },
}


class ConflictResolver:
    """Detects and resolves conflicts between AI opinions."""

    # Disagreement indicators
    DISAGREEMENT_PATTERNS = [
        r'\b(disagree|동의하지 않|다른 의견|however|but|그러나|반면|alternatively)\b',
        r'\b(instead|대신|rather than|오히려|on the contrary)\b',
        r'\b(not recommend|추천하지 않|against|반대)\b',
        r'\b(wrong|잘못|incorrect|틀린|mistake)\b',
    ]

    # Agreement indicators
    AGREEMENT_PATTERNS = [
        r'\b(agree|동의|correct|맞|build on|추가|support|지지)\b',
        r'\b(good point|좋은 의견|exactly|정확|same|같은)\b',
    ]

    def __init__(self, task_type: TaskType = TaskType.GENERAL):
        """Initialize conflict resolver.

        Args:
            task_type: Current task type for weight calculation.
        """
        self.task_type = task_type

    def detect_conflict(self, context: SharedContext) -> Optional[Conflict]:
        """Detect conflicts between AI opinions.

        Args:
            context: The shared discussion context.

        Returns:
            Conflict if detected, None otherwise.
        """
        # Skip conflict detection for simple chats
        if self.task_type == TaskType.SIMPLE_CHAT:
            return None

        if len(context.messages) < 2:
            return None

        # Extract opinions from recent messages
        opinions = self._extract_opinions(context)

        if len(opinions) < 2:
            return None

        # Check for disagreement
        disagreement_score = self._calculate_disagreement(context, opinions)

        if disagreement_score < 0.3:
            return None  # Not enough disagreement

        # Determine severity
        severity = self._calculate_severity(disagreement_score, opinions)

        # Identify the topic of conflict
        topic = self._identify_topic(context)

        return Conflict(
            topic=topic,
            opinions=opinions,
            severity=severity,
            round_detected=context.current_round,
            context_summary=self._create_context_summary(context),
        )

    def _extract_opinions(self, context: SharedContext) -> dict[str, Opinion]:
        """Extract opinions from AI messages."""
        opinions = {}

        # Group messages by AI
        ai_messages: dict[str, list[str]] = {}
        for msg in context.messages:
            if msg.ai_name not in ai_messages:
                ai_messages[msg.ai_name] = []
            ai_messages[msg.ai_name].append(msg.content)

        for ai_name, messages in ai_messages.items():
            if not messages:
                continue

            # Use the latest message for opinion
            latest = messages[-1]

            # Extract position (first sentence or key phrase)
            position = self._extract_position(latest)

            # Calculate confidence based on language
            confidence = self._estimate_confidence(latest)

            # Extract supporting points
            points = self._extract_supporting_points(latest)

            opinions[ai_name] = Opinion(
                ai_name=ai_name,
                position=position,
                confidence=confidence,
                reasoning=latest[:200] + "..." if len(latest) > 200 else latest,
                supporting_points=points,
            )

        return opinions

    def _extract_position(self, text: str) -> str:
        """Extract the main position/recommendation from text."""
        # Look for recommendation patterns
        patterns = [
            r'(?:recommend|suggest|추천|제안)[s]?[:\s]+([^.!?\n]+)',
            r'(?:should use|should be|해야|사용해야)[:\s]+([^.!?\n]+)',
            r'(?:best|최선|best option|best choice)[:\s]+([^.!?\n]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:100]

        # Fall back to first sentence
        sentences = re.split(r'[.!?]\s+', text)
        if sentences:
            return sentences[0].strip()[:100]

        return text[:100]

    def _estimate_confidence(self, text: str) -> float:
        """Estimate confidence level from text."""
        confidence = 0.7  # Base confidence

        # High confidence indicators
        high_confidence = [
            r'\b(definitely|certainly|확실히|분명히|strongly)\b',
            r'\b(best|최선|optimal|최적)\b',
            r'\b(must|반드시|should definitely)\b',
        ]

        # Low confidence indicators
        low_confidence = [
            r'\b(maybe|아마|perhaps|possibly)\b',
            r'\b(could|might|할 수도)\b',
            r'\b(not sure|확실하지 않|uncertain)\b',
        ]

        text_lower = text.lower()

        for pattern in high_confidence:
            if re.search(pattern, text_lower, re.IGNORECASE):
                confidence += 0.1

        for pattern in low_confidence:
            if re.search(pattern, text_lower, re.IGNORECASE):
                confidence -= 0.1

        return max(0.3, min(1.0, confidence))

    def _extract_supporting_points(self, text: str) -> list[str]:
        """Extract supporting points from text."""
        points = []

        # Look for numbered lists
        numbered = re.findall(r'^\d+[.)]\s*(.+)$', text, re.MULTILINE)
        points.extend(numbered[:5])

        # Look for bullet points
        bullets = re.findall(r'^[-*]\s*(.+)$', text, re.MULTILINE)
        points.extend(bullets[:5])

        # Clean and limit
        points = [p.strip()[:100] for p in points if len(p.strip()) > 10]
        return points[:5]

    def _calculate_disagreement(
        self,
        context: SharedContext,
        opinions: dict[str, Opinion],
    ) -> float:
        """Calculate overall disagreement score."""
        if len(opinions) < 2:
            return 0.0

        disagreement_count = 0
        total_comparisons = 0

        # Check each message for disagreement indicators
        for msg in context.messages:
            content_lower = msg.content.lower()

            for pattern in self.DISAGREEMENT_PATTERNS:
                if re.search(pattern, content_lower, re.IGNORECASE):
                    disagreement_count += 1
                    break

            total_comparisons += 1

        if total_comparisons == 0:
            return 0.0

        # Also check position similarity
        positions = list(opinions.values())
        position_diversity = self._calculate_position_diversity(positions)

        disagreement_ratio = disagreement_count / total_comparisons

        # Combine explicit disagreement with position diversity
        return (disagreement_ratio * 0.6) + (position_diversity * 0.4)

    def _calculate_position_diversity(self, opinions: list[Opinion]) -> float:
        """Calculate how diverse the positions are."""
        if len(opinions) < 2:
            return 0.0

        # Simple heuristic: compare first words of positions
        positions = [o.position.lower().split()[:3] for o in opinions]

        # Count unique starting phrases
        unique_starts = len(set(tuple(p) for p in positions))

        # Normalize
        return (unique_starts - 1) / (len(opinions) - 1) if len(opinions) > 1 else 0.0

    def _calculate_severity(
        self,
        disagreement_score: float,
        opinions: dict[str, Opinion],
    ) -> ConflictSeverity:
        """Calculate conflict severity."""
        # Factor in confidence levels
        avg_confidence = sum(o.confidence for o in opinions.values()) / len(opinions)

        # High confidence disagreement is more severe
        severity_score = disagreement_score * (0.5 + avg_confidence * 0.5)

        if severity_score < 0.3:
            return ConflictSeverity.LOW
        elif severity_score < 0.5:
            return ConflictSeverity.MEDIUM
        elif severity_score < 0.7:
            return ConflictSeverity.HIGH
        else:
            return ConflictSeverity.CRITICAL

    def _identify_topic(self, context: SharedContext) -> str:
        """Identify the topic of conflict."""
        # Look for common technical terms
        tech_patterns = [
            r'\b(framework|프레임워크)\b',
            r'\b(language|언어)\b',
            r'\b(database|데이터베이스)\b',
            r'\b(architecture|아키텍처)\b',
            r'\b(approach|접근|방법)\b',
            r'\b(library|라이브러리)\b',
        ]

        all_text = " ".join(m.content for m in context.messages)

        for pattern in tech_patterns:
            if re.search(pattern, all_text, re.IGNORECASE):
                match = re.search(pattern, all_text, re.IGNORECASE)
                return f"Choice of {match.group(0)}"

        # Fall back to original prompt
        words = context.original_prompt.split()[:5]
        return " ".join(words) + "..." if len(words) == 5 else context.original_prompt

    def _create_context_summary(self, context: SharedContext) -> str:
        """Create a summary of the discussion context."""
        summary_parts = []
        summary_parts.append(f"Discussion about: {context.original_prompt[:100]}")
        summary_parts.append(f"Rounds completed: {context.current_round}")
        summary_parts.append(f"Messages: {len(context.messages)}")
        return "\n".join(summary_parts)

    async def resolve(self, conflict: Conflict) -> Resolution:
        """Resolve a conflict using weighted voting.

        Args:
            conflict: The conflict to resolve.

        Returns:
            Resolution with winner or options for user.
        """
        # Calculate weighted votes
        votes: dict[str, VotedOption] = {}

        for ai_name, opinion in conflict.opinions.items():
            position = opinion.position

            # Get AI strength for current task type
            ai_key = ai_name.lower()
            strength = AI_STRENGTHS.get(ai_key, {}).get(self.task_type, 0.5)

            # Weight = strength * confidence
            weight = strength * opinion.confidence

            if position not in votes:
                votes[position] = VotedOption(
                    position=position,
                    supporters=[ai_name],
                    weight=weight,
                    reasoning=opinion.reasoning,
                )
            else:
                votes[position].supporters.append(ai_name)
                votes[position].weight += weight

        # Sort by weight
        sorted_options = sorted(votes.values(), key=lambda x: x.weight, reverse=True)

        if not sorted_options:
            return Resolution(
                type=ResolutionType.DEFERRED,
                explanation="No clear positions identified",
            )

        # Check if clear winner or close race
        if len(sorted_options) >= 2:
            top = sorted_options[0]
            second = sorted_options[1]

            diff = (top.weight - second.weight) / top.weight if top.weight > 0 else 0

            if diff < 0.1:  # Less than 10% difference
                return Resolution(
                    type=ResolutionType.USER_DECISION,
                    options=sorted_options[:2],
                    explanation=f"Close vote: {top.weight:.2f} vs {second.weight:.2f}",
                    confidence=diff,
                )

        # Clear winner
        winner = sorted_options[0]
        return Resolution(
            type=ResolutionType.AUTO_RESOLVED,
            winner=winner.position,
            options=sorted_options,
            explanation=f"Winner by weighted vote: {winner.weight:.2f}",
            confidence=winner.weight / sum(o.weight for o in sorted_options),
        )

    def format_conflict(self, conflict: Conflict) -> str:
        """Format conflict for display.

        Args:
            conflict: The conflict to format.

        Returns:
            Formatted string.
        """
        lines = []
        lines.append(f"Topic: {conflict.topic}")
        lines.append(f"Severity: {conflict.severity.value.upper()}")
        lines.append("")

        for ai_name, opinion in conflict.opinions.items():
            lines.append(f"{ai_name}:")
            lines.append(f"  Position: {opinion.position}")
            lines.append(f"  Confidence: {opinion.confidence:.0%}")
            lines.append("")

        return "\n".join(lines)

    def format_resolution(self, resolution: Resolution) -> str:
        """Format resolution for display.

        Args:
            resolution: The resolution to format.

        Returns:
            Formatted string.
        """
        lines = []
        lines.append(f"Resolution Type: {resolution.type.value}")

        if resolution.winner:
            lines.append(f"Winner: {resolution.winner}")

        if resolution.options:
            lines.append("Options:")
            for i, opt in enumerate(resolution.options, 1):
                lines.append(f"  {i}. {opt.position}")
                lines.append(f"     Supporters: {', '.join(opt.supporters)}")
                lines.append(f"     Weight: {opt.weight:.2f}")

        lines.append(f"Explanation: {resolution.explanation}")
        lines.append(f"Confidence: {resolution.confidence:.0%}")

        return "\n".join(lines)
