interface Props {
  points: number[];
  width?: number;
  height?: number;
  color?: string;
}

/** Inline SVG sparkline over a battery-percentage series (0-100). */
export function Sparkline({ points, width = 80, height = 20, color = "#17a2b8" }: Props) {
  if (points.length < 2) {
    return <svg width={width} height={height} role="img" aria-label="battery history" />;
  }

  const step = width / (points.length - 1);
  const path = points
    .map((value, index) => `${index === 0 ? "M" : "L"}${index * step},${height - (value / 100) * height}`)
    .join(" ");

  return (
    <svg width={width} height={height} role="img" aria-label="battery history">
      <path d={path} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}
