"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { FleetStatus, Mission, RosterDrone } from "@/types/fleet";

/**
 * Owns fleet-wide state shared across the operator console: energy budget,
 * the accumulated missions map, the roster, and the selected drone.
 *
 * - D-01: a single Context provider is the sole `GET /api/fleet` reader —
 *   every consumer goes through `useFleetOps()` instead of fetching directly.
 * - D-02: state refreshes on a 5s interval poll AND immediately after any
 *   mutating action (dispatch, recall, chat) via the same `refetch()`.
 * - D-04: `selectedDroneId` lives here as plain client state, no URL sync.
 */

const FLEET_POLL_INTERVAL_MS = 5000;

export function mergeMissions(
  prev: Map<string, Mission>,
  activeFromPoll: Mission[],
): Map<string, Mission> {
  const next = new Map(prev);
  const activeIds = new Set(activeFromPoll.map((mission) => mission.id));
  for (const mission of activeFromPoll) next.set(mission.id, mission);
  for (const [id, mission] of next) {
    if (mission.status === "en_route" && !activeIds.has(id)) {
      next.set(id, { ...mission, status: "delivered" });
    }
  }
  return next;
}

interface FleetOpsState {
  energyBudgetKwh: number | null;
  remainingKwh: number | null;
  activeMissionCount: number | null;
  missions: Mission[];
  roster: RosterDrone[];
  selectedDroneId: string | null;
  select: (droneId: string | null) => void;
  loaded: boolean;
  refetch: () => Promise<void>;
  upsertMission: (mission: Mission) => void;
}

const FleetOpsContext = createContext<FleetOpsState | null>(null);

export function FleetOpsProvider({ children }: { children: ReactNode }) {
  const [budget, setBudget] = useState<{
    energyBudgetKwh: number | null;
    remainingKwh: number | null;
    activeMissionCount: number | null;
  }>({ energyBudgetKwh: null, remainingKwh: null, activeMissionCount: null });
  const missionsRef = useRef<Map<string, Mission>>(new Map());
  const [missions, setMissions] = useState<Mission[]>([]);
  const [roster, setRoster] = useState<RosterDrone[]>([]);
  const [selectedDroneId, setSelectedDroneId] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  // Monotonic counter guarding against out-of-order GET /api/fleet
  // resolution (RESEARCH.md Pitfall 2): the interval poll and an
  // action-triggered refetch can both be in flight at once, and network
  // timing offers no guarantee the one issued first resolves first. Only
  // the result of the most-recently-issued call is applied to state; an
  // older call's response, however late it arrives, is discarded rather
  // than rolling the budget/mission state backward.
  const latestRequestIdRef = useRef(0);

  const upsertMission = useCallback((mission: Mission) => {
    missionsRef.current = new Map(missionsRef.current).set(mission.id, mission);
    setMissions(Array.from(missionsRef.current.values()));
  }, []);

  const refetch = useCallback(async () => {
    const requestId = ++latestRequestIdRef.current;
    const [fleetRes, rosterRes] = await Promise.all([
      fetch("/api/fleet"),
      fetch("/api/roster"),
    ]);
    const fleetData: FleetStatus = await fleetRes.json();
    const rosterData: { drones: RosterDrone[] } = await rosterRes.json();

    if (requestId !== latestRequestIdRef.current) return;

    setBudget({
      energyBudgetKwh: fleetData.energy_budget_kwh,
      remainingKwh: fleetData.remaining_kwh,
      activeMissionCount: fleetData.active_mission_count,
    });
    missionsRef.current = mergeMissions(missionsRef.current, fleetData.missions);
    setMissions(Array.from(missionsRef.current.values()));
    setRoster(rosterData.drones);
    setLoaded(true);
  }, []);

  useEffect(() => {
    refetch();
    const id = setInterval(refetch, FLEET_POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [refetch]);

  return (
    <FleetOpsContext.Provider
      value={{
        ...budget,
        missions,
        roster,
        selectedDroneId,
        select: setSelectedDroneId,
        loaded,
        refetch,
        upsertMission,
      }}
    >
      {children}
    </FleetOpsContext.Provider>
  );
}

export function useFleetOps() {
  const ctx = useContext(FleetOpsContext);
  if (!ctx) throw new Error("useFleetOps must be used within FleetOpsProvider");
  return ctx;
}
