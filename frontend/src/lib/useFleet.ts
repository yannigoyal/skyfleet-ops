"use client";

import { useCallback, useEffect, useState } from "react";
import { getFleet, getFleetHistory, getRoster } from "./api";
import type { BudgetSnapshot, FleetStatus, RosterEntry } from "@/types/fleet";

const EMPTY_FLEET: FleetStatus = {
  energy_budget_kwh: 0,
  remaining_kwh: 0,
  active_mission_count: 0,
  missions: [],
};

/**
 * Polls the fleet REST endpoints. Missions and budget change only on dispatch
 * or the backend's 30s snapshot loop, so polling is enough — live per-drone
 * data comes from the SSE stream instead.
 */
export function useFleet(pollMs = 5000) {
  const [fleet, setFleet] = useState<FleetStatus>(EMPTY_FLEET);
  const [history, setHistory] = useState<BudgetSnapshot[]>([]);
  const [roster, setRoster] = useState<RosterEntry[]>([]);

  const refresh = useCallback(async () => {
    const [fleetResult, historyResult, rosterResult] = await Promise.allSettled([
      getFleet(),
      getFleetHistory(),
      getRoster(),
    ]);
    if (fleetResult.status === "fulfilled") setFleet(fleetResult.value);
    if (historyResult.status === "fulfilled") setHistory(historyResult.value);
    if (rosterResult.status === "fulfilled") setRoster(rosterResult.value);
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, pollMs);
    return () => clearInterval(timer);
  }, [refresh, pollMs]);

  return { fleet, history, roster, refresh };
}
