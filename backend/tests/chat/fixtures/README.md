# Chat reference-dataset fixtures

Fourteen JSON files, each one canned "completion" the flight-director LLM could have returned,
replayed offline through the real `/api/chat` endpoint by `tests/chat/test_evals.py`. This is the
phase's CI gate: no network call, no judge model, deterministic assertions over executed actions,
refused actions, error text, and resulting database state.

## Governance rule

New fixtures are added only from real observed failures during live or UAT runs, never as
speculative pre-coverage (AI-SPEC §5). If a new failure mode is found, capture the exact completion
string that triggered it, reduce it to the smallest reproducing case, and add it here with a `covers`
entry naming the requirement or dimension it now pins.

## Schema

```json
{
  "id": "01-explicit-launch",
  "covers": ["D7", "D5", "CHAT-02"],
  "seed": {
    "launch": [{"drone_id": "FALCON-04", "zone": "Downtown", "distance_km": 5.0}],
    "roster_remove": []
  },
  "user_message": "Launch FALCON-03 to Riverside, 4.2 km.",
  "completion": "{\"message\": \"...\", \"missions\": [...], \"roster_changes\": [...]}",
  "expect": {
    "status": 200,
    "missions": [{"drone_id": "FALCON-03", "action": "launch"}],
    "roster_changes": [],
    "error_contains": [["FALCON-99", "launch", "unknown_drone"]],
    "mission_row_delta": 1,
    "budget_delta_kwh": -3.36,
    "chat_row_delta": 2
  }
}
```

- `id` — matches the filename stem.
- `covers` — the AI-SPEC dimension ids and/or `REQUIREMENTS.md` ids this fixture exercises.
- `seed` — state to establish before the request, applied through the real HTTP endpoints (never
  direct SQL) so seeding exercises the same code paths as the scenario itself:
  - `launch` — a list of `{drone_id, zone, distance_km}` objects, each POSTed to
    `/api/fleet/missions` before the request. Defaults to `[]`.
  - `roster_remove` — a list of drone ids DELETEd from `/api/roster/{drone_id}` before the request.
    Defaults to `[]`. None of the fourteen fixtures currently need this, but the harness supports it
    for future scenarios that seed a roster gap.
- `user_message` — the operator's chat message string, POSTed as `{"message": ...}`.
- `completion` — the raw string `litellm.acompletion` would have returned in
  `choices[0].message.content`, replayed through `stub_completion` with
  `app.chat.llm.mock_mode_enabled` forced to return `False` so it flows through the real
  `parse_reply` and execution path rather than the keyword-based `mock_reply`.
- `expect` — the assertions the harness checks after the request:
  - `status` — the HTTP status code.
  - `missions` / `roster_changes` — the executed-action lists the response should contain, compared
    to the response body as sets of `(drone_id, action)` pairs. Omitted or `[]` means none executed.
    Ignored when `status != 200` (an HTTPException body has a different shape).
  - `error_contains` — a list of lists, one inner list of required substrings per expected error
    string, positional (the first inner list must all appear in `errors[0]`, and so on). Ignored
    when `status != 200`.
  - `mission_row_delta` — change in `SELECT COUNT(*) FROM missions` between immediately after `seed`
    is applied and immediately after the request completes.
  - `budget_delta_kwh` — change in `remaining_kwh` (via `missions_repository.get_remaining_kwh`)
    over the same window. Every non-zero value here must be derived from
    `Mission.energy_cost_for(distance_km)` — never a hand-typed number — so a drift in the energy
    constant fails the fixture that assumed the old value instead of silently passing.
  - `chat_row_delta` — change in `SELECT COUNT(*) FROM chat_messages` over the same window. A
    successful turn always writes 2 (the operator's message, the assistant's reply); a turn that
    never reaches persistence (the two malformed-completion fixtures) writes 0.
  - `final_mission_status` — *optional*, `{drone_id: status}`. When present, asserts the most
    recently updated `missions` row for that drone has exactly this status after the request. Used
    by fixtures that pin a specific ordering outcome (13, 14) rather than only an aggregate delta.
  - `final_active_mission_count` — *optional*, an int asserting
    `SELECT COUNT(*) FROM missions WHERE status = 'en_route'` after the request. Same purpose as
    `final_mission_status`.

## The fourteen scenarios

| # | File | Covers |
|---|------|--------|
| 1 | `01-explicit-launch.json` | D7, D5, CHAT-02 |
| 2 | `02-recall-en-route.json` | D7, D5, CHAT-03 |
| 3 | `03-roster-add.json` | D7, CHAT-04 |
| 4 | `04-roster-remove-with-active-mission.json` | D2, CHAT-04 |
| 5 | `05-read-only-question.json` | D7, CHAT-01 |
| 6 | `06-hallucinated-drone.json` | D1, D4, CHAT-07 |
| 7 | `07-invalid-launch-arguments.json` | D1, D4, CHAT-07 |
| 8 | `08-over-budget-launch.json` | D1, D4, CHAT-07 |
| 9 | `09-recall-no-active-mission.json` | D1, D4, CHAT-07 |
| 10 | `10-non-json-completion.json` | D3, D4, CHAT-07 |
| 11 | `11-schema-violation.json` | D3, D4, CHAT-07 |
| 12 | `12-two-launches-budget-exhausted.json` | D6, D4 |
| 13 | `13-contradictory-launch-and-recall.json` | D6 |
| 14 | `14-injection-style-message.json` | D8 |
