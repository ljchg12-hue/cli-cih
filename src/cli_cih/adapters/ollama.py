"""Ollama HTTP adapter for CLI-CIH."""

import json
from collections.abc import AsyncIterator

import httpx

from cli_cih.adapters.base import (
    AdapterConfig,
    AdapterError,
    AdapterTimeoutError,
    AIAdapter,
)


class OllamaAdapter(AIAdapter):
    """Adapter for Ollama local LLM server."""

    name = "ollama"
    display_name = "Ollama"
    color = "bright_magenta"
    icon = "🟣"

    DEFAULT_ENDPOINT = "http://localhost:11434"
    DEFAULT_MODEL = "llama3.1:70b"

    # Korean language system prompt - ENHANCED
    KOREAN_SYSTEM_PROMPT = """당신은 한국어로 응답하는 AI 어시스턴트입니다.

중요 규칙:
1. 모든 답변을 반드시 한국어로 작성하세요.
2. 영어로 질문해도 한국어로 답변하세요.
3. 코드 주석도 한국어로 작성하세요.
4. 전문적이면서도 친근한 톤을 유지하세요.
5. 간결하고 명확하게 답변하세요.
6. 기술 용어는 한국어 번역과 영어 원문을 함께 사용하세요 (예: 함수(function)).

응답 형식:
- 짧은 질문에는 간단히 답변
- 기술적 질문에는 예제 코드 포함
- 복잡한 질문에는 단계별 설명"""

    def __init__(
        self,
        config: AdapterConfig | None = None,
        use_korean: bool = True,
    ):
        """Initialize Ollama adapter.

        Args:
            config: Adapter configuration.
            use_korean: Whether to respond in Korean (default: True).
        """
        super().__init__(config)
        self._endpoint = config.endpoint if config and config.endpoint else self.DEFAULT_ENDPOINT
        self._model = config.model if config and config.model else self.DEFAULT_MODEL
        self._use_korean = use_korean

    async def _check_availability(self) -> bool:
        """Check if Ollama server is running.

        Returns:
            True if Ollama API is accessible.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._endpoint}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def get_version(self) -> str:
        """Get Ollama version.

        Returns:
            Version string.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._endpoint}/api/version")
                if response.status_code == 200:
                    data = response.json()
                    return data.get("version", "unknown")
        except Exception:
            pass
        return "unknown"

    async def list_models(self) -> list[str]:
        """List available Ollama models.

        Returns:
            List of model names.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self._endpoint}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    return [m.get("name", "") for m in models if m.get("name")]
        except Exception:
            pass
        return []

    async def send(self, prompt: str) -> AsyncIterator[str]:
        """Send a prompt to Ollama and stream response.

        Args:
            prompt: The prompt to send.

        Yields:
            Response chunks as they arrive.
        """
        if not await self.is_available():
            raise AdapterError(
                f"Ollama를 사용할 수 없습니다 ({self._endpoint}). 실행: ollama serve"
            )

        # Use chat API with system prompt for Korean support
        if self._use_korean:
            messages = [
                {"role": "system", "content": self.KOREAN_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            async for chunk in self.send_chat(messages):
                yield chunk
            return

        url = f"{self._endpoint}/api/generate"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                    timeout=httpx.Timeout(self.config.timeout, connect=10.0),
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        raise AdapterError(f"Ollama 오류: {error_text.decode()}")

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

        except httpx.TimeoutException as err:
            raise AdapterTimeoutError(f"Ollama 응답 시간 초과 ({self.config.timeout}초)") from err
        except httpx.HTTPError as e:
            raise AdapterError(f"Ollama HTTP 오류: {e}") from e

    async def send_chat(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        """Send a chat conversation to Ollama.

        Args:
            messages: List of message dicts with 'role' and 'content'.

        Yields:
            Response chunks.
        """
        url = f"{self._endpoint}/api/chat"
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                    timeout=httpx.Timeout(self.config.timeout, connect=10.0),
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        raise AdapterError(f"Ollama 오류: {error_text.decode()}")

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

        except httpx.TimeoutException as err:
            raise AdapterTimeoutError(f"Ollama 응답 시간 초과 ({self.config.timeout}초)") from err
        except httpx.HTTPError as e:
            raise AdapterError(f"Ollama HTTP 오류: {e}") from e

    def set_model(self, model: str) -> None:
        """Set the model to use.

        Args:
            model: Model name (e.g., 'llama3.1:70b').
        """
        self._model = model

    def set_endpoint(self, endpoint: str) -> None:
        """Set the Ollama endpoint.

        Args:
            endpoint: Endpoint URL.
        """
        self._endpoint = endpoint

    def set_korean(self, enabled: bool) -> None:
        """Enable or disable Korean response mode.

        Args:
            enabled: True to respond in Korean.
        """
        self._use_korean = enabled
