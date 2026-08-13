"use client";

import { useFleetOps } from "@/lib/FleetOpsProvider";
import type { Mission } from "@/types/fleet";

const MISSION_STATUS_LABEL: Record<string, string> = {
  en_route: "En Route",
  delivered: "Delivered",
  recalled: "Recalled",
};

/**
 * Sorts by a stable key derived from the mission fields themselves
 * (updated_at descending, tie-broken by id) rather than trusting incoming
 * array order — so a poll that returns the active list in a different
 * order can never reshuffle the table under the operator's cursor.
 */
function sortMissions(missions: Mission[]): Mission[] {
  return [...missions].sort((a, b) => {
    if (a.updated_at !== b.updated_at) return a.updated_at < b.updated_at ? 1 : -1;
    return a.id < b.id ? 1 : -1;
  });
}

/**
 * Tabular view of every mission accumulated this session (FE-05) — en_route,
 * delivered, and recalled alike, since FleetOpsProvider's mergeMissions()
 * never drops a mission once seen. Mirrors FleetRosterPanel's table idiom
 * (panel shell, thead classes, colSpan empty state) so the two tables read
 * as one system. ETA renders the backend's own eta_minutes verbatim
 * (supersedes D-13) rather than a client-computed distance/speed formula.
 */
export function MissionsTable() {
  const { missions, select } = useFleetOps();
  const sorted = sortMissions(missions);

  return (
    <div className="rounded-lg border border-ops-border bg-ops-panel">
      <div className="border-b border-ops-border px-4 py-2 text-sm font-semibold text-slate-300">
        Missions
      </div>
      <div className="max-h-[22rem] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-ops-panel text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2">Drone</th>
              <th className="px-4 py-2">Zone</th>
              <th className="px-4 py-2">Distance</th>
              <th className="px-4 py-2">Energy</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">ETA</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((mission) => (
              <tr
                key={mission.id}
                onClick={() => select(mission.drone_id)}
                className="cursor-pointer border-t border-ops-border transition-colors hover:bg-white/5"
              >
                <td className="px-4 py-2 font-mono text-slate-200">{mission.drone_id}</td>
                <td
                  className="truncate max-w-[12rem] px-4 py-2 text-slate-400"
                  title={mission.zone}
                >
                  {mission.zone}
                </td>
                <td className="px-4 py-2 text-slate-400">{mission.distance_km.toFixed(1)} km</td>
                <td className="px-4 py-2 text-slate-400">
                  {mission.energy_cost_kwh.toFixed(2)} kWh
                </td>
                <td className="px-4 py-2 text-slate-400">
                  {MISSION_STATUS_LABEL[mission.status] ?? mission.status}
                </td>
                <td className="px-4 py-2 font-mono text-ops-teal">
                  {mission.eta_minutes !== undefined ? `${mission.eta_minutes} min` : "—"}
                </td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  <div className="font-semibold text-slate-300">No active missions</div>
                  <div className="mt-1 text-xs">
                    Launch a mission from the dispatch bar to see it here.
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
