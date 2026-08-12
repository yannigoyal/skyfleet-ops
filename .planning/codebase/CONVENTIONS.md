# Coding Conventions

**Analysis Date:** 2026-08-12

## Naming Patterns

**Python Files:**
- Lowercase with underscores: `telemetry_models.py`, `mission_queue.py`, `conftest.py`
- Avoid abbreviations unless standard: `repo` → `repository`
- Test files: `test_*.py` (e.g., `test_models.py`, `test_queue.py`)
- Private/internal modules: single leading underscore in variables/functions (e.g., `_error_response()`)

**Python Functions:**
- Snake_case: `launch_mission()`, `get_battery()`, `seed_if_empty()`
- Boolean functions may use `is_*` or `get_*` prefix: `is_drone_on_roster()`, `is_eligible()`
- Async functions: same snake_case, no special prefix: `async def launch_mission()`
- Factory functions: `create_*` prefix: `create_telemetry_source()`, `create_stream_router()`
- Lifecycle/scheduler: `run_*` prefix: `run_assignment_scheduler()`, `run_delivery_scheduler()`

**Python Classes:**
- PascalCase: `TelemetryUpdate`, `MissionQueue`, `TelemetryCache`
- Exception classes: PascalCase ending with `Error`: `MissionError`, `UnknownDroneError`, `InsufficientBudgetError`
- Dataclasses: `@dataclass(frozen=True, slots=True)` for immutable value types

**Python Variables:**
- Snake_case: `drone_id`, `battery_pct`, `distance_km`, `energy_cost_kwh`
- Private instance variables: `_readings`, `_lock`, `_version`
- Module-level constants: UPPER_SNAKE_CASE: `UNSAFE_TELEMETRY_STATUSES`, `ENERGY_COST_PER_KM_KWH`, `MAX_ASSIGNMENT_ATTEMPTS`
- Type hint variables: use full names, not abbreviations: `battery_pct` not `batt_pct`, `altitude_m` not `alt_m`

**TypeScript/React Files:**
- Component files: PascalCase: `FleetRosterPanel.tsx`, `ConnectionDot.tsx`, `Header.tsx`
- Hook files: `use*.ts` prefix: `useTelemetryStream.ts`
- Type/constant files: lowercase: `telemetry.ts`
- Utility/lib files: lowercase: `useTelemetryStream.ts`

**TypeScript Functions:**
- Exported components: PascalCase: `FleetRosterPanel()`, `ConnectionDot()`
- Exported hooks: camelCase with `use` prefix: `useTelemetryStream()`
- Internal functions: camelCase: `batteryColor()`, `seed_telemetry()`
- Factory functions: `create*`: `createTelemetrySource()`, `createStreamRouter()`

**TypeScript Variables & Types:**
- Constants: UPPER_SNAKE_CASE: `COLORS`, `LABELS`, `STATUS_LABEL`
- Type names: PascalCase: `TelemetryReading`, `ConnectionStatus`, `DroneStatus`
- Interface names: PascalCase with `Props` suffix for component props: `interface Props { ... }`
- Regular variables: camelCase: `droneId`, `selectedDroneId`, `maxHistoryPoints`

## Code Style

**Formatting:**
- Python: Ruff formatter (configured in `pyproject.toml`):
  - Line length: 100 characters (E501 ignored, formatter respects this)
  - Enforce: E (pycodestyle errors), F (pyflakes), I (isort imports), N (naming), W (warnings)
  - Target: Python 3.12+
- TypeScript: Next.js default (Prettier-compatible via `next lint`)
  - No explicit `.eslintrc` or `.prettierrc` — relies on Next.js sensible defaults
  - Strict TypeScript enabled: `"strict": true` in `tsconfig.json`

**Linting:**
- Python backend: `uv run --extra dev ruff check app/ tests/`
- TypeScript frontend: `npm run lint` (Next.js built-in linting)
- Run before committing for code quality checks

**String Formatting:**
- Python: f-strings preferred for all string interpolation
- Python docstrings: Triple-quoted, concise, describe purpose and behavior
- TypeScript: Template literals for dynamic strings, JSX expressions for React

## Import Organization

**Python:**
1. `from __future__ import annotations` (first, enables postponed evaluation)
2. Standard library imports (alphabetical): `import asyncio`, `from pathlib import Path`
3. Third-party imports (alphabetical): `from fastapi import FastAPI`, `from pydantic import BaseModel`
4. Local imports (relative or absolute): `from app.db import Database`, `from .models import Mission`

**Example Python imports:**
```python
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, replace
from threading import Lock

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import Database
from .models import Mission, MissionError
from .repository import create_mission
```

**TypeScript/React:**
1. React/Next.js core imports
2. Internal type imports (`import type { ... }`)
3. Internal component/util imports (using `@/` path alias)

**Example TypeScript imports:**
```typescript
import { useEffect, useRef, useState } from "react";
import type { TelemetrySnapshot } from "@/types/telemetry";

export type ConnectionStatus = "connecting" | "connected" | "disconnected";
```

**Path Aliases:**
- Frontend: `@/*` maps to `./src/*` (configured in `tsconfig.json`)
- Use `@/` for all internal imports (types, components, lib, utilities)

## Error Handling

**Python Exception Strategy:**
- Inherit from domain-specific base: `MissionError` (not `Exception` directly) for validation failures
- Domain exceptions have a `reason` class attribute (string key): `reason = "unknown_drone"`
- Each exception captures relevant data as instance attributes: `drone_id`, `requested_kwh`, `remaining_kwh`
- Provide detailed messages in `super().__init__()`: `f"drone not on roster: {drone_id}"`
- Router layer catches exceptions and maps to HTTP status codes via a lookup table (e.g., `_ERROR_STATUS`)

**Example Python exception:**
```python
class UnknownDroneError(MissionError):
    reason = "unknown_drone"
    
    def __init__(self, drone_id: str) -> None:
        self.drone_id = drone_id
        super().__init__(f"drone not on roster: {drone_id}")
```

**Router error mapping:**
```python
_ERROR_STATUS = {
    "unknown_drone": 404,
    "drone_already_en_route": 409,
    "insufficient_budget": 422,
}

def _error_response(exc: MissionError) -> HTTPException:
    status_code = _ERROR_STATUS.get(exc.reason, 400)
    return HTTPException(status_code=status_code, detail={"reason": exc.reason})
```

**TypeScript/React:**
- No custom error types yet (components are minimal/growing)
- Use native `EventSource` error handling for SSE reconnection
- Pass error info through component props or return values where needed

## Logging

**Framework:**
- Python: `logging` module (configured in `app/main.py`):
  - `logging.basicConfig(level=logging.INFO)`
  - Each module creates: `logger = logging.getLogger(__name__)`
- TypeScript: `console` (no structured logging library yet)

**When to Log (Python):**
- Application lifecycle: `"SkyFleet Ops backend started"`, `"SkyFleet Ops backend stopped"`
- Errors/warnings: caught exceptions, startup issues
- Debug info: spawned background tasks, telemetry updates (use `logger.debug()` if verbose)
- Do NOT log in tests unless debugging a failure

**Example:**
```python
logger = logging.getLogger(__name__)
logger.info("SkyFleet Ops backend started")
logger.debug(f"Updated telemetry for {drone_id}")
```

## Comments

**When to Comment:**
- Clarify *why*, not *what*: Code reads clearly; comments explain intent
- Algorithm complexity: Exponential backoff calculation, retry logic
- Non-obvious behavior: OU-drain model assumptions, thread-safety guarantees
- Design decisions documented in module docstrings

**Module Docstrings:**
- Triple-quoted, first line: one-sentence purpose
- Blank line, then details (if complex)
- For packages (`__init__.py`): list public API with `__all__`

**Example module docstring:**
```python
"""Mission launch/recall validation and drone-assignment logic.

Two entry points into mission creation:
  - launch_mission(): explicit drone_id, used by manual dispatch
  - auto_assign_mission(): picks best eligible drone automatically

Both call repository.create_mission() for atomic validation.
"""
```

**Function Docstrings:**
- One-liner for simple functions; multi-line for complex ones
- Describe parameters, return value, and any exceptions raised
- Use NumPy/Google style format

**Example function docstring:**
```python
def update(
    self,
    drone_id: str,
    battery_pct: float,
    altitude_m: float,
    speed_kmh: float,
    status: str,
    timestamp: float | None = None,
) -> TelemetryUpdate:
    """Record a new reading for a drone. Returns the created TelemetryUpdate.

    Automatically computes battery delta/direction from the previous reading.
    If this is the first reading for the drone, previous_battery_pct == battery_pct
    (direction='flat').
    """
```

**Inline Comments:**
- Rare; only for non-obvious logic
- Use `#` with space: `# comment here`
- Keep brief and above the relevant code

## Function Design

**Size & Scope:**
- Functions should be small and focused (typically < 50 lines)
- Single responsibility: one logical task per function
- If logic is complex, break into helper functions (prefix with `_` if internal to module)

**Parameters:**
- Explicit is better than implicit: pass all dependencies as arguments
- No reliance on module-level mutable state (except for DI containers like `app.state.*`)
- Use type hints for all parameters and return types
- Python: use `*` to force keyword-only args when appropriate (e.g., `async def launch_mission(..., *, drone_id: str, zone: str)`)

**Return Values:**
- Consistent types: function always returns the same type (or `None`)
- Avoid returning tuples without names; use dataclasses or dicts with keys
- Dataclass instances preferred for structured returns: `Mission`, `TelemetryUpdate`, `QueuedMission`
- `None` for operations with no meaningful return (e.g., `remove()`, `update()` that modifies in-place returns the created object, not None)

**Example function with keyword-only args:**
```python
async def launch_mission(
    db: Database, cache: TelemetryCache, *, drone_id: str, zone: str, distance_km: float
) -> Mission:
    """Validate and dispatch a mission to an explicit drone."""
    if not await repository.is_drone_on_roster(db, drone_id):
        raise UnknownDroneError(drone_id)
    energy_cost_kwh = Mission.energy_cost_for(distance_km)
    return await repository.create_mission(db, drone_id, zone, distance_km, energy_cost_kwh)
```

## Module Design

**Exports:**
- Explicit `__all__` list in `__init__.py` files
- Only export public API; private helpers stay in their module
- Group related exports together (e.g., models before routers)

**Example `__init__.py`:**
```python
from .cache import TelemetryCache
from .models import TelemetryUpdate
from .stream import create_stream_router

__all__ = [
    "TelemetryUpdate",
    "TelemetryCache",
    "create_stream_router",
]
```

**Module Organization:**
- `models.py`: Data types, constants, exceptions
- `cache.py` or `store.py`: Stateful stores (thread-safe)
- `router.py`: FastAPI endpoints (dependency injection at factory-function level)
- `service.py`: Business logic (validation, domain rules)
- `repository.py`: Database queries (CRUD, transactions)
- `interface.py`: Abstract base classes (if multiple implementations)
- `factory.py`: Constructors that select implementations (e.g., simulator vs. MAVLink)

**Dependency Injection:**
- No global singletons; pass dependencies as function/constructor arguments
- Router factories accept dependencies: `def create_missions_router(db: Database, cache: TelemetryCache, queue: MissionQueue) -> APIRouter:`
- Thread-safety achieved via class-level locks, not module-level state manipulation

**Example immutable dataclass:**
```python
@dataclass(frozen=True, slots=True)
class TelemetryUpdate:
    """Immutable snapshot of a single drone's telemetry at a point in time."""
    drone_id: str
    battery_pct: float
    altitude_m: float
    speed_kmh: float
    status: str
    timestamp: float = field(default_factory=time.time)
```

---

*Convention analysis: 2026-08-12*
