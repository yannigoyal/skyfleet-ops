---
phase: 03
slug: frontend-buildout
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-13
---

# Phase 03 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| npm registry → developer machine / lockfile | Third-party package code executes at install time (lifecycle scripts) and at test time | Executable package code |
| Existing frontend source → test runner | Test config controls which files Vitest walks and executes | Test file discovery glob |
| Browser → backend REST API (`/api/*`) | Unauthenticated same-origin calls; the backend is the only validation authority | Mission/roster/telemetry/chat requests |
| Operator free-text input (zone, chat message) → DOM and → backend | Untrusted operator-authored strings cross into both render and persistence | Free-text strings |
| Backend error/response bodies → DOM | `detail.reason`, mission fields, telemetry numerics, and LLM `message` text are rendered directly | Reason codes, numerics, LLM-generated text |
| Client-inferred mission status → operator's mental model | The `delivered` status is derived from a polling delta, not asserted by the server | Inferred state label |
| SSE telemetry stream → client memory | An unbounded server-driven event stream accumulates into client-side arrays | Battery/altitude/speed history |
| Colour encoding → operator's criticality judgement | Battery criticality is communicated visually to a human making dispatch decisions | Heatmap fill colour |
| AI-proposed action outcomes → operator's belief about fleet state | Confirmation cards are the only signal that an AI action did or did not execute | `missions` / `roster_changes` / `errors` arrays |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-03-SC | Tampering | `npm install --save-dev jsdom @testing-library/jest-dom @vitejs/plugin-react` | high | mitigate | Blocking human checkpoint verified each package's registry page, source repo, and download volume before install; versions pinned to the exact ones checked. Checkpoint approved by operator before Task 2 ran. | closed |
| T-03-01 | Elevation of Privilege | Vitest `test.include` glob | low | mitigate | `vitest.config.ts` restricts `include` to `src/**/*.{test,spec}.{ts,tsx}` — verified present. | closed |
| T-03-02 | Information Disclosure | Test harness config files committed to git | low | accept | `vitest.config.ts`/`vitest.setup.ts` contain no secrets, endpoints, or credentials. | closed |
| T-03-03 | Tampering | `DispatchBar` zone field rendered into the DOM and echoed back from mission responses | medium | mitigate | Plain JSX text child only; `grep -rn dangerouslySetInnerHTML frontend/src` returns no matches. | closed |
| T-03-04 | Tampering | `distance_km` number input reaching display and POST body | medium | mitigate | Backend rejects non-positive values (Pydantic `gt=0`) and guards `isfinite`; client formats echoed numerics with `.toFixed(n)`. | closed |
| T-03-05 | Elevation of Privilege | Client-side eligibility/budget logic in `DispatchBar` | high | mitigate | No client-side pre-submit eligibility/budget gate exists (verified: `DispatchBar.tsx` docstring states "no client-side eligibility/budget/roster re-validation is duplicated here"); backend `missions/service.py` remains sole authority. | closed |
| T-03-06 | Information Disclosure | Backend error `detail` body rendered inline | low | accept | Only a reason key plus `requested_kwh`/`remaining_kwh` — data already visible in the header. No stack traces or internal identifiers. | closed |
| T-03-07 | Denial of Service | 5s interval poll against `GET /api/fleet` | low | accept | Single-operator local demo; `clearInterval` on unmount prevents leaked timers. | closed |
| T-03-08 | Spoofing | No authentication on `/api/fleet/missions` | low | accept | Authentication explicitly out of scope project-wide (REQUIREMENTS.md); ASVS V2 recorded not applicable. | closed |
| T-03-09 | Tampering | Zone free-text cell in `MissionsTable` | medium | mitigate | Plain JSX text child, `truncate max-w-[12rem]`, full value only via `title` attribute; no raw-HTML injection prop present. | closed |
| T-03-10 | Tampering | Numeric mission fields rendered into table cells | low | mitigate | Formatted via `.toFixed(n)`; backend guards `isfinite` at the write path. | closed |
| T-03-11 | Repudiation | Client-inferred `delivered` status | medium | mitigate | Recorded as explicit judgment-tier prohibition; human-confirmed in UAT (Test 9: status labels read as informational, not an overclaimed server assertion). Long-term fix (backend all-statuses endpoint) documented for a later phase. | closed |
| T-03-12 | Elevation of Privilege | Recall path bypassing validation | high | mitigate | Recall issues a plain `DELETE`; no client-side "is this drone recallable" check exists (verified via code review — `DispatchBar.submit()` has no pre-check); `missions/service.recall_mission` remains sole authority. | closed |
| T-03-13 | Denial of Service | Unbounded mission accumulation over a long session | low | accept | Grows only with real dispatch actions in a single-operator demo; table's internal scroll bounds the rendered DOM. | closed |
| T-03-14 | Denial of Service | Unbounded telemetry history growth in `useTelemetryStream` | medium | mitigate | All three series (battery/altitude/speed) share one push-then-shift cap at `maxHistoryPoints` — verified `grep -c maxHistoryPoints` = 6 (2 references × 3 series). | closed |
| T-03-15 | Tampering | Telemetry numerics rendered as detail-panel readouts | low | mitigate | Formatted via `.toFixed(n)`; chart series are numeric arrays, never interpolated into markup. | closed |
| T-03-16 | Repudiation | Stale telemetry shown for a drone that has left the fleet | medium | mitigate | Detail panel checks snapshot membership before rendering, shows "Drone offline or removed from roster" otherwise; human-confirmed in UAT (Test 5, pass). | closed |
| T-03-17 | Information Disclosure | Drone identifiers rendered in chart labels and readouts | low | accept | Non-sensitive fleet labels already displayed throughout the console via unauthenticated endpoints. | closed |
| T-03-18 | Tampering | Non-finite `energy_cost_kwh` or `remaining_kwh` reaching chart geometry | medium | mitigate | Every heatmap weight floored at `IDLE_HEATMAP_WEIGHT_KWH`; displayed numerics formatted via `.toFixed(n)` — verified present in `FleetHeatmap.tsx`. | closed |
| T-03-19 | Tampering | Drone id rendered inside the Treemap's SVG subtree | medium | mitigate | Ids rendered as SVG `text` children via JSX interpolation (React-escaped); cell renderer contains only `g`/`rect`/`text` primitives; no `dangerouslySetInnerHTML` present. | closed |
| T-03-20 | Repudiation | Colour-only criticality signalling | medium | mitigate | Recorded as explicit judgment-tier prohibition; human-confirmed in UAT (Test 10, pass) — battery percentage rendered as SVG text in every legible cell. | closed |
| T-03-21 | Denial of Service | Second polling loop from `EnergyBudgetChart` alongside the provider's | low | accept | One additional 5s GET against a local SQLite-backed endpoint; unmount guard (`cancelled` flag + `AbortController`) prevents leaked closures. | closed |
| T-03-22 | Information Disclosure | Budget history exposed without authentication | low | accept | `GET /api/fleet/history` is an existing unauthenticated endpoint; authentication out of scope project-wide, ASVS V4 recorded not applicable. | closed |
| T-03-23 | Tampering | LLM `message` text and operator input rendered in `ChatMessage` | high | mitigate | Every message string rendered as a plain JSX text child; no `dangerouslySetInnerHTML` under `src/components/chat/` — verified via grep. | closed |
| T-03-24 | Tampering | Multi-byte text truncation in the transcript | medium | mitigate | Assistant content never truncated; zone-field truncation (the only truncation used) is CSS ellipsis on a max-width, never byte/index arithmetic. | closed |
| T-03-25 | Repudiation | A failed AI action presented as executed | high | mitigate | Only entries the backend actually returned in `missions`/`roster_changes` carry a success badge; every `errors` string renders its own failure card. Judgment-tier prohibition, human-confirmed in UAT (Test 11, pass). | closed |
| T-03-26 | Elevation of Privilege | AI-issued actions bypassing dispatch validation | high | mitigate | Frontend only renders backend-returned arrays; no direct dispatch call exists in the chat path — verified via grep (`fetch("/api/fleet/missions"` absent from `lib/useChat.ts` and `components/chat/*`). Server-side enforcement (AST import-boundary test, two-database differential test) is Phase 2's existing contract. | closed |
| T-03-27 | Information Disclosure | Chat transport error surfaced to the operator | low | mitigate | Transport-failure path renders a fixed copy string (`TRANSPORT_ERROR_COPY`), never the raw exception, response body, or request URL — verified present in `useChat.ts`. | closed |
| T-03-28 | Denial of Service | Rapid repeated chat sends | low | mitigate | `sending` flag guards the request body; a second send while in flight is a no-op — verified present in `useChat.ts`. Backend additionally caps `message` at 4000 characters. | closed |

*Status: open · closed · open — below {block_on} threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-03-01 | T-03-02 | Test harness config files contain no secrets/endpoints/credentials | Phase 03 planner | 2026-08-13 |
| R-03-02 | T-03-06 | Backend error body exposes only data already visible in the header | Phase 03 planner | 2026-08-13 |
| R-03-03 | T-03-07 | Single-operator local demo; polling load is trivial and unmount-safe | Phase 03 planner | 2026-08-13 |
| R-03-04 | T-03-08 | Authentication explicitly out of scope project-wide (REQUIREMENTS.md) | Phase 03 planner | 2026-08-13 |
| R-03-05 | T-03-13 | Bounded by session length and internal table scroll in a single-operator demo | Phase 03 planner | 2026-08-13 |
| R-03-06 | T-03-17 | Drone ids are non-sensitive labels already exposed via unauthenticated endpoints | Phase 03 planner | 2026-08-13 |
| R-03-07 | T-03-21 | One additional low-frequency GET against a local backend; unmount-guarded | Phase 03 planner | 2026-08-13 |
| R-03-08 | T-03-22 | Existing unauthenticated endpoint; this phase adds a consumer, not new exposure | Phase 03 planner | 2026-08-13 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-13 | 29 | 29 | 0 | Claude (gsd-secure-phase, orchestrator L1 grep-depth — register_authored_at_plan_time: true, asvs_level: 1, short-circuit per workflow step 3) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-13
