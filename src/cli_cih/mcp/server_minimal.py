#!/usr/bin/env python3
"""CLI-CIH MCP Server - External AI Helper (Claude handles itself)"""

import asyncio
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from fastmcp import FastMCP

from cli_cih.mcp.exceptions import (
    MCPAdapterError,
    MCPTimeoutError,
    MCPValidationError,
)
from cli_cih.orchestration.task_analyzer import TaskAnalyzer

logger = logging.getLogger(__name__)

mcp = FastMCP("cli-cih", instructions="External AI orchestrator (Codex/Gemini/Ollama/Copilot)")

_task_analyzer = TaskAnalyzer()

def get_cli_path(name: str) -> str:
    env_key = f"{name.upper()}_BIN"
    env_path = os.getenv(env_key)
    if env_path:
        return env_path
    path = shutil.which(name)
    if path:
        return path
    return name

# External AI CLIs only (Claude is handled by current session)
GEMINI_CMD = get_cli_path("gemini")
CODEX_CMD = get_cli_path("codex")
COPILOT_CMD = get_cli_path("copilot")
OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")

# GLM (Z.AI) configuration - Anthropic-compatible API
ZAI_API_KEY = os.getenv("ZAI_API_KEY") or os.getenv("GLM_API_KEY")
ZAI_BASE_URL = os.getenv("ZAI_BASE_URL", "https://api.z.ai/api/anthropic/v1")
GLM_MODEL = os.getenv("GLM_MODEL", "claude-3-5-sonnet-20241022")  # Z.AI maps to GLM-4.7

KOREAN_SYSTEM_PROMPT = "당신은 한국어로 응답하는 AI 어시스턴트입니다."
VALID_AI_NAMES = {"codex", "gemini", "ollama", "copilot", "glm"}  # No claude - handled by session
ALLOWED_COMMANDS: dict[str, set[str]] = {
    "codex": {"exec", "--skip-git-repo-check", "--version", "--help"},
    "gemini": {"-p", "--version", "--help"},
    "copilot": {"-p", "--allow-all", "--version", "--help"},
}

def validate_command(command: list[str]) -> bool:
    if not command:
        return False
    base_cmd = command[0].split("/")[-1]
    if base_cmd not in ALLOWED_COMMANDS:
        return False
    allowed_args = ALLOWED_COMMANDS[base_cmd]
    for arg in command[1:]:
        if arg.startswith("-") and arg not in allowed_args:
            return False
    return True

@dataclass
class MCPResponse:
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"success": self.success, "data": self.data, "error": self.error, "metadata": self.metadata or {}}

def make_response(success: bool, data: dict[str, Any] | None = None, error: str | None = None,
                  error_type: str | None = None, duration_ms: int | None = None, ai_used: list[str] | None = None) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if duration_ms is not None:
        metadata["duration_ms"] = duration_ms
    if ai_used:
        metadata["ai_used"] = ai_used
    if error_type:
        metadata["error_type"] = error_type
    return MCPResponse(success=success, data=data, error=error, metadata=metadata if metadata else None).to_dict()

async def run_cli_async(command: list[str], timeout: int = 120, skip_validation: bool = False) -> dict[str, Any]:
    if not skip_validation and not validate_command(command):
        raise MCPValidationError(f"Command not allowed: {command[0]}")
    try:
        env = os.environ.copy()
        env["TERM"] = "dumb"
        env["NO_COLOR"] = "1"
        env["CI"] = "1"
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            return {"stdout": stdout.decode().strip() if stdout else "", "stderr": stderr.decode().strip() if stderr else "", "returncode": process.returncode, "success": process.returncode == 0}
        except asyncio.TimeoutError as e:
            process.kill()
            await process.wait()
            raise MCPTimeoutError(f"Timeout ({timeout}s)") from e
    except FileNotFoundError as e:
        raise MCPAdapterError(f"Command not found: {command[0]}") from e
    except (MCPValidationError, MCPTimeoutError):
        raise
    except Exception as e:
        raise MCPAdapterError(f"Execution error: {e}") from e

async def call_ollama(prompt: str, model: str = "llama3.1:70b") -> dict[str, Any]:
    url = f"{OLLAMA_ENDPOINT}/api/chat"
    payload = {"model": model, "messages": [{"role": "system", "content": KOREAN_SYSTEM_PROMPT}, {"role": "user", "content": prompt}], "stream": False}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                data = response.json()
                return {"response": data.get("message", {}).get("content", ""), "model": model, "success": True, "source": "ollama"}
            return {"error": f"HTTP {response.status_code}", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}

async def call_glm(prompt: str, model: str | None = None) -> dict[str, Any]:
    """Call Z.AI GLM API (Anthropic-compatible)."""
    if not ZAI_API_KEY:
        return {"error": "ZAI_API_KEY not set", "success": False}

    model = model or GLM_MODEL
    url = f"{ZAI_BASE_URL}/messages"
    headers = {
        "x-api-key": ZAI_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "max_tokens": 4096,
        "system": KOREAN_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                content = data.get("content", [])
                if content and len(content) > 0:
                    text = content[0].get("text", "")
                    return {"response": text, "model": "GLM-4.7", "success": True, "source": "glm"}
                return {"error": "No response content", "success": False}
            elif response.status_code == 401:
                return {"error": "GLM API authentication failed", "success": False}
            elif response.status_code == 429:
                return {"error": "GLM API rate limited", "success": False}
            return {"error": f"HTTP {response.status_code}: {response.text}", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}

# ═══════════════════════════════════════════════
# MCP Tools - 7 tools only
# ═══════════════════════════════════════════════

@mcp.tool()
async def cih_quick(prompt: str, ai: str = "ollama", timeout: int = 60) -> dict[str, Any]:
    """Quick external AI response (codex/gemini/ollama/copilot/glm)"""
    start = time.time()
    try:
        if not prompt or not prompt.strip():
            raise MCPValidationError("Empty prompt")
        if ai not in VALID_AI_NAMES:
            raise MCPValidationError(f"Invalid AI: {ai}. Use: codex, gemini, ollama, copilot, glm")
        if ai == "codex":
            result = await run_cli_async([CODEX_CMD, "exec", "--skip-git-repo-check", prompt], timeout=timeout)
        elif ai == "gemini":
            result = await run_cli_async([GEMINI_CMD, prompt], timeout=timeout)
        elif ai == "ollama":
            result = await call_ollama(prompt)
        elif ai == "copilot":
            result = await run_cli_async([COPILOT_CMD, "-p", prompt, "--allow-all"], timeout=timeout)
        elif ai == "glm":
            result = await call_glm(prompt)
        else:
            raise MCPValidationError(f"Unknown AI: {ai}")
        duration = int((time.time() - start) * 1000)
        if result.get("success"):
            return make_response(True, data={"response": result.get("stdout") or result.get("response"), "ai": ai}, duration_ms=duration, ai_used=[ai])
        if ai != "ollama":
            ollama_result = await call_ollama(prompt)
            if ollama_result["success"]:
                return make_response(True, data={"response": ollama_result["response"], "ai": "ollama", "fallback": True}, duration_ms=int((time.time() - start) * 1000), ai_used=[ai, "ollama"])
        return make_response(False, error=result.get("error", "Unknown error"), error_type="adapter")
    except MCPValidationError as e:
        return make_response(False, error=str(e), error_type="validation")
    except MCPTimeoutError as e:
        return make_response(False, error=str(e), error_type="timeout")
    except MCPAdapterError as e:
        return make_response(False, error=str(e), error_type="adapter")
    except Exception as e:
        return make_response(False, error=f"Internal error: {type(e).__name__}", error_type="internal")

@mcp.tool()
async def cih_analyze(prompt: str) -> dict[str, Any]:
    """Analyze task"""
    start = time.time()
    try:
        task = _task_analyzer.analyze(prompt)
        data = {"prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt, "task_type": task.task_type.value, "complexity": round(task.complexity, 2), "requires_multi_ai": task.requires_multi_ai, "suggested_rounds": task.suggested_rounds}
        return make_response(True, data=data, duration_ms=int((time.time() - start) * 1000))
    except Exception as e:
        return make_response(False, error=str(e))

async def _discuss_impl(prompt: str, ais: list[str], include_synthesis: bool = True, timeout: int = 90) -> dict[str, Any]:
    """Internal implementation for multi-AI discussion (shared by cih_discuss and cih_compare)"""
    start = time.time()
    try:
        task = _task_analyzer.analyze(prompt)
        # Filter out claude if accidentally passed
        ais = [ai for ai in ais if ai in VALID_AI_NAMES]
        if not ais:
            ais = ["ollama"]
        responses: dict[str, dict[str, Any]] = {}
        errors: list[str] = []
        async def call_ai(ai_name: str) -> tuple[str, dict[str, Any]]:
            if ai_name == "codex":
                result = await run_cli_async([CODEX_CMD, "exec", "--skip-git-repo-check", prompt], timeout=timeout)
            elif ai_name == "gemini":
                result = await run_cli_async([GEMINI_CMD, prompt], timeout=timeout)
            elif ai_name == "ollama":
                return ai_name, await call_ollama(prompt)
            elif ai_name == "copilot":
                result = await run_cli_async([COPILOT_CMD, "-p", prompt, "--allow-all"], timeout=timeout)
            elif ai_name == "glm":
                return ai_name, await call_glm(prompt)
            else:
                return ai_name, {"error": f"Unknown AI: {ai_name}", "success": False}
            if result["success"]:
                return ai_name, {"response": result["stdout"], "success": True}
            return ai_name, {"error": result.get("error", "Unknown"), "success": False}
        tasks = [call_ai(ai) for ai in ais]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, BaseException):
                errors.append(str(result))
            else:
                ai_name_result, response = result
                responses[ai_name_result] = response
        synthesis = None
        if include_synthesis and len([r for r in responses.values() if r.get("success")]) > 1:
            successful_responses = {ai: r["response"] for ai, r in responses.items() if r.get("success") and r.get("response")}
            if successful_responses:
                synthesis_prompt = f"다음 응답들을 요약해주세요 '{prompt}':\n{json.dumps(successful_responses, ensure_ascii=False, indent=2)}"
                synthesis_result = await call_ollama(synthesis_prompt, model="llama3.1:70b")
                if synthesis_result["success"]:
                    synthesis = {"summary": synthesis_result["response"], "synthesized_by": "ollama"}
        duration = int((time.time() - start) * 1000)
        successful_ais = [ai for ai, r in responses.items() if r.get("success")]
        return make_response(success=len(successful_ais) > 0, data={"prompt": prompt, "task_type": task.task_type.value, "responses": responses, "synthesis": synthesis, "errors": errors if errors else None}, duration_ms=duration, ai_used=successful_ais)
    except Exception as e:
        return make_response(False, error=str(e))

@mcp.tool()
async def cih_discuss(prompt: str, ais: list[str] | None = None, max_rounds: int = 2, include_synthesis: bool = True, timeout: int = 90) -> dict[str, Any]:
    """Multi external AI discussion (codex/gemini/ollama/copilot/glm)"""
    if ais is None:
        task = _task_analyzer.analyze(prompt)
        if task.requires_multi_ai:
            ais = ["codex", "gemini", "ollama"][:task.suggested_ai_count]
        else:
            ais = ["ollama"]
    return await _discuss_impl(prompt, ais, include_synthesis, timeout)

@mcp.tool()
async def cih_compare(prompt: str, ais: list[str] | None = None, timeout: int = 90) -> dict[str, Any]:
    """Compare external AI responses (codex/gemini/ollama/copilot/glm)"""
    if ais is None:
        ais = ["codex", "gemini", "copilot", "glm"]
    result = await _discuss_impl(prompt, ais, include_synthesis=True, timeout=timeout)
    if isinstance(result, dict) and result.get("data"):
        result["data"]["mode"] = "comparison"
    return result

@mcp.tool()
async def cih_status() -> dict[str, Any]:
    """Check external AI status (codex/gemini/ollama/copilot/glm)"""
    start = time.time()
    status = {}
    result = await run_cli_async([CODEX_CMD, "--version"], timeout=10)
    status["codex"] = {"available": result["success"], "path": CODEX_CMD}
    result = await run_cli_async([GEMINI_CMD, "--version"], timeout=10)
    status["gemini"] = {"available": result["success"], "path": GEMINI_CMD}
    result = await run_cli_async([COPILOT_CMD, "--version"], timeout=10)
    status["copilot"] = {"available": result["success"], "path": COPILOT_CMD}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
            response = await client.get(f"{OLLAMA_ENDPOINT}/api/tags")
            if response.status_code == 200:
                ollama_models = response.json().get("models", [])
                status["ollama"] = {"available": True, "endpoint": OLLAMA_ENDPOINT, "models": [m.get("name") for m in ollama_models[:5]]}
            else:
                status["ollama"] = {"available": False, "endpoint": OLLAMA_ENDPOINT}
    except Exception:
        status["ollama"] = {"available": False, "endpoint": OLLAMA_ENDPOINT}
    # Check GLM (Z.AI) status
    if ZAI_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
                headers = {"Authorization": f"Bearer {ZAI_API_KEY}"}
                response = await client.get(f"{ZAI_BASE_URL}/models", headers=headers)
                status["glm"] = {"available": response.status_code == 200, "endpoint": ZAI_BASE_URL, "model": GLM_MODEL}
        except Exception:
            status["glm"] = {"available": False, "endpoint": ZAI_BASE_URL, "model": GLM_MODEL}
    else:
        status["glm"] = {"available": False, "error": "ZAI_API_KEY not set"}
    available_count = sum(1 for s in status.values() if isinstance(s, dict) and s.get("available"))
    return make_response(True, data={"ais": status, "summary": {"total_ais": 5, "available": available_count}, "note": "Claude handled by current session"}, duration_ms=int((time.time() - start) * 1000))

@mcp.tool()
async def cih_smart(prompt: str, task_type: Literal["code", "debug", "design", "research", "explain", "general"] | None = None, timeout: int = 90) -> dict[str, Any]:
    """Smart routing to external AI (codex/gemini/ollama/copilot/glm)"""
    start = time.time()
    try:
        if task_type is None:
            task = _task_analyzer.analyze(prompt)
            resolved_task_type = task.task_type.value
        else:
            resolved_task_type = task_type
        # Route to external AIs (Claude handled by current session)
        # GLM is preferred for code tasks if available
        if ZAI_API_KEY:
            routing = {"code": ("glm", "code-glm"), "debug": ("glm", "debug-glm"), "design": ("ollama", "design"), "research": ("gemini", "research"), "explain": ("glm", "explain-glm"), "general": ("ollama", "general")}
        else:
            routing = {"code": ("codex", "code"), "debug": ("codex", "debug"), "design": ("ollama", "design"), "research": ("gemini", "research"), "explain": ("ollama", "explain"), "general": ("ollama", "general")}
        ai, reason = routing.get(resolved_task_type, ("ollama", "default"))
        if ai == "codex":
            result = await run_cli_async([CODEX_CMD, "exec", "--skip-git-repo-check", prompt], timeout=timeout)
        elif ai == "gemini":
            result = await run_cli_async([GEMINI_CMD, prompt], timeout=timeout)
        elif ai == "copilot":
            result = await run_cli_async([COPILOT_CMD, "-p", prompt, "--allow-all"], timeout=timeout)
        elif ai == "glm":
            result = await call_glm(prompt)
        else:  # ollama
            result = await call_ollama(prompt)
        duration = int((time.time() - start) * 1000)
        if result.get("success"):
            return make_response(True, data={"response": result.get("stdout") or result.get("response"), "selected_ai": ai, "task_type": resolved_task_type}, duration_ms=duration, ai_used=[ai])
        return make_response(False, error=result.get("error", "Unknown error"), duration_ms=duration)
    except Exception as e:
        return make_response(False, error=str(e))

@mcp.tool()
async def cih_models() -> dict[str, Any]:
    """List external AI models (codex/gemini/ollama/copilot/glm)"""
    start = time.time()
    try:
        models = {}
        for name, cmd in [("codex", CODEX_CMD), ("gemini", GEMINI_CMD), ("copilot", COPILOT_CMD)]:
            result = await run_cli_async([cmd, "--version"], timeout=10)
            models[name] = {"available": result["success"], "type": "cloud"}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                response = await client.get(f"{OLLAMA_ENDPOINT}/api/tags")
                if response.status_code == 200:
                    ollama_models = response.json().get("models", [])
                    models["ollama"] = {"available": True, "type": "local", "model_count": len(ollama_models)}
                else:
                    models["ollama"] = {"available": False, "type": "local"}
        except Exception:
            models["ollama"] = {"available": False, "type": "local"}
        # Check GLM (Z.AI) availability
        if ZAI_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
                    headers = {"Authorization": f"Bearer {ZAI_API_KEY}"}
                    response = await client.get(f"{ZAI_BASE_URL}/models", headers=headers)
                    models["glm"] = {"available": response.status_code == 200, "type": "cloud", "model": GLM_MODEL, "endpoint": ZAI_BASE_URL}
            except Exception:
                models["glm"] = {"available": False, "type": "cloud", "model": GLM_MODEL}
        else:
            models["glm"] = {"available": False, "type": "cloud", "error": "ZAI_API_KEY not set"}
        return make_response(True, data={"models": models, "note": "Claude handled by current session"}, duration_ms=int((time.time() - start) * 1000))
    except Exception as e:
        return make_response(False, error=str(e))

def run_server() -> None:
    mcp.run(transport="stdio")

if __name__ == "__main__":
    run_server()
