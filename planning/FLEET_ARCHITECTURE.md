# Fleet Architecture Notes

Research notes on telemetry/fleet architecture patterns (MAVLink, ground control stations, multi-drone coordination), applied to SkyFleet Ops's telemetry cache design (PLAN.md §6, `planning/TELEMETRY_SUMMARY.md`). This is background for why the shared-cache/SSE approach was chosen and what to preserve as the real telemetry path (MAVLink gateway) gets built.

## 1. Industry Patterns Observed

- **MAVLink is the de facto protocol** for PX4/ArduPilot telemetry and command — position, altitude, speed, battery, and mode changes flow over it in both directions. It's designed to scale from single consumer drones to large coordinated fleets, which is why PLAN.md's MAVLink gateway option (§6) is a reasonable "real hardware" path rather than a toy integration.
- **REST-polling gateways over raw MAVLink sockets** are a common simplification in fleet backends that don't need sub-100ms control latency: a bridge service speaks MAVLink to the aircraft and exposes a JSON REST/polling API to the rest of the stack. This avoids every backend service needing a MAVLink parser and works across arbitrary network boundaries (cloud backend, drone on a cellular link). SkyFleet Ops's `MAVLINK_GATEWAY_URL` design already follows this pattern rather than embedding a MAVLink client directly.
- **Ground control stations (e.g., QGroundControl) separate concerns** into: a telemetry ingest layer, a shared "current state" store, and N independent consumers (map view, mission planner, alerts) that all read from that shared store rather than each parsing the wire protocol themselves. This is the same shape as SkyFleet Ops's telemetry cache → SSE fan-out design.
- **Multi-drone coordination systems model correlated behavior** (formation flying, shared weather/terrain effects) rather than treating each aircraft as fully independent — this validates PLAN.md's requirement that the simulator correlate battery drain within a squadron rather than generating fully independent noise per drone.

## 2. Why the Shared Cache + SSE Design Is the Right Call Here

- **One producer, many consumers**: exactly one background task (simulator loop or MAVLink poller) should ever write telemetry. Every SSE connection reads from the same in-memory cache rather than each opening its own simulator/poller instance — this matches the GCS pattern above and is the only way telemetry stays consistent across multiple browser tabs.
- **Interface parity between simulator and gateway is the actual hard requirement**, not a nice-to-have: both must produce identical shaped readings (drone_id, battery_pct, altitude_m, speed_kmh, status, timestamp, battery_direction) so that SSE streaming, the frontend, and tests written against `LLM_MOCK`/simulator mode keep working unchanged if `MAVLINK_GATEWAY_URL` is ever set. Any new field added to one implementation must be added to both.
- **SSE, not WebSockets, is sufficient and simpler**: telemetry is one-way (server→client); the only bidirectional actions (launch/recall/chat) are already normal REST POST/DELETE calls, not part of the telemetry stream. Don't blend mission commands into the SSE channel — keep it read-only.
- **Correlated drain (OU-style) beats independent-per-drone noise**: real fleets under shared conditions (weather cells, mission profiles) drain together; fully independent random walks per drone would look artificial on the dashboard and undercut the "live ops console" feel PLAN.md is going for.

## 3. Things to Watch as the MAVLink Gateway Path Gets Built

- **Polling interval mismatch**: the simulator ticks at ~500ms; a real MAVLink gateway may only be pollable at a coarser interval (e.g., 1–2s) depending on the bridge implementation. The telemetry cache should tolerate stale reads gracefully (reuse last known reading) rather than assuming a fixed cadence — SSE consumers already only care about "latest known state," not a guaranteed tick rate.
- **Partial fleet responses**: a real gateway may return telemetry for a subset of drones (one offline, one out of range). The cache/merge logic should update only the drones present in a given poll response, not treat a partial response as "the whole fleet went stale."
- **Failure isolation**: if the MAVLink gateway becomes unreachable, that should degrade to "stale telemetry with a connection-status indicator," not crash the SSE stream for connected clients — this is exactly what the frontend's green/yellow/red connection dot (PLAN.md §2) is meant to communicate.

## Sources

- [MAVLink vs MAVSDK vs PyMAVLink: What to Use for Drone App and Telemetry Integration](https://wezom.com/blog/mavlink-vs-mavsdk-vs-pymavlink-for-drone-telemetry-integration)
- [MAVLink in Drones: What It Means & Where It's Used - Fly Eye](https://www.flyeye.io/drone-acronym-mavlink/)
- [GitHub - alireza787b/mavsdk_drone_show: Open-source MAVLink fleet operations for PX4](https://github.com/alireza787b/mavsdk_drone_show)
- [MAV-Link-Based Control and Coordination of a Multi-Drone Cluster](https://www.researchgate.net/publication/383796453_MAV-Link-Based_Control_and_Coordination_of_a_Multi-Drone_Cluster_for_Intelligence_Surveillance_and_Reconnaissance_Tasks)
