import type { Mission } from "@/types/fleet";

const STATUS_CLASS: Record<string, string> = {
  en_route: "text-ops-teal",
  delivered: "text-emerald-400",
  recalled: "text-slate-400",
};

export function MissionsTable({ missions }: { missions: Mission[] }) {
  return (
    <div data-testid="missions-table" className="rounded-lg border border-ops-border bg-ops-panel">
      <div className="border-b border-ops-border px-4 py-2 text-sm font-semibold text-slate-300">
        Missions
      </div>
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase text-slate-500">
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
          {missions.map((mission) => (
            <tr key={mission.id} className="border-t border-ops-border">
              <td className="px-4 py-2 font-mono text-slate-200">{mission.drone_id}</td>
              <td className="px-4 py-2 text-slate-300">{mission.zone}</td>
              <td className="px-4 py-2 font-mono text-slate-400">{mission.distance_km.toFixed(1)} km</td>
              <td className="px-4 py-2 font-mono text-slate-400">
                {mission.energy_cost_kwh.toFixed(1)} kWh
              </td>
              <td className={`px-4 py-2 ${STATUS_CLASS[mission.status] ?? "text-slate-400"}`}>
                {mission.status.replace("_", " ")}
              </td>
              <td className="px-4 py-2 font-mono text-slate-400">
                {mission.eta_minutes !== undefined ? `${mission.eta_minutes.toFixed(0)} min` : "—"}
              </td>
            </tr>
          ))}
          {missions.length === 0 && (
            <tr>
              <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                No active missions.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
