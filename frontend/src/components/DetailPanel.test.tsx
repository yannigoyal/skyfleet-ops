import { useEffect } from "react";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { DetailPanel } from "./DetailPanel";
import { FleetOpsProvider, useFleetOps } from "@/lib/FleetOpsProvider";
import type { Mission } from "@/types/fleet";
import type { TelemetrySnapshot } from "@/types/telemetry";

const EMPTY_ROSTER = { drones: [] };
const EMPTY_FLEET = {
  energy_budget_kwh: 500,
  remaining_kwh: 500,
  active_mission_count: 0,
  missions: [],
};

function reading(
  droneId: string,
  overrides: Partial<TelemetrySnapshot[string]> = {},
): TelemetrySnapshot[string] {
  return {
    drone_id: droneId,
    battery_pct: 72,
    previous_battery_pct: 72,
    altitude_m: 120,
    speed_kmh: 40,
    status: "in_flight",
    timestamp: Date.now(),
    battery_delta: 0,
    battery_direction: "flat",
    ...overrides,
  };
}

function mission(overrides: Partial<Mission> & { id: string; drone_id: string }): Mission {
  return {
    zone: "Riverside",
    distance_km: 4.2,
    energy_cost_kwh: 3.36,
    status: "en_route",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

/** Seeds selection + missions only after the provider's own mount-triggered
 * refetch() resolves — same race-avoidance pattern as MissionsTable.test.tsx. */
function Setup({
  selectedDroneId,
  missions,
}: {
  selectedDroneId: string | null;
  missions: Mission[];
}) {
  const { select, upsertMission, loaded } = useFleetOps();
  useEffect(() => {
    if (!loaded) return;
    missions.forEach((m) => upsertMission(m));
    if (selectedDroneId) select(selectedDroneId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded]);
  return null;
}

function renderPanel({
  selectedDroneId = null,
  missions = [],
  snapshot = {},
}: {
  selectedDroneId?: string | null;
  missions?: Mission[];
  snapshot?: TelemetrySnapshot;
}) {
  const history: Record<string, number[]> = {};
  const altitudeHistory: Record<string, number[]> = {};
  const speedHistory: Record<string, number[]> = {};
  for (const [droneId, r] of Object.entries(snapshot)) {
    history[droneId] = [r.battery_pct];
    altitudeHistory[droneId] = [r.altitude_m];
    speedHistory[droneId] = [r.speed_kmh];
  }

  return render(
    <FleetOpsProvider>
      <Setup selectedDroneId={selectedDroneId} missions={missions} />
      <DetailPanel
        snapshot={snapshot}
        history={history}
        altitudeHistory={altitudeHistory}
        speedHistory={speedHistory}
      />
    </FleetOpsProvider>,
  );
}

describe("DetailPanel — selected-drone telemetry over time plus current mission", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/roster") return new Response(JSON.stringify(EMPTY_ROSTER), { status: 200 });
        if (url === "/api/fleet") return new Response(JSON.stringify(EMPTY_FLEET), { status: 200 });
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );
  });

  afterEach(() => {
    cleanup();
  });

  it("Test 1: with no drone selected, renders a neutral prompt and no telemetry charts", async () => {
    renderPanel({});

    await waitFor(() => {
      expect(screen.getByText(/select a drone/i)).toBeInTheDocument();
    });
    expect(document.querySelectorAll(".recharts-responsive-container").length).toBe(0);
  });

  it("Test 2: with a drone selected and present in the snapshot, renders its id, readouts, and three chart series", async () => {
    const snapshot = {
      "FALCON-01": reading("FALCON-01", { battery_pct: 72, altitude_m: 120, speed_kmh: 40 }),
    };
    renderPanel({ selectedDroneId: "FALCON-01", snapshot });

    await waitFor(() => {
      expect(screen.getByText("FALCON-01")).toBeInTheDocument();
    });
    expect(screen.getByText("72.0%")).toBeInTheDocument();
    expect(screen.getByText("120m")).toBeInTheDocument();
    expect(screen.getByText("40km/h")).toBeInTheDocument();
    expect(document.querySelectorAll(".recharts-responsive-container").length).toBe(3);
  });

  it("Test 3 (D-16): a selected drone with no mission shows 'No active mission' and still renders all three charts", async () => {
    const snapshot = { "FALCON-01": reading("FALCON-01") };
    renderPanel({ selectedDroneId: "FALCON-01", snapshot });

    await waitFor(() => {
      expect(screen.getByText("No active mission")).toBeInTheDocument();
    });
    expect(document.querySelectorAll(".recharts-responsive-container").length).toBe(3);
  });

  it("Test 4: a selected drone with an en_route mission shows zone, distance, and energy cost", async () => {
    const snapshot = { "FALCON-01": reading("FALCON-01") };
    renderPanel({
      selectedDroneId: "FALCON-01",
      snapshot,
      missions: [
        mission({
          id: "m1",
          drone_id: "FALCON-01",
          zone: "Riverside",
          distance_km: 4.2,
          energy_cost_kwh: 3.36,
          status: "en_route",
        }),
      ],
    });

    await waitFor(() => {
      expect(screen.getByText("Riverside")).toBeInTheDocument();
    });
    expect(screen.getByText("4.2 km")).toBeInTheDocument();
    expect(screen.getByText("3.36 kWh")).toBeInTheDocument();
  });

  it("Test 5: a delivered/recalled mission for the selected drone does NOT count as current — empty state renders", async () => {
    const snapshot = { "FALCON-01": reading("FALCON-01") };
    renderPanel({
      selectedDroneId: "FALCON-01",
      snapshot,
      missions: [mission({ id: "m1", drone_id: "FALCON-01", status: "delivered" })],
    });

    await waitFor(() => {
      expect(screen.getByText("No active mission")).toBeInTheDocument();
    });
  });

  // Test 6 (backstop): held-out for the UI-SPEC partial-state consideration
  // — a selected drone that vanishes from the live snapshot must not show
  // stale/blank last-known values.
  it("Test 6 (backstop): a selected drone absent from the snapshot shows the offline message instead of stale readouts", async () => {
    renderPanel({ selectedDroneId: "FALCON-99", snapshot: {} });

    await waitFor(() => {
      expect(screen.getByText("Drone offline or removed from roster")).toBeInTheDocument();
    });
  });

  it("Test 7: the battery readout uses the same three-band color thresholds as the roster row", async () => {
    const snapshot = { "FALCON-01": reading("FALCON-01", { battery_pct: 15 }) };
    renderPanel({ selectedDroneId: "FALCON-01", snapshot });

    await waitFor(() => {
      expect(screen.getByText("15.0%")).toBeInTheDocument();
    });
    expect(screen.getByText("15.0%").className).toContain("text-red-400");
  });
});
