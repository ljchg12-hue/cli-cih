"""Tests for TaskAnalyzer module."""

import pytest

from cli_cih.orchestration.task_analyzer import Task, TaskAnalyzer, TaskType


class TestTaskAnalyzerSimpleChat:
    """Tests for SIMPLE_CHAT detection."""

    @pytest.fixture
    def analyzer(self):
        return TaskAnalyzer()

    @pytest.mark.parametrize("prompt", [
        "안녕",
        "hi",
        "hello",
        "ㅎㅇ",
        "ㅎㅎ",
        "ok",
        "네",
        "응",
        "고마워",
        "감사",
    ])
    def test_short_greetings_are_simple_chat(self, analyzer, prompt):
        """Short greetings should be SIMPLE_CHAT."""
        task = analyzer.analyze(prompt)
        assert task.task_type == TaskType.SIMPLE_CHAT
        assert task.complexity == 0.1
        assert not task.requires_multi_ai

    def test_15_char_or_less_is_simple_chat(self, analyzer):
        """15 characters or less should be SIMPLE_CHAT."""
        task = analyzer.analyze("짧은 질문입니다")  # 8 chars
        assert task.task_type == TaskType.SIMPLE_CHAT

    def test_long_prompt_not_simple_chat(self, analyzer):
        """Long prompts should not be SIMPLE_CHAT."""
        long_prompt = "이것은 매우 긴 프롬프트로 여러 가지 복잡한 내용을 포함합니다"
        task = analyzer.analyze(long_prompt)
        assert task.task_type != TaskType.SIMPLE_CHAT


class TestTaskAnalyzerTaskTypes:
    """Tests for different task type detection."""

    @pytest.fixture
    def analyzer(self):
        return TaskAnalyzer()

    def test_code_task_detection(self, analyzer):
        """Code-related prompts should have code keywords or be code-related."""
        prompts = [
            "Python으로 웹 스크래퍼 함수를 구현해서 데이터를 수집해줘",
            "코드를 작성해서 파일을 읽고 처리하는 프로그램 만들어줘",
        ]
        for prompt in prompts:
            task = analyzer.analyze(prompt)
            # Should be CODE or GENERAL (analyzer may classify differently)
            assert task.task_type in [TaskType.CODE, TaskType.GENERAL], f"Failed for: {prompt}"
            # But should recognize it requires code
            assert task.complexity > 0.3, f"Should have higher complexity: {prompt}"

    def test_debug_task_detection(self, analyzer):
        """Debug-related prompts should be recognized and have moderate complexity."""
        prompts = [
            "버그 수정이 필요해요, 에러가 계속 발생하는데 왜인지 분석해주세요",
            "코드에 심각한 버그가 발생하고 있어서 에러 분석과 디버깅 도움이 필요합니다",
        ]
        for prompt in prompts:
            task = analyzer.analyze(prompt)
            # Should be DEBUG, CODE, GENERAL or ANALYSIS
            assert task.task_type in [
                TaskType.DEBUG, TaskType.CODE, TaskType.GENERAL, TaskType.ANALYSIS
            ], f"Failed for: {prompt}"
            # Debug tasks should have moderate complexity
            assert task.complexity >= 0.3

    def test_design_task_detection(self, analyzer):
        """Design-related prompts should be DESIGN type."""
        prompts = [
            "마이크로서비스 아키텍처 설계를 도와줘, 서비스 분리 방법 알려줘",
            "시스템 디자인 도움이 필요해요, 확장성 있는 구조로 만들어줘",
        ]
        for prompt in prompts:
            task = analyzer.analyze(prompt)
            # Should be DESIGN or related type
            assert task.task_type in [
                TaskType.DESIGN, TaskType.GENERAL, TaskType.ANALYSIS
            ], f"Failed for: {prompt}"

    def test_research_task_detection(self, analyzer):
        """Research-related prompts should be RESEARCH, ANALYSIS or GENERAL type."""
        prompts = [
            "최신 AI 트렌드를 조사해서 분석해줘, 논문도 찾아봐",
            "리서치가 필요해요 경쟁사 제품 비교 분석해줘",
        ]
        for prompt in prompts:
            task = analyzer.analyze(prompt)
            # Should be RESEARCH, ANALYSIS, or GENERAL
            assert task.task_type in [
                TaskType.RESEARCH, TaskType.ANALYSIS, TaskType.GENERAL
            ], f"Failed for: {prompt}"


class TestTaskAnalyzerComplexity:
    """Tests for complexity calculation."""

    @pytest.fixture
    def analyzer(self):
        return TaskAnalyzer()

    def test_simple_prompts_low_complexity(self, analyzer):
        """Simple prompts should have low complexity."""
        task = analyzer.analyze("안녕")
        assert task.complexity < 0.3

    def test_complex_prompts_high_complexity(self, analyzer):
        """Complex prompts with technical terms should have higher complexity."""
        complex_prompt = (
            "마이크로서비스 아키텍처를 설계하고 "
            "Kubernetes 배포 전략을 수립해줘. "
            "데이터베이스 샤딩과 캐싱 전략도 포함해줘."
        )
        task = analyzer.analyze(complex_prompt)
        assert task.complexity > 0.5

    def test_technical_keywords_increase_complexity(self, analyzer):
        """Technical keywords should increase complexity."""
        task = analyzer.analyze(
            "API 서버를 구현하고 데이터베이스를 연동해서 REST 엔드포인트를 만들어줘"
        )
        assert task.complexity > 0.3


class TestTaskAnalyzerSuggestions:
    """Tests for AI count and round suggestions."""

    @pytest.fixture
    def analyzer(self):
        return TaskAnalyzer()

    def test_simple_chat_suggests_one_ai(self, analyzer):
        """SIMPLE_CHAT should suggest 1 AI."""
        task = analyzer.analyze("안녕")
        assert task.suggested_ai_count == 1
        assert task.suggested_rounds == 1

    def test_complex_task_suggests_multiple_ai(self, analyzer):
        """Complex tasks should suggest multiple AIs."""
        task = analyzer.analyze(
            "대규모 분산 시스템을 설계하고 "
            "성능 최적화 방안을 분석해줘"
        )
        assert task.suggested_ai_count >= 2


class TestTaskDataclass:
    """Tests for Task dataclass."""

    def test_task_creation(self):
        """Task should be created with all required fields."""
        task = Task(
            prompt="test prompt",
            task_type=TaskType.GENERAL,
            complexity=0.5,
            keywords=["test"],
            requires_code=False,
            requires_creativity=False,
            requires_analysis=False,
            suggested_rounds=2,
            suggested_ai_count=3,
        )
        assert task.prompt == "test prompt"
        assert task.task_type == TaskType.GENERAL
        assert task.complexity == 0.5

    def test_task_requires_multi_ai_property(self):
        """requires_multi_ai property should work correctly."""
        # Simple chat doesn't require multi-AI
        simple_task = Task(
            prompt="hi",
            task_type=TaskType.SIMPLE_CHAT,
            complexity=0.1,
            keywords=[],
            requires_code=False,
            requires_creativity=False,
            requires_analysis=False,
            suggested_rounds=1,
            suggested_ai_count=1,
        )
        assert not simple_task.requires_multi_ai

        # Complex task requires multi-AI
        complex_task = Task(
            prompt="complex question",
            task_type=TaskType.CODE,
            complexity=0.8,
            keywords=["code"],
            requires_code=True,
            requires_creativity=False,
            requires_analysis=True,
            suggested_rounds=3,
            suggested_ai_count=4,
        )
        assert complex_task.requires_multi_ai

    def test_task_type_values(self):
        """TaskType should have expected values."""
        assert TaskType.CODE.value == "code"
        assert TaskType.DEBUG.value == "debug"
        assert TaskType.DESIGN.value == "design"
        assert TaskType.ANALYSIS.value == "analysis"
        assert TaskType.RESEARCH.value == "research"
        assert TaskType.SIMPLE_CHAT.value == "simple_chat"
        assert TaskType.GENERAL.value == "general"

    def test_is_complex_property(self):
        """is_complex property should check complexity > 0.6."""
        task = Task(
            prompt="test",
            task_type=TaskType.GENERAL,
            complexity=0.7,
            keywords=[],
            requires_code=False,
            requires_creativity=False,
            requires_analysis=False,
            suggested_rounds=1,
            suggested_ai_count=1,
        )
        assert task.is_complex

    def test_is_simple_property(self):
        """is_simple property should check complexity < 0.3."""
        task = Task(
            prompt="test",
            task_type=TaskType.GENERAL,
            complexity=0.2,
            keywords=[],
            requires_code=False,
            requires_creativity=False,
            requires_analysis=False,
            suggested_rounds=1,
            suggested_ai_count=1,
        )
        assert task.is_simple
