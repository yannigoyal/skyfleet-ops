"use client";

import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";
import { useFleetOps } from "@/lib/FleetOpsProvider";
import { batteryColor } from "@/components/FleetRosterPanel";
import type { TelemetryReading, TelemetrySnapshot } from "@/types/telemetry";
import type { Mission } from "@/types/fleet";

interface Props {
  snapshot: TelemetrySnapshot;
  history: Record<string, number[]>;
  altitudeHistory: Record<string, number[]>;
  speedHistory: Record<string, number[]>;
}

const CHART_WIDTH = 280;
const CHART_HEIGHT = 60;

/** One labelled telemetry-over-time chart, following the DroneSparkline
 * idiom (ResponsiveContainer + LineChart + Line, isAnimationActive={false}). */
function TelemetryChart({ label, points, stroke }: { label: string; points: number[]; stroke: string }) {
  const data = points.map((value, i) => ({ i, value }));
  return (
    <div>
      <div className="mb-1 text-xs uppercase text-slate-500">{label}</div>
      <ResponsiveContainer width={CHART_WIDTH} height={CHART_HEIGHT}>
        <LineChart data={data}>
          <YAxis hide domain={["dataMin", "dataMax"]} />
          <Line
            type="monotone"
            dataKey="value"
            stroke={stroke}
            dot={false}
            strokeWidth={1.5}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function CurrentMission({ mission }: { mission: Mission | null }) {
  if (!mission) {
    return <p className="text-sm text-slate-500">No active mission</p>;
  }
  return (
    <div className="grid grid-cols-3 gap-4 text-sm">
      <div>
        <div className="text-xs uppercase text-slate-500">Zone</div>
        <div className="text-slate-300">{mission.zone}</div>
      </div>
      <div>
        <div className="text-xs uppercase text-slate-500">Distance</div>
        <div className="text-slate-300">{mission.distance_km.toFixed(1)} km</div>
      </div>
      <div>
        <div className="text-xs uppercase text-slate-500">Energy</div>
        <div className="text-slate-300">{mission.energy_cost_kwh.toFixed(2)} kWh</div>
      </div>
    </div>
  );
}

function DetailBody({
  reading,
  history,
  altitudeHistory,
  speedHistory,
  mission,
}: {
  reading: TelemetryReading;
  history: number[];
  altitudeHistory: number[];
  speedHistory: number[];
  mission: Mission | null;
}) {
  return (
    <div className="flex flex-col gap-4">
      <div className="font-mono text-lg text-slate-200">{reading.drone_id}</div>
      <div className="grid grid-cols-3 gap-4 text-sm">
        <div>
          <div className="text-xs uppercase text-slate-500">Battery</div>
          <div className={`font-mono ${batteryColor(reading.battery_pct)}`}>
            {reading.battery_pct.toFixed(1)}%
          </div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">Altitude</div>
          <div className="font-mono text-slate-300">{reading.altitude_m.toFixed(0)}m</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">Speed</div>
          <div className="font-mono text-slate-300">{reading.speed_kmh.toFixed(0)}km/h</div>
        </div>
      </div>
      <TelemetryChart label="Battery" points={history} stroke="#17a2b8" />
      <TelemetryChart label="Altitude" points={altitudeHistory} stroke="#f2a900" />
      <TelemetryChart label="Speed" points={speedHistory} stroke="#34d399" />
      <div>
        <div className="mb-1 text-xs uppercase text-slate-500">Current Mission</div>
        <CurrentMission mission={mission} />
      </div>
    </div>
  );
}

/**
 * Detail view for the selected drone (FE-02): battery, altitude, and speed
 * over time, plus its current mission. Reads selectedDroneId and the
 * accumulated missions array from FleetOpsProvider — D-04's single
 * selected-drone state, shared with the roster row click and, from plan
 * 05, the heatmap cell click. The telemetry snapshot and three history
 * maps are passed as props from page.tsx's single useTelemetryStream()
 * call, since calling the hook again here would open a second EventSource.
 */
export function DetailPanel({ snapshot, history, altitudeHistory, speedHistory }: Props) {
  const { selectedDroneId, missions } = useFleetOps();

  return (
    <div className="rounded-lg border border-ops-border bg-ops-panel">
      <div className="border-b border-ops-border px-4 py-2 text-sm font-semibold text-slate-300">
        Drone Detail
      </div>
      <div className="p-4">
        {selectedDroneId === null && (
          <p className="text-sm text-slate-500">
            Select a drone from the roster to see live telemetry.
          </p>
        )}
        {selectedDroneId !== null && !snapshot[selectedDroneId] && (
          <p className="text-sm text-red-400">Drone offline or removed from roster</p>
        )}
        {selectedDroneId !== null && snapshot[selectedDroneId] && (
          <DetailBody
            reading={snapshot[selectedDroneId]}
            history={history[selectedDroneId] ?? []}
            altitudeHistory={altitudeHistory[selectedDroneId] ?? []}
            speedHistory={speedHistory[selectedDroneId] ?? []}
            mission={
              missions.find((m) => m.drone_id === selectedDroneId && m.status === "en_route") ??
              null
            }
          />
        )}
      </div>
    </div>
  );
}
