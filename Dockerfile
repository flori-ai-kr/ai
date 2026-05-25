# 멀티스테이지 — uv로 의존성 설치 후 슬림 런타임.
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# 1) 의존성만 먼저 설치(레이어 캐시)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 2) 앱 소스 복사 후 프로젝트 설치
COPY app ./app
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

COPY --from=builder /app/.venv /app/.venv
COPY app ./app

# 비-root 실행 (컨테이너 탈출 시 영향 최소화)
RUN addgroup --system flori && adduser --system --ingroup flori flori
USER flori

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
