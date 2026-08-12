# Feature Research

**Domain:** Real-time fleet-ops / mission-control console (drone delivery) with an autonomous LLM copilot
**Researched:** 2026-08-12
**Confidence:** MEDIUM

SkyFleet Ops already has its feature list locked by `planning/PLAN.md` — this document is not "what to build" but "how to build it well," calibrated against how real fleet-ops/ATC-style dashboards and agentic copilots are structured elsewhere, and where the spec's choices (atomic missions, no-confirmation auto-execution, single operator) sit relative to industry norms.

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist in any ops-console / fleet-management product. Missing these makes it feel like a toy, not a console.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Live telemetry grid with per-unit status (battery, altitude, speed, position/zone) | Every fleet-management and mission-control tool reviewed (NASA Open MCT, Loft Orbital Cockpit, DroneDesk, commercial fleet dashboards) leads with a roster/table of live units — it's the primary "is everything OK" view | LOW (already built — telemetry phase complete) | SkyFleet's `/api/stream/telemetry` + roster panel covers this |
| Connection/health status indicator | Ops consoles are trusted only if operators know the data is live — a stale dashboard showing green is worse than an honest red | LOW | Header dot (green/yellow/red) per spec section 10 — standard SSE/EventSource pattern with native reconnect |
| Per-unit detail drill-down | Grid views are for scanning; operators always need a focused view of one unit's full history when something looks off | LOW-MEDIUM | Click-to-select detail panel per spec — matches "select from all-fleet view, drill into one" pattern seen in Fleet Command UI, Loft Orbital Cockpit |
| Resource/budget accounting visible at all times | Every dispatch decision is gated by a shared constrained resource (energy budget here); consoles that hide the constraint let operators over-commit and get surprised | LOW-MEDIUM | Header budget display + budget-over-time chart; must update atomically with every launch/recall |
| Action log / mission history table | Fleet dashboards universally include a tabular history (missions, mission control command logs, energy-consumption timelines) — it's how operators reconstruct "what happened" | LOW-MEDIUM | Missions table (drone, zone, distance, cost, status, ETA) per spec section 10 |
| Manual dispatch controls independent of AI | An AI copilot is additive, not a replacement control surface — every reviewed pattern (Microsoft Copilot, agentic UX surveys) keeps the direct manipulation UI intact alongside the conversational one | LOW | Dispatch bar (drone/zone/distance/launch/recall) already specified |
| Visual severity coding (color = health/urgency) | Universal fleet-dashboard convention: green/amber/red mapped to battery or alert severity, used for at-a-glance triage without reading numbers | LOW | Telemetry flash animations + heatmap coloring already specified; keep the 3-state semantic consistent across grid, heatmap, and sparkline |
| Fast, non-blocking chat response indicator | Any chat UI that can take >1s needs a loading/typing state or users assume it's broken | LOW | Spec already calls for a loading indicator during LLM calls (no token streaming needed given Cerebras speed) |

### Differentiators (Competitive Advantage)

Features that set SkyFleet Ops apart from a "generic telemetry dashboard." These map directly to the Core Value in PROJECT.md — the AI flight director acting as a second control surface.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| LLM copilot that can read live fleet state AND execute mission/roster changes | This is the actual differentiator of the whole project — dashboards that only "chat about" data are common; ones where the chat *is* an actuator are still rare in demo/course contexts and are the entire point of the capstone | HIGH | Requires the chat endpoint to reuse the exact same validated service-layer functions as manual dispatch (see Architecture/Pitfalls note below) so AI actions can never bypass business rules |
| Inline, structured confirmation of AI-executed actions in the chat transcript | Research on agentic UX (Microsoft Copilot guidance, "chat & confirm" patterns, audit-trail literature) converges on one rule: even when an agent auto-executes, the *result* must be shown immediately as a distinct, inspectable element (not buried in prose) | LOW-MEDIUM | Spec already requires "mission launches and roster changes shown inline as confirmations" — treat these as structured cards (action, params, before/after state), not just text the LLM wrote |
| Fleet heatmap (treemap sized by mission value, colored by battery health) | Two-dimensional visual triage (size = stakes, color = risk) is a differentiator vs. flat tables — lets an operator spot "expensive mission on a dying battery" in one glance without cross-referencing rows | MEDIUM | Needs a canvas-based charting lib (Recharts has a Treemap primitive); depends on live telemetry + mission energy cost being joined server- or client-side |
| Accumulated client-side sparklines per drone | Most dashboards show *current* state; a persistent scrolling history per unit (even if only since page load) turns a snapshot view into a trend view with near-zero backend cost | LOW-MEDIUM | Pure frontend accumulation from the SSE stream — no new backend endpoint needed, keep it in a ring buffer, cap memory growth |
| AI proactively manages roster (not just missions) | Extends the "AI as operator" story beyond dispatch into fleet composition — a step past most chat-with-your-dashboard demos, which usually only let the AI answer questions or take one class of action | MEDIUM | Same execute-through-service-layer requirement as mission actions |
| Deterministic mock-LLM mode | Not a differentiator for end users, but a differentiator for the *course capstone* use case — lets graders/CI run the full agentic flow without API cost or flakiness | LOW-MEDIUM | Already spec'd (`LLM_MOCK=true`); worth treating as a first-class code path, not an afterthought, since E2E tests depend on it |

### Anti-Features (Commonly Requested, Often Problematic)

Patterns that look attractive for this kind of product but that the research and the existing spec correctly avoid or that future contributors will be tempted to add — flagged here so they aren't accidentally reintroduced.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|------------------|-------------|
| Confirmation dialog before every AI-executed action | Standard "safe agent" advice (OWASP AI Agent Cheat Sheet, human-in-the-loop literature) says gate consequential actions behind explicit approval | Kills the "fluid, agentic" demo experience that is the entire point of this capstone; stakes are genuinely zero (simulated drones, virtual budget) so the standard enterprise-agent caution doesn't transfer | Keep auto-execution, but make the *inline confirmation card* rich enough (what/why/result) that the operator has full retroactive visibility — transparency instead of gated approval |
| Partial/multi-leg mission dispatch, en-route re-routing | Feels "more realistic" for a drone delivery simulation | Spec explicitly calls this out as a complexity trap — multiplies fleet math (partial energy accounting, mid-flight state transitions, re-validation) for a demo app where atomic missions already teach the agentic-dispatch lesson | Keep atomic launch/recall only, as spec'd |
| WebSocket bidirectional channel for chat + telemetry | Feels "more real-time" and unifies the transport | Adds reconnection/backpressure/handshake complexity for zero UX gain — chat is naturally request/response (POST + JSON), telemetry is naturally one-way (SSE); mixing them into one socket couples two unrelated concerns | SSE for telemetry (already spec'd), plain POST for chat (already spec'd) |
| Free-text LLM output parsed with regex/heuristics for actions | Feels quicker to prototype than defining a schema | Silently drops or misfires actions when the LLM phrases things unexpectedly; undermines the "AI can be trusted to act" premise the whole capstone demonstrates | Structured output / JSON schema (already spec'd) validated by Pydantic before any action executes |
| Letting the LLM call mutation logic directly (its own DB writes) | Seems simpler than routing through the same service functions as the REST API | Two code paths for "launch a mission" drift apart over time — the AI path can end up bypassing budget/validation checks the manual path enforces, which is exactly the trust failure mode the agentic-UX research warns about | LLM only *proposes* structured actions (missions/roster_changes arrays); backend executes them through the identical validated service functions the REST endpoints use, then reports success/failure back into the response |
| Full auth/multi-tenant system "since we might need it later" | Common scope-creep instinct once `operator_id` columns already exist in the schema | Explicitly out of scope per PROJECT.md — no multi-tenant use case exists for a single-operator demo; adding auth now is speculative complexity with no current requirement | Keep `operator_id="default"` hardcoded; the column exists for future extensibility, not for building auth now |
| Push notifications / alerting system (email, SMS, browser push) for low battery or mission events | Feels like a natural extension of "ops console" — real fleet tools have alerting | Not in PLAN.md scope; adds an entire notification-delivery subsystem (channels, preferences, rate limiting) to a single-page, single-session demo app | Visual alerting only (color coding, flash animations) — sufficient because the operator is always looking at the screen in this demo context |

## Feature Dependencies

```
Fleet telemetry cache + SSE stream (DONE)
    └──requires──> Fleet roster grid with live values
                       └──requires──> Per-drone sparklines (accumulated client-side)
                       └──requires──> Fleet heatmap (needs telemetry + mission energy cost joined)

SQLite schema + lazy init
    └──requires──> Fleet operations service layer (launch/recall/budget accounting)
                       └──requires──> Fleet operations REST API
                       └──requires──> LLM chat action execution (reuses same service layer, not duplicated)
                       └──requires──> Budget snapshot recording ──enhances──> Energy-budget chart

Fleet operations service layer
    └──requires──> Missions table (reads mission + mission_log state)

LLM flight-director chat
    └──requires──> Structured-output schema (missions[], roster_changes[])
    └──requires──> Fleet operations service layer (validated execution)
    └──requires──> Inline action-confirmation rendering (frontend)
    └──requires──> chat_messages persistence (conversation history for follow-up prompts)

LLM mock mode ──enhances──> E2E test suite (enables deterministic, cost-free agentic-flow tests)

Atomic mission launches ──conflicts──> Partial/multi-leg dispatch (deliberately excluded, not a phase)
```

### Dependency Notes

- **LLM chat action execution requires the fleet operations service layer to exist first, and to be the single source of truth.** This is the most important ordering constraint for the roadmap: build launch/recall/roster mutation as validated, reusable service functions *before* wiring the LLM chat endpoint to them. If chat is built first against ad hoc logic, it will need rework once the "real" service layer lands — and worse, the two paths can silently diverge on validation rules (see Anti-Features).
- **Budget snapshot recording enhances the energy-budget chart** but the chart itself only needs the `budget_snapshots` table populated on a timer (30s) and after every launch/recall — this can be built as a thin addition once mission launch/recall write paths exist, not a separate subsystem.
- **Fleet heatmap requires telemetry (already done) joined with mission energy cost (from the operations layer)** — it cannot be built before missions exist, since "size" comes from mission energy cost, not raw telemetry.
- **Atomic mission launches conflict with partial/multi-leg dispatch** — this is intentional per PLAN.md and should stay that way; do not let a future phase reintroduce re-routing as a "nice to have."
- **Inline action-confirmation rendering depends on chat responses carrying structured `missions`/`roster_changes` arrays**, not just prose — the frontend cannot build trustworthy confirmation cards from freeform text.

## MVP Definition

PLAN.md already defines full milestone scope; this maps that scope onto build-order priority for the roadmap, not a reduced feature set (nothing here should be cut from PLAN.md).

### Launch With (v1 — this milestone)

- [ ] SQLite schema + lazy init — everything downstream depends on it
- [ ] Fleet operations service layer (launch/recall/budget/roster, atomic, validated) — the single source of truth for both manual dispatch and AI actions
- [ ] Fleet operations + roster REST API — exposes the service layer to the manual dispatch bar
- [ ] LLM chat with structured output, executing through the same service layer — the core differentiator
- [ ] LLM mock mode — required for deterministic E2E tests, not optional polish
- [ ] Frontend: roster grid, detail panel, dispatch bar, missions table, chat panel with inline confirmations, header status/budget — the full console per spec section 10
- [ ] Fleet heatmap + energy-budget chart — explicitly named in spec as core visualizations, not stretch
- [ ] Docker packaging (single container, single port) — required for the "one command to run" experience
- [ ] Unit + E2E test suites — required per spec, not deferred

### Add After Validation (v1.x)

Nothing is explicitly deferred within this milestone's stated scope — PROJECT.md scopes the entire remaining platform into one milestone. If time pressure forces trade-offs mid-build, the safest things to soften first (least central to Core Value) are:
- [ ] Sparkline polish (data is accumulated regardless; visual refinement can lag)
- [ ] Heatmap interaction polish (tooltips, click-through) — the color/size encoding is the essential part, interactivity is secondary

### Future Consideration (v2+, not this milestone)

- [ ] Cloud deployment (Terraform/App Runner) — explicitly a stretch goal in PLAN.md section 11
- [ ] Auth / multi-tenant support — explicitly out of scope, schema only prepared for it
- [ ] Push/email/SMS alerting — not in spec, would need its own design pass
- [ ] Multi-leg / re-routable missions — deliberately excluded by design, revisit only if the atomic-mission constraint is ever reconsidered as a product decision, not a default extension

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Fleet operations service layer (launch/recall/budget) | HIGH | MEDIUM | P1 |
| SQLite schema + lazy init | HIGH | LOW | P1 |
| LLM chat with structured-output execution | HIGH | HIGH | P1 |
| Inline action-confirmation cards in chat | HIGH | LOW-MEDIUM | P1 |
| Roster grid + detail panel + dispatch bar | HIGH | MEDIUM | P1 |
| Missions table | MEDIUM | LOW | P1 |
| Energy-budget chart | MEDIUM | LOW-MEDIUM | P1 |
| Fleet heatmap | MEDIUM | MEDIUM | P1 |
| LLM mock mode | HIGH (for testing) | LOW-MEDIUM | P1 |
| Docker packaging | HIGH (for "one command") | MEDIUM | P1 |
| E2E test suite | HIGH (for correctness confidence) | MEDIUM-HIGH | P1 |
| Sparkline accumulation | MEDIUM | LOW | P2 |
| Roster CRUD via chat | MEDIUM | LOW (reuses service layer) | P2 |
| Cloud deployment config | LOW (for this milestone) | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch (this milestone, per PLAN.md scope)
- P2: Should have, add when possible within this milestone (small marginal cost once P1 dependencies exist)
- P3: Nice to have, explicitly deferred per PLAN.md

## Competitor / Reference Pattern Analysis

No direct commercial competitor exists for "toy drone-delivery ops console with agentic chat," so this compares against the closest reference categories: mission-control software (aerospace/satellite ops) and modern AI-copilot products.

| Feature area | Mission-control reference (NASA Open MCT, Loft Orbital Cockpit, SPACEBEL BASILES) | AI-copilot reference (Microsoft Copilot, agentic-UX surveys) | Our approach |
|---------|--------------|--------------|--------------|
| Dashboard composition | Widget-based, user-composable panels; map-centric layouts | N/A | Fixed layout per spec (roster, detail, heatmap, budget chart, missions table, chat) — appropriate for a bounded demo scope, composability is unnecessary complexity here |
| Event/action history | Command log pinned at screen bottom, sequential | Full audit trail of every tool call with params/timestamp | `mission_log` table + missions table + inline chat confirmations cover both angles: persistent log and live inline visibility |
| Resource/health visualization | Basic charts for battery/performance, limited explicit "budget" pattern found | N/A | Heatmap (size=value, color=health) + budget-over-time line chart is more sophisticated than most reviewed mission-control tools for this specific use case |
| Agent action execution | N/A (not agentic) | Converging pattern: agent proposes, user reviews via inline card, can accept/adjust/reject; consent required for consequential actions | Deliberate deviation: auto-execute (no consent gate) because stakes are zero and the demo's purpose is showing agentic capability — but inline confirmation cards are still adopted from this pattern, delivering transparency without friction |
| Business-logic reuse across surfaces | N/A | Best practice: agent and direct-manipulation UI both call the same underlying service/tool layer, never duplicate mutation logic | Directly adopted: LLM chat and manual dispatch bar both execute through one fleet-operations service layer |

## Sources

- [Mission Control Software UX Design Patterns & Benchmarking](https://uxplanet.org/mission-control-software-ux-design-patterns-benchmarking-e8a2d802c1f3) (UX Planet) — MEDIUM confidence, cross-referenced dashboard/navigation/alerting patterns across NASA Open MCT, Bright Ascension, SPACEBEL, Loft Orbital
- [Drone Fleet Command Dashboard — Mission Control UI/UX](https://dribbble.com/shots/27616773-Drone-Fleet-Command-Dashboard-Mission-Control-UI-UX) — LOW-MEDIUM confidence (design portfolio, illustrative not authoritative)
- [Fleet Command UI — Interface Design for Multi-Drone Operations](https://contra.com/p/e3RlNU7M-fleet-command-ui-interface-design-for-multi-drone-operations) — LOW-MEDIUM confidence (design case study)
- [Fleet Management Dashboard UI: A Design Guide](https://hicronsoftware.com/blog/fleet-management-dashboard-ui-design/) (Hicron Software) — MEDIUM confidence
- [UAS Fleet Management System Guide for Drone Ops](https://blog.dronedesk.io/uas-fleet-management-system/) — MEDIUM confidence
- [Designing a Production-Grade AI Chat Service with FastAPI](https://blog.masteringbackend.com/designing-a-production-grade-ai-chat-service-with-fast-api) — MEDIUM confidence, corroborated by [Agents Arcade: Building LLM apps with FastAPI — best practices](https://agentsarcade.com/blog/building-llm-apps-with-fastapi-best-practices)
- [Human-in-the-Loop AI Agents: Chat & Confirm](https://www.getmacha.com/blog/chatting-ai-agents-tool-calls-confirmations-attachments) (Macha) — MEDIUM confidence, corroborated by [Copilot Tasks: From Answers to Actions](https://www.microsoft.com/en-us/microsoft-copilot/blog/2026/02/26/copilot-tasks-from-answers-to-actions/) and [AI Copilot UX Design: How to Build Copilots Users Actually Trust](https://www.theskinsfactory.com/uiux-design-blog/ai-copilot-ux-design)
- [Plan-Then-Execute: An Empirical Study of User Trust and Team Performance When Using LLM Agents As A Daily Assistant](https://arxiv.org/pdf/2502.01390) — MEDIUM confidence (academic, cross-referenced with OWASP)
- [AI Agent Security — OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html) — MEDIUM confidence
- [AI Audit Trail: What to Log Across Prompts and Tool Calls](https://aurascape.ai/answers/ai-audit-trail/) (Aurascape) — MEDIUM confidence
- [UX in the age of copilots and agents](https://medium.com/design-bootcamp/ux-in-the-age-of-copilots-and-agents-designing-the-new-hybrid-experience-b789d4774d4f) — LOW-MEDIUM confidence (opinion/practitioner piece)
- Cross-referenced against `planning/PLAN.md` and `.planning/PROJECT.md` (project's own committed spec — treated as ground truth for scope, not an external source)

---
*Feature research for: real-time fleet-ops console + agentic LLM copilot (drone delivery domain)*
*Researched: 2026-08-12*
