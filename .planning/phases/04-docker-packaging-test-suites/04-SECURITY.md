---
phase: 04
slug: docker-packaging-test-suites
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-14
---

# Phase 04 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Repository working tree → Docker daemon | Whole build context is uploaded before `COPY` filtering; `.env` holding the real `OPENROUTER_API_KEY` lives in that tree | Credentials (mitigated via `.dockerignore`) |
| Host filesystem → container | Bind mount grants the containerized process read/write access to a host directory | Operator's SQLite data |
| Docker-managed volume → bind mount | Storage-location cutover across which previously written operator data can become unreachable | Operator's SQLite data |
| Container stdout → operator terminal | Application and script output read by a human as ground truth about system state | Lifecycle log lines only |
| Existing test suites → requirement-satisfaction claims | A green run is converted into "this requirement is met," a claim later readers rely on without re-deriving | Test-pass claims |
| Test process → external network | `backend/tests/chat/test_live_smoke.py` could reach the real OpenRouter endpoint with the real API key if not deselected | API credentials |
| E2E harness container → app container | Test traffic crosses the compose network into the same production image the start scripts run | HTTP requests, mock LLM responses |
| Repository `.env` → test app container | Test compose supplies its own environment rather than the operator's real credentials | API credentials (isolated) |
| host network → test app container | A published host port would expose the mock-mode app (seeded database, mutation endpoints) on every host interface for the duration of a suite run | Seeded fleet/mission data |
| start script → local container HTTP | Scripts poll `http://localhost:8000/api/health` on a container started with `--env-file .env`; response content must not reach terminal scrollback or CI logs | Health-check response |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-04-01 | Information Disclosure | `docker build` context upload | high | mitigate | `.dockerignore` excludes `.env`, `.env.local`, `database/*.db*`, `.git`, `node_modules`, `frontend/.next`, `backend/.venv`, `.planning`, `.claude` — verified all 9 entries present, all build entry points use repo root as context | closed |
| T-04-02 | Information Disclosure | Container stdout | low | accept | App logs only lifecycle strings (`backend/app/main.py:72,79`); on key-load failure only the key's *name* is logged, never its value | closed |
| T-04-03 | Denial of Service | Orphaned `skyfleet-data` volume | medium | mitigate | `docker/MIGRATION.md` documents WAL-checkpoint-and-copy recovery; both start scripts print an operator-visible notice; no script runs `docker volume rm` | closed |
| T-04-04 | Tampering | Stale image reuse | medium | mitigate | Verification commands pass `--build`/`--no-cache` explicitly; confirmed in `04-01-SUMMARY.md` and UAT Test 1 | closed |
| T-04-05 | Elevation of Privilege | Bind mount container→host | low | accept | Mount source derived from script's own `$ROOT_DIR`/`$RootDir`, never operator input or env var | closed |
| T-04-06 | Tampering | Dependency supply chain (04-01) | low | accept | No package-manager install introduced by this plan — git-verified, no manifest changed | closed |
| T-04-07 | Tampering | Test suites under audit | high | mitigate | Deletion/skip/loosening prohibited; `git diff --numstat` shows zero deleted lines in pre-existing test files across the whole phase; baselines re-measured (300 backend / 81 frontend) | closed |
| T-04-08 | Information Disclosure | Live-smoke test reaching real OpenRouter | medium | mitigate | `addopts = "-m 'not live'"` in `backend/pyproject.toml` deselects the live suite; deselected count confirmed nonzero | closed |
| T-04-09 | Repudiation | Requirement-satisfaction claim | medium | mitigate | Each TEST-01/02/03 noun mapped to a named, read test function in `04-02-SUMMARY.md`; no gaps found | closed |
| T-04-10 | Denial of Service | Suite runtime | low | accept | Combined runtime ~11.6s (7.73s backend + 3.83s frontend, per `04-02-SUMMARY.md`) — acceptance holds at this scale; original rationale's "under six seconds" figure was inaccurate and is corrected here | closed |
| T-04-11 | Information Disclosure | Test app container env | medium | mitigate | `tests/docker-compose.test.yml` supplies `LLM_MOCK=true` and a placeholder key inline; no `env_file:` key anywhere in the file, so the root `.env` is never read | closed |
| T-04-12 | Repudiation | E2E suite green signal | high | mitigate | Assertion-pinning clause verified in code (drone id + zone pinned, not bare counts). Break-then-fix clause not literally recorded (live harness was `unrun` at execution time in 04-03/04-04); closed instead on a compensating control — UAT Test 3 (live green run, twice) and UAT Test 5 (explicit human sign-off) | closed (compensating control — see note below) |
| T-04-13 | Denial of Service | Cross-spec interference | medium | mitigate | `workers: 1`, `fullyParallel: false`, `restoreFleetState` in `afterEach`, relative (not absolute) budget assertions | closed |
| T-04-14 | Tampering | Suite detection power | high | mitigate | `grep -rEn 'test\.(skip\|fixme\|only)' tests/specs/` returns nothing | closed |
| T-04-15 | Elevation of Privilege | Browser runtime in production image | low | mitigate | Declared mitigation (probe of shipped image for absent `/ms-playwright` dir and `node` binary) was never executed — recorded `status: unrun` in `04-03-SUMMARY.md`. Dockerfile inspection supports the claim (runtime stage is `python:3.12-slim` + `uv`, static frontend output copied only) but does not fully substitute for the declared runtime probe | open — below `high` threshold (non-blocking) |
| T-04-16 | Repudiation | SSE reconnect assertion | high | mitigate | No `page.reload()` between route restoration and the recovery assertion in `sse-resilience.spec.ts`; confirmed live at UAT Test 4 | closed |
| T-04-17 | Information Disclosure | Chat spec reaching real OpenRouter | medium | mitigate | Asserts assistant reply carries the mock's `[mock]` prefix; harness never reads root `.env` | closed |
| T-04-18 | Repudiation | Visualization assertions | medium | mitigate | Heatmap cells selected by the three actual battery-band fill values compared against live roster length, not a bare element count | closed |
| T-04-19 | Tampering | Suite detection power under flake pressure | high | mitigate | No skip/fixme/only/screenshot comparison; `retries` unchanged from initial commit value; timeouts carry documented cadence rationale | closed |
| T-04-20 | Denial of Service | Budget history absent when chart asserted | low | mitigate | Visualization spec creates its own snapshots via launch+recall rather than depending on prior specs | closed |
| T-04-05-01 | Information Disclosure | `wait_for_health.sh` curl invocation | low | mitigate | Runs with `-o /dev/null`, no `-v` — no response body/header echoed | closed |
| T-04-05-02 | Denial of Service | Readiness loop in start scripts | medium | mitigate | Deadline-bounded (60s); both callers treat timeout as a warning and proceed, never hang | closed |
| T-04-05-03 | Tampering | URL argument to `wait_for_health.sh` | low | accept | Built from script's own `PORT`/`$Port` constant, never external input | closed |
| T-04-05-04 | Spoofing | Localhost health poll target | low | accept | Accepted — an attacker able to bind the operator's loopback ports already has local code execution, outside this single-operator dev tool's threat model | closed |
| T-04-05-SC | Tampering | Package installs (04-05) | low | accept | No manifest touched by any 04-05 commit — git-verified | closed |
| T-04-06-01 | Information Disclosure | Test app host port publish | medium | mitigate | `tests/docker-compose.test.yml`'s `app` service has no `ports:` key — reachable only from the private Compose network | closed |
| T-04-06-02 | Denial of Service | E2E harness startup port contention | high | mitigate | Contended host-port resource removed rather than documented around; confirmed live at UAT Test 3 (harness ran alongside a running production container) | closed |
| T-04-06-03 | Tampering | `tests/README.md` operator guidance | low | accept | Corrected to name `scripts/start_mac.sh` as the real collision source (one remaining minor drift: still references `curl` for the healthcheck, which was replaced by a `python3` urllib probe — documentation-only, no exploit path) | closed |
| T-04-06-SC | Tampering | Package installs (04-06) | low | accept | `tests/package.json`/`package-lock.json` untouched by 04-06 — only 04-03's commit modified them | closed |

*Status: open · closed · open — below `high` threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (`high`) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-04-01 | T-04-02 | Lifecycle-only logging verified in `backend/app/main.py`; key-load failure logs the key's name, never its value | gsd-security-auditor | 2026-08-14 |
| AR-04-02 | T-04-05 | Bind-mount source is script-derived (`$ROOT_DIR`/`$RootDir`), never operator/env input — no path traversal surface | gsd-security-auditor | 2026-08-14 |
| AR-04-03 | T-04-06 | No package installs introduced in phase 04-01 — git-verified, no manifest changed | gsd-security-auditor | 2026-08-14 |
| AR-04-04 | T-04-10 | Combined suite runtime ~11.6s — acceptable at this scale (corrects the original plan-time estimate of "under six seconds") | gsd-security-auditor | 2026-08-14 |
| AR-04-05 | T-04-05-03 | Health-check URL built from the start script's own port constant, never external input | gsd-security-auditor | 2026-08-14 |
| AR-04-06 | T-04-05-04 | Local-port-squatting attack presupposes local code execution already, outside this single-operator dev tool's threat model | gsd-security-auditor | 2026-08-14 |
| AR-04-07 | T-04-05-SC | No dependency manifest touched by plan 04-05 — git-verified | gsd-security-auditor | 2026-08-14 |
| AR-04-08 | T-04-06-03 | `tests/README.md` guidance corrected to name the real collision source; documentation-only surface, no exploit path | gsd-security-auditor | 2026-08-14 |
| AR-04-09 | T-04-06-SC | `tests/package.json`/lockfile untouched by plan 04-06 — git-verified | gsd-security-auditor | 2026-08-14 |
| AR-04-10 | T-04-15 | Non-blocking (low severity, below `high` threshold). Declared runtime probe (image inspected for absent Playwright/Node) was never executed live — `unrun` per `04-03-SUMMARY.md` — but static Dockerfile inspection (runtime stage is `python:3.12-slim` + `uv`, no Node install, static frontend output copied only) supports the same conclusion. Carried forward as a follow-up: run the declared probe (`docker run --rm skyfleet-ops` checked for `/ms-playwright` and `node`) once a live Docker environment is available. | gsd-security-auditor | 2026-08-14 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-14 | 29 | 28 | 1 (non-blocking) | gsd-security-auditor |

**Notes on this audit:**
- The supplied threat register initially enumerated 27 rows under an "18 threats" header; the auditor additionally located and verified `T-04-05-SC` and `T-04-06-SC` from the PLAN.md `<threat_model>` blocks directly, bringing the verified total to 29.
- **Unregistered flag (non-blocking, informational):** Plan 04-03 added `typescript: "^5.6.0"` to `tests/package.json` devDependencies (commit `fac5529`) with no corresponding supply-chain threat entry in its `<threat_model>` block — unlike 04-05 (`T-04-05-SC`) and 04-06 (`T-04-06-SC`), which both explicitly registered one, and unlike this project's Phase 03 precedent, which required a blocking human checkpoint before any `npm install`. Residual risk is assessed low (first-party Microsoft package, devDependency, test-harness-only, executes inside the isolated playwright service), but it is unregistered attack surface worth noting for future phases' plan-time discipline.
- None of the six phase-04 SUMMARY.md files contains a `## Threat Flags` section — that channel provided no signal for this audit; all findings came from direct PLAN.md `<threat_model>` extraction and code verification.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed (blocking threshold: `high`; T-04-15 remains open at `low` severity, non-blocking)
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-14
