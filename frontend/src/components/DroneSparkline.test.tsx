import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { DroneSparkline } from "./DroneSparkline";
import { FleetRosterPanel } from "./FleetRosterPanel";
import type { TelemetrySnapshot } from "@/types/telemetry";

function reading(droneId: string, batteryPct: number): TelemetrySnapshot[string] {
  return {
    drone_id: droneId,
    battery_pct: batteryPct,
    previous_battery_pct: batteryPct,
    altitude_m: 100,
    speed_kmh: 30,
    status: "in_flight",
    timestamp: Date.now(),
    battery_delta: 0,
    battery_direction: "flat",
  };
}

describe("DroneSparkline — compact per-drone battery trend", () => {
  it("Test 1: given varying battery values, renders an SVG path element", () => {
    const { container } = render(<DroneSparkline points={[90, 85, 88, 80, 82]} />);
    expect(container.querySelectorAll("path.recharts-line-curve").length).toBeGreaterThan(0);
  });

  it("Test 2: given an empty array, renders without throwing and produces no path (blank cell)", () => {
    const { container } = render(<DroneSparkline points={[]} />);
    expect(container.querySelectorAll("path").length).toBe(0);
  });

  it("Test 3: given a single-point array, renders without throwing", () => {
    expect(() => render(<DroneSparkline points={[50]} />)).not.toThrow();
  });

  it("Test 4: given identical consecutive values, renders a visible flat line rather than collapsing or throwing", () => {
    const { container } = render(<DroneSparkline points={[60, 60, 60, 60]} />);
    expect(container.querySelectorAll("path.recharts-line-curve").length).toBeGreaterThan(0);
  });

  it("Test 5: FleetRosterPanel renders one sparkline cell per drone row, and its empty-state row still spans every column", () => {
    const snapshot: TelemetrySnapshot = {
      "FALCON-01": reading("FALCON-01", 90),
      "FALCON-02": reading("FALCON-02", 80),
    };
    const history = {
      "FALCON-01": [88, 89, 90],
      "FALCON-02": [78, 79, 80],
    };

    const { container, rerender } = render(
      <FleetRosterPanel
        snapshot={snapshot}
        history={history}
        selectedDroneId={null}
        onSelect={() => {}}
      />,
    );
    // One ResponsiveContainer (sparkline root) per drone row.
    expect(container.querySelectorAll(".recharts-responsive-container").length).toBe(2);

    rerender(
      <FleetRosterPanel snapshot={{}} history={{}} selectedDroneId={null} onSelect={() => {}} />,
    );
    const emptyCell = container.querySelector("td[colspan]");
    expect(emptyCell?.getAttribute("colspan")).toBe("6");
  });
});
