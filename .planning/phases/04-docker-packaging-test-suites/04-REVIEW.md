---
phase: 04-docker-packaging-test-suites
reviewed: 2026-08-14T00:00:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - docker/docker-compose.yml
  - .dockerignore
  - docker/MIGRATION.md
  - .gitignore
  - scripts/start_mac.sh
  - scripts/start_windows.ps1
  - tests/package.json
  - tests/playwright.config.ts
  - tests/README.md
  - tests/specs/chat.spec.ts
  - tests/specs/fresh-start.spec.ts
  - tests/specs/helpers.ts
  - tests/specs/missions.spec.ts
  - tests/specs/roster.spec.ts
  - tests/specs/sse-resilience.spec.ts
  - tests/specs/visualization.spec.ts
  - tests/tsconfig.json
findings:
  critical: 2
  warning: 2
  info: 0
  total: 4
status: fixed
fixed: 2026-08-14
fix_notes: >-
  CR-01, CR-02, WR-01, WR-02 all fixed directly by the orchestrator.
  CR-01/CR-02: replaced regex-style volume/image filters with
  `docker volume inspect` / `docker image inspect` + exit-code checks in both
  start_mac.sh and start_windows.ps1; start_windows.ps1 also toggles
  $PSNativeCommandUseErrorActionPreference around the native probes so an
  expected first-run miss doesn't terminate the script under PowerShell 7.4+.
  WR-01: dropped the no-op try/catch in helpers.ts (Playwright's delete()
  doesn't throw on non-2xx) and corrected the comment. WR-02: scoped
  fresh-start.spec.ts's readBattery() to the "Fleet Roster" panel, matching
  the pattern missions.spec.ts already documents and uses.
---

# Phase 04: Docker Packaging & Test Suites Code Review Report

**Reviewed:** 2026-08-14T00:00:00Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Reviewed the Docker packaging assets (`docker-compose.yml`, `.dockerignore`, `MIGRATION.md`, start scripts) and the Playwright E2E test suite (config, helpers, all six spec files, README) for this phase. The bind-mount migration story in `MIGRATION.md` is internally consistent and the checkpoint-then-stop-then-copy procedure is correctly ordered relative to SQLite's WAL semantics. The E2E specs are well-scoped and mostly defend carefully against the suite's own shared-mutable-state hazard (see `missions.spec.ts`'s explicit locator scoping).

Two blockers were found, both in the Windows/macOS start scripts: the "leftover `skyfleet-data` volume" detection uses a Docker volume-name filter as if it supported regex anchors, which it does not — so the migration notice this feature exists to show can never fire. Separately, `start_windows.ps1` combines `$ErrorActionPreference = "Stop"` with an unguarded native `docker image inspect` probe call that is *expected* to fail on a fresh install; on PowerShell 7.4+ (where `$PSNativeCommandUseErrorActionPreference` defaults to `$true`), that expected failure becomes a terminating error and aborts the script before the image is ever built — breaking the single-command first-launch flow described in `planning/PLAN.md` for a large share of the Windows audience. Two further warnings cover a misleading/no-op comment in the test helpers' cleanup routine and a locator fragility in `fresh-start.spec.ts` that the suite's own sibling spec explicitly documents and defends against elsewhere.

## Critical Issues

### CR-01: `docker volume ls -f name=^skyfleet-data$` never matches — the leftover-volume notice can never fire

**File:** `scripts/start_mac.sh:44` and `scripts/start_windows.ps1:42`
**Issue:** Both scripts detect a leftover `skyfleet-data` named volume (from the pre-bind-mount setup) with:

```bash
docker volume ls -q -f name=^skyfleet-data$ | grep -q .
```
```powershell
$OldVolume = docker volume ls -q -f name=^skyfleet-data$
```

Unlike `docker ps --filter name=`, Docker's `docker volume ls --filter name=` does **substring** matching, not regex — the docs state "The `name` filter matches on all or part of a volume's name." The literal characters `^` and `$` are therefore treated as part of the substring to search for, and no real volume name will ever contain them. This filter returns zero volumes even when `skyfleet-data` exists, unconditionally. `docker/MIGRATION.md` and the surrounding script comments promise this exact notice ("the old volume is announced (not deleted) so you can still recover it later") — that promise is silently broken for every user, on every run.
**Fix:**
```bash
# scripts/start_mac.sh
if docker volume inspect skyfleet-data >/dev/null 2>&1; then
```
```powershell
# scripts/start_windows.ps1 (see CR-02 for why the ErrorAction guard is required)
$PSNativeCommandUseErrorActionPreference = $false
docker volume inspect skyfleet-data 1>$null 2>$null
$OldVolumeExists = ($LASTEXITCODE -eq 0)
$PSNativeCommandUseErrorActionPreference = $true
if ($OldVolumeExists) {
```

### CR-02: `start_windows.ps1` aborts on first run under PowerShell 7.4+ instead of building the image

**File:** `scripts/start_windows.ps1:2,17`
**Issue:** The script sets `$ErrorActionPreference = "Stop"` at the top, then probes for an existing image with:

```powershell
$ImageExists = docker image inspect $ImageName 2>$null
```

On a fresh install (the primary documented flow — `planning/PLAN.md` §2: "The dispatcher runs a single Docker command (or a provided start script)"), the image does not exist yet, so `docker image inspect` exits non-zero by design — this is meant to be an expected, recoverable condition that triggers the build step below it. Since PowerShell 7.4, `$PSNativeCommandUseErrorActionPreference` defaults to `$true`, which makes any native command's non-zero exit code respect `$ErrorActionPreference`. With it set to `"Stop"`, this expected failure becomes a *terminating* error and the script exits immediately — before `docker build` ever runs. Redirecting stderr (`2>$null`) does not prevent this, since the behavior is keyed on exit code, not stderr content. This only affects `pwsh` (PowerShell 7.x), not the legacy Windows PowerShell 5.1 that ships by default, but `pwsh` is Microsoft's actively promoted install path (`winget install Microsoft.PowerShell`) and a plausible default for the developer audience running Docker on Windows.
**Fix:**
```powershell
$PSNativeCommandUseErrorActionPreference = $false
docker image inspect $ImageName 1>$null 2>$null
$ImageExists = ($LASTEXITCODE -eq 0)
$PSNativeCommandUseErrorActionPreference = $true

if ($Build -or -not $ImageExists) {
    Write-Host "Building $ImageName..."
    docker build -f docker/Dockerfile -t $ImageName .
}
```

## Warnings

### WR-01: `restoreFleetState`'s try/catch does not do what its comment claims

**File:** `tests/specs/helpers.ts:98-111`
**Issue:** Both cleanup loops wrap `request.delete(...)` in try/catch with comments claiming they "tolerate a non-2xx" response:

```ts
for (const droneId of launchedDroneIds) {
  try {
    await request.delete(`/api/fleet/missions/${droneId}`);
  } catch {
    // Tolerated — the mission may already be recalled or delivered.
  }
}
```

Playwright's `APIRequestContext.delete()` (and the rest of the fetch-style API testing methods) does not throw for non-2xx HTTP responses — it resolves normally with an `APIResponse` whose `.ok()` is `false`. The comment's stated rationale is therefore incorrect: the try/catch does nothing for the case it claims to guard against. What it actually — silently — swallows is a genuine network/transport-level failure (connection refused, timeout, DNS failure), which is exactly the kind of test-infrastructure problem that should be visible, not hidden, since it can mask real failures in `afterEach` cleanup and cause the *next* spec to fail for an unrelated, undiagnosed reason.
**Fix:** Either drop the try/catch (a non-2xx from an already-recalled/removed target is silently accepted since the response isn't awaited for `.ok()`), or replace it with an explicit tolerance check and surface real transport errors:
```ts
for (const droneId of launchedDroneIds) {
  const res = await request.delete(`/api/fleet/missions/${droneId}`);
  if (!res.ok() && res.status() !== 404) {
    console.warn(`restoreFleetState: unexpected recall failure for ${droneId}: ${res.status()}`);
  }
}
```

### WR-02: `readBattery` in `fresh-start.spec.ts` uses an unscoped `tr` locator that a sibling spec explicitly warns against

**File:** `tests/specs/fresh-start.spec.ts:14-17,55-58`
**Issue:**
```ts
async function readBattery(page: import("@playwright/test").Page, droneId: string) {
  const row = page.locator("tr", { has: page.getByText(droneId, { exact: true }) });
  return row.locator("td").nth(1).innerText();
}
```
called against `"FALCON-01"` — the same drone `pickIdleDrone()` in `helpers.ts` picks first, and the one the mocked chat scenario (`chat.spec.ts`, which sorts before this file) launches by default. `missions.spec.ts:49-51` explicitly documents this exact hazard in its own comments: "the roster panel also has a `<tr>` containing this drone id, and an unscoped locator would match both, tripping Playwright's strict mode" — and scopes its own row lookup to the Missions panel specifically to avoid it. `readBattery` here has no such scoping: if FALCON-01 is left `en_route` when this spec runs (e.g. a prior CI run aborted mid-test before its `afterEach` cleanup completed), the missions table would render a second `<tr>` containing "FALCON-01", and this locator would throw a Playwright strict-mode violation instead of a clear diagnostic — turning an unrelated leftover-state problem into a confusing failure in the one spec that's supposed to be resilient to prior state.
**Fix:** Scope to the roster table the same way `visualization.spec.ts` scopes to it by its unique column header, e.g.:
```ts
async function readBattery(page: Page, droneId: string) {
  const rosterTable = page.locator("table", { has: page.getByText("Battery Trend", { exact: true }) });
  const row = rosterTable.locator("tr", { has: page.getByText(droneId, { exact: true }) });
  return row.locator("td").nth(1).innerText();
}
```

---

_Reviewed: 2026-08-14T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
