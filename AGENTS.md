# CLAUDE.md - CLI Intelligence Hub
<!-- 전역: ~/.claude/CLAUDE.md | 루트: ~/CLAUDE.md -->

## 🤖 권장 에이전트

| 작업 | 에이전트 |
|------|----------|
| AI 통합 설계 | orchestrator (opus) |
| 라우팅/어댑터 | backend-dev (sonnet) |
| API 설계 | api-designer (opus) |

## Workflow

**새 AI 백엔드**: api-designer(인터페이스) → backend-dev(어댑터) → test-runner → security-auditor(API 키)
**라우팅 개선**: orchestrator(전략) → perf-analyst(분석) → backend-dev(구현)

## 🔍 Forensics Tools (전역 사용 가능)

**디지털 포렌식 도구** - 메모리, 펌웨어, 네트워크 분석
- **설치 완료**: Volatility3, Binwalk, Wireshark/tshark
- **도구 가이드**: `~/.claude/forensics/FORENSICS_TOOLS.md`
- **자동 분석**: forensics-expert agent (키워드: "메모리 분석", "펌웨어 분석", "패킷 분석")

**사용 예시**:
```bash
# Volatility3 - 메모리 포렌식
vol -f memory.dump windows.pslist

# Binwalk - 펌웨어 분석
binwalk -e firmware.bin

# tshark - 네트워크 분석
tshark -r capture.pcap -Y "http"
```

## 🤖 AI CLI 설정

### Cloud CLI 4개 (항상 병렬)
```bash
# 1. Claude (현재 세션)

# 2. Gemini (빠른 실행 - MCP 비활성화)
gemini-fast "prompt"

# 3. Codex (trusted dir 체크 우회)
codex exec --skip-git-repo-check "prompt"

# 4. Copilot
copilot -p "prompt"
```

### Ollama Cloud 4개 (S-Tier 우선)
```bash
ollama run mistral-large-3:675b-cloud "prompt" &
ollama run kimi-k2:1t-cloud "prompt" &
ollama run deepseek-v3.1:671b-cloud "prompt" &
ollama run cogito-2.1:671b-cloud "prompt" &
wait
```

### Ollama Local 2개 (작업별 선택)
```bash
ollama run codellama:70b "prompt" &
ollama run llama3.3:latest "prompt" &
wait
```

**참조**: `~/.local/bin/ai-cli/AI_CLI_RULES.md`
**전역 설정**: `~/.claude/CLAUDE.md`
