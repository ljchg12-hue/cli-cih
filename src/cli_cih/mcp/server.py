#!/usr/bin/env python3
"""
CLI-CIH MCP Server
멀티AI 토론 오케스트레이션을 MCP 프로토콜로 제공

기존 cli-orchestrator의 AI 호출 기능 + CLI-CIH의 토론 로직 통합
Docker MCP Gateway 연동 지원

Phase 5: Refactored to use orchestration modules (no duplication)
"""

import asyncio
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from fastmcp import FastMCP

from cli_cih.orchestration.ai_selector import AISelector

# ═══════════════════════════════════════════════
# Import from orchestration (NO DUPLICATION)
# ═══════════════════════════════════════════════
from cli_cih.orchestration.task_analyzer import TaskAnalyzer
from cli_cih.storage.history import get_history_storage

# ═══════════════════════════════════════════════
# MCP Server 초기화
# ═══════════════════════════════════════════════

mcp = FastMCP(
    "cli-cih", instructions="Multi-AI Discussion Orchestrator - 여러 AI를 조율하여 최적의 답변 도출"
)

# ═══════════════════════════════════════════════
# Shared Instances (Singleton)
# ═══════════════════════════════════════════════

_task_analyzer = TaskAnalyzer()
_ai_selector = AISelector()

# ═══════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════


def get_cli_path(name: str) -> str:
    """CLI 실행 파일 경로 찾기 (환경변수 > which > 기본값)."""
    env_key = f"{name.upper()}_BIN"
    if os.getenv(env_key):
        return os.getenv(env_key)
    path = shutil.which(name)
    if path:
        return path
    return name


# CLI 경로 (동적으로 찾기)
CLAUDE_CMD = get_cli_path("claude")
GEMINI_CMD = get_cli_path("gemini")
CODEX_CMD = get_cli_path("codex")
COPILOT_CMD = get_cli_path("copilot")
OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")

# Docker MCP Gateway 설정
DOCKER_GATEWAY_URL = os.environ.get("DOCKER_GATEWAY_URL", "http://localhost:8811")
DOCKER_GATEWAY_ENABLED = os.environ.get("DOCKER_GATEWAY_ENABLED", "true").lower() == "true"

# 한글 시스템 프롬프트
KOREAN_SYSTEM_PROMPT = (
    "당신은 한국어로 응답하는 AI 어시스턴트입니다. "
    "사용자의 질문에 한국어로 명확하고 도움이 되게 답변해 주세요."
)


# ═══════════════════════════════════════════════
# Standard Response Schema
# ═══════════════════════════════════════════════


@dataclass
class MCPResponse:
    """Standardized MCP tool response."""

    success: bool
    data: dict | None = None
    error: str | None = None
    metadata: dict | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata or {},
        }


def make_response(
    success: bool,
    data: dict | None = None,
    error: str | None = None,
    duration_ms: int | None = None,
    ai_used: list[str] | None = None,
) -> dict:
    """Create standardized response."""
    metadata = {}
    if duration_ms is not None:
        metadata["duration_ms"] = duration_ms
    if ai_used:
        metadata["ai_used"] = ai_used

    return MCPResponse(
        success=success,
        data=data,
        error=error,
        metadata=metadata if metadata else None,
    ).to_dict()


# ═══════════════════════════════════════════════
# CLI 실행 헬퍼
# ═══════════════════════════════════════════════


def run_cli_safe(command: list[str], timeout: int = 120) -> dict:
    """CLI 명령어 안전하게 실행."""
    try:
        env = os.environ.copy()
        env["TERM"] = "dumb"
        env["NO_COLOR"] = "1"
        env["CI"] = "1"

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Timeout after {timeout}s", "success": False}
    except FileNotFoundError:
        return {"error": f"Command not found: {command[0]}", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


async def call_ollama(prompt: str, model: str = "llama3.1:70b") -> dict:
    """Ollama HTTP API 직접 호출."""
    url = f"{OLLAMA_ENDPOINT}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": KOREAN_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                data = response.json()
                return {
                    "response": data.get("message", {}).get("content", ""),
                    "model": model,
                    "success": True,
                    "source": "ollama",
                }
            return {"error": f"HTTP {response.status_code}", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


# ═══════════════════════════════════════════════
# Docker MCP Gateway 클라이언트
# ═══════════════════════════════════════════════


class DockerGatewayClient:
    """Docker MCP Gateway HTTP 클라이언트 with retry."""

    def __init__(self, base_url: str = DOCKER_GATEWAY_URL, max_retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request_with_retry(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make request with retry logic."""
        client = await self._get_client()
        last_error = None

        for attempt in range(self.max_retries):
            try:
                if method == "GET":
                    response = await client.get(path, **kwargs)
                else:
                    response = await client.post(path, **kwargs)
                return response
            except httpx.RequestError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))  # Backoff

        raise last_error

    async def list_servers(self) -> dict:
        """등록된 MCP 서버 목록 조회."""
        try:
            response = await self._request_with_retry("GET", "/servers")
            if response.status_code == 200:
                return {"success": True, "servers": response.json()}
            return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def find_server(self, query: str, limit: int = 10) -> dict:
        """서버 검색 (mcp-find)."""
        try:
            response = await self._request_with_retry(
                "GET", "/servers/search", params={"query": query, "limit": limit}
            )
            if response.status_code == 200:
                return {"success": True, "results": response.json()}
            return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def call_tool(
        self,
        server: str,
        tool: str,
        arguments: dict | None = None,
        timeout: float = 60.0,
    ) -> dict:
        """MCP 서버의 도구 호출 (mcp-exec) with timeout."""
        try:
            client = await self._get_client()
            payload = {"server": server, "tool": tool, "arguments": arguments or {}}
            response = await asyncio.wait_for(
                client.post("/tools/call", json=payload), timeout=timeout
            )
            if response.status_code == 200:
                return {"success": True, "result": response.json()}
            return {"success": False, "error": f"HTTP {response.status_code}"}
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Timeout after {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_server_tools(self, server: str) -> dict:
        """특정 서버의 도구 목록 조회."""
        try:
            response = await self._request_with_retry("GET", f"/servers/{server}/tools")
            if response.status_code == 200:
                return {"success": True, "tools": response.json()}
            return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def check_health(self) -> dict:
        """Gateway 상태 확인."""
        try:
            response = await self._request_with_retry("GET", "/health")
            return {
                "success": response.status_code == 200,
                "status": response.json() if response.status_code == 200 else None,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# 전역 클라이언트 인스턴스
_gateway_client: DockerGatewayClient | None = None


def get_gateway_client() -> DockerGatewayClient:
    """Docker Gateway 클라이언트 싱글톤."""
    global _gateway_client
    if _gateway_client is None:
        _gateway_client = DockerGatewayClient()
    return _gateway_client


# ═══════════════════════════════════════════════
# MCP Tools - Core Functions
# ═══════════════════════════════════════════════


@mcp.tool()
async def cih_quick(prompt: str, ai: str = "claude", timeout: int = 60) -> dict:
    """
    빠른 단일 AI 응답 (간단한 질문용)

    Args:
        prompt: 사용자 질문
        ai: 사용할 AI (claude/codex/gemini/ollama)
        timeout: 타임아웃 (초)

    Returns:
        표준화된 응답 {success, data, error, metadata}
    """
    start = time.time()

    try:
        if ai == "claude":
            result = run_cli_safe([CLAUDE_CMD, "-p", prompt], timeout=timeout)
        elif ai == "codex":
            result = run_cli_safe(
                [CODEX_CMD, "exec", "--skip-git-repo-check", prompt], timeout=timeout
            )
        elif ai == "gemini":
            result = run_cli_safe([GEMINI_CMD, prompt], timeout=timeout)
        elif ai == "ollama":
            result = await call_ollama(prompt)
        else:
            return make_response(False, error=f"Unknown AI: {ai}")

        duration = int((time.time() - start) * 1000)

        if result.get("success"):
            return make_response(
                True,
                data={"response": result.get("stdout") or result.get("response"), "ai": ai},
                duration_ms=duration,
                ai_used=[ai],
            )

        # Fallback to Ollama if primary fails
        if ai != "ollama":
            ollama_result = await call_ollama(prompt)
            if ollama_result["success"]:
                return make_response(
                    True,
                    data={"response": ollama_result["response"], "ai": "ollama", "fallback": True},
                    duration_ms=int((time.time() - start) * 1000),
                    ai_used=[ai, "ollama"],
                )

        return make_response(False, error=result.get("error", "Unknown error"))

    except Exception as e:
        return make_response(False, error=str(e))


@mcp.tool()
async def cih_analyze(prompt: str) -> dict:
    """
    작업 분석 - 프롬프트를 분석하여 최적의 AI 조합 추천
    Uses orchestration.TaskAnalyzer (no duplication)

    Args:
        prompt: 분석할 사용자 질문

    Returns:
        작업 유형, 복잡도, 추천 AI 목록
    """
    start = time.time()

    try:
        task = _task_analyzer.analyze(prompt)

        data = {
            "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,
            "task_type": task.task_type.value,
            "complexity": round(task.complexity, 2),
            "complexity_level": "low"
            if task.complexity < 0.3
            else "medium"
            if task.complexity < 0.7
            else "high",
            "keywords": task.keywords[:5],
            "requires_multi_ai": task.requires_multi_ai,
            "suggested_rounds": task.suggested_rounds,
            "suggested_ai_count": task.suggested_ai_count,
            "recommendation": (
                "단일 AI 빠른 응답 (cih_quick)"
                if not task.requires_multi_ai
                else "멀티 AI 토론 (cih_discuss)"
            ),
        }

        return make_response(
            True,
            data=data,
            duration_ms=int((time.time() - start) * 1000),
        )

    except Exception as e:
        return make_response(False, error=str(e))


@mcp.tool()
async def cih_discuss(
    prompt: str,
    ais: list[str] | None = None,
    max_rounds: int = 2,
    include_synthesis: bool = True,
    timeout: int = 90,
) -> dict:
    """
    멀티 AI 토론 - 여러 AI의 의견을 수집하고 종합

    Args:
        prompt: 토론 주제/질문
        ais: 참여할 AI 목록 (기본: 자동 선택)
        max_rounds: 최대 토론 라운드 (기본: 2)
        include_synthesis: 종합 결과 포함 여부
        timeout: 각 AI 타임아웃 (초)

    Returns:
        각 AI의 응답과 종합 결과
    """
    start = time.time()

    try:
        # 작업 분석 (using TaskAnalyzer)
        task = _task_analyzer.analyze(prompt)

        # AI 선택
        if ais is None:
            if task.requires_multi_ai:
                ais = ["claude", "codex", "gemini"][: task.suggested_ai_count]
            else:
                ais = ["claude"]

        # 간단한 질문은 빠른 응답으로 리다이렉트
        if not task.requires_multi_ai:
            quick_result = await cih_quick(prompt)
            quick_result["data"]["note"] = "Simple question - redirected to quick response"
            return quick_result

        responses = {}
        errors = []

        # 병렬로 AI 호출
        async def call_ai(ai_name: str):
            if ai_name == "claude":
                result = run_cli_safe([CLAUDE_CMD, "-p", prompt], timeout=timeout)
                if result["success"]:
                    return ai_name, {"response": result["stdout"], "success": True}
                return ai_name, {"error": result.get("error", "Unknown"), "success": False}

            elif ai_name == "codex":
                result = run_cli_safe(
                    [CODEX_CMD, "exec", "--skip-git-repo-check", prompt], timeout=timeout
                )
                if result["success"]:
                    return ai_name, {"response": result["stdout"], "success": True}
                return ai_name, {"error": result.get("error", "Unknown"), "success": False}

            elif ai_name == "gemini":
                result = run_cli_safe([GEMINI_CMD, prompt], timeout=timeout)
                if result["success"]:
                    return ai_name, {"response": result["stdout"], "success": True}
                return ai_name, {"error": result.get("error", "Unknown"), "success": False}

            elif ai_name == "ollama":
                return ai_name, await call_ollama(prompt)

            elif ai_name == "copilot":
                result = run_cli_safe([COPILOT_CMD, "explain", prompt], timeout=timeout)
                if result["success"]:
                    return ai_name, {"response": result["stdout"], "success": True}
                return ai_name, {"error": result.get("error", "Unknown"), "success": False}

            return ai_name, {"error": f"Unknown AI: {ai_name}", "success": False}

        # 병렬 실행
        tasks = [call_ai(ai) for ai in ais]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            else:
                ai_name, response = result
                responses[ai_name] = response

        # 종합 (Claude로 요청)
        synthesis = None
        if include_synthesis and len([r for r in responses.values() if r.get("success")]) > 1:
            successful_responses = {
                ai: r["response"]
                for ai, r in responses.items()
                if r.get("success") and r.get("response")
            }

            if successful_responses:
                synthesis_prompt = f"""다음은 '{prompt}'에 대한 여러 AI의 응답입니다.
각 응답을 종합하여 최종 결론을 한국어로 제시해주세요.

{json.dumps(successful_responses, ensure_ascii=False, indent=2)}

종합 결론:"""

                synthesis_result = run_cli_safe([CLAUDE_CMD, "-p", synthesis_prompt], timeout=60)
                if synthesis_result["success"]:
                    synthesis = {"summary": synthesis_result["stdout"], "synthesized_by": "claude"}

        duration = int((time.time() - start) * 1000)
        successful_ais = [ai for ai, r in responses.items() if r.get("success")]

        return make_response(
            success=len(successful_ais) > 0,
            data={
                "prompt": prompt,
                "task_type": task.task_type.value,
                "complexity": round(task.complexity, 2),
                "participating_ais": ais,
                "responses": responses,
                "synthesis": synthesis,
                "errors": errors if errors else None,
            },
            duration_ms=duration,
            ai_used=successful_ais,
        )

    except Exception as e:
        return make_response(False, error=str(e))


@mcp.tool()
async def cih_compare(
    prompt: str,
    ais: list[str] | None = None,
    timeout: int = 90,
) -> dict:
    """
    AI 응답 비교 - 동일 질문에 대한 여러 AI 응답을 나란히 비교

    Args:
        prompt: 비교할 질문
        ais: 비교할 AI 목록
        timeout: 타임아웃 (초)

    Returns:
        각 AI 응답과 비교 분석
    """
    if ais is None:
        ais = ["claude", "codex", "gemini"]
    result = await cih_discuss(prompt, ais=ais, include_synthesis=True, timeout=timeout)
    if result.get("data"):
        result["data"]["mode"] = "comparison"
    return result


@mcp.tool()
async def cih_status() -> dict:
    """
    CLI-CIH 상태 확인 - 사용 가능한 AI와 연결 상태

    Returns:
        각 AI의 가용성 정보 (표준 응답 형식)
    """
    start = time.time()
    status = {}

    # Claude
    result = run_cli_safe([CLAUDE_CMD, "--version"], timeout=10)
    status["claude"] = {
        "available": result["success"],
        "version": result.get("stdout", "unknown") if result["success"] else None,
        "path": CLAUDE_CMD,
    }

    # Codex
    result = run_cli_safe([CODEX_CMD, "--version"], timeout=10)
    status["codex"] = {
        "available": result["success"],
        "version": result.get("stdout", "unknown") if result["success"] else None,
        "path": CODEX_CMD,
    }

    # Gemini
    result = run_cli_safe([GEMINI_CMD, "--version"], timeout=10)
    status["gemini"] = {
        "available": result["success"],
        "version": result.get("stdout", "unknown") if result["success"] else None,
        "path": GEMINI_CMD,
    }

    # Copilot
    result = run_cli_safe([COPILOT_CMD, "--version"], timeout=10)
    status["copilot"] = {
        "available": result["success"],
        "version": result.get("stdout", "unknown") if result["success"] else None,
        "path": COPILOT_CMD,
    }

    # Ollama
    try:
        response = httpx.get(f"{OLLAMA_ENDPOINT}/api/tags", timeout=5.0)
        if response.status_code == 200:
            models = response.json().get("models", [])
            status["ollama"] = {
                "available": True,
                "endpoint": OLLAMA_ENDPOINT,
                "models": [m.get("name") for m in models[:5]],
            }
        else:
            status["ollama"] = {"available": False, "endpoint": OLLAMA_ENDPOINT}
    except Exception:
        status["ollama"] = {"available": False, "endpoint": OLLAMA_ENDPOINT}

    available_count = sum(1 for s in status.values() if isinstance(s, dict) and s.get("available"))

    return make_response(
        True,
        data={
            "ais": status,
            "summary": {
                "total_ais": 5,
                "available": available_count,
                "ready": available_count >= 2,
            },
        },
        duration_ms=int((time.time() - start) * 1000),
    )


@mcp.tool()
async def cih_smart(
    prompt: str,
    task_type: Literal["code", "debug", "design", "research", "explain", "general"] | None = None,
    timeout: int = 90,
) -> dict:
    """
    스마트 라우팅 - 작업 유형에 따라 최적 AI 자동 선택

    Args:
        prompt: 사용자 질문
        task_type: 작업 유형 (생략시 자동 분석)
        timeout: 타임아웃 (초)

    Returns:
        선택된 AI의 응답 (표준 응답 형식)
    """
    start = time.time()

    try:
        # 작업 유형 결정 (using TaskAnalyzer)
        if task_type is None:
            task = _task_analyzer.analyze(prompt)
            task_type = task.task_type.value

        # 라우팅 로직
        routing = {
            "code": ("codex", "코드 특화"),
            "debug": ("codex", "디버깅 특화"),
            "design": ("claude", "설계/아키텍처 특화"),
            "research": ("gemini", "리서치/검색 특화"),
            "explain": ("claude", "설명 특화"),
            "general": ("claude", "범용"),
            "simple_chat": ("claude", "빠른 응답"),
        }

        ai, reason = routing.get(task_type, ("claude", "기본값"))

        # AI 호출
        if ai == "codex":
            result = run_cli_safe(
                [CODEX_CMD, "exec", "--skip-git-repo-check", prompt], timeout=timeout
            )
        elif ai == "gemini":
            result = run_cli_safe([GEMINI_CMD, prompt], timeout=timeout)
        else:  # claude
            result = run_cli_safe([CLAUDE_CMD, "-p", prompt], timeout=timeout)

        duration = int((time.time() - start) * 1000)

        if result["success"]:
            return make_response(
                True,
                data={
                    "response": result["stdout"],
                    "selected_ai": ai,
                    "task_type": task_type,
                    "routing_reason": reason,
                },
                duration_ms=duration,
                ai_used=[ai],
            )

        return make_response(
            False,
            error=result.get("error", "Unknown error"),
            duration_ms=duration,
        )

    except Exception as e:
        return make_response(False, error=str(e))


# ═══════════════════════════════════════════════
# MCP Tools - New in Phase 5
# ═══════════════════════════════════════════════


@mcp.tool()
async def cih_history(limit: int = 10, search: str | None = None) -> dict:
    """
    대화 히스토리 조회

    Args:
        limit: 최대 결과 수 (기본: 10)
        search: 검색어 (선택)

    Returns:
        최근 대화 목록
    """
    start = time.time()

    try:
        storage = get_history_storage()

        if search:
            sessions = await storage.search(search, limit=limit)
        else:
            sessions = await storage.get_recent(limit=limit)

        conversations = [
            {
                "id": s.id,
                "query": s.user_query[:100] + "..." if len(s.user_query) > 100 else s.user_query,
                "task_type": s.task_type,
                "participating_ais": s.participating_ais,
                "rounds": s.total_rounds,
                "status": s.status.value,
                "created_at": s.created_at.isoformat(),
            }
            for s in sessions
        ]

        return make_response(
            True,
            data={"conversations": conversations, "count": len(conversations)},
            duration_ms=int((time.time() - start) * 1000),
        )

    except Exception as e:
        return make_response(False, error=str(e))


@mcp.tool()
async def cih_history_detail(session_id: str, format: str = "json") -> dict:
    """
    대화 히스토리 상세 조회

    Args:
        session_id: 세션 ID
        format: 출력 형식 (json/md/txt)

    Returns:
        세션 상세 정보
    """
    start = time.time()

    try:
        storage = get_history_storage()
        session = await storage.get_session(session_id)

        if not session:
            return make_response(False, error=f"Session not found: {session_id}")

        if format in ["md", "txt"]:
            content = await storage.export_session(session_id, format=format)
            return make_response(
                True,
                data={"content": content, "format": format},
                duration_ms=int((time.time() - start) * 1000),
            )

        return make_response(
            True,
            data={
                "id": session.id,
                "query": session.user_query,
                "task_type": session.task_type,
                "participating_ais": session.participating_ais,
                "rounds": session.total_rounds,
                "status": session.status.value,
                "messages": [
                    {
                        "sender": m.sender_id,
                        "content": m.content[:200] + "..." if len(m.content) > 200 else m.content,
                        "round": m.round_num,
                    }
                    for m in session.messages
                ],
                "result": {
                    "summary": session.result.summary if session.result else None,
                    "consensus": session.result.consensus_reached if session.result else None,
                },
            },
            duration_ms=int((time.time() - start) * 1000),
        )

    except Exception as e:
        return make_response(False, error=str(e))


@mcp.tool()
async def cih_models() -> dict:
    """
    사용 가능한 AI 모델 목록 (상세)

    Returns:
        각 AI 서비스의 모델 정보
    """
    start = time.time()

    try:
        models = {}

        # Cloud AIs (CLI-based)
        for name, cmd in [
            ("claude", CLAUDE_CMD),
            ("codex", CODEX_CMD),
            ("gemini", GEMINI_CMD),
            ("copilot", COPILOT_CMD),
        ]:
            result = run_cli_safe([cmd, "--version"], timeout=10)
            models[name] = {
                "available": result["success"],
                "type": "cloud",
                "version": result.get("stdout", "unknown")[:50] if result["success"] else None,
            }

        # Ollama (local models)
        try:
            response = httpx.get(f"{OLLAMA_ENDPOINT}/api/tags", timeout=10.0)
            if response.status_code == 200:
                ollama_models = response.json().get("models", [])
                models["ollama"] = {
                    "available": True,
                    "type": "local",
                    "endpoint": OLLAMA_ENDPOINT,
                    "models": [
                        {
                            "name": m.get("name"),
                            "size": m.get("size", 0) // (1024**3),  # GB
                            "modified": m.get("modified_at"),
                        }
                        for m in ollama_models[:10]
                    ],
                    "model_count": len(ollama_models),
                }
            else:
                models["ollama"] = {"available": False, "type": "local"}
        except Exception as e:
            models["ollama"] = {"available": False, "type": "local", "error": str(e)}

        return make_response(
            True,
            data={"models": models},
            duration_ms=int((time.time() - start) * 1000),
        )

    except Exception as e:
        return make_response(False, error=str(e))


@mcp.tool()
async def cih_stats() -> dict:
    """
    CLI-CIH 사용 통계

    Returns:
        히스토리 통계 및 AI 사용량
    """
    start = time.time()

    try:
        storage = get_history_storage()
        stats = await storage.get_stats()

        return make_response(
            True,
            data=stats,
            duration_ms=int((time.time() - start) * 1000),
        )

    except Exception as e:
        return make_response(False, error=str(e))


# ═══════════════════════════════════════════════
# Docker Gateway MCP Tools
# ═══════════════════════════════════════════════


@mcp.tool()
async def cih_gateway_status() -> dict:
    """
    Docker MCP Gateway 상태 확인 (상세)

    Returns:
        Gateway 연결 상태, 서버 목록, 도구 수
    """
    start = time.time()

    if not DOCKER_GATEWAY_ENABLED:
        return make_response(
            False, error="Docker Gateway가 비활성화되어 있습니다 (DOCKER_GATEWAY_ENABLED=false)"
        )

    try:
        client = get_gateway_client()
        health = await client.check_health()

        if not health["success"]:
            return make_response(
                False,
                data={"gateway_url": DOCKER_GATEWAY_URL, "enabled": True},
                error=health.get("error", "Connection failed"),
            )

        servers = await client.list_servers()
        server_list = servers.get("servers", []) if servers["success"] else []

        # Count tools per server (sample first 5)
        tool_counts = {}
        for server in server_list[:5]:
            server_name = server.get("name", "") if isinstance(server, dict) else server
            tools = await client.get_server_tools(server_name)
            tool_counts[server_name] = len(tools.get("tools", [])) if tools["success"] else 0

        return make_response(
            True,
            data={
                "enabled": True,
                "connected": True,
                "gateway_url": DOCKER_GATEWAY_URL,
                "server_count": len(server_list),
                "servers": [
                    s.get("name", s) if isinstance(s, dict) else s for s in server_list[:10]
                ],
                "tool_counts_sample": tool_counts,
                "health": health.get("status"),
            },
            duration_ms=int((time.time() - start) * 1000),
        )

    except Exception as e:
        return make_response(False, error=str(e))


@mcp.tool()
async def cih_gateway_find(query: str, limit: int = 10) -> dict:
    """
    Docker Gateway에서 MCP 서버 검색

    Args:
        query: 검색어 (서버 이름, 설명)
        limit: 최대 결과 수

    Returns:
        검색된 서버 목록
    """
    start = time.time()

    if not DOCKER_GATEWAY_ENABLED:
        return make_response(False, error="Docker Gateway disabled")

    try:
        client = get_gateway_client()
        result = await client.find_server(query, limit)

        return make_response(
            result["success"],
            data={"results": result.get("results", [])} if result["success"] else None,
            error=result.get("error"),
            duration_ms=int((time.time() - start) * 1000),
        )

    except Exception as e:
        return make_response(False, error=str(e))


@mcp.tool()
async def cih_gateway_tools(server: str) -> dict:
    """
    Docker Gateway 서버의 도구 목록 조회

    Args:
        server: MCP 서버 이름

    Returns:
        해당 서버의 사용 가능한 도구 목록
    """
    start = time.time()

    if not DOCKER_GATEWAY_ENABLED:
        return make_response(False, error="Docker Gateway disabled")

    try:
        client = get_gateway_client()
        result = await client.get_server_tools(server)

        return make_response(
            result["success"],
            data={"server": server, "tools": result.get("tools", [])}
            if result["success"]
            else None,
            error=result.get("error"),
            duration_ms=int((time.time() - start) * 1000),
        )

    except Exception as e:
        return make_response(False, error=str(e))


@mcp.tool()
async def cih_gateway_exec(
    server: str,
    tool: str,
    arguments: dict[str, Any] | None = None,
    timeout: float = 60.0,
) -> dict:
    """
    Docker Gateway를 통해 MCP 도구 실행

    Args:
        server: MCP 서버 이름
        tool: 도구 이름
        arguments: 도구 인자 (선택사항)
        timeout: 타임아웃 (초)

    Returns:
        도구 실행 결과
    """
    start = time.time()

    if not DOCKER_GATEWAY_ENABLED:
        return make_response(False, error="Docker Gateway disabled")

    try:
        client = get_gateway_client()
        result = await client.call_tool(server, tool, arguments, timeout=timeout)

        return make_response(
            result["success"],
            data={"server": server, "tool": tool, "result": result.get("result")}
            if result["success"]
            else None,
            error=result.get("error"),
            duration_ms=int((time.time() - start) * 1000),
        )

    except Exception as e:
        return make_response(False, error=str(e))


@mcp.tool()
async def cih_gateway_multi_exec(
    calls: list[dict[str, Any]],
    timeout: float = 60.0,
) -> dict:
    """
    Docker Gateway를 통해 여러 MCP 도구 병렬 실행

    Args:
        calls: 호출 목록 [{"server": str, "tool": str, "arguments": dict}, ...]
        timeout: 각 호출 타임아웃 (초)

    Returns:
        모든 도구 실행 결과
    """
    start = time.time()

    if not DOCKER_GATEWAY_ENABLED:
        return make_response(False, error="Docker Gateway disabled")

    try:
        client = get_gateway_client()

        async def exec_call(call_spec: dict):
            server = call_spec.get("server", "")
            tool = call_spec.get("tool", "")
            args = call_spec.get("arguments", {})
            result = await client.call_tool(server, tool, args, timeout=timeout)
            return {"server": server, "tool": tool, **result}

        tasks = [exec_call(call) for call in calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(
                    {
                        "server": calls[i].get("server"),
                        "tool": calls[i].get("tool"),
                        "success": False,
                        "error": str(result),
                    }
                )
            else:
                processed.append(result)

        succeeded = sum(1 for r in processed if r.get("success"))

        return make_response(
            succeeded > 0,
            data={
                "total": len(calls),
                "succeeded": succeeded,
                "failed": len(calls) - succeeded,
                "results": processed,
            },
            duration_ms=int((time.time() - start) * 1000),
        )

    except Exception as e:
        return make_response(False, error=str(e))


# ═══════════════════════════════════════════════
# 서버 실행
# ═══════════════════════════════════════════════


def run_server():
    """MCP 서버 실행."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
