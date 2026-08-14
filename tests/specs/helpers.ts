import type { APIRequestContext, Page } from "@playwright/test";

/**
 * Shared fixtures for the E2E suite. Every spec that mutates fleet state
 * (roster, missions) imports from here so the suite can pass twice in a row
 * against the same app container with no manual reset between runs
 * (TEST-04 idempotency).
 */

interface Mission {
  id: string;
  drone_id: string;
  zone: string;
  distance_km: number;
  energy_cost_kwh: number;
  status: string;
  updated_at: string;
}

interface FleetStatus {
  energy_budget_kwh: number;
  remaining_kwh: number;
  active_mission_count: number;
  missions: Mission[];
}

interface RosterDrone {
  drone_id: string;
  [key: string]: unknown;
}

interface RosterResponse {
  drones: RosterDrone[];
}

/** GET /api/fleet — energy budget, remaining kWh, active mission count, active missions. */
export async function getFleet(request: APIRequestContext): Promise<FleetStatus> {
  const res = await request.get("/api/fleet");
  return (await res.json()) as FleetStatus;
}

/** GET /api/roster — current fleet roster with latest telemetry. */
export async function getRoster(request: APIRequestContext): Promise<RosterResponse> {
  const res = await request.get("/api/roster");
  return (await res.json()) as RosterResponse;
}

/**
 * Read the header's `{remaining} / {total} kWh` text and parse the
 * remaining figure out as a number, so callers can compare before/after
 * rather than matching a literal — the absolute figure is shared mutable
 * state that earlier specs legitimately reduce.
 */
export async function readHeaderRemainingKwh(page: Page): Promise<number> {
  const text = await page.locator("header").innerText();
  const match = text.match(/([\d.]+)\s*\/\s*[\d.]+\s*kWh/);
  if (!match) {
    throw new Error(`could not parse remaining kWh from header text: "${text}"`);
  }
  return Number(match[1]);
}

/**
 * Return the id of a roster drone that has no `en_route` mission, so a spec
 * can launch a mission without colliding with whatever an earlier spec (or
 * the mocked chat scenario) already launched. Throws a clear error if every
 * drone is busy, rather than returning an undefined selector value.
 */
export async function pickIdleDrone(request: APIRequestContext): Promise<string> {
  const [roster, fleet] = await Promise.all([getRoster(request), getFleet(request)]);
  const busy = new Set(
    fleet.missions.filter((mission) => mission.status === "en_route").map((mission) => mission.drone_id),
  );
  const idle = roster.drones.find((drone) => !busy.has(drone.drone_id));
  if (!idle) {
    throw new Error("no idle drone available — every roster drone has an active mission");
  }
  return idle.drone_id;
}

interface RestoreOptions {
  addedDroneIds?: string[];
  launchedDroneIds?: string[];
}

/**
 * Return the fleet to its pre-spec shape: recall each launched drone, then
 * remove each added drone. Tolerates a non-2xx on each individually — the
 * mission may already be recalled by the spec body, or delivered by the
 * background scheduler; the drone may already be removed. This is what
 * makes the suite re-runnable: without it, the second run starts from a
 * roster and budget the first run left behind.
 */
export async function restoreFleetState(
  request: APIRequestContext,
  { addedDroneIds = [], launchedDroneIds = [] }: RestoreOptions,
): Promise<void> {
  for (const droneId of launchedDroneIds) {
    try {
      await request.delete(`/api/fleet/missions/${droneId}`);
    } catch {
      // Tolerated — the mission may already be recalled or delivered.
    }
  }
  for (const droneId of addedDroneIds) {
    try {
      await request.delete(`/api/roster/${droneId}`);
    } catch {
      // Tolerated — the drone may already be removed.
    }
  }
}
