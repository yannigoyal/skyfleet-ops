import type { APIRequestContext } from "@playwright/test";

export interface FleetStatus {
  energy_budget_kwh: number;
  remaining_kwh: number;
  active_mission_count: number;
  missions: { drone_id: string; zone: string; status: string }[];
}

export interface RosterEntry {
  drone_id: string;
  status?: string;
}

const UNSAFE_STATUSES = new Set(["offline", "low_battery"]);

export async function getFleet(request: APIRequestContext): Promise<FleetStatus> {
  const response = await request.get("/api/fleet");
  return response.json();
}

export async function getRoster(request: APIRequestContext): Promise<RosterEntry[]> {
  const response = await request.get("/api/roster");
  return (await response.json()).drones;
}

/** A roster drone that is idle and telemetry-safe, so a launch will be accepted. */
export async function pickLaunchableDrone(
  request: APIRequestContext,
  exclude: string[] = [],
): Promise<string> {
  const [roster, fleet] = await Promise.all([getRoster(request), getFleet(request)]);
  const busy = new Set(fleet.missions.map((mission) => mission.drone_id));
  const candidate = roster.find(
    (entry) =>
      !busy.has(entry.drone_id) &&
      !exclude.includes(entry.drone_id) &&
      !UNSAFE_STATUSES.has(entry.status ?? ""),
  );
  if (!candidate) throw new Error("no launchable drone available");
  return candidate.drone_id;
}

/** Best-effort teardown — tests share one server, so they clean up after themselves. */
export async function recallIfActive(request: APIRequestContext, droneId: string): Promise<void> {
  await request.delete(`/api/fleet/missions/${encodeURIComponent(droneId)}`);
}

export async function removeFromRosterIfPresent(
  request: APIRequestContext,
  droneId: string,
): Promise<void> {
  await request.delete(`/api/roster/${encodeURIComponent(droneId)}`);
}
