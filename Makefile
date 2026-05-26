.DEFAULT_GOAL := help
.PHONY: help sync dev test lint fmt up down

help:  ## 명령 목록 보기
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-7s\033[0m %s\n", $$1, $$2}'

sync:  ## 의존성 설치 (uv sync)
	uv sync

dev:  ## 로컬 서버 실행 (hot-reload, :8000)
	uv run uvicorn app.main:app --reload --port 8000

test:  ## 테스트 (pytest)
	uv run pytest

lint:  ## 린트 + 포맷 검사
	uv run ruff check . && uv run ruff format --check .

fmt:  ## 포맷·자동수정 적용
	uv run ruff format . && uv run ruff check --fix .

up:  ## 로컬 Redis 띄우기 (docker)
	docker compose up -d redis

down:  ## 로컬 스택 중지
	docker compose down
