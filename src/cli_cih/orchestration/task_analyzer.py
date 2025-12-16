"""Task analysis for determining discussion parameters."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TaskType(str, Enum):
    """Types of tasks that can be analyzed."""

    CODE = "code"
    DESIGN = "design"
    ANALYSIS = "analysis"
    CREATIVE = "creative"
    RESEARCH = "research"
    DEBUG = "debug"
    EXPLAIN = "explain"
    GENERAL = "general"
    SIMPLE_CHAT = "simple_chat"  # Simple greetings, short responses


@dataclass
class Task:
    """Analyzed task information."""

    prompt: str
    task_type: TaskType
    complexity: float  # 0.0 to 1.0
    keywords: list[str]
    requires_code: bool
    requires_creativity: bool
    requires_analysis: bool
    suggested_rounds: int
    suggested_ai_count: int

    @property
    def is_complex(self) -> bool:
        """Check if task is complex."""
        return self.complexity > 0.6

    @property
    def is_simple(self) -> bool:
        """Check if task is simple."""
        return self.complexity < 0.3

    @property
    def requires_multi_ai(self) -> bool:
        """Check if task requires multi-AI discussion."""
        # Simple chat doesn't need multi-AI
        if self.task_type == TaskType.SIMPLE_CHAT:
            return False
        # Low complexity tasks don't need multi-AI
        if self.complexity < 0.3:
            return False
        # Single round tasks don't need multi-AI
        if self.suggested_rounds <= 1:
            return False
        return True


class TaskAnalyzer:
    """Analyzes user prompts to determine task characteristics."""

    # Simple chat patterns (greetings, short responses) - EXPANDED
    SIMPLE_PATTERNS = [
        # 인사
        '안녕', '하이', 'hi', 'hello', '헬로', '방가', '반가',
        '안녕하세요', 'good morning', 'good night', '잘자',
        # 감사
        '고마워', '감사', 'thx', 'thanks', 'thank you', 'thank',
        # 긍정/부정
        '응', '네', '예', '아니', '노', 'ok', 'okay', 'yes', 'no', 'sure',
        'ㅇㅇ', 'ㄴㄴ', '그래', '알겠어',
        # 이모티콘/감탄사
        'ㅎㅎ', 'ㅋㅋ', 'ㅠㅠ', 'ㅜㅜ', 'ㅎ', 'ㅋ', 'ㅠ', 'ㅜ',
        '오', '와', '헐', '대박',
        # 작별
        'bye', '잘가', '바이', '굿나잇', '굿모닝',
        # 기타 짧은 대화
        '뭐해', '뭐야', '왜', '어때', '좋아', '싫어',
    ]

    # Maximum length for simple chat (15 characters)
    SIMPLE_MAX_LENGTH = 15

    # Keyword patterns for task type detection
    CODE_PATTERNS = [
        r"\b(코드|code|implement|구현|function|함수|class|클래스)\b",
        r"\b(프로그램|program|script|스크립트|algorithm|알고리즘)\b",
        r"\b(python|javascript|typescript|java|rust|go)\b",
    ]

    DESIGN_PATTERNS = [
        r"\b(설계|design|architecture|아키텍처|structure|구조)\b",
        r"\b(api|인터페이스|interface|schema|스키마)\b",
        r"\b(시스템|system|database|데이터베이스)\b",
    ]

    ANALYSIS_PATTERNS = [
        r"\b(분석|analyze|analysis|평가|evaluate|review|리뷰)\b",
        r"\b(비교|compare|comparison|장단점|pros|cons)\b",
        r"\b(최적화|optimize|performance|성능)\b",
    ]

    CREATIVE_PATTERNS = [
        r"\b(아이디어|idea|창의|creative|brainstorm|브레인스토밍)\b",
        r"\b(새로운|new|혁신|innovative|unique|독특)\b",
    ]

    RESEARCH_PATTERNS = [
        r"\b(조사|research|찾아|find|search|검색)\b",
        r"\b(트렌드|trend|최신|latest|현재|current)\b",
    ]

    DEBUG_PATTERNS = [
        r"\b(버그|bug|에러|error|오류|fix|수정|debug|디버그)\b",
        r"\b(안되|doesn't work|not working|문제|problem|issue)\b",
    ]

    EXPLAIN_PATTERNS = [
        r"\b(설명|explain|explanation|뭐야|what is|어떻게|how)\b",
        r"\b(이해|understand|meaning|의미)\b",
    ]

    # Complexity indicators
    COMPLEXITY_BOOSTERS = [
        r"\b(복잡|complex|advanced|고급|sophisticated)\b",
        r"\b(전체|entire|complete|전부|all|모든)\b",
        r"\b(통합|integrate|integration|연동)\b",
        r"\b(대규모|large-scale|enterprise|엔터프라이즈)\b",
    ]

    COMPLEXITY_REDUCERS = [
        r"\b(간단|simple|basic|기본|쉬운|easy)\b",
        r"\b(하나|one|single|단일)\b",
        r"\b(예시|example|샘플|sample)\b",
    ]

    def analyze(self, prompt: str) -> Task:
        """Analyze a user prompt.

        Args:
            prompt: The user's input prompt.

        Returns:
            Analyzed Task object.
        """
        prompt_lower = prompt.lower().strip()

        # Fast path: Check for simple chat patterns first
        if self._is_simple_chat(prompt_lower):
            return Task(
                prompt=prompt,
                task_type=TaskType.SIMPLE_CHAT,
                complexity=0.1,
                keywords=[],
                requires_code=False,
                requires_creativity=False,
                requires_analysis=False,
                suggested_rounds=1,
                suggested_ai_count=1,
            )

        # Detect task type
        task_type = self._detect_task_type(prompt_lower)

        # Extract keywords
        keywords = self._extract_keywords(prompt_lower)

        # Calculate complexity
        complexity = self._calculate_complexity(prompt_lower, keywords)

        # Determine requirements
        requires_code = self._check_patterns(prompt_lower, self.CODE_PATTERNS)
        requires_creativity = self._check_patterns(prompt_lower, self.CREATIVE_PATTERNS)
        requires_analysis = self._check_patterns(prompt_lower, self.ANALYSIS_PATTERNS)

        # Calculate suggested parameters
        suggested_rounds = self._suggest_rounds(complexity, task_type)
        suggested_ai_count = self._suggest_ai_count(complexity, task_type)

        return Task(
            prompt=prompt,
            task_type=task_type,
            complexity=complexity,
            keywords=keywords,
            requires_code=requires_code,
            requires_creativity=requires_creativity,
            requires_analysis=requires_analysis,
            suggested_rounds=suggested_rounds,
            suggested_ai_count=suggested_ai_count,
        )

    def _detect_task_type(self, prompt: str) -> TaskType:
        """Detect the primary task type."""
        type_scores = {
            TaskType.CODE: self._pattern_score(prompt, self.CODE_PATTERNS),
            TaskType.DESIGN: self._pattern_score(prompt, self.DESIGN_PATTERNS),
            TaskType.ANALYSIS: self._pattern_score(prompt, self.ANALYSIS_PATTERNS),
            TaskType.CREATIVE: self._pattern_score(prompt, self.CREATIVE_PATTERNS),
            TaskType.RESEARCH: self._pattern_score(prompt, self.RESEARCH_PATTERNS),
            TaskType.DEBUG: self._pattern_score(prompt, self.DEBUG_PATTERNS),
            TaskType.EXPLAIN: self._pattern_score(prompt, self.EXPLAIN_PATTERNS),
        }

        # Find highest scoring type
        max_score = max(type_scores.values())
        if max_score == 0:
            return TaskType.GENERAL

        for task_type, score in type_scores.items():
            if score == max_score:
                return task_type

        return TaskType.GENERAL

    def _pattern_score(self, text: str, patterns: list[str]) -> int:
        """Count how many patterns match."""
        score = 0
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score += 1
        return score

    def _check_patterns(self, text: str, patterns: list[str]) -> bool:
        """Check if any pattern matches."""
        return self._pattern_score(text, patterns) > 0

    def _extract_keywords(self, prompt: str) -> list[str]:
        """Extract relevant keywords from prompt."""
        # Remove common words and extract meaningful terms
        common_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "can", "to", "of",
            "in", "for", "on", "with", "at", "by", "from", "as", "or",
            "and", "but", "if", "then", "else", "when", "where", "what",
            "which", "who", "how", "why", "all", "each", "every", "both",
            "few", "more", "most", "other", "some", "such", "no", "not",
            "only", "same", "so", "than", "too", "very", "just", "also",
            "now", "here", "there", "this", "that", "these", "those",
            "해", "줘", "해줘", "주세요", "하세요", "좀", "것", "거", "이", "그",
        }

        # Tokenize
        words = re.findall(r'\b\w+\b', prompt.lower())

        # Filter
        keywords = [w for w in words if w not in common_words and len(w) > 2]

        # Unique, keep order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        return unique_keywords[:10]  # Limit to 10 keywords

    def _calculate_complexity(self, prompt: str, keywords: list[str]) -> float:
        """Calculate task complexity score (0.0 to 1.0)."""
        score = 0.5  # Base score

        # Length factor
        word_count = len(prompt.split())
        if word_count > 50:
            score += 0.15
        elif word_count > 20:
            score += 0.08
        elif word_count < 10:
            score -= 0.1

        # Keyword count factor
        if len(keywords) > 7:
            score += 0.1
        elif len(keywords) > 4:
            score += 0.05

        # Complexity boosters
        if self._check_patterns(prompt, self.COMPLEXITY_BOOSTERS):
            score += 0.2

        # Complexity reducers
        if self._check_patterns(prompt, self.COMPLEXITY_REDUCERS):
            score -= 0.2

        # Multiple requirements increase complexity
        type_count = sum([
            self._check_patterns(prompt, self.CODE_PATTERNS),
            self._check_patterns(prompt, self.DESIGN_PATTERNS),
            self._check_patterns(prompt, self.ANALYSIS_PATTERNS),
        ])
        if type_count > 1:
            score += 0.1 * (type_count - 1)

        # Clamp to 0.0-1.0
        return max(0.0, min(1.0, score))

    def _suggest_rounds(self, complexity: float, task_type: TaskType) -> int:
        """Suggest number of discussion rounds."""
        base_rounds = 3

        # Complexity adjustment
        if complexity > 0.7:
            base_rounds += 2
        elif complexity > 0.4:
            base_rounds += 1

        # Task type adjustment
        if task_type in (TaskType.DESIGN, TaskType.ANALYSIS):
            base_rounds += 1
        elif task_type in (TaskType.EXPLAIN, TaskType.GENERAL):
            base_rounds -= 1

        return max(2, min(7, base_rounds))

    def _suggest_ai_count(self, complexity: float, task_type: TaskType) -> int:
        """Suggest number of AIs to involve."""
        if complexity < 0.3:
            return 2
        elif complexity < 0.6:
            return 3
        else:
            return 4

    def _is_simple_chat(self, prompt: str) -> bool:
        """Check if prompt is a simple chat message.

        Args:
            prompt: Lowercased, stripped prompt.

        Returns:
            True if this is a simple greeting/chat.
        """
        # 1. Empty input
        if not prompt:
            return True

        # 2. Very short input (less than SIMPLE_MAX_LENGTH characters)
        if len(prompt) < self.SIMPLE_MAX_LENGTH:
            return True

        # 3. Check for simple patterns (only if not too long)
        for pattern in self.SIMPLE_PATTERNS:
            if pattern in prompt:
                # Pattern found - check if it's a longer technical question
                if len(prompt) < 30:
                    return True

        # 4. Short prompt with only common words (3 words or less)
        word_count = len(prompt.split())
        if word_count <= 3:
            return True

        # 5. Check for technical keywords - if present, NOT simple chat
        technical_indicators = [
            '코드', 'code', '함수', 'function', '구현', 'implement',
            '버그', 'bug', '에러', 'error', '디버그', 'debug',
            '설계', 'design', '아키텍처', 'architecture',
            '분석', 'analyze', '비교', 'compare',
            '만들어', '작성', '생성', 'create', 'make', 'build',
        ]
        for indicator in technical_indicators:
            if indicator in prompt:
                return False  # Technical content = NOT simple chat

        return False
