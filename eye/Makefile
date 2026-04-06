.PHONY: dev api frontend docker clean

# 로컬 개발 (API + Frontend 동시 실행)
dev: api frontend

# FastAPI 서버 (port 8000)
api:
	uvicorn api.server:app --reload --port 8000

# Next.js 개발 서버 (port 3000)
frontend:
	cd frontend && npm run dev

# Docker Compose 전체 실행
docker:
	docker compose up --build -d

# 정리
clean:
	docker compose down -v
