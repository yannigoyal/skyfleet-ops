---
status: complete
phase: 01-roster-module
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md]
started: 2026-08-12T15:20:00Z
updated: 2026-08-12T15:24:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Add a drone
expected: POST /api/roster with {"drone_id": "FALCON-11"} returns 201 with the created entry and registers the drone with the TelemetrySource
result: pass
source: automated
coverage_id: D1

### 2. List roster with live telemetry
expected: GET /api/roster returns every tracked drone merged with its latest TelemetryCache reading
result: pass
source: automated
coverage_id: D2

### 3. Roster module layering (tracer)
expected: backend/app/roster/ is organized as models/service/repository/router/__init__, with the write path running router -> service -> repository, and is mounted on the real app.main:app
result: pass
source: automated
coverage_id: D3

### 4. Telemetry sync failure survives add
expected: A TelemetrySource.add_drone() failure during POST /api/roster is logged with the drone_id and the fleet_roster row stays committed
result: pass
source: automated
coverage_id: D4

### 5. Remove a drone with no active mission
expected: DELETE /api/roster/{drone_id} removes a drone with no active mission — fleet_roster row gone, no missions/mission_log changes
result: pass
source: automated
coverage_id: D1 (01-02)

### 6. Remove a drone with an active mission (auto-recall)
expected: Removing a drone with an en_route mission auto-recalls it first — mission status becomes recalled, a mission_log recall row is written, a budget_snapshots row is written
result: pass
source: automated
coverage_id: D2 (01-02)

### 7. Removal uses check-first guard, not exception-driven control flow
expected: Removal calls get_active_mission_for_drone before recall_mission (source-order proven), and roster imports only the two named functions it needs from app.missions (one-directional)
result: pass
source: automated
coverage_id: D3 (01-02)

### 8. Remove idempotency and crash-window retry
expected: A repeated DELETE for an already-removed drone returns 404 unknown_drone with no recall and no state change; a drone recalled out-of-band before DELETE still removes cleanly
result: pass
source: automated
coverage_id: D4 (01-02)

### 9. Telemetry sync failure survives remove
expected: A failing TelemetrySource.remove_drone() during DELETE is logged with the drone_id and the fleet_roster deletion stays committed
result: pass
source: automated
coverage_id: D5 (01-02)

### 10. Duplicate add returns 409
expected: POST /api/roster with a drone_id already on the roster returns 409 with {"reason": "drone_already_tracked"} and does not grow the roster
result: pass
source: automated
coverage_id: D1 (01-03)

### 11. Empty/missing drone_id returns 422
expected: POST /api/roster with an empty or missing drone_id returns 422 before any database access, and the roster is untouched
result: pass
source: automated
coverage_id: D2 (01-03)

### 12. Delete unknown drone returns 404
expected: DELETE /api/roster/{drone_id} for a never-tracked drone returns 404 with {"reason": "unknown_drone"}
result: pass
source: automated
coverage_id: D3 (01-03)

### 13. Telemetry merge response shape
expected: A roster entry with no telemetry reading returns exactly {drone_id, added_at}; one with a cached reading adds exactly the four telemetry fields
result: pass
source: automated
coverage_id: D4 (01-03)

### 14. Operator isolation
expected: A drone added under a different operator_id is invisible to both the repository listing and the GET /api/roster response
result: pass
source: automated
coverage_id: D5 (01-03)

### 15. Write routes delegate through roster.service
expected: Both POST and DELETE HTTP handlers route through roster.service rather than roster.repository directly (runtime-observable half of ROST-04)
result: pass
source: automated
coverage_id: D6 (01-03)

### 16. Concurrent duplicate add
expected: Two overlapping add_drone calls for the same new drone_id leave exactly one row; the loser raises DroneAlreadyTrackedError
result: pass
source: automated
coverage_id: D7 (01-03)

### 17. ROST-04 layering — human structural check
expected: backend/app/roster/ mirrors backend/app/missions/'s five-module shape (models, repository, service, router, __init__), and both HTTP write handlers (POST, DELETE) route through roster.service rather than calling roster.repository directly.
result: pass

## Summary

total: 17
passed: 17
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

<!-- none yet -->
