# CLAUDE.md v6.3.0 (Q&A + Error Handling + Agent Routing)

## Language Protocol
- Internal processing: English | User output: **Korean only**
- Exceptions: code blocks, technical terms, commands

## Mode Selection (Self-determine, never ask)
| Trigger | Mode | Action |
|---------|------|--------|
| Keywords: analyze/review/debug/fix/분석/리뷰 | PRECISION | Full Q&A Loop → AI CLI parallel |
| File path (no trigger keyword) | SIMPLE | Q&A Loop → parallel tools |
| Questions/greetings only | CONVERSATION | Respond without tools |
| `/pipeline` or `l` | PIPELINE | Auto-chaining: 기획→개발→테스트→리뷰 |

### Pipeline Mode (prompt once before execution)
```
[파이프라인 모드]
1. AUTO - Delegate to Task agent, execute until completion without interruption
2. STEP - Confirm after each phase
```
- **AUTO**: Delegate entire pipeline to Task(a:pipeline) agent → auto-complete internally → return only final result
- **STEP**: Existing method (confirm at each phase)
  - Confirmation prompt: `Phase N 완료. 다음 진행? (y/n/s)`
  - `y`: 다음 Phase 진행
  - `n`: 현재 Phase 수정 요청
  - `s`: 파이프라인 중단
- **Intervention**: "stop/멈춰/중단" → abort agent → report state

### Pipeline Auto-Suggestion (complexity detection)
Automatically add pipeline option to Q&A when:
- "만들어줘" + 3 or more features
- Project/system creation request
- Tasks expecting multiple file generation

## Q&A Loop / Protocol (SIMPLE/PRECISION modes)
**MANDATORY**: No modifying tools (Write/Edit/Bash) before "p"
- ✅ **허용**: Read, Grep, Glob (컨텍스트 수집)
- ❌ **금지**: Write, Edit, Bash (수정 작업)
```
Required: PURPOSE / SCOPE / CONTEXT
Format: [질문 N] + options (1-5) + commands (p/c/a/b/x/l)
```

### Commands
| Shortcut | Action |
|----------|--------|
| `p` | 진행 (Proceed) |
| `c` | 취소 (Cancel) |
| `a` | 전체 기본값 적용 |
| `b` | 이전으로 |
| `x` | 종료 |
| `l` | **파이프라인 모드** → 자동 체이닝 실행 |

Display format:
```
(p:진행 / c:취소 / a:전체적용 / b:이전 / x:종료 / l:파이프라인)
```

### Pipeline Option Display (when complexity is high)
```
[질문 N] 작업 방식
1. 단계별 진행 (일반)
2. 파이프라인 (기획→개발→테스트→리뷰 자동) ← 권장
```

## Prohibited Actions
- Screenshot/browser automation without explicit request
- Background Bash processes > 2
- Kill Docker/Ollama/MCP servers
- Skip Q&A Loop for SIMPLE/PRECISION modes

## PRECISION Mode: AI CLI 3-Tier (after Q&A)
```bash
# Tier1 Cloud CLI 5개 (Parallel - Required)
#   Claude(현재), Gemini, Codex, Copilot, GLM
#   → cih_compare로 병렬 실행

# Tier2 Ollama Cloud S-Tier 4개 (Parallel - Required)
#   mistral-large-3:675b-cloud, kimi-k2:1t-cloud
#   deepseek-v3.1:671b-cloud, cogito-2.1:671b-cloud
#   → MCP ollama 병렬 실행

# Tier3 Local 2~4개 (Sequential - Optional)
#   llama3.3, deepseek-r1:70b, ingu627/exaone4.0:32b(한국어)
#   → VRAM 사용하므로 순차 실행

# 코드 Task 추가: qwen3-coder:480b-cloud, codellama:70b
# Total: Cloud 5 + Ollama Cloud 4 = 9개 (Required)
#        + Local 2~4개 (Optional) = 11~13개
```

### 🔄 실행 순서 (Execution Order)
```
1단계: Cloud CLI 5개 → cih_compare (Parallel)
2단계: Ollama Cloud 4개 → MCP ollama (Parallel)
3단계: Ollama 로컬 → 순차 실행 (VRAM 체크 필수)
       → nvidia-smi --query-gpu=memory.free
       → 70B: 40GB / 32B: 20GB 필요
```

## TDD Workflow
RED (failing test) → GREEN (minimal code) → REFACTOR

## Stop Triggers
"stop", "멈춰", "중단", "cancel" → Immediately halt all tool calls

## Error Handling
| 상황 | 대응 |
|------|------|
| AI CLI 응답 실패 | 해당 AI 스킵, 나머지로 진행 |
| MCP 서버 연결 실패 | 재시도 1회 → 실패 시 사용자 알림 |
| Tool 호출 실패 | 재시도 2회 → 대안 방법 시도 |
| 전체 실패 | 현재까지 결과 보고 + 다음 단계 제안 |

## MCP Servers (cli-cih)

### Tools
| Tool | 용도 | 비고 |
|------|------|------|
| `cih_quick` | 단일 AI 빠른 응답 | default: ollama |
| `cih_compare` | 멀티 AI 비교 | 병렬 실행 |
| `cih_discuss` | 멀티 AI 토론 | 합성 포함 |
| `cih_status` | AI 상태 확인 | 사용 가능 체크 |
| `cih_smart` | 태스크별 자동 라우팅 | code/debug/research |
| `cih_models` | 모델 목록 조회 | - |

### 명령어 형식
```bash
# Cloud CLI (cih_compare로 병렬)
gemini -p "prompt"
codex exec "prompt" --skip-git-repo-check
copilot -p "prompt" --allow-all  # Node 24 필요
cih glm "prompt"

# Ollama Cloud (MCP ollama)
ollama run model:tag "prompt"
```

## References
- AI CLI: `~/.local/bin/ai-cli/AI_CLI_RULES.md`
- Agents: `~/.claude/agents/` (라우팅: `ROUTING.md`)
- Skills: `~/.claude/skills/`
- Pipeline: `~/.claude/pipeline/` (state, workspace, templates, history)
