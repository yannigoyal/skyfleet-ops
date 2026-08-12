# Testing Patterns

**Analysis Date:** 2026-08-12

## Test Framework

**Python Backend (pytest):**
- Framework: pytest 8.3.0+
- Async support: pytest-asyncio 0.24.0+
- Coverage: pytest-cov 5.0.0+
- Config: `pyproject.toml` → `[tool.pytest.ini_options]`
  - Test discovery: `testpaths = ["tests"]`, `python_files = ["test_*.py"]`
  - Classes: `python_classes = ["Test*"]`, Functions: `python_functions = ["test_*"]`
  - Async mode: `asyncio_mode = "auto"`, `asyncio_default_fixture_loop_scope = "function"`

**TypeScript/React Frontend (Vitest):**
- Framework: vitest 2.1.0+
- React Testing Library: @testing-library/react 16.0.0+
- Config: inline in `package.json` (no vitest.config.* file yet)
- Test script: `npm run test` (runs once), `npm run test -- --watch` (watch mode)

**E2E Tests (Playwright):**
- Framework: @playwright/test 1.48.0+
- Config: `tests/` directory with `specs/*.spec.ts` files
- Run: `npm test` in `tests/` directory
- Infrastructure: `docker-compose.test.yml` for test container orchestration

**Run Commands:**
```bash
# Backend
cd backend
uv run --extra dev pytest -v              # Run all tests
uv run --extra dev pytest --cov=app       # With coverage report
uv run --extra dev pytest -k test_queue   # Run specific test class/function
uv run --extra dev ruff check app/ tests/ # Lint before testing

# Frontend
cd frontend
npm run test                              # Run Vitest once
npm run test -- --watch                   # Watch mode

# E2E
cd tests
npm test                                  # Run Playwright specs
```

## Test File Organization

**Backend Location:**
- Layout: Mirror source structure under `tests/`
- Examples: `tests/telemetry/test_models.py` mirrors `app/telemetry/models.py`
- Conftest: Shared fixtures live in `tests/conftest.py` (root) and `tests/{module}/conftest.py`

**Backend Directory Structure:**
```
backend/
├── app/
│   ├── telemetry/
│   ├── missions/
│   ├── db/
│   └── main.py
└── tests/
    ├── conftest.py           # Global fixtures (event loop policy)
    ├── telemetry/
    │   └── test_*.py
    ├── missions/
    │   ├── conftest.py       # Shared db, cache fixtures
    │   └── test_*.py
    └── db/
        └── test_*.py
```

**Frontend Location:**
- Co-located with source: `src/components/Button.tsx` → `src/components/Button.test.tsx`
- OR separate test directory: `src/__tests__/components/Button.test.tsx`
- Current codebase: No frontend tests yet; pattern established by pytest backend

**Naming:**
- Test files: `test_*.py` (Python) or `*.test.ts` / `*.spec.ts` (TypeScript)
- Test classes: `class Test*` (Python) — groups related tests with setup/teardown
- Test functions: `async def test_*` (Python async) or `test` export (TypeScript)
- Descriptive names: `test_launches_when_valid`, `test_rejects_unknown_drone`, not `test_1`, `test_2`

## Test Structure

**Python Test Suite Organization:**

```python
class TestLaunchMission:
    """Group of tests for launch_mission() function."""
    
    async def test_launches_when_valid(self, db, cache):
        """Success case: drone eligible, budget sufficient."""
        seed_telemetry(cache, "FALCON-01", battery_pct=90.0, status="idle")
        mission = await service.launch_mission(
            db, cache, drone_id="FALCON-01", zone="Riverside", distance_km=4.2
        )
        assert mission.status == "en_route"
        assert mission.drone_id == "FALCON-01"
    
    async def test_rejects_unknown_drone(self, db, cache):
        """Error case: drone not on roster."""
        with pytest.raises(UnknownDroneError):
            await service.launch_mission(
                db, cache, drone_id="GHOST-01", zone="Riverside", distance_km=4.2
            )
```

**Pattern Conventions:**
- Arrange-Act-Assert structure (implicit): setup in fixtures, act in function body, assert in assertions
- One logical assertion per test (may have multiple `assert` statements for a single behavior)
- Fixtures provide clean state; tests modify via service/repository calls
- Docstrings explain the scenario: `"""Success case: drone eligible, budget sufficient."""`
- No setup/teardown methods yet; rely on fixture teardown and pytest's cleanup

**TypeScript/React Test Structure:**

```typescript
import { test, expect } from "@playwright/test";

test("backend health check responds ok", async ({ request }) => {
  const response = await request.get("/api/health");
  expect(response.ok()).toBeTruthy();
  expect(await response.json()).toEqual({ status: "ok" });
});
```

**Pattern:**
- One test per logical scenario (Playwright handles setup/teardown via fixtures)
- Use `test()` to declare a test case with a descriptive name
- Arrange-Act-Assert: setup mocks/state, call API, assert response

## Mocking

**Python Mocking Strategy:**

- **Databases:** Not mocked — `tmp_path` fixture creates isolated SQLite files
  - Each test gets a fresh, seeded database: `Database(tmp_path / "skyfleet.db")`
  - Fixtures in `tests/missions/conftest.py` handle setup
  
- **Telemetry Cache:** Not mocked — real `TelemetryCache()` instance passed to tests
  - Helper: `seed_telemetry(cache, drone_id, battery_pct=90.0, status="idle")`
  - Allows testing of cache behavior (thread-safety, version counter)

- **Immutable Data:** No mocking — dataclasses like `TelemetryUpdate` are value objects
  - Constructed directly in tests with required fields
  - Immutability (`frozen=True`) ensures no side effects

- **Async/await:** Real async execution via pytest-asyncio
  - No mocking of `asyncio` — tests run in real event loops
  - Test methods: `async def test_*` (not wrapped in `@pytest.mark.asyncio`)
  - asyncio_mode = "auto" enables implicit marking

**What NOT to Mock:**
- Database layer (use isolated temp DBs)
- Telemetry cache (use real instance)
- Internal service functions (test end-to-end through service layer)
- Time functions for most tests (use real `time.time()`) unless testing backoff windows

**Fixture Example (Missions):**

```python
@pytest.fixture
def db(tmp_path):
    """Isolated SQLite database for each test."""
    database = Database(tmp_path / "skyfleet.db")
    database.ensure_initialized()
    yield database
    database.close()

@pytest.fixture
def cache():
    """Fresh telemetry cache for each test."""
    return TelemetryCache()

def seed_telemetry(
    cache: TelemetryCache, drone_id: str, battery_pct: float = 90.0, status: str = "idle"
) -> None:
    """Helper: populate cache with a test drone."""
    cache.update(drone_id, battery_pct=battery_pct, altitude_m=100.0, speed_kmh=40.0, status=status)
```

**TypeScript/React Mocking (Not Yet Implemented):**
- Will use Jest/Vitest mocking (still TBD as components are minimal)
- Mock API calls using `jest.mock()` or `vi.mock()` when component tests are written
- Mock telemetry stream via `EventSource` mock if needed

## Fixtures and Factories

**Test Fixtures (Python):**
- Centralized in `tests/conftest.py` (global) and module-level `conftest.py` (e.g., `tests/missions/conftest.py`)
- Scope: `function` (default, fresh fixture per test), `session` (shared across all tests)
- Use `yield` for setup-teardown: code before `yield` runs before test, after runs cleanup

**Database Fixture Pattern:**
```python
@pytest.fixture
def db(tmp_path):
    """Create isolated database with schema and seed data."""
    database = Database(tmp_path / "skyfleet.db")
    database.ensure_initialized()  # Creates tables and seed data
    yield database
    database.close()
```

**Test Data Helpers:**
- `seed_telemetry(cache, drone_id, battery_pct, status)` — populate cache for a drone
- Direct dataclass construction for models: `TelemetryUpdate(...)`
- No factory libraries; keep it simple with direct construction

**Coverage Exclusions (pyproject.toml):**
```toml
[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
```

## Coverage

**Requirements:** None explicitly enforced (no `fail_under` threshold in config)

**View Coverage:**
```bash
cd backend
uv run --extra dev pytest --cov=app --cov-report=html
# Open htmlcov/index.html in browser
```

**Current Coverage:**
- Telemetry: High coverage (models, cache, sources)
- Missions: High coverage (queue, service, repository, router)
- Database: Good coverage (connection, schema, seed)
- E2E: Minimal (health check only; other specs placeholder)

**Coverage Report Format:**
- Terminal: `--cov-report=term` (default with `--cov`)
- HTML: `--cov-report=html` (generates `htmlcov/index.html`)
- Exclude: pragma comments (`# pragma: no cover`)

## Test Types

**Unit Tests:**
- Scope: Single class or function
- Examples: `test_telemetry_update.py` (TelemetryUpdate properties), `test_cache.py` (TelemetryCache methods)
- Speed: Instant (< 100ms per test)
- Isolation: Use fixtures (temp DB, fresh cache) — no shared state
- Files: `tests/{module}/test_models.py`, `tests/{module}/test_cache.py`

**Integration Tests:**
- Scope: Multiple layers (service + repository + database)
- Examples: `test_service.py` (mission launch flow), `test_queue.py` (MissionQueue + backoff)
- Speed: Fast (< 500ms per test)
- Setup: Fixtures provide real DB + cache; tests exercise workflows
- Files: `tests/{module}/test_service.py`, `tests/{module}/test_repository.py`

**End-to-End Tests:**
- Framework: Playwright
- Scope: Full application (frontend + backend + database)
- Examples: `tests/specs/health.spec.ts` (HTTP endpoint working), future: mission launch flow
- Speed: Slower (1-5s per test)
- Setup: Docker container running; tests make real HTTP requests
- Files: `tests/specs/*.spec.ts`
- Current: Only health check implemented; mission/chat tests are placeholder specs per `tests/README.md`

## Common Patterns

**Async Testing (Python):**
```python
class TestAsyncFunction:
    async def test_returns_mission(self, db, cache):
        """Async test using fixtures and await."""
        mission = await service.launch_mission(
            db, cache, drone_id="FALCON-01", zone="Riverside", distance_km=4.2
        )
        assert mission.status == "en_route"
```

- No `@pytest.mark.asyncio` needed (asyncio_mode = "auto")
- Fixtures work seamlessly with async tests
- Await service/repository calls directly

**Error Testing (Python):**
```python
async def test_rejects_unknown_drone(self, db, cache):
    """Test exception is raised with expected type and message."""
    with pytest.raises(UnknownDroneError) as exc_info:
        await service.launch_mission(
            db, cache, drone_id="GHOST-01", zone="Riverside", distance_km=4.2
        )
    assert exc_info.value.drone_id == "GHOST-01"
```

- Use `pytest.raises()` context manager to assert exception type
- Access exception instance via `exc_info.value` for further assertions
- Verify custom attributes on exception (e.g., `drone_id`, `requested_kwh`)

**Parameterized Tests (Python):**
```python
@pytest.mark.parametrize("battery_pct,expected_status", [
    (95.0, 200),
    (20.0, 200),
    (5.0, 409),  # low battery, should fail
])
async def test_launch_with_battery_levels(self, db, cache, battery_pct, expected_status):
    """Test launch success/failure at different battery levels."""
    seed_telemetry(cache, "FALCON-01", battery_pct=battery_pct, status="idle")
    # ... test logic
```

- Not yet heavily used in codebase; simple enough to test edge cases individually

**Snapshot Testing (Python):**
- Not used; dataclasses have `to_dict()` methods tested via `assert ==`

**Mocking Time (Python):**
```python
def test_backoff_grows_with_each_failure(self):
    """Test exponential backoff window increases on retries."""
    queue = MissionQueue()
    entry = queue.enqueue("Riverside", 4.2)
    first = queue.record_failure(entry.id, "err")
    second = queue.record_failure(entry.id, "err")
    assert second.next_attempt_at > first.next_attempt_at
```

- Tests use real time via `time.time()`; optional `now` parameter for tests that check backoff windows
- No monkeypatching of time module (tests are fast enough)

**Defensive Copy Testing (Python):**
```python
def test_due_returns_copies_not_live_references(self):
    """Snapshot accessors return copies to prevent external mutation."""
    queue = MissionQueue()
    queue.enqueue("Riverside", 4.2)
    snapshot = queue.due()[0]
    snapshot.attempts = 99
    assert queue.due()[0].attempts == 0  # Original unchanged
```

- Ensures thread-safety and isolation: callers can't mutate cache/queue state
- Uses `dataclasses.replace()` to create defensive copies

---

*Testing analysis: 2026-08-12*
