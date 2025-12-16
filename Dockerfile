# CLI-CIH MCP Server Docker Image
# Multi-AI Discussion Orchestrator

FROM python:3.11-slim

LABEL maintainer="CLI-CIH Team"
LABEL description="Multi-AI Discussion Orchestrator MCP Server"
LABEL version="1.0.0"

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Docker Gateway 기본 설정
ENV DOCKER_GATEWAY_URL=http://host.docker.internal:8811 \
    DOCKER_GATEWAY_ENABLED=true

# 작업 디렉토리
WORKDIR /app

# 의존성 파일 복사
COPY pyproject.toml README.md ./
COPY src/ ./src/

# 패키지 설치
RUN pip install --no-cache-dir .

# MCP 서버 포트 (stdio 모드에서는 사용 안함)
EXPOSE 8000

# 헬스체크 (선택적 HTTP 모드용)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import cli_cih; print('OK')" || exit 1

# 기본 실행 명령 (MCP stdio 모드)
ENTRYPOINT ["python", "-m", "cli_cih.mcp.server"]
