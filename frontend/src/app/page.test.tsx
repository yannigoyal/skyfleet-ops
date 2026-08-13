import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Home from "./page";

const ROSTER_RESPONSE = {
  drones: [
    { drone_id: "FALCON-01", added_at: "2026-01-01T00:00:00Z", battery_pct: 95 },
    { drone_id: "FALCON-02", added_at: "2026-01-01T00:00:00Z", battery_pct: 88 },
  ],
};

const FLEET_BEFORE = {
  energy_budget_kwh: 500.0,
  remaining_kwh: 500.0,
  active_mission_count: 0,
  missions: [],
};

const LAUNCHED_MISSION = {
  id: "m1",
  drone_id: "FALCON-01",
  zone: "Riverside",
  distance_km: 4.2,
  energy_cost_kwh: 3.36,
  status: "en_route",
  updated_at: "2026-01-01T00:05:00Z",
  eta_minutes: 6.3,
};

const FLEET_AFTER = {
  energy_budget_kwh: 500.0,
  remaining_kwh: 496.64,
  active_mission_count: 1,
  missions: [LAUNCHED_MISSION],
};

class NoOpEventSource {
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  close() {}
}

describe("Console page — launch a mission and watch the budget drop", () => {
  beforeEach(() => {
    vi.stubGlobal("EventSource", NoOpEventSource as unknown as typeof EventSource);

    let fleetCallCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();

        if (url === "/api/roster" && (!init || init.method === undefined)) {
          return new Response(JSON.stringify(ROSTER_RESPONSE), { status: 200 });
        }
        if (url === "/api/fleet") {
          fleetCallCount += 1;
          const body = fleetCallCount === 1 ? FLEET_BEFORE : FLEET_AFTER;
          return new Response(JSON.stringify(body), { status: 200 });
        }
        if (url === "/api/fleet/missions" && init?.method === "POST") {
          return new Response(JSON.stringify(LAUNCHED_MISSION), { status: 201 });
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );
  });

  it("launches a mission through the dispatch bar and updates the header live", async () => {
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText(/500\.0 \/ 500\.0 kWh/)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByRole("option", { name: "FALCON-01" })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Drone"), { target: { value: "FALCON-01" } });
    fireEvent.change(screen.getByLabelText("Zone"), { target: { value: "Riverside" } });
    fireEvent.change(screen.getByLabelText("Distance (km)"), { target: { value: "4.2" } });

    fireEvent.click(screen.getByRole("button", { name: "Launch Mission" }));

    await waitFor(() => {
      expect(screen.getByText(/496\.6 \/ 500\.0 kWh/)).toBeInTheDocument();
    });
    expect(screen.getByText("Active Missions:").parentElement).toHaveTextContent("1");
  });
});
