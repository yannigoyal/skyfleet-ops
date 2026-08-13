import { useEffect } from "react";
import { render, screen, waitFor, cleanup, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { FleetHeatmap } from "./FleetHeatmap";
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

/** Seeds missions and exposes the last-selected drone id, mirroring the
 * DetailPanel.test.tsx race-avoidance pattern (seed only after the
 * provider's mount-triggered refetch() resolves). */
function Setup({
  missions,
  onSelected,
}: {
  missions: Mission[];
  onSelected: (id: string | null) => void;
}) {
  const { upsertMission, loaded, selectedDroneId } = useFleetOps();
  useEffect(() => {
    if (!loaded) return;
    missions.forEach((m) => upsertMission(m));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded]);
  useEffect(() => {
    onSelected(selectedDroneId);
  }, [selectedDroneId, onSelected]);
  return null;
}

function renderHeatmap({
  snapshot = {},
  missions = [],
  onSelected = () => {},
}: {
  snapshot?: TelemetrySnapshot;
  missions?: Mission[];
  onSelected?: (id: string | null) => void;
}) {
  return render(
    <FleetOpsProvider>
      <Setup missions={missions} onSelected={onSelected} />
      <FleetHeatmap snapshot={snapshot} />
    </FleetOpsProvider>,
  );
}

function buildSnapshot(count: number, batteryPct = 72): TelemetrySnapshot {
  const snapshot: TelemetrySnapshot = {};
  for (let i = 1; i <= count; i++) {
    const id = `FALCON-${String(i).padStart(2, "0")}`;
    snapshot[id] = reading(id, { battery_pct: batteryPct });
  }
  return snapshot;
}

describe("FleetHeatmap — treemap sized by mission energy, coloured by battery health", () => {
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

  it("Test 1 (D-10, empty/fresh start): ten drones with zero active missions still render ten cells", async () => {
    const snapshot = buildSnapshot(10);
    const { container } = renderHeatmap({ snapshot });

    await waitFor(() => {
      expect(container.querySelectorAll("rect").length).toBe(10);
    });
  });

  it("Test 2: an en_route mission's energy_cost_kwh weights its cell; a delivered-only drone falls back to the idle floor", async () => {
    const snapshot = {
      "FALCON-01": reading("FALCON-01"),
      "FALCON-02": reading("FALCON-02"),
    };
    const { container } = renderHeatmap({
      snapshot,
      missions: [
        mission({ id: "m1", drone_id: "FALCON-01", energy_cost_kwh: 8, status: "en_route" }),
        mission({ id: "m2", drone_id: "FALCON-02", energy_cost_kwh: 8, status: "delivered" }),
      ],
    });

    // The mission upsert (Setup's effect) lands after the provider's own
    // mount-triggered refetch resolves, one render tick after the initial
    // idle-weighted layout — poll until the areas reflect the settled
    // mission-weighted state rather than asserting on the first paint.
    await waitFor(() => {
      const rects = Array.from(container.querySelectorAll("rect"));
      expect(rects.length).toBe(2);
      const areas = rects.map((rect) => {
        const width = Number(rect.getAttribute("width"));
        const height = Number(rect.getAttribute("height"));
        return width * height;
      });
      // The en_route drone's mission (8 kWh) must dominate the delivered
      // drone's idle-floor weight (0.1 kWh) by a wide margin.
      const [larger, smaller] = [Math.max(...areas), Math.min(...areas)];
      expect(larger).toBeGreaterThan(smaller * 5);
    });
  });

  it("Test 3 (D-11, colour bands): 75% renders emerald, 35% renders amber, 8% renders red", async () => {
    const snapshot = {
      "FALCON-01": reading("FALCON-01", { battery_pct: 75 }),
      "FALCON-02": reading("FALCON-02", { battery_pct: 35 }),
      "FALCON-03": reading("FALCON-03", { battery_pct: 8 }),
    };
    const { container } = renderHeatmap({ snapshot });

    await waitFor(() => {
      expect(container.querySelectorAll("rect").length).toBe(3);
    });

    function fillForDrone(droneId: string): string | null {
      const label = Array.from(container.querySelectorAll("text")).find(
        (el) => el.textContent === droneId,
      );
      const cell = label?.closest("g");
      return cell?.querySelector("rect")?.getAttribute("fill") ?? null;
    }

    expect(fillForDrone("FALCON-01")).toBe("#34d399");
    expect(fillForDrone("FALCON-02")).toBe("#f2a900");
    expect(fillForDrone("FALCON-03")).toBe("#f87171");
  });

  it("Test 4 (boundary): exactly 50% renders amber, exactly 20% renders red — same at-or-below direction as batteryColor()", async () => {
    const snapshot = {
      "FALCON-01": reading("FALCON-01", { battery_pct: 50 }),
      "FALCON-02": reading("FALCON-02", { battery_pct: 20 }),
    };
    const { container } = renderHeatmap({ snapshot });

    await waitFor(() => {
      expect(container.querySelectorAll("rect").length).toBe(2);
    });

    function fillForDrone(droneId: string): string | null {
      const label = Array.from(container.querySelectorAll("text")).find(
        (el) => el.textContent === droneId,
      );
      const cell = label?.closest("g");
      return cell?.querySelector("rect")?.getAttribute("fill") ?? null;
    }

    expect(fillForDrone("FALCON-01")).toBe("#f2a900");
    expect(fillForDrone("FALCON-02")).toBe("#f87171");
  });

  it("Test 5 (SVG-only, Pitfall 3): the svg subtree contains zero div and zero foreignObject elements", async () => {
    const snapshot = buildSnapshot(4);
    const { container } = renderHeatmap({ snapshot });

    await waitFor(() => {
      expect(container.querySelectorAll("rect").length).toBe(4);
    });

    expect(container.querySelectorAll("svg div").length).toBe(0);
    expect(container.querySelectorAll("svg foreignObject").length).toBe(0);
  });

  it("Test 6 (prohibition, non-colour cue): a legible cell renders both the drone id and its battery percentage as text", async () => {
    const snapshot = {
      "FALCON-01": reading("FALCON-01", { battery_pct: 8 }),
      "FALCON-02": reading("FALCON-02", { battery_pct: 72 }),
    };
    renderHeatmap({ snapshot });

    await waitFor(() => {
      expect(screen.getByText("FALCON-01")).toBeInTheDocument();
    });
    expect(screen.getByText("FALCON-02")).toBeInTheDocument();
    expect(screen.getByText("8.0%")).toBeInTheDocument();
    expect(screen.getByText("72.0%")).toBeInTheDocument();
  });

  it("Test 7 (D-12): clicking a cell selects that drone through the shared provider", async () => {
    const snapshot = { "FALCON-01": reading("FALCON-01") };
    let selected: string | null = null;
    const { container } = renderHeatmap({
      snapshot,
      onSelected: (id) => {
        selected = id;
      },
    });

    await waitFor(() => {
      expect(container.querySelectorAll("rect").length).toBe(1);
    });

    fireEvent.click(container.querySelector("rect") as Element);

    await waitFor(() => {
      expect(selected).toBe("FALCON-01");
    });
  });

  it("Test 8 (zero-one-many): renders without throwing at zero, one, and twenty drones", async () => {
    expect(() => renderHeatmap({ snapshot: {} })).not.toThrow();
    cleanup();
    expect(() => renderHeatmap({ snapshot: buildSnapshot(1) })).not.toThrow();
    cleanup();
    expect(() => renderHeatmap({ snapshot: buildSnapshot(20) })).not.toThrow();
  });
});
