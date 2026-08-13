import type { TelemetrySnapshot } from "@/types/telemetry";
import { DroneSparkline } from "@/components/DroneSparkline";

const STATUS_LABEL: Record<string, string> = {
  idle: "Idle",
  in_flight: "In Flight",
  charging: "Charging",
  low_battery: "Low Battery",
  offline: "Offline",
};

function batteryColor(pct: number): string {
  if (pct <= 20) return "text-red-400";
  if (pct <= 50) return "text-ops-amber";
  return "text-emerald-400";
}

interface Props {
  snapshot: TelemetrySnapshot;
  history: Record<string, number[]>;
  selectedDroneId: string | null;
  onSelect: (droneId: string) => void;
}

/** Live-updating grid of tracked drones — battery, altitude, speed, status, trend. */
export function FleetRosterPanel({ snapshot, history, selectedDroneId, onSelect }: Props) {
  const drones = Object.values(snapshot).sort((a, b) => a.drone_id.localeCompare(b.drone_id));

  return (
    <div className="rounded-lg border border-ops-border bg-ops-panel">
      <div className="border-b border-ops-border px-4 py-2 text-sm font-semibold text-slate-300">
        Fleet Roster
      </div>
      <div className="max-h-[22rem] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-ops-panel text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2">Drone</th>
              <th className="px-4 py-2">Battery</th>
              <th className="px-4 py-2">Altitude</th>
              <th className="px-4 py-2">Speed</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Battery Trend</th>
            </tr>
          </thead>
          <tbody>
            {drones.map((reading) => {
              const flashClass =
                reading.battery_direction === "draining"
                  ? "animate-flash-drain"
                  : reading.battery_direction === "charging"
                    ? "animate-flash-charge"
                    : "";
              return (
                <tr
                  key={reading.drone_id}
                  onClick={() => onSelect(reading.drone_id)}
                  className={`cursor-pointer border-t border-ops-border transition-colors hover:bg-white/5 ${
                    selectedDroneId === reading.drone_id ? "bg-white/5" : ""
                  } ${flashClass}`}
                >
                  <td className="px-4 py-2 font-mono text-slate-200">{reading.drone_id}</td>
                  <td className={`px-4 py-2 font-mono ${batteryColor(reading.battery_pct)}`}>
                    {reading.battery_pct.toFixed(1)}%
                  </td>
                  <td className="px-4 py-2 text-slate-400">{reading.altitude_m.toFixed(0)}m</td>
                  <td className="px-4 py-2 text-slate-400">{reading.speed_kmh.toFixed(0)}km/h</td>
                  <td className="px-4 py-2 text-slate-400">{STATUS_LABEL[reading.status] ?? reading.status}</td>
                  <td className="px-4 py-2">
                    <DroneSparkline points={history[reading.drone_id] ?? []} />
                  </td>
                </tr>
              );
            })}
            {drones.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  Waiting for telemetry…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
