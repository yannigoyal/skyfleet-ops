import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";

const SPARKLINE_WIDTH = 80;
const SPARKLINE_HEIGHT = 24;

interface Props {
  points: number[];
}

/**
 * Compact axis-free battery trend line for a single roster row — a
 * props-only render component with no local state, following the
 * ConnectionDot.tsx small-pure-component template. Deliberately omits
 * axes, grid, legend, and tooltip: this is a sparkline, not a chart.
 */
export function DroneSparkline({ points }: Props) {
  if (points.length === 0) {
    // Blank placeholder at the same fixed size, not a crash and not a
    // zero-width cell that would make the row jump.
    return <div style={{ width: SPARKLINE_WIDTH, height: SPARKLINE_HEIGHT }} />;
  }

  const data = points.map((battery_pct, i) => ({ i, battery_pct }));
  const isFlat = points.every((value) => value === points[0]);
  // A perfectly flat series has zero range; Recharts' auto-domain would
  // collapse the line to a single point. Pad an explicit domain around the
  // constant value so a flat battery still draws as a visible horizontal
  // line — a flat reading is meaningful information, not an absence of it.
  const domain: [number | string, number | string] = isFlat
    ? [points[0] - 1, points[0] + 1]
    : ["dataMin", "dataMax"];

  return (
    <ResponsiveContainer width={SPARKLINE_WIDTH} height={SPARKLINE_HEIGHT}>
      <LineChart data={data}>
        <YAxis hide domain={domain} />
        <Line
          type="monotone"
          dataKey="battery_pct"
          stroke="#17a2b8"
          dot={false}
          strokeWidth={1.5}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
