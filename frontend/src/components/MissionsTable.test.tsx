import { useEffect } from "react";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { MissionsTable } from "./MissionsTable";
import { FleetOpsProvider, useFleetOps } from "@/lib/FleetOpsProvider";
import type { Mission } from "@/types/fleet";

const EMPTY_ROSTER = { drones: [] };
const EMPTY_FLEET = { energy_budget_kwh: 500, remaining_kwh: 500, active_mission_count: 0, missions: [] };

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

function Seed({ missions }: { missions: Mission[] }) {
  const { upsertMission, loaded } = useFleetOps();
  useEffect(() => {
    // Wait for FleetOpsProvider's own mount-triggered refetch() to resolve
    // first. Seeding before that resolves races mergeMissions(): the
    // provider's initial (empty-active-list) poll would mark a
    // freshly-upserted en_route mission "delivered" out from under us.
    if (!loaded) return;
    missions.forEach((m) => upsertMission(m));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded]);
  return null;
}

function SelectedProbe() {
  const { selectedDroneId } = useFleetOps();
  return <div data-testid="selected">{selectedDroneId ?? "none"}</div>;
}

function renderTable(missions: Mission[]) {
  return render(
    <FleetOpsProvider>
      <Seed missions={missions} />
      <MissionsTable />
      <SelectedProbe />
    </FleetOpsProvider>,
  );
}

describe("MissionsTable — full accumulated history with the backend's ETA", () => {
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

  it("Test 1: an empty missions map renders the documented empty state and no data rows", async () => {
    renderTable([]);

    await waitFor(() => {
      expect(screen.getByText("No active missions")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Launch a mission from the dispatch bar to see it here."),
    ).toBeInTheDocument();
    expect(screen.queryAllByRole("row")).toHaveLength(2); // thead row + empty-state row
  });

  it("Test 2: an en_route mission renders drone, zone, distance, energy, En Route label, and eta_minutes", async () => {
    renderTable([
      mission({
        id: "m1",
        drone_id: "FALCON-01",
        zone: "Riverside",
        distance_km: 4.2,
        energy_cost_kwh: 3.36,
        status: "en_route",
        eta_minutes: 6.3,
      }),
    ]);

    await waitFor(() => {
      expect(screen.getByText("FALCON-01")).toBeInTheDocument();
    });
    expect(screen.getByText("Riverside")).toBeInTheDocument();
    expect(screen.getByText("4.2 km")).toBeInTheDocument();
    expect(screen.getByText("3.36 kWh")).toBeInTheDocument();
    expect(screen.getByText("En Route")).toBeInTheDocument();
    expect(screen.getByText("6.3 min")).toBeInTheDocument();
  });

  it("Test 3: delivered and recalled missions render the Delivered and Recalled labels", async () => {
    renderTable([
      mission({ id: "m1", drone_id: "FALCON-01", status: "delivered" }),
      mission({ id: "m2", drone_id: "FALCON-02", status: "recalled" }),
    ]);

    await waitFor(() => {
      expect(screen.getByText("Delivered")).toBeInTheDocument();
    });
    expect(screen.getByText("Recalled")).toBeInTheDocument();
  });

  it("Test 4: a mission with undefined eta_minutes renders an em-dash, never undefined or NaN", async () => {
    renderTable([mission({ id: "m1", drone_id: "FALCON-01", status: "delivered" })]);

    await waitFor(() => {
      expect(screen.getByText("FALCON-01")).toBeInTheDocument();
    });
    const row = screen.getByText("FALCON-01").closest("tr");
    expect(row?.textContent).toContain("—");
    expect(row?.textContent).not.toContain("undefined");
    expect(row?.textContent).not.toContain("NaN");
  });

  // Test 5 (backstop): held-out for the FE-05 row-ordering condition — rows
  // are sorted by a stable key (updated_at desc, tie-broken by id) computed
  // from the mission fields, not by incoming array/insertion order.
  it("Test 5 (backstop): row order is stable regardless of the seeding order", async () => {
    const m1 = mission({ id: "m1", drone_id: "FALCON-01", updated_at: "2026-01-01T00:00:00Z" });
    const m2 = mission({ id: "m2", drone_id: "FALCON-02", updated_at: "2026-01-01T00:05:00Z" });
    const m3 = mission({ id: "m3", drone_id: "FALCON-03", updated_at: "2026-01-01T00:10:00Z" });

    const { unmount } = renderTable([m1, m2, m3]);
    await waitFor(() => {
      expect(screen.getAllByRole("row")).toHaveLength(4); // thead + 3 data rows
    });
    const firstOrder = screen
      .getAllByRole("row")
      .slice(1)
      .map((row) => row.textContent?.match(/FALCON-0\d/)?.[0]);
    unmount();

    renderTable([m3, m1, m2]);
    await waitFor(() => {
      expect(screen.getAllByRole("row")).toHaveLength(4);
    });
    const secondOrder = screen
      .getAllByRole("row")
      .slice(1)
      .map((row) => row.textContent?.match(/FALCON-0\d/)?.[0]);

    expect(secondOrder).toEqual(firstOrder);
    expect(firstOrder).toEqual(["FALCON-03", "FALCON-02", "FALCON-01"]);
  });

  // Test 6 (backstop): held-out for the UI-SPEC zone-overflow consideration
  // — a long free-text zone truncates visually and stays inspectable via
  // the native title attribute holding the untruncated value.
  it("Test 6 (backstop): a 200-character zone name truncates with a title attribute holding the full value", async () => {
    const longZone = "A".repeat(200);
    renderTable([mission({ id: "m1", drone_id: "FALCON-01", zone: longZone })]);

    await waitFor(() => {
      expect(screen.getByText("FALCON-01")).toBeInTheDocument();
    });
    const zoneCell = screen.getByTitle(longZone);
    expect(zoneCell).toBeInTheDocument();
    expect(zoneCell.className).toContain("truncate");
    expect(zoneCell.className).toContain("max-w-[12rem]");
  });

  it("Test 7: clicking a mission row selects that mission's drone through the provider", async () => {
    renderTable([mission({ id: "m1", drone_id: "FALCON-01" })]);

    await waitFor(() => {
      expect(screen.getByText("FALCON-01")).toBeInTheDocument();
    });
    expect(screen.getByTestId("selected").textContent).toBe("none");

    fireEvent.click(screen.getByText("FALCON-01").closest("tr")!);

    await waitFor(() => {
      expect(screen.getByTestId("selected").textContent).toBe("FALCON-01");
    });
  });
});
