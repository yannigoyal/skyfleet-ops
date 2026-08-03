# syntax=docker/dockerfile:1

# --- Stage 1: build the Next.js static export ---
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python backend + bundled static frontend ---
FROM python:3.12-slim AS backend
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv sync --no-dev --no-install-project

COPY backend/ ./
RUN uv sync --no-dev

# Next.js `output: 'export'` writes to frontend/out — bundle it as static/
COPY --from=frontend-build /frontend/out ./static

RUN mkdir -p /app/database

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
