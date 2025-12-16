"""AI selection logic for multi-AI discussions."""

from dataclasses import dataclass

from cli_cih.adapters import AIAdapter, get_all_adapters
from cli_cih.orchestration.task_analyzer import Task, TaskType


@dataclass
class AIScore:
    """Score for an AI on a specific task."""

    adapter: AIAdapter
    score: float
    specialties: list[str]
    reason: str


@dataclass
class OllamaInstance:
    """Ollama individual instance for multi-model support."""

    model: str
    name: str
    specialty: str


# Task-specific Ollama model profiles
OLLAMA_PROFILES = {
    "coding": [
        OllamaInstance("qwen2.5-coder:7b", "Ollama-Coder", "code"),
        OllamaInstance("deepseek-r1:70b", "Ollama-Reasoner", "reasoning"),
    ],
    "analysis": [
        OllamaInstance("llama3.1:70b", "Ollama-Analysis", "analysis"),
        OllamaInstance("qwen3:32b", "Ollama-Logic", "logic"),
        OllamaInstance("deepseek-r1:32b", "Ollama-Deep", "deep_thinking"),
    ],
    "creative": [
        OllamaInstance("llama3.3:latest", "Ollama-Creative", "creative"),
        OllamaInstance("mistral:7b", "Ollama-Fast", "speed"),
    ],
    "default": [
        OllamaInstance("llama3.1:70b", "Ollama-Main", "general"),
    ],
}


class AISelector:
    """Selects appropriate AIs for a given task."""

    # AI specialty scores by task type (0.0 to 1.0)
    # Higher score = better fit for that task type
    AI_SPECIALTIES: dict[str, dict[TaskType, float]] = {
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

    # AI specialty descriptions
    AI_SPECIALTY_DESCRIPTIONS: dict[str, list[str]] = {
        "claude": ["reasoning", "analysis", "explanation", "design"],
        "codex": ["code", "implementation", "debugging", "algorithms"],
        "gemini": ["research", "creativity", "multimodal", "current events"],
        "ollama": ["local processing", "privacy", "customization"],
    }

    def __init__(self, min_ais: int = 2, max_ais: int = 6):
        """Initialize AI selector.

        Args:
            min_ais: Minimum number of AIs to select.
            max_ais: Maximum number of AIs to select (4 base + 2 Ollama).
        """
        self.min_ais = min_ais
        self.max_ais = max_ais

    async def select(
        self,
        task: Task,
        available_adapters: list[AIAdapter] | None = None,
    ) -> list[AIAdapter]:
        """Select AIs for a task - 4 base AIs + multiple Ollama models.

        Args:
            task: The analyzed task.
            available_adapters: List of available adapters.

        Returns:
            List of selected AIAdapters.
        """
        # Simple chat: Claude only
        if task.task_type == TaskType.SIMPLE_CHAT or task.complexity < 0.3:
            return await self._select_single_ai(available_adapters)

        # Get available adapters
        if available_adapters is None:
            all_adapters = get_all_adapters()
            available_adapters = []
            for adapter in all_adapters:
                if await adapter.is_available():
                    available_adapters.append(adapter)

        if not available_adapters:
            return []

        # Complex tasks: Select all 4 base AIs + Ollama multi-model
        selected = []
        adapter_map = {a.name.lower(): a for a in available_adapters}

        # 1. Claude (required)
        if "claude" in adapter_map:
            selected.append(adapter_map["claude"])

        # 2. Codex (required)
        if "codex" in adapter_map:
            selected.append(adapter_map["codex"])

        # 3. Gemini (required)
        if "gemini" in adapter_map:
            selected.append(adapter_map["gemini"])

        # 4. Ollama multi-model (2-4 models based on task)
        ollama_instances = await self._select_ollama_models(task, adapter_map.get("ollama"))
        selected.extend(ollama_instances)

        return selected

    async def _select_single_ai(
        self,
        available_adapters: list[AIAdapter] | None = None,
    ) -> list[AIAdapter]:
        """Select single AI (Claude preferred) for simple tasks."""
        if available_adapters is None:
            all_adapters = get_all_adapters()
            available_adapters = []
            for adapter in all_adapters:
                if await adapter.is_available():
                    available_adapters.append(adapter)

        if not available_adapters:
            return []

        # Prefer Claude
        for adapter in available_adapters:
            if adapter.name.lower() == "claude":
                return [adapter]

        # Fallback to first available
        return [available_adapters[0]]

    async def _select_ollama_models(
        self,
        task: Task,
        base_ollama: AIAdapter | None = None,
    ) -> list[AIAdapter]:
        """Select multiple Ollama models based on task type.

        Args:
            task: The analyzed task.
            base_ollama: Base Ollama adapter to check availability.

        Returns:
            List of Ollama adapters with different models.
        """
        if base_ollama is None:
            return []

        # Check if Ollama is available
        if not await base_ollama.is_available():
            return []

        from cli_cih.adapters.ollama import OllamaAdapter

        # Select profile based on task type
        if task.task_type in [TaskType.CODE, TaskType.DEBUG]:
            profile_key = "coding"
        elif task.task_type in [TaskType.ANALYSIS, TaskType.RESEARCH]:
            profile_key = "analysis"
        elif task.task_type == TaskType.CREATIVE:
            profile_key = "creative"
        else:
            profile_key = "default"

        profiles = OLLAMA_PROFILES.get(profile_key, OLLAMA_PROFILES["default"])

        # Determine model count based on complexity
        if task.complexity > 0.7:
            count = min(len(profiles), 3)  # High complexity: up to 3
        elif task.complexity > 0.5:
            count = min(len(profiles), 2)  # Medium: 2
        else:
            count = 1  # Low: 1

        # Create Ollama instances with different models
        instances = []
        for profile in profiles[:count]:
            from cli_cih.adapters.base import AdapterConfig

            config = AdapterConfig(model=profile.model)
            adapter = OllamaAdapter(config=config)
            adapter.display_name = profile.name
            adapter.set_model(profile.model)
            instances.append(adapter)

        return instances

    def _score_ai(self, adapter: AIAdapter, task: Task) -> AIScore:
        """Calculate score for an AI on a task."""
        ai_name = adapter.name.lower()

        # Get base score from specialties
        specialties = self.AI_SPECIALTIES.get(ai_name, {})
        base_score = specialties.get(task.task_type, 0.7)

        # Bonus for matching requirements
        bonus = 0.0

        # Strong bonus for Codex on coding tasks
        if task.requires_code:
            if ai_name == "codex":
                bonus += 0.25  # Significant boost for Codex on code tasks
            elif ai_name == "claude":
                bonus += 0.1

        # Codex priority for DEBUG tasks
        if task.task_type == TaskType.DEBUG and ai_name == "codex":
            bonus += 0.2

        # Codex priority for CODE tasks
        if task.task_type == TaskType.CODE and ai_name == "codex":
            bonus += 0.15

        if task.requires_creativity and ai_name in ("gemini", "claude"):
            bonus += 0.1

        if task.requires_analysis and ai_name in ("claude", "gemini"):
            bonus += 0.1

        # Slight randomization for variety (±0.05)
        import random

        variation = (random.random() - 0.5) * 0.1

        final_score = min(1.0, base_score + bonus + variation)

        # Generate reason
        specialty_list = self.AI_SPECIALTY_DESCRIPTIONS.get(ai_name, ["general"])
        reason = f"Good at: {', '.join(specialty_list[:2])}"

        return AIScore(
            adapter=adapter,
            score=final_score,
            specialties=specialty_list,
            reason=reason,
        )

    def _select_with_diversity(
        self,
        scores: list[AIScore],
        target_count: int,
    ) -> list[AIScore]:
        """Select AIs while ensuring diversity and Gemini inclusion."""
        if len(scores) <= target_count:
            return scores

        selected = []
        remaining = scores.copy()

        while len(selected) < target_count and remaining:
            # Take highest scoring AI
            best = remaining.pop(0)
            selected.append(best)

            # If we need more, consider diversity
            if len(selected) < target_count and remaining:
                # Check if remaining top AIs have same specialties
                selected_specialties = set()
                for s in selected:
                    selected_specialties.update(s.specialties[:2])

                # Find AI with different specialties if possible
                for i, candidate in enumerate(remaining):
                    candidate_specialties = set(candidate.specialties[:2])
                    if not candidate_specialties.issubset(selected_specialties):
                        # Boost this candidate's position
                        remaining.insert(0, remaining.pop(i))
                        break

        # ★ Gemini 포함 보장: 복잡한 작업에서 Gemini가 빠졌다면 추가
        selected_names = {s.adapter.name.lower() for s in selected}
        if "gemini" not in selected_names and target_count >= 3:
            # Gemini 찾기
            for score in scores:
                if score.adapter.name.lower() == "gemini":
                    # 마지막 AI를 Gemini로 교체
                    if len(selected) >= target_count:
                        selected[-1] = score
                    else:
                        selected.append(score)
                    break

        return selected

    def get_selection_explanation(
        self,
        task: Task,
        selected: list[AIAdapter],
    ) -> str:
        """Generate explanation for AI selection.

        Args:
            task: The analyzed task.
            selected: Selected adapters.

        Returns:
            Human-readable explanation.
        """
        parts = []
        parts.append(f"Task Type: {task.task_type.value}")
        parts.append(f"Complexity: {task.complexity:.0%}")
        parts.append(f"Selected {len(selected)} AIs:")

        for adapter in selected:
            specialties = self.AI_SPECIALTY_DESCRIPTIONS.get(adapter.name.lower(), ["general"])
            parts.append(f"  - {adapter.display_name}: {', '.join(specialties[:2])}")

        return "\n".join(parts)
