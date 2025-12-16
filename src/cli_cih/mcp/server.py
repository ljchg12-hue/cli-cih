#!/usr/bin/env python3
"""
CLI-CIH MCP Server
멀티AI 토론 오케스트레이션을 MCP 프로토콜로 제공

기존 cli-orchestrator의 AI 호출 기능 + CLI-CIH의 토론 로직 통합
Docker MCP Gateway 연동 지원
"""

import asyncio
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, Optional

import httpx
from fastmcp import FastMCP

# ═══════════════════════════════════════════════
# MCP Server 초기화
# ═══════════════════════════════════════════════

mcp = FastMCP(
    "cli-cih",
    instructions="Multi-AI Discussion Orchestrator - 여러 AI를 조율하여 최적의 답변 도출"
)

# ═══════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════


def get_cli_path(name: str) -> str:
    """CLI 실행 파일 경로 찾기 (환경변수 > which > 기본값).

    Args:
        name: CLI 이름 (claude, codex, gemini, copilot)

    Returns:
        실행 파일 경로
    """
    # 1. 환경변수 확인 (CLAUDE_BIN, CODEX_BIN 등)
    env_key = f'{name.upper()}_BIN'
    if os.getenv(env_key):
        return os.getenv(env_key)

    # 2. which로 PATH에서 검색
    path = shutil.which(name)
    if path:
        return path

    # 3. 기본값 (명령어 이름만)
    return name


# CLI 경로 (동적으로 찾기 - 하드코딩 제거)
CLAUDE_CMD = get_cli_path('claude')
GEMINI_CMD = get_cli_path('gemini')
CODEX_CMD = get_cli_path('codex')
COPILOT_CMD = get_cli_path('copilot')
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
# Task Types & AI Specialties
# ═══════════════════════════════════════════════

class TaskType(str, Enum):
    CODE = "code"
    DESIGN = "design"
    ANALYSIS = "analysis"
    CREATIVE = "creative"
    RESEARCH = "research"
    DEBUG = "debug"
    EXPLAIN = "explain"
    GENERAL = "general"
    SIMPLE_CHAT = "simple_chat"


# AI별 전문 분야 점수 (0.0 ~ 1.0)
AI_SPECIALTIES = {
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


# ═══════════════════════════════════════════════
# CLI 실행 헬퍼
# ═══════════════════════════════════════════════

def run_cli_safe(command: list[str], timeout: int = 120) -> dict:
    """CLI 명령어 안전하게 실행."""
    try:
        # 비대화형 환경 설정
        env = os.environ.copy()
        env['TERM'] = 'dumb'
        env['NO_COLOR'] = '1'
        env['CI'] = '1'

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
                    "source": "ollama"
                }
            return {"error": f"HTTP {response.status_code}", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


# ═══════════════════════════════════════════════
# Docker MCP Gateway 클라이언트
# ═══════════════════════════════════════════════

class DockerGatewayClient:
    """Docker MCP Gateway HTTP 클라이언트."""

    def __init__(self, base_url: str = DOCKER_GATEWAY_URL):
        self.base_url = base_url.rstrip("/")
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

    async def list_servers(self) -> dict:
        """등록된 MCP 서버 목록 조회."""
        try:
            client = await self._get_client()
            response = await client.get("/servers")
            if response.status_code == 200:
                return {"success": True, "servers": response.json()}
            return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def find_server(self, query: str, limit: int = 10) -> dict:
        """서버 검색 (mcp-find)."""
        try:
            client = await self._get_client()
            response = await client.get(
                "/servers/search",
                params={"query": query, "limit": limit}
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
        arguments: dict | None = None
    ) -> dict:
        """MCP 서버의 도구 호출 (mcp-exec)."""
        try:
            client = await self._get_client()
            payload = {
                "server": server,
                "tool": tool,
                "arguments": arguments or {}
            }
            response = await client.post("/tools/call", json=payload)
            if response.status_code == 200:
                return {"success": True, "result": response.json()}
            return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_server_tools(self, server: str) -> dict:
        """특정 서버의 도구 목록 조회."""
        try:
            client = await self._get_client()
            response = await client.get(f"/servers/{server}/tools")
            if response.status_code == 200:
                return {"success": True, "tools": response.json()}
            return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def check_health(self) -> dict:
        """Gateway 상태 확인."""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return {
                "success": response.status_code == 200,
                "status": response.json() if response.status_code == 200 else None
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
# 작업 분석기
# ═══════════════════════════════════════════════

def analyze_task(prompt: str) -> dict:
    """입력 프롬프트 분석하여 작업 유형 및 복잡도 판단."""
    prompt_lower = prompt.lower()
    length = len(prompt)

    # 키워드 기반 작업 유형 분류 (먼저 체크)
    code_keywords = ["코드", "code", "함수", "function", "구현", "implement", "프로그램", "작성", "만들어"]
    debug_keywords = ["버그", "bug", "에러", "error", "디버그", "debug", "수정", "fix"]
    design_keywords = ["설계", "design", "아키텍처", "architecture", "구조", "structure"]
    research_keywords = ["조사", "research", "검색", "search", "찾아", "find", "최신"]
    explain_keywords = ["설명", "explain", "알려", "tell", "무엇", "what", "어떻게", "how"]

    # 코드/디버그/설계 키워드가 있으면 간단한 대화가 아님
    has_technical_keywords = (
        any(k in prompt_lower for k in code_keywords) or
        any(k in prompt_lower for k in debug_keywords) or
        any(k in prompt_lower for k in design_keywords)
    )

    # 간단한 인사/대화 감지 (기술 키워드가 없는 경우만)
    simple_patterns = [
        "안녕", "hello", "hi", "고마워", "감사", "ok", "yes", "no",
        "응", "네", "아니", "좋아", "알겠어"
    ]
    if not has_technical_keywords and (length < 15 and any(p in prompt_lower for p in simple_patterns)):
        return {
            "task_type": TaskType.SIMPLE_CHAT,
            "complexity": 0.1,
            "suggested_ais": ["claude"],
            "requires_discussion": False,
        }

    # 작업 유형 결정
    task_type = TaskType.GENERAL
    if any(k in prompt_lower for k in debug_keywords):
        task_type = TaskType.DEBUG
    elif any(k in prompt_lower for k in code_keywords):
        task_type = TaskType.CODE
    elif any(k in prompt_lower for k in design_keywords):
        task_type = TaskType.DESIGN
    elif any(k in prompt_lower for k in research_keywords):
        task_type = TaskType.RESEARCH
    elif any(k in prompt_lower for k in explain_keywords):
        task_type = TaskType.EXPLAIN

    # 복잡도 계산
    complexity = min(1.0, length / 200)  # 더 낮은 기준점

    # 작업 유형에 따른 복잡도 보너스
    if task_type in [TaskType.DESIGN, TaskType.ANALYSIS]:
        complexity += 0.4  # 설계/분석은 본질적으로 복잡
    elif task_type in [TaskType.CODE, TaskType.DEBUG]:
        complexity += 0.3  # 코드/디버그도 복잡
    elif task_type == TaskType.RESEARCH:
        complexity += 0.35  # 리서치는 다양한 관점 필요

    if "?" in prompt:
        complexity += 0.1
    if any(k in prompt_lower for k in ["분석", "비교", "장단점", "최적", "설계", "아키텍처"]):
        complexity += 0.2

    complexity = min(1.0, complexity)

    # AI 선택
    if complexity < 0.3 or task_type == TaskType.SIMPLE_CHAT:
        suggested_ais = ["claude"]
        requires_discussion = False
    elif complexity < 0.6:
        suggested_ais = ["claude", "codex"] if task_type in [TaskType.CODE, TaskType.DEBUG] else ["claude", "gemini"]
        requires_discussion = True
    else:
        suggested_ais = ["claude", "codex", "gemini"]
        requires_discussion = True

    return {
        "task_type": task_type,
        "complexity": round(complexity, 2),
        "suggested_ais": suggested_ais,
        "requires_discussion": requires_discussion,
    }


# ═══════════════════════════════════════════════
# MCP Tools
# ═══════════════════════════════════════════════

@mcp.tool()
async def cih_quick(prompt: str) -> dict:
    """
    빠른 단일 AI 응답 (간단한 질문용)

    Args:
        prompt: 사용자 질문

    Returns:
        단일 AI의 빠른 응답
    """
    # Claude CLI로 빠른 응답
    result = run_cli_safe([CLAUDE_CMD, "-p", prompt], timeout=60)

    if result["success"]:
        return {
            "response": result["stdout"],
            "ai": "claude",
            "mode": "quick",
            "success": True
        }

    # Claude 실패 시 Ollama fallback
    ollama_result = await call_ollama(prompt)
    if ollama_result["success"]:
        return {
            "response": ollama_result["response"],
            "ai": "ollama",
            "mode": "quick_fallback",
            "success": True
        }

    return {
        "error": "All AI backends unavailable",
        "success": False
    }


@mcp.tool()
async def cih_analyze(prompt: str) -> dict:
    """
    작업 분석 - 프롬프트를 분석하여 최적의 AI 조합 추천

    Args:
        prompt: 분석할 사용자 질문

    Returns:
        작업 유형, 복잡도, 추천 AI 목록
    """
    analysis = analyze_task(prompt)
    return {
        "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,
        "task_type": analysis["task_type"].value,
        "complexity": analysis["complexity"],
        "complexity_level": "low" if analysis["complexity"] < 0.3 else "medium" if analysis["complexity"] < 0.7 else "high",
        "suggested_ais": analysis["suggested_ais"],
        "requires_discussion": analysis["requires_discussion"],
        "recommendation": (
            "단일 AI 빠른 응답 (cih_quick)" if not analysis["requires_discussion"]
            else "멀티 AI 토론 (cih_discuss)"
        )
    }


@mcp.tool()
async def cih_discuss(
    prompt: str,
    ais: Optional[list[str]] = None,
    max_rounds: int = 2,
    include_synthesis: bool = True,
) -> dict:
    """
    멀티 AI 토론 - 여러 AI의 의견을 수집하고 종합

    Args:
        prompt: 토론 주제/질문
        ais: 참여할 AI 목록 (기본: 자동 선택)
        max_rounds: 최대 토론 라운드 (기본: 2)
        include_synthesis: 종합 결과 포함 여부

    Returns:
        각 AI의 응답과 종합 결과
    """
    # 작업 분석
    analysis = analyze_task(prompt)

    # AI 선택
    if ais is None:
        ais = analysis["suggested_ais"]

    # 간단한 질문은 빠른 응답으로 리다이렉트
    if not analysis["requires_discussion"]:
        quick_result = await cih_quick(prompt)
        quick_result["note"] = "Simple question - redirected to quick response"
        return quick_result

    responses = {}
    errors = []

    # 병렬로 AI 호출
    async def call_ai(ai_name: str):
        if ai_name == "claude":
            result = run_cli_safe([CLAUDE_CMD, "-p", prompt], timeout=90)
            if result["success"]:
                return ai_name, {"response": result["stdout"], "success": True}
            return ai_name, {"error": result.get("error", "Unknown"), "success": False}

        elif ai_name == "codex":
            result = run_cli_safe([CODEX_CMD, "exec", "--skip-git-repo-check", prompt], timeout=90)
            if result["success"]:
                return ai_name, {"response": result["stdout"], "success": True}
            return ai_name, {"error": result.get("error", "Unknown"), "success": False}

        elif ai_name == "gemini":
            result = run_cli_safe([GEMINI_CMD, prompt], timeout=90)
            if result["success"]:
                return ai_name, {"response": result["stdout"], "success": True}
            return ai_name, {"error": result.get("error", "Unknown"), "success": False}

        elif ai_name == "ollama":
            return ai_name, await call_ollama(prompt)

        elif ai_name == "copilot":
            result = run_cli_safe([COPILOT_CMD, "explain", prompt], timeout=90)
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

    # 결과 구성
    output = {
        "prompt": prompt,
        "task_type": analysis["task_type"].value,
        "complexity": analysis["complexity"],
        "participating_ais": ais,
        "responses": responses,
        "success": any(r.get("success") for r in responses.values()),
    }

    if errors:
        output["errors"] = errors

    # 종합 (Claude로 요청)
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
                output["synthesis"] = {
                    "summary": synthesis_result["stdout"],
                    "synthesized_by": "claude"
                }

    return output


@mcp.tool()
async def cih_compare(
    prompt: str,
    ais: list[str] = ["claude", "codex", "gemini"],
) -> dict:
    """
    AI 응답 비교 - 동일 질문에 대한 여러 AI 응답을 나란히 비교

    Args:
        prompt: 비교할 질문
        ais: 비교할 AI 목록

    Returns:
        각 AI 응답과 비교 분석
    """
    result = await cih_discuss(prompt, ais=ais, include_synthesis=True)
    result["mode"] = "comparison"
    return result


@mcp.tool()
def cih_status() -> dict:
    """
    CLI-CIH 상태 확인 - 사용 가능한 AI와 연결 상태

    Returns:
        각 AI의 가용성 정보
    """
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
    import httpx
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

    available_count = sum(1 for s in status.values() if s.get("available"))
    status["summary"] = {
        "total_ais": len(status) - 1,  # Exclude summary itself
        "available": available_count,
        "ready": available_count >= 2,
    }

    return status


@mcp.tool()
def cih_smart(
    prompt: str,
    task_type: Optional[Literal["code", "debug", "design", "research", "explain", "general"]] = None,
) -> dict:
    """
    스마트 라우팅 - 작업 유형에 따라 최적 AI 자동 선택

    Args:
        prompt: 사용자 질문
        task_type: 작업 유형 (생략시 자동 분석)

    Returns:
        선택된 AI의 응답
    """
    # 작업 유형 결정
    if task_type is None:
        analysis = analyze_task(prompt)
        task_type = analysis["task_type"].value

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
        result = run_cli_safe([CODEX_CMD, "exec", "--skip-git-repo-check", prompt], timeout=90)
    elif ai == "gemini":
        result = run_cli_safe([GEMINI_CMD, prompt], timeout=90)
    else:  # claude
        result = run_cli_safe([CLAUDE_CMD, "-p", prompt], timeout=90)

    if result["success"]:
        return {
            "response": result["stdout"],
            "selected_ai": ai,
            "task_type": task_type,
            "routing_reason": reason,
            "success": True,
        }

    return {
        "error": result.get("error", "Unknown error"),
        "selected_ai": ai,
        "task_type": task_type,
        "success": False,
    }


# ═══════════════════════════════════════════════
# Docker Gateway MCP Tools
# ═══════════════════════════════════════════════

@mcp.tool()
async def cih_gateway_status() -> dict:
    """
    Docker MCP Gateway 상태 확인

    Returns:
        Gateway 연결 상태 및 사용 가능한 서버 수
    """
    if not DOCKER_GATEWAY_ENABLED:
        return {
            "enabled": False,
            "message": "Docker Gateway가 비활성화되어 있습니다 (DOCKER_GATEWAY_ENABLED=false)"
        }

    client = get_gateway_client()
    health = await client.check_health()

    if not health["success"]:
        return {
            "enabled": True,
            "connected": False,
            "gateway_url": DOCKER_GATEWAY_URL,
            "error": health.get("error", "Connection failed")
        }

    servers = await client.list_servers()
    server_count = len(servers.get("servers", [])) if servers["success"] else 0

    return {
        "enabled": True,
        "connected": True,
        "gateway_url": DOCKER_GATEWAY_URL,
        "server_count": server_count,
        "status": health.get("status")
    }


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
    if not DOCKER_GATEWAY_ENABLED:
        return {"success": False, "error": "Docker Gateway disabled"}

    client = get_gateway_client()
    return await client.find_server(query, limit)


@mcp.tool()
async def cih_gateway_tools(server: str) -> dict:
    """
    Docker Gateway 서버의 도구 목록 조회

    Args:
        server: MCP 서버 이름

    Returns:
        해당 서버의 사용 가능한 도구 목록
    """
    if not DOCKER_GATEWAY_ENABLED:
        return {"success": False, "error": "Docker Gateway disabled"}

    client = get_gateway_client()
    return await client.get_server_tools(server)


@mcp.tool()
async def cih_gateway_exec(
    server: str,
    tool: str,
    arguments: Optional[dict[str, Any]] = None
) -> dict:
    """
    Docker Gateway를 통해 MCP 도구 실행

    Args:
        server: MCP 서버 이름
        tool: 도구 이름
        arguments: 도구 인자 (선택사항)

    Returns:
        도구 실행 결과
    """
    if not DOCKER_GATEWAY_ENABLED:
        return {"success": False, "error": "Docker Gateway disabled"}

    client = get_gateway_client()
    return await client.call_tool(server, tool, arguments)


@mcp.tool()
async def cih_gateway_multi_exec(
    calls: list[dict[str, Any]]
) -> dict:
    """
    Docker Gateway를 통해 여러 MCP 도구 병렬 실행

    Args:
        calls: 호출 목록 [{"server": str, "tool": str, "arguments": dict}, ...]

    Returns:
        모든 도구 실행 결과
    """
    if not DOCKER_GATEWAY_ENABLED:
        return {"success": False, "error": "Docker Gateway disabled"}

    client = get_gateway_client()

    async def exec_call(call_spec: dict):
        server = call_spec.get("server", "")
        tool = call_spec.get("tool", "")
        args = call_spec.get("arguments", {})
        result = await client.call_tool(server, tool, args)
        return {"server": server, "tool": tool, **result}

    tasks = [exec_call(call) for call in calls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed.append({
                "server": calls[i].get("server"),
                "tool": calls[i].get("tool"),
                "success": False,
                "error": str(result)
            })
        else:
            processed.append(result)

    return {
        "success": any(r.get("success") for r in processed),
        "total": len(calls),
        "succeeded": sum(1 for r in processed if r.get("success")),
        "results": processed
    }


# ═══════════════════════════════════════════════
# 서버 실행
# ═══════════════════════════════════════════════

def run_server():
    """MCP 서버 실행."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
