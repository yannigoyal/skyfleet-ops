# Contributing to SkyFleet Ops

## Project Overview

SkyFleet Ops is a real-time operations console for a simulated drone delivery fleet: live telemetry over SSE, mission dispatch against an energy budget, and an LLM flight director that can act on the fleet. Frontend (Next.js, static export) and backend (FastAPI/uv, SQLite) are independent workstreams sharing the contract in `planning/PLAN.md` — read that first.

## Coding Standards

- Keep changes small, focused, and incremental. Validate each step before moving on.
- No over-engineering: favor clear, readable code over clever code; short modules, small functions.
- Comments and docstrings only where they add clarity — be sparing.
- No emojis in code, logs, or print/console output.
- Python: use `uv` (`uv run`, `uv add`) — never call `python` or `pip` directly.
- Frontend and backend must not leak implementation details across their boundary — talk only through `/api/*` and `/api/stream/*`.
- Match the framework's own conventions (pytest for backend, React Testing Library for frontend).

## Branch Naming

```
<type>/<short-description>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`. Example: `feat/mission-recall-endpoint`.

## Commit Message Format

```
<type>: <concise summary>

<optional body explaining why, not what>
```

- Written in imperative mood ("add", not "added").
- One logical change per commit.
- Types match branch types above (`feat`, `fix`, `refactor`, `docs`, `test`, `chore`).

## Pull Request Guidelines

- Keep PRs scoped to a single task or feature.
- Describe what changed and why; link any relevant planning doc or issue.
- Include test evidence (unit test output, or manual verification steps for UI changes).
- Ensure backend (`pytest`) and frontend tests pass before requesting review.
- Update `planning/` docs if the change affects the shared contract (API shape, schema, env vars).
