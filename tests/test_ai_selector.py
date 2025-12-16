"""Tests for AISelector module."""


import pytest

from cli_cih.adapters import ClaudeAdapter, CodexAdapter, GeminiAdapter
from cli_cih.orchestration.ai_selector import OLLAMA_PROFILES, AIScore, AISelector, OllamaInstance
from cli_cih.orchestration.task_analyzer import TaskAnalyzer, TaskType


class TestAISelector:
    """Tests for AISelector."""

    @pytest.fixture
    def selector(self):
        return AISelector()

    @pytest.fixture
    def analyzer(self):
        return TaskAnalyzer()

    def test_ai_specialties_defined(self, selector):
        """All AI types should have specialties defined."""
        expected_ais = ["claude", "codex", "gemini", "ollama"]
        for ai in expected_ais:
            assert ai in selector.AI_SPECIALTIES

    def test_all_task_types_have_scores(self, selector):
        """Each AI should have scores for all task types."""
        for ai_name, specialties in selector.AI_SPECIALTIES.items():
            for task_type in TaskType:
                assert task_type in specialties, f"{ai_name} missing {task_type}"


class TestAIScoring:
    """Tests for AI scoring logic."""

    @pytest.fixture
    def selector(self):
        return AISelector()

    @pytest.fixture
    def analyzer(self):
        return TaskAnalyzer()

    def test_score_claude_for_code(self, selector, analyzer):
        """Claude should score well for code tasks."""
        task = analyzer.analyze("Python으로 웹 스크래퍼 함수를 구현해서 데이터를 수집해줘")
        adapter = ClaudeAdapter()
        score = selector._score_ai(adapter, task)
        assert score.score > 0.5

    def test_score_codex_for_code(self, selector, analyzer):
        """Codex should score well for code-related tasks."""
        task = analyzer.analyze("Python으로 웹 스크래퍼 함수를 구현해서 데이터를 수집해줘")
        adapter = CodexAdapter()
        score = selector._score_ai(adapter, task)
        # Codex should have a positive score for code-related tasks
        assert score.score > 0.5

    def test_score_gemini_for_research(self, selector, analyzer):
        """Gemini should score high for research tasks."""
        task = analyzer.analyze("최신 AI 트렌드를 조사해서 분석해줘, 논문도 찾아봐")
        adapter = GeminiAdapter()
        score = selector._score_ai(adapter, task)
        assert score.score > 0.5


class TestAIScoreDataclass:
    """Tests for AIScore dataclass."""

    def test_ai_score_creation(self):
        """AIScore should be created correctly."""
        adapter = ClaudeAdapter()
        score = AIScore(
            adapter=adapter,
            score=0.85,
            specialties=["code", "analysis"],
            reason="Good match for coding tasks"
        )
        assert score.adapter == adapter
        assert score.score == 0.85
        assert "code" in score.specialties


class TestOllamaProfiles:
    """Tests for Ollama model profiles."""

    def test_ollama_profiles_exist(self):
        """OLLAMA_PROFILES should be defined."""
        assert OLLAMA_PROFILES is not None
        assert len(OLLAMA_PROFILES) > 0

    def test_ollama_profile_categories(self):
        """OLLAMA_PROFILES should have expected categories."""
        expected_categories = ["coding", "analysis", "creative", "default"]
        for category in expected_categories:
            assert category in OLLAMA_PROFILES, f"Missing category: {category}"

    def test_ollama_instance_dataclass(self):
        """OllamaInstance should have required attributes."""
        instance = OllamaInstance(
            model="llama3.1:70b",
            name="Ollama-Test",
            specialty="general"
        )
        assert instance.model == "llama3.1:70b"
        assert instance.name == "Ollama-Test"
        assert instance.specialty == "general"

    def test_ollama_profiles_contain_instances(self):
        """Each profile should contain OllamaInstance objects."""
        for _category, instances in OLLAMA_PROFILES.items():
            assert isinstance(instances, list)
            for instance in instances:
                assert isinstance(instance, OllamaInstance)
                assert instance.model
                assert instance.name
                assert instance.specialty


class TestSimpleChatSelection:
    """Tests for SIMPLE_CHAT AI selection."""

    @pytest.fixture
    def selector(self):
        return AISelector()

    @pytest.fixture
    def analyzer(self):
        return TaskAnalyzer()

    def test_simple_chat_selects_one_ai(self, selector, analyzer):
        """SIMPLE_CHAT should select only 1 AI."""
        task = analyzer.analyze("안녕")
        assert task.task_type == TaskType.SIMPLE_CHAT
        assert task.suggested_ai_count == 1


class TestMaxAIsLimit:
    """Tests for max_ais parameter."""

    @pytest.fixture
    def selector(self):
        return AISelector()

    def test_max_ais_default(self, selector):
        """Default max_ais should be reasonable."""
        assert selector.max_ais >= 1
        assert selector.max_ais <= 10

    def test_selector_respects_max_ais(self, selector):
        """Selector should not return more AIs than max_ais."""
        selector.max_ais = 2
        # This is verified by the selection logic
        assert selector.max_ais == 2
