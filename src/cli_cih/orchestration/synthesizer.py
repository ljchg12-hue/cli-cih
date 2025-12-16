"""Result synthesis for multi-AI discussions."""

from dataclasses import dataclass, field
from typing import Optional

from cli_cih.orchestration.context import SharedContext


@dataclass
class SynthesisResult:
    """Result of synthesizing a discussion."""

    summary: str
    key_points: list[str]
    agreements: list[str]
    disagreements: list[str]
    recommendations: list[str]
    ai_contributions: dict[str, int]
    total_messages: int
    total_rounds: int
    consensus_reached: bool


class Synthesizer:
    """Synthesizes multi-AI discussion results."""

    def __init__(self, max_summary_length: int = 500):
        """Initialize synthesizer.

        Args:
            max_summary_length: Maximum length of summary.
        """
        self.max_summary_length = max_summary_length

    async def synthesize(
        self,
        context: SharedContext,
        use_ai: bool = False,
    ) -> SynthesisResult:
        """Synthesize discussion results.

        Args:
            context: The shared context with all messages.
            use_ai: Whether to use an AI for synthesis.

        Returns:
            SynthesisResult with combined insights.
        """
        # For now, use heuristic synthesis
        # In production, you could use an AI to create a better summary

        # Extract key points
        key_points = self._extract_key_points(context)

        # Find agreements and disagreements
        agreements, disagreements = self._analyze_positions(context)

        # Extract recommendations
        recommendations = self._extract_recommendations(context)

        # Create summary
        summary = self._create_summary(
            context,
            key_points,
            agreements,
            recommendations,
        )

        # Get contribution stats
        ai_contributions = {
            name: count
            for name, count in context.ai_message_counts.items()
        }

        return SynthesisResult(
            summary=summary,
            key_points=key_points,
            agreements=agreements,
            disagreements=disagreements,
            recommendations=recommendations,
            ai_contributions=ai_contributions,
            total_messages=len(context.messages),
            total_rounds=context.current_round,
            consensus_reached=context.consensus_reached,
        )

    def _extract_key_points(self, context: SharedContext) -> list[str]:
        """Extract key points from the discussion."""
        # Use context's key points plus additional extraction
        points = list(context.key_points)

        # Look for additional patterns in messages
        for msg in context.messages:
            content = msg.content

            # Look for numbered items
            import re
            numbered = re.findall(r'^\d+[\.\)]\s*(.+)$', content, re.MULTILINE)
            for item in numbered:
                item = item.strip()[:100]
                if item and item not in points:
                    points.append(item)

            # Look for "key"/"important" phrases
            important_patterns = [
                r'중요한[^.]*점[은는]?\s*:?\s*(.+)',
                r'key point[s]?[:]?\s*(.+)',
                r'important[ly]?[:]?\s*(.+)',
            ]
            for pattern in important_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    match = match.strip()[:100]
                    if match and match not in points:
                        points.append(match)

        # Limit and deduplicate
        seen = set()
        unique_points = []
        for point in points:
            normalized = point.lower().strip()
            if normalized not in seen:
                seen.add(normalized)
                unique_points.append(point)

        return unique_points[:10]

    def _analyze_positions(
        self,
        context: SharedContext,
    ) -> tuple[list[str], list[str]]:
        """Analyze agreements and disagreements."""
        agreements = []
        disagreements = []

        # Agreement phrases
        agreement_patterns = [
            r'동의합니다[.:]?\s*(.+)',
            r'agree[d]?[.:]?\s*(.+)',
            r'맞습니다[.:]?\s*(.+)',
            r'좋은 의견입니다[.:]?\s*(.+)',
            r'build on (?:that|this)[.:]?\s*(.+)',
        ]

        # Disagreement phrases
        disagreement_patterns = [
            r'동의하지 않[습니다는][.:]?\s*(.+)',
            r'disagree[.:]?\s*(.+)',
            r'다른 의견[.:]?\s*(.+)',
            r'however[,]?\s*(.+)',
            r'but[,]?\s*(.+)',
            r'그러나[,]?\s*(.+)',
        ]

        import re

        for msg in context.messages:
            content = msg.content

            for pattern in agreement_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    match = match.strip()[:100]
                    if match and match not in agreements:
                        agreements.append(f"{msg.ai_name}: {match}")

            for pattern in disagreement_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    match = match.strip()[:100]
                    if match and match not in disagreements:
                        disagreements.append(f"{msg.ai_name}: {match}")

        return agreements[:5], disagreements[:5]

    def _extract_recommendations(self, context: SharedContext) -> list[str]:
        """Extract recommendations from the discussion."""
        recommendations = []

        recommendation_patterns = [
            r'추천[합니다하면][.:]?\s*(.+)',
            r'recommend[s]?[.:]?\s*(.+)',
            r'제안[합니다하면][.:]?\s*(.+)',
            r'suggest[s]?[.:]?\s*(.+)',
            r'should[:]?\s*(.+)',
            r'~해야\s*합니다[.:]?\s*(.+)',
        ]

        import re

        for msg in context.messages:
            content = msg.content

            for pattern in recommendation_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    match = match.strip()[:100]
                    if match and match not in recommendations:
                        recommendations.append(match)

        return recommendations[:5]

    def _create_summary(
        self,
        context: SharedContext,
        key_points: list[str],
        agreements: list[str],
        recommendations: list[str],
    ) -> str:
        """Create a summary of the discussion."""
        parts = []

        # Opening
        ai_count = len(context.ai_message_counts)
        parts.append(
            f"{ai_count}개의 AI가 {context.current_round}라운드에 걸쳐 토론했습니다."
        )

        # Consensus status
        if context.consensus_reached:
            parts.append("토론 결과 합의에 도달했습니다.")
        else:
            parts.append("다양한 관점이 제시되었습니다.")

        # Key points
        if key_points:
            parts.append("\n주요 포인트:")
            for i, point in enumerate(key_points[:3], 1):
                parts.append(f"  {i}. {point}")

        # Top recommendation
        if recommendations:
            parts.append(f"\n권장 사항: {recommendations[0]}")

        summary = " ".join(parts)

        # Truncate if too long
        if len(summary) > self.max_summary_length:
            summary = summary[:self.max_summary_length - 3] + "..."

        return summary

    def format_result(self, result: SynthesisResult) -> str:
        """Format synthesis result for display.

        Args:
            result: The synthesis result.

        Returns:
            Formatted string.
        """
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append("📊 토론 결과 요약")
        lines.append("=" * 60)

        # Summary
        lines.append(f"\n{result.summary}\n")

        # Stats
        lines.append(f"📈 통계:")
        lines.append(f"  - 총 라운드: {result.total_rounds}")
        lines.append(f"  - 총 메시지: {result.total_messages}")
        lines.append(f"  - 합의 도달: {'✅ 예' if result.consensus_reached else '❌ 아니오'}")

        # AI Contributions
        if result.ai_contributions:
            lines.append(f"\n🤖 AI 기여:")
            for ai_name, count in result.ai_contributions.items():
                lines.append(f"  - {ai_name}: {count}개 메시지")

        # Key Points
        if result.key_points:
            lines.append(f"\n💡 핵심 포인트:")
            for i, point in enumerate(result.key_points[:5], 1):
                lines.append(f"  {i}. {point}")

        # Recommendations
        if result.recommendations:
            lines.append(f"\n📌 권장 사항:")
            for rec in result.recommendations[:3]:
                lines.append(f"  • {rec}")

        lines.append("\n" + "=" * 60)

        return "\n".join(lines)
