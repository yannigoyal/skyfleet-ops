"use client";

import { Treemap } from "recharts";
import { useFleetOps } from "@/lib/FleetOpsProvider";
import type { TelemetrySnapshot } from "@/types/telemetry";

/**
 * D-10: idle drones (no en_route mission) still occupy a small but visible
 * cell instead of collapsing to zero area, so the heatmap is never blank on
 * a fresh start with zero active missions.
 */
const IDLE_HEATMAP_WEIGHT_KWH = 0.1;

const HEATMAP_WIDTH = 640;
const HEATMAP_HEIGHT = 280;
const MIN_LABEL_WIDTH = 40;
const MIN_LABEL_HEIGHT = 28;

interface HeatmapDatum {
  name: string;
  value: number;
  batteryPct: number;
}

/**
 * Same at-or-below three-band thresholds as FleetRosterPanel's
 * batteryColor(), expressed as hex fills for direct use as SVG `fill`
 * attributes — Tailwind background/text utilities don't affect SVG fill/stroke.
 */
function batteryFill(pct: number): string {
  if (pct <= 20) return "#f87171";
  if (pct <= 50) return "#f2a900";
  return "#34d399";
}

/**
 * Recharts' Treemap `content` render-prop type is untyped (`any`) upstream;
 * this narrows it to the fields this renderer actually reads rather than
 * trusting Recharts' shape wholesale — a future prop rename or destructure
 * typo now fails to compile instead of surfacing only as a runtime
 * `undefined`.
 */
interface CellContentProps {
  x: number;
  y: number;
  width: number;
  height: number;
  name?: string;
  batteryPct?: number;
}

/**
 * SVG-only cell renderer (Pitfall 3): g/rect/text primitives only, no HTML
 * elements, since Recharts renders this subtree inside an <svg>. The
 * battery percentage text is load-bearing, not decoration — it is the
 * non-colour cue a red/green colour-blind dispatcher needs to identify a
 * critical drone, satisfying this plan's colour-only prohibition.
 */
function CellContent(props: unknown) {
  const { x, y, width, height, name, batteryPct } = props as CellContentProps;
  // Recharts also invokes `content` once for the synthetic root/container
  // node (depth 0) that wraps all data leaves — it carries no batteryPct,
  // since it isn't one of our HeatmapDatum entries. Render nothing for it.
  if (typeof batteryPct !== "number") return null;
  const fill = batteryFill(batteryPct);
  const showLabels = width > MIN_LABEL_WIDTH && height > MIN_LABEL_HEIGHT;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={fill} stroke="#232a38" />
      {showLabels && (
        <>
          <text x={x + 4} y={y + 14} fontSize={11} fill="#0a0e14" className="font-mono">
            {name}
          </text>
          <text x={x + 4} y={y + 28} fontSize={11} fill="#0a0e14" className="font-mono">
            {batteryPct.toFixed(1)}%
          </text>
        </>
      )}
    </g>
  );
}

interface Props {
  snapshot: TelemetrySnapshot;
}

/**
 * Fleet-wide heatmap (FE-03): one Treemap cell per drone in the live
 * telemetry snapshot, sized by its active mission's energy cost (D-09,
 * floored at IDLE_HEATMAP_WEIGHT_KWH per D-10) and coloured by live battery
 * health (D-11). Clicking a cell selects that drone through the same
 * FleetOpsProvider.select() the roster row and detail panel already share
 * (D-12) — one selection mechanism, multiple entry points.
 */
export function FleetHeatmap({ snapshot }: Props) {
  const { missions, select } = useFleetOps();

  const data: HeatmapDatum[] = Object.values(snapshot).map((reading) => {
    const activeMission = missions.find(
      (mission) => mission.drone_id === reading.drone_id && mission.status === "en_route",
    );
    return {
      name: reading.drone_id,
      value: activeMission ? activeMission.energy_cost_kwh : IDLE_HEATMAP_WEIGHT_KWH,
      batteryPct: reading.battery_pct,
    };
  });

  return (
    <div className="rounded-lg border border-ops-border bg-ops-panel">
      <div className="border-b border-ops-border px-4 py-2 text-sm font-semibold text-slate-300">
        Fleet Heatmap
      </div>
      <div className="p-4">
        <Treemap
          width={HEATMAP_WIDTH}
          height={HEATMAP_HEIGHT}
          data={data}
          dataKey="value"
          isAnimationActive={false}
          content={<CellContent />}
          onClick={(node: unknown) => select((node as { name?: string }).name ?? null)}
        />
      </div>
    </div>
  );
}
