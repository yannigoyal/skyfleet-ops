# Codebase Concerns

**Analysis Date:** 2026-08-12

## Tech Debt

### Single-Threaded Database Bottleneck

**Issue:** All database operations are serialized through a single `asyncio.Lock` in `Database` (`backend/app/db/connection.py`). While this guarantees atomicity for multi-statement transactions and prevents concurrent write conflicts on SQLite, it means every read/write operation waits for all previous operations to complete.

**Files:** `backend/app/db/connection.py` (lines 28, 54-79)

**Impact:** 
- Query latency is unpredictable and degrades with concurrent requests
- At 100+ concurrent clients, database operations become a bottleneck
- Cannot scale horizontally without refactoring to a real database

**Fix approach:** 
- For immediate scaling: migrate to PostgreSQL with connection pooling
- For quick demo improvement: add read-only query optimization (separate read lock from write lock)
- Document the limitation clearly in architectural docs

### Telemetry Version Counter Monotonic Growth

**Issue:** The telemetry cache's `version` counter (`backend/app/telemetry/cache.py` line 21, 53) increments on every telemetry update. With updates every 500ms and 10 drones, this is ~1.2M increments per day. While Python integers don't overflow, the counter grows unbounded and provides diminishing value as a change detector (SSE clients see every message anyway).

**Files:** `backend/app/telemetry/cache.py` (lines 21, 53, 76-79)

**Impact:** 
- Long-running deployments accumulate large counter values (minor memory issue)
- Provides no real value since SSE streams all updates anyway
- Could cause issues if version is later used for distributed cache invalidation

**Fix approach:** 
- Remove or reset the counter on a schedule (e.g., every 24 hours)
- Alternatively, use a hash of the cache state instead of a monotonic counter

### Hardcoded Single-Operator Design

**Issue:** The entire system is hardcoded to `operator_id = "default"`. Multi-tenant support would require:
- Adding `operator_id` to all API routes (URL param or header)
- Adding authentication/authorization layer
- Refactoring mission queue to per-operator
- Schema changes to enforce operator isolation

**Files:** `backend/app/missions/repository.py` (line 21), `backend/app/main.py` (line 27)

**Impact:** 
- Cannot support multiple dispatchers without major refactoring
- All data is mixed in a single namespace
- No tenant isolation or access control

**Fix approach:** 
- This is architectural, not a bug fix
- Defer to a future scaling phase
- Document multi-tenant migration path in design docs

## Known Bugs

### Race Condition in Drone Eligibility Check

**Issue:** In `backend/app/missions/service.py` line 80, the code accesses `cache.get(candidate_id).battery_pct` without guaranteeing the cache read is non-None, despite passing the eligibility check. The `_is_eligible()` function checks `reading is not None`, but there's a race window where the drone could be removed from cache between the check and the attribute access.

**Symptom:** `AttributeError: 'NoneType' object has no attribute 'battery_pct'` when a drone is removed during auto-assignment

**Files:** `backend/app/missions/service.py` (lines 65-88)

**Trigger:** 
1. Trigger auto-assignment with multiple eligible drones
2. Simultaneously remove one of the candidate drones from the roster
3. If the removal happens after eligibility check but before battery access, the code crashes

**Workaround:** The fleet roster is static in the demo (10 pre-seeded drones), so this doesn't manifest in practice. But it's unsafe under concurrent roster mutations.

**Fix:** Add a None check before attribute access:
```python
candidates = [
    (cache.get(candidate_id).battery_pct, candidate_id)
    for candidate_id in roster
    if _is_eligible(candidate_id) and cache.get(candidate_id) is not None  # Add guard
]
```

## Security Considerations

### Missing Authentication & Authorization

**Risk:** The backend has no authentication layer. Any client with network access to port 8000 can dispatch missions, recall drones, and drain the entire energy budget.

**Files:** `backend/app/main.py`, `backend/app/missions/router.py` (all routes)

**Current mitigation:** 
- Designed for local/trusted networks only (typical for demo software)
- Energy budget is shared (one operator per container)
- No sensitive data in the system

**Recommendations:** 
- For production deployment, add JWT or API-key authentication
- Add authorization checks to enforce per-operator data access
- Document security limitations clearly in README

### Environment Variable Secrets in Logs

**Risk:** If logging is enabled at DEBUG level, the OPENROUTER_API_KEY and other secrets could be logged in request/response traces.

**Files:** `backend/app/main.py` (line 24)

**Current mitigation:** Logging is set to INFO level by default

**Recommendations:** 
- Explicitly disable logging of Authorization headers in HTTPx
- Sanitize log output to mask API keys
- Document secret handling in deployment guide

### No HTTPS in Single-Container Deployment

**Risk:** The demo runs HTTP-only on port 8000. If deployed on an untrusted network, mission data and commands could be intercepted.

**Files:** `docker/Dockerfile` (line 29)

**Impact:** Low for demo; high for any production use

**Recommendations:** 
- Document that HTTPS should be enforced by a reverse proxy (nginx, Caddy)
- Provide example proxy configurations

## Performance Bottlenecks

### Cholesky Decomposition on Every Roster Add/Remove

**Problem:** The telemetry simulator rebuilds the drone correlation matrix's Cholesky decomposition every time a drone is added or removed (`backend/app/telemetry/simulator.py` line 150). The decomposition is O(n²) in dense form but uses numpy's optimized implementation.

**Files:** `backend/app/telemetry/simulator.py` (lines 195-212)

**Cause:** The correlation matrix is built from scratch on every call to `_rebuild_cholesky()`. With n=10 drones it's negligible; with n=1000+ it becomes noticeable.

**Improvement path:** 
- Cache the correlation matrix and update it incrementally
- Use sparse matrix representation if drone count grows
- Lazy rebuild: only rebuild if new drone added, not on every step

### SSE Fan-Out Not Backpressure-Aware

**Problem:** The telemetry stream endpoint (`backend/app/telemetry/stream.py`) broadcasts all drones' readings to all clients on every tick. If there are 100 connected clients and 10 drones, that's 1000 JSON messages per 500ms interval.

**Files:** `backend/app/telemetry/stream.py`

**Impact:** 
- High bandwidth usage for large fleets
- No mechanism to filter to subset of drones per client
- No compression or delta encoding

**Improvement path:** 
- Add query params to filter drones: `GET /api/stream/telemetry?drones=FALCON-01,FALCON-02`
- Consider message delta encoding (send only changed fields)
- Add gzip compression for SSE payloads

## Fragile Areas

### Telemetry Simulator Assumes Positive-Definite Correlation Matrix

**Files:** `backend/app/telemetry/simulator.py` (line 212)

**Why fragile:** The Cholesky decomposition requires the correlation matrix to be positive definite. If the hardcoded correlation parameters in `seed_fleet.py` are adjusted incorrectly (e.g., INTRA_NORTH_CORR set to a value that violates the constraints), the decomposition will fail with `numpy.linalg.LinAlgError: Matrix is not positive definite`.

**Safe modification:** 
- Only adjust correlation parameters after testing with `numpy.linalg.eigh()` to verify eigenvalues are positive
- Add a validation test that confirms the correlation matrix is positive definite for all possible drone groupings

### Docker Build Doesn't Verify Frontend Output Exists

**Files:** `docker/Dockerfile` (lines 9, 24)

**Why fragile:** If `npm run build` fails or doesn't produce `frontend/out/`, the COPY command silently succeeds (copies nothing). The backend then serves an empty static directory with no 404 handling, giving users a blank screen.

**Safe modification:** 
- Add a validation step after COPY: `RUN test -d /frontend/out || (echo "Frontend build missing" && exit 1)`
- Or verify that index.html exists: `RUN test -f ./static/index.html || (echo "Frontend build failed" && exit 1)`

### SQLite WAL Mode Without Checkpoint Tuning

**Files:** `backend/app/db/connection.py` (line 36)

**Why fragile:** SQLite in WAL mode accumulates checkpoint data. The backend sets `PRAGMA journal_mode=WAL` but doesn't configure checkpointing. After weeks of operation, the WAL file can grow to gigabytes, slowing down startups.

**Safe modification:** 
- Configure a checkpoint policy: `PRAGMA wal_autocheckpoint=1000` (checkpoint every 1000 pages)
- Document cleanup: `PRAGMA wal_checkpoint(TRUNCATE)` before upgrades

## Scaling Limits

### Fleet Roster Size

**Current capacity:** 10-100 drones with no performance degradation

**Limit:** ~1000 drones before:
- Telemetry cache update latency becomes noticeable (O(n) iteration)
- SSE broadcast size exceeds useful bandwidth
- Correlation matrix computation time grows O(n²)

**Scaling path:** 
- Partition fleet into regions, each with its own telemetry cache
- Push drone filtering to the client (subscribe to subset of drones)
- Cache only recent telemetry history, not full time-series

### Mission Queue Persistence

**Current capacity:** ~10 queued missions with no issues

**Limit:** In-memory queue with no persistence. A crash loses all queued assignments waiting for retry.

**Scaling path:** 
- Move MissionQueue into SQLite with a `mission_queue` table
- Add a `status` column: pending, failed, completed
- Rebuild queue on startup from table

### Database Write Throughput

**Current capacity:** ~10-20 writes/second (conservative estimate)

**Limit:** SQLite is single-writer. With multiple concurrent mission launches or high telemetry ingest, write lock contention becomes obvious.

**Scaling path:** 
- Move to PostgreSQL for multi-writer concurrency
- Add connection pooling (pgbouncer)
- Index high-cardinality queries (missions by drone_id, by updated_at)

## Dependencies at Risk

### numpy Dependency

**Risk:** Imported only for Cholesky decomposition in the simulator. If numpy is dropped or version pinning breaks, the correlation logic fails.

**Files:** `backend/app/telemetry/simulator.py` (line 9), `backend/pyproject.toml` (line 10)

**Impact:** The fleet simulator won't run; deployment fails

**Migration plan:** 
- Option 1: Use `scipy.linalg.cholesky()` (but adds scipy dependency)
- Option 2: Implement Cholesky in pure Python (slow, but removes dependency)
- Option 3: Use `math.cholesky()` if available in Python 3.13+

### httpx Dependency for MAVLink Gateway

**Risk:** External HTTP client dependency. If httpx is removed or the version breaks compatibility, real MAVLink hardware support fails.

**Files:** `backend/app/telemetry/mavlink_gateway.py` (line 8), `backend/pyproject.toml` (line 11)

**Impact:** Users with real MAVLink hardware can't telemetry stream; forced to use simulator

**Migration plan:** 
- Use `urllib3` (stdlib alternative) — more verbose but no external dependency
- Or pin httpx version strictly with explicit version testing

## Missing Critical Features

### Chat/LLM Integration Not Implemented

**Problem:** The spec (`planning/PLAN.md` section 9) requires a complete LLM chat endpoint with structured outputs, but `backend/app/chat/` is empty and the endpoint doesn't exist.

**Blocks:** 
- Dispatcher can't use natural language to dispatch or recall missions
- No flight director recommendations
- Core feature of the demo missing

**Scope to implement:**
```
- Create POST /api/chat endpoint
- Implement structured output parsing for mission actions
- Add chat history storage (chat_messages table already exists)
- Integrate LiteLLM → OpenRouter
- Add mission validation for LLM-issued actions
- ~200-300 lines of backend code
```

### Frontend Mission Dispatch UI Not Implemented

**Problem:** The frontend only displays telemetry. No UI for launching/recalling missions, managing roster, or viewing fleet health charts.

**Blocks:** 
- Dispatcher can't do anything except watch telemetry
- All visualizations in PLAN.md section 10 missing: heatmap, budget chart, missions table

**Scope:** ~500-800 lines of React/TypeScript

### Frontend AI Chat Panel Not Implemented

**Problem:** The chat placeholder in `frontend/src/app/page.tsx` (line 26-29) is just a message saying "not yet implemented."

**Blocks:** Dispatcher can't interact with flight director

**Scope:** ~300-400 lines of React

### Roster Management Not Implemented

**Problem:** No frontend UI or API endpoints to add/remove drones from the roster.

**Blocks:** Dispatcher is stuck with the 10 default drones

**Scope:** ~100 lines backend (POST/DELETE `/api/roster`), ~150 lines frontend

## Test Coverage Gaps

### E2E Test Coverage Missing

**Untested:**
- Full mission dispatch → delivery → budget update flow
- Concurrent launches that should fail gracefully
- MAVLink gateway integration (no tests, only code review)
- Frontend SSE connection resilience (reconnection after network loss)
- Docker deployment (no deployment tests)

**Files:** `tests/specs/` has only `health.spec.ts`

**Risk:** High — regressions in critical flows aren't caught until production

**Priority:** High — add E2E tests for mission dispatch, recall, and budget enforcement

### Service Layer Edge Cases Not Tested

**What's not tested:**
- `find_eligible_drone()` with mixed telemetry states (some drones with no reading, some offline)
- Concurrent mission launches that race on the same drone (Should be prevented by atomicity, but untested)
- Battery rounding edge cases (e.g., 20.004 → 20.0 boundary)

**Files:** `backend/tests/missions/test_service.py` has good coverage but is missing edge case suite

**Risk:** Medium — mostly covered by transaction-level tests, but service-level assumptions not verified

## Architectural Concerns

### No Circuit Breaker for MAVLink Gateway

**Problem:** If the MAVLink gateway becomes unreachable, the poller logs errors silently and retries forever. The backend still reports telemetry as "connected" even if all readings are stale.

**Files:** `backend/app/telemetry/mavlink_gateway.py` (lines 89-120)

**Impact:** 
- Dispatcher doesn't know telemetry is stale
- Stale readings could lead to unsafe mission decisions
- No alerting mechanism

**Fix approach:** 
- Track "last successful poll" timestamp
- If stale (> 30s), mark source as "degraded" and send SSE with staleness flag
- Add /api/health endpoint that reports per-drone staleness

### SSE Connection Doesn't Handle Late Subscribers

**Problem:** When a client first connects to `/api/stream/telemetry`, it receives a stream of updates going forward, but misses all historical telemetry. If a client connects after 1 minute, it gets no initial state.

**Files:** `backend/app/telemetry/stream.py`

**Impact:** 
- Frontend shows "Waiting for telemetry..." for up to 1 second after load
- Confusing UX when reconnecting after network outage

**Fix approach:** 
- Send a "full snapshot" event on first connection
- Or cache the latest reading for each drone and send on subscription

---

*Concerns audit: 2026-08-12*
