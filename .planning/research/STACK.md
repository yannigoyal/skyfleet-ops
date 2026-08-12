# Stack Research

**Domain:** Real-time ops-console web app (FastAPI backend + Next.js static frontend + LLM chat agent)
**Researched:** 2026-08-12
**Confidence:** MEDIUM

Scope note: the telemetry subsystem (simulator, MAVLink client, SSE cache) is already built and out of scope. This covers the four remaining stack decisions: (a) SQLite persistence under FastAPI, (b) LiteLLM → OpenRouter structured-output chat, (c) Next.js static export served by FastAPI, (d) dashboard charting library.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python stdlib `sqlite3` | Python 3.12 stdlib (already in use) | DB driver, no ORM | Already the established pattern in `backend/app/db/connection.py` (WAL mode, lazy init). A single-operator, single-writer demo app has no need for SQLAlchemy/SQLModel's mapping overhead — stdlib `sqlite3` + hand-written SQL keeps schema, seed, and query logic transparent and matches PLAN.md's "lazy initialization, no migration step" design. Changing drivers mid-project would be a regression, not an improvement. |
| LiteLLM | 1.96.x (latest stable; pin a specific patch in `pyproject.toml`, e.g. `>=1.96,<1.97`) | Unified completion() call to OpenRouter | PLAN.md mandates LiteLLM → OpenRouter → `openrouter/openai/gpt-oss-120b` via the `cerebras` skill. LiteLLM is the de facto standard unified LLM SDK (16K+ Context7 code snippets, high reputation) and normalizes OpenAI-style `response_format` across providers. |
| Next.js | 15.x (stay on the 15 line already pinned in `frontend/package.json` at 15.0.0; bump to latest 15.1.x+ patch, do not jump to the newly-released Next 16 mid-project) | Frontend framework, static export | `output: 'export'` is unchanged in behavior across 15.x and 16.x, so there is no functional reason to chase the major version this milestone. Staying on 15.x avoids an unplanned, unbudgeted upgrade risk for a course capstone. |
| Recharts | 3.x is current on npm (`3.10.1`); **recommend staying on 2.13.x already installed**, or deliberately upgrading to 3.x as its own small task before building charts | Line chart, sparklines, treemap heatmap | Recharts is the dominant React-native charting library in 2025/2026 (highest weekly npm downloads of any React chart lib), React-first component API (`<LineChart>`, `<Treemap>`, `<AreaChart>` for sparklines), SVG rendering adequate at this app's data volume (10 drones, ~500ms cadence, capped client-side history). Already a dependency — no new library needed. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pydantic` | 2.x (already a FastAPI dependency) | Structured-output schema definitions | Define the chat response schema (`message`, `missions[]`, `roster_changes[]`) as a Pydantic `BaseModel` and pass it to LiteLLM's `response_format` — LiteLLM converts it to a JSON-schema `response_format` dict automatically via `type_to_response_format_param`. |
| `uuid` (stdlib) | — | Primary keys for `missions`, `mission_log`, `budget_snapshots`, `chat_messages` | PLAN.md schema uses UUID TEXT primary keys everywhere except `operator_profile`/`fleet_roster`. |
| `anyio.to_thread.run_sync` (via FastAPI/Starlette, already a transitive dep) | — | Run blocking `sqlite3` calls off the event loop | Only needed if route handlers are `async def`; if handlers stay `def` (sync), FastAPI already runs them in its threadpool automatically — prefer plain `def` route handlers for DB-touching endpoints to avoid manually threading blocking calls. |
| Recharts `Treemap` + custom `content` render prop | bundled with Recharts | Fleet heatmap (size = mission energy cost, color = battery health) | Recharts' built-in Treemap only auto-colors by category cycling; supply a custom `content` component that maps `battery_pct` to a red→green color scale per cell (see Sources). |
| Recharts `AreaChart`/`LineChart` with no axes/legend, small `height` | bundled with Recharts | Per-drone battery sparklines in the roster grid | A sparkline is just a minimal Recharts line/area chart with `hide` on axes and no tooltip/legend chrome — no separate sparkline library needed. |
| `python-dotenv` (already likely a FastAPI-adjacent dep, or Pydantic Settings) | latest | Load `.env` at project root | Backend already reads `OPENROUTER_API_KEY`, `MAVLINK_GATEWAY_URL`, `LLM_MOCK` from `.env` per PLAN.md §5. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `respx` or `pytest-httpx` (mock HTTP layer) | Mock OpenRouter HTTP calls in pytest without hitting the network | Use alongside the app's own `LLM_MOCK=true` deterministic-response path; `LLM_MOCK` covers E2E/integration, but unit tests of the LiteLLM call site still benefit from an HTTP-level mock to test error handling (malformed JSON, timeouts). |
| `StaticFiles` (Starlette, bundled with FastAPI) | Serve the Next.js static export | `app.mount("/", StaticFiles(directory="static", html=True))` — mount **after** all `/api/*` routers are included, since Starlette matches routes in registration order and a root mount would otherwise shadow API paths. |

## Installation

```bash
# Backend (uv project)
cd backend
uv add litellm
uv add pydantic  # already present via fastapi, but pin explicitly if not
uv add --dev respx pytest-httpx  # HTTP mocking for chat-layer unit tests

# Frontend (no new packages needed — Recharts, Tailwind, Next.js already installed)
# Only if deliberately upgrading Recharts:
cd frontend
npm install recharts@^3
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|--------------------------|
| stdlib `sqlite3`, no ORM | SQLAlchemy Core / `encode/databases` (async query builder, not full ORM) | If the schema grows past ~10 tables or the team wants async DB calls without hand-rolled SQL strings, SQLAlchemy Core gives typed query building while staying ORM-light. Not needed for this 6-table schema. |
| stdlib `sqlite3`, no ORM | SQLModel / full SQLAlchemy ORM | Only if this evolves into a multi-tenant product needing relationship-heavy queries, migrations (Alembic), and object mapping. PLAN.md explicitly rejects this (no auth, no migrations, lazy init only). |
| LiteLLM → OpenRouter | Calling OpenRouter's REST API directly with `httpx` (already a backend dependency) | LiteLLM's main value here is the `response_format`-to-pydantic convenience and provider abstraction; if the OpenRouter/LiteLLM structured-output gap below proves too brittle, a direct `httpx` POST to `https://openrouter.ai/api/v1/chat/completions` with an explicit `response_format` JSON body and `provider: {only: ["Cerebras"]}` is a viable fallback that removes one layer of indirection. PLAN.md mandates the `cerebras` skill/LiteLLM path, so treat this as a contingency, not the primary plan. |
| Next.js 15.x static export | Next.js 16.x | Only adopt 16.x if a future milestone explicitly budgets a Next.js major-version upgrade; `output: 'export'` semantics are stable across both. |
| Recharts | Nivo | If the roadmap later wants more exotic chart types (sunburst, calendar heatmap, chord diagrams) with less custom code — Nivo ships more chart types out of the box but at a larger bundle cost and a more D3-flavored API. Not needed for this app's fixed set of line/treemap/sparkline needs. |
| Recharts | visx | If a future phase needs a fully bespoke, pixel-perfect ATC-style visualization that Recharts' component API can't express — visx (~15KB) gives raw D3+React primitives at the cost of much more code per chart. Overkill for this milestone's four chart types. |
| Recharts | Lightweight Charts (TradingView) | Only if the roadmap adds high-frequency financial-style candlestick/OHLC charts over large tick datasets — it is a canvas-based, extremely fast time-series renderer but has **no treemap primitive** and is a poor fit for the general dashboard layout (missions table, sparklines, heatmap) this app needs. Despite PLAN.md's §10 phrasing ("Lightweight Charts or Recharts"), Recharts is the better fit for the actual required chart mix. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Relying on LiteLLM's automatic `supports_response_schema()` gate for OpenRouter models | LiteLLM's own docs (`docs.litellm.ai/docs/completion/json_mode`) list supported structured-output providers as OpenAI, Azure OpenAI, xAI, Google AI Studio/Vertex, Bedrock, Anthropic, Groq, Ollama, Databricks — **OpenRouter is not on that list**, and a community-reported LiteLLM issue shows `supports_response_schema()` returning `False` for OpenRouter models, which can cause `response_format` to be silently dropped so the model free-forms JSON (or prose) instead of guaranteed schema-conformant output. | Pass `response_format` as an explicit dict (`{"type": "json_schema", "json_schema": {...}, "strict": true}`) rather than relying purely on LiteLLM's pydantic auto-conversion+support-check, and additionally set OpenRouter provider routing (`extra_body={"provider": {"only": ["Cerebras"], "require_parameters": true}}`) so the request only routes to an endpoint that actually honors `response_format`. Always parse defensively (`json.loads` in a try/except) and treat malformed output as a recoverable chat-layer error per PLAN.md's mock-mode/error-handling requirements — do not assume schema compliance is guaranteed. |
| SQLAlchemy/SQLModel ORM for this schema | Adds mapping/session/migration machinery (Alembic) this single-operator, 6-table, lazy-init schema doesn't need; contradicts the already-established `backend/app/db/connection.py` pattern | stdlib `sqlite3` with hand-written SQL, as already in use |
| `next export` CLI command | Deprecated since Next.js 13.3+; superseded by `output: 'export'` in `next.config.js`, which is what's already configured | `output: 'export'` (already configured in `frontend/next.config.js`) |
| `i18n`, `headers`, `rewrites`, `redirects`, or `fallback: true` in `getStaticPaths`/route configs | All are incompatible with `output: 'export'` — `i18n` throws a build error, `headers`/`rewrites`/`redirects` are silently no-ops with a warning, `dynamicParams: true` on generated routes throws, `fallback: true` throws | Keep all routing static and fully enumerated; do any header/redirect logic in FastAPI instead (it already owns the single origin) |
| Mounting `StaticFiles` at `"/"` before registering `/api/*` routers | Starlette matches mounts/routes in registration order; a root static mount registered first will swallow requests meant for `/api/*` | Register all API routers first, then `app.mount("/", StaticFiles(...))` last, as the catch-all for the SPA |
| Lightweight Charts for the treemap heatmap | It is a specialized financial time-series/candlestick canvas renderer with no treemap chart type at all | Recharts `Treemap` with a custom `content` renderer |

## Stack Patterns by Variant

**If the LiteLLM/OpenRouter structured-output gap turns out to drop `response_format` in practice (verify with a live smoke test against `openrouter/openai/gpt-oss-120b` early in the chat-integration phase):**
- Fall back to explicit dict-based `response_format` + `extra_body={"provider": {"only": ["Cerebras"], "require_parameters": true}}` as described above
- If it still doesn't guarantee schema conformance, consider a "structured extraction" fallback: request plain JSON via prompt instructions, then validate/repair with Pydantic (`model_validate_json`, catching `ValidationError`) before auto-executing any mission/roster actions — never auto-execute unvalidated LLM output against `POST /api/fleet/missions` internals.

**If SQLite write contention becomes visible under concurrent SSE + mission-dispatch + budget-snapshot writes:**
- WAL mode (already configured) allows concurrent readers with one writer; if write latency becomes an issue, serialize writes through a single `asyncio.Lock` around mutation functions rather than reaching for a connection pool — SQLite's single-writer model doesn't benefit from pooling.

**If the fleet heatmap needs richer treemap interactions (drill-down, animated resize) later:**
- Evaluate Nivo's `ResponsiveTreeMap` at that point rather than pre-emptively adopting it now; Recharts covers the PLAN.md spec (size by energy cost, color by battery health) without it.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `litellm>=1.96,<1.97` | `openrouter/openai/gpt-oss-120b` via OpenRouter | Pin a specific minor to avoid picking up LiteLLM's frequent (near-daily) patch releases mid-development; re-test the OpenRouter structured-output path on any deliberate upgrade. |
| `next@15.0.0` (current) → `next@15.1.x`+ | `recharts@2.13.x` or `recharts@3.x` | Recharts major version is independent of Next.js version; no coupling. If upgrading Recharts to 3.x, budget time for the 3.0 migration (internal state rewrite; removed `CategoricalChartState`, removed `activeIndex` prop, dropped `recharts-scale`/`react-smooth` deps) — treat as its own small task, not a drive-by bump while building charts. |
| `python-3.12` + stdlib `sqlite3` | Docker `python:3.12-slim` base image (already planned per PLAN.md §11) | No native extension/build step required — stdlib `sqlite3` ships with CPython, keeping the multi-stage Docker build simple. |

## Sources

- `/berriai/litellm` (Context7, MEDIUM confidence) — `response_format` → `type_to_response_format_param` pydantic-to-json-schema conversion, OpenRouter API key setup pattern
- `docs.litellm.ai/docs/completion/json_mode` (WebFetch, LOW confidence, cross-checked against Context7 → MEDIUM) — explicit list of LiteLLM-supported structured-output providers; OpenRouter notably absent
- `openrouter.ai/docs/guides/features/structured-outputs` (WebFetch, LOW confidence) — OpenRouter's own structured-output caveats: per-endpoint support varies, `require_parameters: true` needed to force compliant routing
- GitHub `BerriAI/litellm` discussion #11652, "Forcing Structured JSON Output in LiteLLM + OpenRouter (FIXED)" (WebSearch, LOW confidence) — community-reported `supports_response_schema()` False-negative for OpenRouter models and the `extra_body`/provider-routing workaround
- `/vercel/next.js/v15.1.8` (Context7, MEDIUM confidence) — `output: 'export'` config, and the i18n/headers/rewrites/redirects/dynamicParams/fallback incompatibilities
- WebSearch: "serve Next.js static export from FastAPI StaticFiles single port" (LOW confidence) — `StaticFiles(directory=..., html=True)` mount pattern and mount-order caveat
- WebSearch: "Recharts vs Nivo vs visx React charting library comparison 2025 bundle size performance" (LOW confidence) — download-share/bundle-size/use-case comparison across Recharts, Nivo, visx
- WebSearch: "Recharts 3.0 breaking changes migration from 2.x" (LOW confidence) — 3.0 migration guide summary (state rewrite, removed props/deps)
- npm registry (`npm view recharts version`, `npm view next version`) and PyPI (`pip index versions litellm`) — current published versions as of 2026-08-12: `recharts@3.10.1`, `next@16.3.0`, `litellm@1.96.2` (project stays on `next@15.x`/`recharts@2.13.x` per Alternatives Considered above)
- `.planning/codebase/STACK.md` — existing project stack baseline (already-installed versions this research builds on top of)

---
*Stack research for: SkyFleet Ops remaining-platform milestone (DB, mission API, LLM chat, frontend, Docker)*
*Researched: 2026-08-12*
