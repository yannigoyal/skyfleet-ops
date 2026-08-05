# Mission System Notes

Research notes on mission planning/deconfliction practices in the drone industry (UTM standards, delivery operators), applied to SkyFleet Ops's atomic single-leg mission model (PLAN.md §3, §7). This explains why the simplified model is deliberate and where real-world practice would diverge if this were a production system.

## 1. Industry Context

- **ASTM F3548-21 (UTM USS Interoperability)** is the reference standard real drone delivery operators (e.g., Wing) use for strategic deconfliction: operators declare intended flight volumes ahead of time, a UTM system checks for conflicts with other operators' declared volumes, and only a cleared operation is allowed to launch. This is the industry answer to "how do multiple fleets share airspace safely."
- **Real fleets track mission state machines with many phases**: planned → cleared → airborne → en route → delivering → returning → landed, each with its own telemetry and possible abort/replan points.
- **Multi-leg and re-routing logic** (diverting an in-flight drone to a new target, chaining deliveries) is common in production dispatch systems and is the single biggest source of complexity in real fleet software — it requires live conflict-checking against every other active flight, not just budget math.

## 2. Why SkyFleet Ops Deliberately Simplifies This

PLAN.md §3 already states the rationale plainly: *"Mission launches are atomic ... eliminates partial dispatch, en-route re-routing, and multi-leg logic — dramatically simpler fleet math."* This is the correct call for a single-operator simulated fleet with no other airspace users:

- There's only one operator and no shared airspace, so **strategic deconfliction (ASTM F3548) doesn't apply** — there's nothing to deconflict against.
- Missions have exactly two states worth persisting mid-flight — `en_route` and terminal (`delivered`/`recalled`) — instead of a multi-phase state machine, because the simulator doesn't model intermediate flight phases (taxi, climb, cruise, descent) as distinct dispatchable states.
- One active mission per drone (schema: one live row per in-flight drone) avoids needing a mission queue or scheduler.

**Do not** introduce UTM-style conflict-checking, multi-leg routing, or a richer state machine unless the spec changes — it would be solving a problem this system doesn't have.

## 3. What the Simplified Model Still Needs to Get Right

Even in the simplified model, a few things map directly from real practice and are worth being careful about:

- **Energy budget is the actual constraint**, standing in for battery/airspace/regulatory limits in a real system. The validation on launch (`energy_cost_kwh <= remaining budget`) is doing the job that flight-clearance checks do in production — treat it with the same rigor (always validate server-side, never trust a client- or LLM-provided budget number).
- **Append-only audit trail**: `mission_log` mirrors the "every flight must be traceable to pilot/aircraft/job" principle from fleet management best practice — it's what lets you answer "what happened to FALCON-04 at 14:32" after the fact. Keep `missions` (current state) and `mission_log` (history) as separate concerns; don't let log-writing logic leak into places that only need current state.
- **Recall must be safe against races**: since telemetry updates roughly every 500ms independent of mission actions, a recall (`DELETE /api/fleet/missions/{drone_id}`) needs to check the drone still has an `en_route` mission at the moment of recall — the operator (or LLM) may be acting on slightly stale fleet state.
- **ETA is derived, not stored precision**: distance_km and typical cruise speed are enough to estimate ETA for the missions table; no need for a routing engine or waypoint list, consistent with the "atomic" model.

## 4. If Multi-Fleet or Multi-Operator Ever Becomes a Real Requirement

Not in scope now, but worth knowing where the seams already are: the schema's `operator_id` column (defaulted to `"default"` everywhere) is exactly the seam PLAN.md calls out for future multi-tenant support. If real deconfliction were ever needed, it would sit as a new check between "operator requests launch" and "mission row is written" — the atomic single-leg mission model itself wouldn't need to change, just gain a conflict check.

## Sources

- [ASTM F3548-21 - UAS Traffic Management USS Interoperability Standard](https://standards.iteh.ai/catalog/standards/astm/2ba343ae-6e89-454b-a102-e7dcb3369aee/astm-f3548-21)
- [Standards Support Drone Operations and Airspace Management | ASTM](https://www.astm.org/news/standards-support-drone-operations-and-airspace-management-ja22)
- [Unlocking Scalable Drone Operations: ANRA Technologies' UTM Services Approved by FAA](https://www.anratechnologies.com/home/2025/02/06/unlocking-scalable-drone-operations-anra-technologies-utm-services-approved-by-faa/)
- [Service-Based Drone Delivery (arXiv)](https://arxiv.org/pdf/2201.00277)
