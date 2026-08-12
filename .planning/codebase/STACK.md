# Technology Stack

**Analysis Date:** 2026-08-12

## Languages

**Primary:**
- TypeScript 5.6 - Frontend (React components, app logic)
- Python 3.12 - Backend (FastAPI application, telemetry simulation, database)

**Secondary:**
- JavaScript (minimal, package configuration)
- SQL - SQLite schema definitions in `backend/app/db/schema.py`

## Runtime

**Environment:**
- Node.js 20 (LTS) - Frontend build and dev server
- Python 3.12 - Backend runtime

**Package Manager:**
- npm - Frontend dependencies and scripts
- uv - Python package manager for backend (modern, fast, reproducible lockfiles)
  - Lockfile: `backend/uv.lock` (present, checked in)

## Frameworks

**Core:**
- Next.js 15.0.0 - Frontend framework with TypeScript support, SSR/SSG, static export via `output: "export"`
- FastAPI 0.115.0+ - Backend REST API framework, async/await native, automatic OpenAPI docs
- Uvicorn 0.32.0+ - ASGI server for FastAPI, production-ready

**Testing:**
- pytest 8.3.0+ - Backend unit/integration tests
- pytest-asyncio 0.24.0+ - Async test support for FastAPI
- pytest-cov 5.0.0+ - Coverage reporting
- Vitest 2.1.0 - Frontend unit tests (Vite-based)
- Playwright 1.48.0 - E2E tests, browser automation

**Build/Dev:**
- Tailwind CSS 3.4.0 - Utility-first CSS framework for ops-console styling
- PostCSS 8.4.0 - CSS processing pipeline
- Autoprefixer 10.4.0 - Browser vendor prefix injection
- Ruff 0.7.0+ - Python linter and formatter

## Key Dependencies

**Critical:**
- httpx 0.27.0+ - Async HTTP client used by MAVLink gateway telemetry source (`backend/app/telemetry/mavlink_gateway.py`)
- numpy 2.0.0+ - Numeric computations for fleet telemetry simulator; Ornstein-Uhlenbeck correlated drain model with Cholesky decomposition (`backend/app/telemetry/simulator.py`)
- recharts 2.13.0 - React charting library for fleet visualizations (battery trends, energy budget, fleet heatmap)

**Infrastructure:**
- rich 13.0.0+ - Console formatting and logging for backend
- react-dom 18.3.0 - React DOM rendering for frontend
- Testing Library React 16.0.0+ - React component testing utilities

## Configuration

**Environment:**
- Variables read from `.env` file at project root (not in repo, see `.env.example`)
- Critical var: `OPENROUTER_API_KEY` - OpenRouter API key for future LLM integration (planned)
- Optional var: `MAVLINK_GATEWAY_URL` - URL of MAVLink telemetry gateway (if unset, uses built-in simulator)
- Optional var: `LLM_MOCK` - Set to "true" for deterministic mock LLM responses (testing only)
- Optional var: `DATABASE_PATH` - Override SQLite database location (defaults to `database/skyfleet.db`)

**Frontend Build:**
- `frontend/next.config.js` - Static export output, unoptimized images
- `frontend/tsconfig.json` - ES2017 target, strict mode, path alias `@/*` → `./src/*`
- `frontend/tailwind.config.ts` - Dark theme colors (ops.bg, ops.panel, ops.amber, ops.teal, ops.signal), flash animations for battery state changes

**Backend Configuration:**
- `backend/pyproject.toml` - Project metadata, dependencies, dev tools config
  - Pytest configuration: testpaths=`tests`, python_files=`test_*.py`
  - Ruff config: line-length=100, target Python 3.12, lints for E/F/I/N/W rules
  - Coverage config: source=`app`, excludes tests and non-essential code

## Database

**Primary:**
- SQLite - Single-file database at `database/skyfleet.db` (volume-mounted in Docker, gitignored)
- Connection: Python `sqlite3` standard library via `backend/app/db/connection.py`
- Mode: WAL (Write-Ahead Logging) for concurrent reads, foreign keys enabled
- Initialization: Lazy schema creation and seeding on first request (no manual migrations)
- Tables: `operator_profile`, `fleet_roster`, `missions`, `mission_log`, `budget_snapshots`, `chat_messages`

## Platform Requirements

**Development:**
- Node.js 20+ (npm bundled)
- Python 3.12+ (uv installed as dependency)
- Docker 20+ (for containerized deployment)
- Modern browser with EventSource API (Chrome, Firefox, Safari, Edge)

**Production:**
- Docker container, single image serves frontend static export + backend API
- Single port exposure: 8000
- Volume mount: `database/` directory for SQLite persistence
- Environment file: `.env` with `OPENROUTER_API_KEY` and optional `MAVLINK_GATEWAY_URL`

## Build Pipeline

**Frontend:**
- `npm run build` → Next.js static export to `frontend/out/`
- Included in Docker via multi-stage: Node 20 → build stage copies output to Python image as `static/`

**Backend:**
- `uv sync` → Install dependencies from lockfile to `.venv/`
- No compilation step; Python runs directly via `uv run uvicorn`

**Docker Multi-Stage:**
- Stage 1: Node 20-slim, build Next.js static export
- Stage 2: Python 3.12-slim, install uv, sync backend deps, copy static output, expose 8000

## Performance Characteristics

**Telemetry Simulation:**
- numpy-based mean-reverting drain model updates at ~500ms intervals
- Cholesky decomposition for correlated squadron battery moves
- In-memory cache holds latest reading per drone, no DB writes per update (snapshots periodic)

**SSE Streaming:**
- Server pushes telemetry to all connected clients at ~500ms cadence
- EventSource handles reconnection automatically
- Stateless streaming; no session memory

**Database:**
- SQLite with single async lock serializes writes; no bottleneck at current scale
- Transactions atomic for mission dispatch (energy budget, one-per-drone constraint)
- Indexes on drone_id, recorded_at, created_at for query efficiency

---

*Stack analysis: 2026-08-12*
