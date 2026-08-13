# Phase 4: Docker Packaging & Test Suites - Pattern Map

**Mapped:** 2026-08-14
**Files analyzed:** 9 (2 config edits, 2 script edits, 1 new config, 6 new E2E spec files — 1 spec already exists as analog)
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `docker/docker-compose.yml` | config | file-I/O (volume mount) | itself (in-place edit) | exact |
| `scripts/start_mac.sh` | config/script | file-I/O (volume mount) | itself (in-place edit) | exact |
| `scripts/start_windows.ps1` | config/script | file-I/O (volume mount) | `scripts/start_mac.sh` (logic mirror) | exact |
| `.dockerignore` (new) | config | file-I/O | `.gitignore` (same exclusion-list role) | role-match |
| `tests/specs/fresh-start.spec.ts` | test | request-response | `tests/specs/health.spec.ts` | exact |
| `tests/specs/roster.spec.ts` | test | request-response | `tests/specs/health.spec.ts` | exact |
| `tests/specs/missions.spec.ts` | test | request-response | `tests/specs/health.spec.ts` + `frontend/src/components/DispatchBar.tsx` (selectors) | exact |
| `tests/specs/visualization.spec.ts` | test | request-response | `tests/specs/health.spec.ts` + `FleetHeatmap.tsx`/`EnergyBudgetChart.tsx`/`DroneSparkline.tsx` (selectors) | exact |
| `tests/specs/chat.spec.ts` | test | event-driven (mocked LLM) | `tests/specs/health.spec.ts` + `backend/app/chat/llm.py::mock_reply()` | exact |
| `tests/specs/sse-resilience.spec.ts` | test | streaming | `tests/specs/health.spec.ts` + `frontend/src/lib/useTelemetryStream.ts` | exact |

## Pattern Assignments

### `docker/docker-compose.yml` (config, file-I/O)

**Analog:** itself, in-place edit per D-01

**Current pattern** (full file, `docker/docker-compose.yml:1-17`):
```yaml
services:
  app:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - ../.env
    volumes:
      - skyfleet-data:/app/database

volumes:
  skyfleet-data:
```

**Required change:** replace `skyfleet-data:/app/database` (named volume) with a bind mount of the host `database/` directory, and drop the `volumes:` top-level block since no named volume remains:
```yaml
    volumes:
      - ../database:/app/database
```
(No `volumes:` top-level key needed after this change — bind mounts don't require declaration.)

---

### `scripts/start_mac.sh` (script, file-I/O)

**Analog:** itself, in-place edit per D-01

**Full existing pattern** (`scripts/start_mac.sh:1-45`) — idempotent build-then-run guard structure to preserve untouched:
```bash
if $BUILD || ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  echo "Building $IMAGE_NAME..."
  docker build -f docker/Dockerfile -t "$IMAGE_NAME" .
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
  echo "Removing existing container..."
  docker rm -f "$CONTAINER_NAME" >/dev/null
fi

echo "Starting $CONTAINER_NAME on port $PORT..."
docker run -d \
  --name "$CONTAINER_NAME" \
  -v skyfleet-data:/app/database \
  -p "${PORT}:8000" \
  --env-file .env \
  "$IMAGE_NAME"
```

**Required change:** only the `-v` line, per D-01:
```bash
mkdir -p "$ROOT_DIR/database"
...
  -v "$ROOT_DIR/database:/app/database" \
```
Preserve every other line verbatim — idempotency guards (`docker image inspect`, `docker ps -a | grep`) are correct as-is and must not be touched.

---

### `scripts/start_windows.ps1` (script, file-I/O)

**Analog:** `scripts/start_mac.sh` (1:1 logic mirror, PowerShell syntax)

**Full existing pattern** (`scripts/start_windows.ps1:1-40`):
```powershell
$Build = $args -contains "--build"
$ImageExists = docker image inspect $ImageName 2>$null

if ($Build -or -not $ImageExists) {
    Write-Host "Building $ImageName..."
    docker build -f docker/Dockerfile -t $ImageName .
}

$Existing = docker ps -a --format '{{.Names}}' | Select-String -Pattern "^$ContainerName$"
if ($Existing) {
    Write-Host "Removing existing container..."
    docker rm -f $ContainerName | Out-Null
}

Write-Host "Starting $ContainerName on port $Port..."
docker run -d `
  --name $ContainerName `
  -v skyfleet-data:/app/database `
  -p "${Port}:8000" `
  --env-file .env `
  $ImageName
```

**Required change:** only the `-v` line, mirroring the bash change:
```powershell
New-Item -ItemType Directory -Force -Path "$RootDir\database" | Out-Null
...
  -v "${RootDir}\database:/app/database" `
```
No live Windows verification available — verify by code review against the updated `start_mac.sh` per CONTEXT.md's Claude's Discretion note (same idempotency guard shape, same single-line volume edit).

---

### `.dockerignore` (new, config)

**Analog:** repo-root `.gitignore` (same category of file — line-based path exclusion list) — no existing `.dockerignore` on disk (`ls docker/.dockerignore .dockerignore` both return "No such file or directory", confirmed in RESEARCH.md).

**Pattern to follow:** standard `.dockerignore` syntax (same glob rules as `.gitignore`). Minimum required exclusions per RESEARCH.md Pitfall 1:
```
.env
.env.local
database/*.db*
**/node_modules
.git
frontend/.next
frontend/out
backend/.venv
.planning
.claude
```

---

### `tests/specs/fresh-start.spec.ts`, `roster.spec.ts`, `missions.spec.ts`, `visualization.spec.ts`, `chat.spec.ts`, `sse-resilience.spec.ts` (test, request-response/streaming)

**Analog:** `tests/specs/health.spec.ts` (only existing spec — establishes the file-level pattern: import, single/few `test()` blocks, `request` or `page` fixture, `expect().toBeTruthy()`/`toEqual()`)

**Imports + structure pattern** (`tests/specs/health.spec.ts:1-10`, copy verbatim as the header for every new spec file):
```typescript
import { test, expect } from "@playwright/test";

test("backend health check responds ok", async ({ request }) => {
  const response = await request.get("/api/health");
  expect(response.ok()).toBeTruthy();
  expect(await response.json()).toEqual({ status: "ok" });
});
```

**`roster.spec.ts` — direct-API-setup + UI-observed-assertion pattern** (RESEARCH.md Pattern 1, no manual roster UI exists — confirmed by grep, use `request` fixture for mutation):
```typescript
test("adding a drone appears in the roster panel", async ({ page, request }) => {
  const res = await request.post("/api/roster", { data: { drone_id: "FALCON-11" } });
  expect(res.status()).toBe(201);
  await page.goto("/");
  await expect(page.getByText("FALCON-11")).toBeVisible({ timeout: 10_000 });
});
```

**`missions.spec.ts` — dispatch bar selectors** (RESEARCH.md Pattern 2, verified against `frontend/src/components/DispatchBar.tsx`):
- Drone select: `<select>` inside `<label>` text "Drone" (`DispatchBar.tsx:78-92`)
- Zone input: `<input type="text">` inside label "Zone" (`DispatchBar.tsx:96-103`)
- Distance input: `<input type="number">` inside label "Distance (km)" (`DispatchBar.tsx:106-114`)
- Launch button: text `"Launch Mission"` (`DispatchBar.tsx:121`); Recall button: text `"Recall"` (`DispatchBar.tsx:129`)
- After launch/recall, header remaining-kWh updates immediately (`DispatchBar.tsx:41-42` calls `refetch()`) — assert on header text `"Energy Budget:"` (`Header.tsx:28-33`), NOT on `EnergyBudgetChart` (separate 5s poll, will lag — RESEARCH.md Pitfall 3).

**`visualization.spec.ts` — structural assertions only, per D-03** (RESEARCH.md Pattern 2):
- Heatmap: text `"Fleet Heatmap"` header (`FleetHeatmap.tsx:112`), assert SVG `<g><rect fill="..."><text>` count matches roster snapshot size (`FleetHeatmap.tsx:59-82`)
- Budget chart: text `"Energy Budget"` header (`EnergyBudgetChart.tsx:96`), assert `svg path.recharts-line-curve` exists (chart has `dot={false}`, so assert path presence not dot count) (`EnergyBudgetChart.tsx:104-125`)
- Sparkline: assert `svg path` exists per roster row cell (`DroneSparkline.tsx:33-46`)
- No pixel/screenshot diffs — explicitly ruled out by D-03.

**`chat.spec.ts` — mocked LLM keyword-trigger pattern** (RESEARCH.md Pattern 3, verified against `backend/app/chat/llm.py:149-186`):
```typescript
test("mocked chat launches a mission on request", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder("Ask the flight director...").fill("Launch a drone");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByTestId("confirmation-card").first()).toContainText("LAUNCH");
  await expect(page.getByTestId("confirmation-card").first()).toContainText("Dispatched");
});
```
`mock_reply()` contract: message containing `"launch"` (case-insensitive) + idle drone available → launches to `"Riverside"`, `distance_km=4.0`. Message containing `"recall"` + active mission → recalls first active mission. `tests/docker-compose.test.yml` already sets `LLM_MOCK: "true"` — no env change needed.

**`sse-resilience.spec.ts` — route-interception + reload pattern** (RESEARCH.md Pattern 4, `context.route()` scoped to the stream URL, not `context.setOffline()` which also breaks unrelated 5s polls):
```typescript
test("SSE disconnects and reconnects, connection dot reflects both states", async ({ page, context }) => {
  await page.goto("/");
  await expect(page.getByText("Live")).toBeVisible();

  await context.route("**/api/stream/telemetry", (route) => route.abort());
  await page.reload();
  await expect(page.getByText("Disconnected")).toBeVisible({ timeout: 10_000 });

  await context.unroute("**/api/stream/telemetry");
  await expect(page.getByText("Live")).toBeVisible({ timeout: 10_000 });
});
```
Connection dot labels: `"Live"` (connected), `"Connecting"`, `"Disconnected"` — `frontend/src/components/ConnectionDot.tsx:3-13`. Caveat: `route.abort()` only intercepts new requests, not an already-open `EventSource`; reload-after-route forces a fresh connection that immediately fails — this is the documented, deterministic mechanism (fallback: `context.setOffline()` if unreliable).

---

## Shared Patterns

### Playwright spec file skeleton
**Source:** `tests/specs/health.spec.ts` (entire file)
**Apply to:** All 6 new spec files
```typescript
import { test, expect } from "@playwright/test";

test("<scenario description>", async ({ page, request, context }) => {
  // arrange via request fixture (API) or page.goto("/") (UI)
  // act
  // assert via expect(...).toBeVisible()/toContainText()/toEqual()
});
```

### Idempotent shell/PowerShell script guards
**Source:** `scripts/start_mac.sh:22-30`, mirrored in `scripts/start_windows.ps1:17-27`
**Apply to:** Any script edit in this phase — preserve the `docker image inspect` (build guard) and `docker ps -a | grep`/`Select-String` (container-replace guard) exactly; only the `-v` volume-mount line changes per D-01.

### Docker build context hygiene
**Source:** none exists yet — new file, modeled on `.gitignore` conventions
**Apply to:** `.dockerignore` (new) — excludes `.env`, `database/*.db*`, `node_modules`, `.git`, build artifacts from the Docker build context per RESEARCH.md Pitfall 1.

## No Analog Found

None — every file in this phase's scope has a direct in-repo analog (either itself for in-place edits, or `health.spec.ts` for new spec files, or `.gitignore` conventions for the new `.dockerignore`).

## Metadata

**Analog search scope:** `docker/`, `scripts/`, `tests/specs/`, `tests/docker-compose.test.yml`, `frontend/src/components/`, `backend/app/chat/llm.py`, `backend/app/main.py`, `frontend/src/lib/`
**Files scanned:** 9 target files + 10 analog/reference files read directly this session and in RESEARCH.md's prior session
**Pattern extraction date:** 2026-08-14
