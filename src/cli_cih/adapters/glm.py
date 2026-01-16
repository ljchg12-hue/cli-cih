"""GLM (Z.AI) adapter for CLI-CIH.

This adapter provides integration with Z.AI's GLM-4.7 model.
Uses Anthropic-compatible API format.
"""

import asyncio
import json
import os
from collections.abc import AsyncIterator

import aiohttp

from cli_cih.adapters.base import (
    AdapterConfig,
    AdapterConnectionError,
    AdapterError,
    AdapterRateLimitError,
    AdapterTimeoutError,
    AIAdapter,
)


class GLMAdapter(AIAdapter):
    """Adapter for Z.AI GLM-4.7 API (Anthropic-compatible)."""

    name = "glm"
    display_name = "GLM-4.7"
    color = "bright_cyan"
    icon = "🔵"

    # Default API configuration (Anthropic-compatible)
    DEFAULT_BASE_URL = "https://api.z.ai/api/anthropic/v1"
    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"  # Z.AI maps this to GLM-4.7
    ANTHROPIC_VERSION = "2023-06-01"

    def __init__(self, config: AdapterConfig | None = None):
        """Initialize GLM adapter.

        Args:
            config: Optional adapter configuration.
        """
        super().__init__(config)

        # API configuration from environment or config
        self._api_key = os.environ.get("ZAI_API_KEY") or os.environ.get("GLM_API_KEY")
        self._base_url = os.environ.get("ZAI_BASE_URL", self.DEFAULT_BASE_URL)
        self._model = self.config.model or os.environ.get("GLM_MODEL", self.DEFAULT_MODEL)

    async def _check_availability(self) -> bool:
        """Check if GLM API is available.

        Returns:
            True if API key is set and API is reachable.
        """
        if not self._api_key:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": self._api_key,
                    "anthropic-version": self.ANTHROPIC_VERSION,
                    "Content-Type": "application/json",
                }
                # Simple health check - send minimal request
                payload = {
                    "model": self._model,
                    "max_tokens": 5,
                    "messages": [{"role": "user", "content": "hi"}],
                }
                async with session.post(
                    f"{self._base_url}/messages",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    return response.status == 200
        except Exception:
            return False

    async def get_version(self) -> str:
        """Get GLM model version.

        Returns:
            Model name/version string.
        """
        return "GLM-4.7 (via Z.AI)"

    async def send(self, prompt: str) -> AsyncIterator[str]:
        """Send a prompt to GLM API and stream response.

        Args:
            prompt: The prompt to send.

        Yields:
            Response chunks as they arrive.

        Raises:
            AdapterError: If API call fails.
        """
        if not self._api_key:
            raise AdapterError(
                "GLM API 키가 설정되지 않았습니다. "
                "환경변수 ZAI_API_KEY 또는 GLM_API_KEY를 설정하세요."
            )

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self.ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }

        try:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self._base_url}/messages",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status == 429:
                        raise AdapterRateLimitError("GLM API 요청 제한에 도달했습니다.")

                    if response.status == 401:
                        raise AdapterError("GLM API 인증 실패. API 키를 확인하세요.")

                    if response.status != 200:
                        error_text = await response.text()
                        raise AdapterError(f"GLM API 오류 ({response.status}): {error_text}")

                    # Stream SSE response (Anthropic format)
                    async for line in response.content:
                        line = line.decode("utf-8").strip()

                        if not line:
                            continue

                        if line.startswith("data: "):
                            data = line[6:]  # Remove "data: " prefix

                            if data == "[DONE]":
                                break

                            try:
                                chunk_data = json.loads(data)
                                event_type = chunk_data.get("type", "")

                                if event_type == "content_block_delta":
                                    delta = chunk_data.get("delta", {})
                                    if delta.get("type") == "text_delta":
                                        text = delta.get("text", "")
                                        if text:
                                            yield text
                            except json.JSONDecodeError:
                                continue

        except aiohttp.ClientConnectorError as e:
            raise AdapterConnectionError(f"GLM API 연결 실패: {e}") from e
        except asyncio.TimeoutError as e:
            raise AdapterTimeoutError(
                f"GLM API 응답 시간 초과 ({self.config.timeout}초)"
            ) from e
        except aiohttp.ClientError as e:
            raise AdapterError(f"GLM API 요청 오류: {e}") from e

    async def send_non_streaming(self, prompt: str) -> str:
        """Send a prompt and get complete response (non-streaming).

        Args:
            prompt: The prompt to send.

        Returns:
            Complete response text.
        """
        if not self._api_key:
            raise AdapterError(
                "GLM API 키가 설정되지 않았습니다. "
                "환경변수 ZAI_API_KEY 또는 GLM_API_KEY를 설정하세요."
            )

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self.ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self._base_url}/messages",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status == 429:
                        raise AdapterRateLimitError("GLM API 요청 제한에 도달했습니다.")

                    if response.status == 401:
                        raise AdapterError("GLM API 인증 실패. API 키를 확인하세요.")

                    if response.status != 200:
                        error_text = await response.text()
                        raise AdapterError(f"GLM API 오류 ({response.status}): {error_text}")

                    result = await response.json()
                    content = result.get("content", [])
                    if content and len(content) > 0:
                        return content[0].get("text", "")
                    return ""

        except aiohttp.ClientConnectorError as e:
            raise AdapterConnectionError(f"GLM API 연결 실패: {e}") from e
        except asyncio.TimeoutError as e:
            raise AdapterTimeoutError(
                f"GLM API 응답 시간 초과 ({self.config.timeout}초)"
            ) from e
        except aiohttp.ClientError as e:
            raise AdapterError(f"GLM API 요청 오류: {e}") from e
