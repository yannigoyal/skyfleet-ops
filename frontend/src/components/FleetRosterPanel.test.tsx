import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FleetRosterPanel } from "./FleetRosterPanel";
import type { TelemetryReading, TelemetrySnapshot } from "@/types/telemetry";

function reading(overrides: Partial<TelemetryReading> = {}): TelemetryReading {
  return {
    drone_id: "FALCON-01",
    battery_pct: 80,
    previous_battery_pct: 82,
    altitude_m: 120,
    speed_kmh: 40,
    status: "in_flight",
    timestamp: 1,
    battery_delta: -2,
    battery_direction: "draining",
    ...overrides,
  };
}

function renderPanel(snapshot: TelemetrySnapshot) {
  return render(
    <FleetRosterPanel snapshot={snapshot} history={{}} selectedDroneId={null} onSelect={() => {}} />,
  );
}

describe("FleetRosterPanel telemetry flash", () => {
  it("applies the drain flash class when the battery is falling", () => {
    renderPanel({ "FALCON-01": reading({ battery_direction: "draining" }) });
    expect(screen.getByText("FALCON-01").closest("tr")).toHaveClass("animate-flash-drain");
  });

  it("applies the charge flash class when the battery is rising", () => {
    renderPanel({ "FALCON-01": reading({ battery_direction: "charging" }) });
    expect(screen.getByText("FALCON-01").closest("tr")).toHaveClass("animate-flash-charge");
  });

  it("applies no flash class when the battery is flat", () => {
    renderPanel({ "FALCON-01": reading({ battery_direction: "flat" }) });
    const row = screen.getByText("FALCON-01").closest("tr");
    expect(row).not.toHaveClass("animate-flash-drain");
    expect(row).not.toHaveClass("animate-flash-charge");
  });
});
