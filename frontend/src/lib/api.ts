import type {
  BudgetSnapshot,
  ChatResponse,
  FleetStatus,
  Mission,
  RosterEntry,
} from "@/types/fleet";

/** Thrown for any non-2xx API response; `reason` is the backend's error code. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly reason?: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const reason = body?.detail?.reason ?? body?.detail ?? response.statusText;
    throw new ApiError(String(reason), response.status, body?.detail?.reason);
  }
  return body as T;
}

export const getFleet = () => request<FleetStatus>("/api/fleet");

export const getFleetHistory = () =>
  request<{ snapshots: BudgetSnapshot[] }>("/api/fleet/history").then((r) => r.snapshots);

export const launchMission = (droneId: string, zone: string, distanceKm: number) =>
  request<Mission>("/api/fleet/missions", {
    method: "POST",
    body: JSON.stringify({ drone_id: droneId, zone, distance_km: distanceKm }),
  });

export const recallMission = (droneId: string) =>
  request<Mission>(`/api/fleet/missions/${encodeURIComponent(droneId)}`, { method: "DELETE" });

export const getRoster = () =>
  request<{ drones: RosterEntry[] } | RosterEntry[]>("/api/roster").then((body) =>
    Array.isArray(body) ? body : body.drones,
  );

export const addDrone = (droneId: string) =>
  request<unknown>("/api/roster", { method: "POST", body: JSON.stringify({ drone_id: droneId }) });

export const removeDrone = (droneId: string) =>
  request<unknown>(`/api/roster/${encodeURIComponent(droneId)}`, { method: "DELETE" });

export const sendChatMessage = (message: string) =>
  request<ChatResponse>("/api/chat", { method: "POST", body: JSON.stringify({ message }) });
