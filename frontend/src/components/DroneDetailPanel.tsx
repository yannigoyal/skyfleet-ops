import type { TelemetryReading } from "@/types/telemetry";
import type { Mission } from "@/types/fleet";
import { Sparkline } from "./Sparkline";

interface Props {
  reading: TelemetryReading | null;
  batteryHistory: number[];
  mission: Mission | null;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="font-mono text-lg text-slate-200">{value}</div>
    </div>
  );
}

export function DroneDetailPanel({ reading, batteryHistory, mission }: Props) {
  return (
    <div className="rounded-lg border border-ops-border bg-ops-panel">
      <div className="border-b border-ops-border px-4 py-2 text-sm font-semibold text-slate-300">
        Drone Detail
      </div>
      {reading === null ? (
        <p className="px-4 py-6 text-sm text-slate-500">Select a drone from the roster.</p>
      ) : (
        <div className="space-y-4 p-4">
          <div className="font-mono text-xl text-ops-amber">{reading.drone_id}</div>
          <div className="grid grid-cols-3 gap-4">
            <Stat label="Battery" value={`${reading.battery_pct.toFixed(1)}%`} />
            <Stat label="Altitude" value={`${reading.altitude_m.toFixed(0)} m`} />
            <Stat label="Speed" value={`${reading.speed_kmh.toFixed(0)} km/h`} />
          </div>
          <div>
            <div className="mb-1 text-xs uppercase tracking-wide text-slate-500">Battery Over Time</div>
            <Sparkline points={batteryHistory} width={320} height={64} />
          </div>
          <div>
            <div className="mb-1 text-xs uppercase tracking-wide text-slate-500">Current Mission</div>
            {mission ? (
              <div className="text-sm text-slate-300">
                <span className="text-ops-teal">{mission.zone}</span> · {mission.distance_km.toFixed(1)} km ·{" "}
                {mission.energy_cost_kwh.toFixed(1)} kWh
                {mission.eta_minutes !== undefined && ` · ETA ${mission.eta_minutes.toFixed(0)} min`}
              </div>
            ) : (
              <div className="text-sm text-slate-500">No active mission.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
