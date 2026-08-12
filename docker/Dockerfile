# syntax=docker/dockerfile:1

# --- Stage 1: build the Next.js static export ---
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python backend + bundled static frontend ---
FROM python:3.12-slim AS backend
WORKDIR /app

# curl is used by the container healthcheck (tests/docker-compose.test.yml)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv sync --no-dev --no-install-project

COPY backend/ ./
RUN uv sync --no-dev

# Next.js `output: 'export'` writes to frontend/out — bundle it as static/
COPY --from=frontend-build /frontend/out ./static

RUN mkdir -p /app/database

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
  CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
