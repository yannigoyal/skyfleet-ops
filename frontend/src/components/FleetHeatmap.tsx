"use client";

import { ResponsiveContainer, Treemap } from "recharts";
import type { Mission } from "@/types/fleet";
import type { TelemetrySnapshot } from "@/types/telemetry";

// Idle drones have no mission cost, so they get a floor size to stay visible.
const IDLE_TILE_SIZE = 0.5;

function batteryFill(pct: number): string {
  if (pct <= 20) return "#dc2626";
  if (pct <= 50) return "#f2a900";
  return "#10b981";
}

interface TileProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  batteryPct?: number;
}

function Tile({ x = 0, y = 0, width = 0, height = 0, name = "", batteryPct = 0 }: TileProps) {
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={batteryFill(batteryPct)}
        stroke="#12161f"
        fillOpacity={0.75}
      />
      {width > 56 && height > 28 && (
        <text x={x + 6} y={y + 18} fill="#0a0e14" fontSize={11} fontFamily="monospace">
          {name}
        </text>
      )}
    </g>
  );
}

interface Props {
  snapshot: TelemetrySnapshot;
  missions: Mission[];
}

/** Treemap of the fleet — area is mission energy cost, color is battery health. */
export function FleetHeatmap({ snapshot, missions }: Props) {
  const costByDrone = new Map(missions.map((m) => [m.drone_id, m.energy_cost_kwh]));
  const data = Object.values(snapshot).map((reading) => ({
    name: reading.drone_id,
    size: costByDrone.get(reading.drone_id) ?? IDLE_TILE_SIZE,
    batteryPct: reading.battery_pct,
  }));

  return (
    <div data-testid="fleet-heatmap" className="rounded-lg border border-ops-border bg-ops-panel">
      <div className="border-b border-ops-border px-4 py-2 text-sm font-semibold text-slate-300">
        Fleet Heatmap
      </div>
      <div className="h-56 p-2">
        {data.length === 0 ? (
          <p className="p-4 text-sm text-slate-500">Waiting for telemetry…</p>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <Treemap data={data} dataKey="size" isAnimationActive={false} content={<Tile />} />
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
