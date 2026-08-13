import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { DispatchBar } from "./DispatchBar";
import { FleetOpsProvider, useFleetOps } from "@/lib/FleetOpsProvider";

const ROSTER_RESPONSE = {
  drones: [{ drone_id: "FALCON-01", added_at: "2026-01-01T00:00:00Z", battery_pct: 95 }],
};

const FLEET_STATUS = {
  energy_budget_kwh: 500,
  remaining_kwh: 500,
  active_mission_count: 0,
  missions: [],
};

const RECALLED_MISSION = {
  id: "m1",
  drone_id: "FALCON-01",
  zone: "Riverside",
  distance_km: 4.2,
  energy_cost_kwh: 3.36,
  status: "recalled",
  updated_at: "2026-01-01T00:10:00Z",
};

const LAUNCHED_MISSION = {
  id: "m2",
  drone_id: "FALCON-01",
  zone: "Downtown",
  distance_km: 2.1,
  energy_cost_kwh: 1.68,
  status: "en_route",
  updated_at: "2026-01-01T00:00:00Z",
  eta_minutes: 3.2,
};

class NoOpEventSource {
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  close() {}
}

function MissionProbe() {
  const { missions } = useFleetOps();
  return (
    <div data-testid="mission-status">
      {missions.map((mission) => `${mission.id}:${mission.status}`).join(",")}
    </div>
  );
}

function renderDispatchBar() {
  return render(
    <FleetOpsProvider>
      <DispatchBar />
      <MissionProbe />
    </FleetOpsProvider>,
  );
}

async function selectFalcon01() {
  await waitFor(() => {
    expect(screen.getByRole("option", { name: "FALCON-01" })).toBeInTheDocument();
  });
  fireEvent.change(screen.getByLabelText("Drone"), { target: { value: "FALCON-01" } });
}

function fillLaunchForm() {
  fireEvent.change(screen.getByLabelText("Zone"), { target: { value: "Riverside" } });
  fireEvent.change(screen.getByLabelText("Distance (km)"), { target: { value: "4.2" } });
}

describe("DispatchBar — recall and the inline backend-error matrix", () => {
  beforeEach(() => {
    vi.stubGlobal("EventSource", NoOpEventSource as unknown as typeof EventSource);
  });

  it("Test 1: clicking Recall with a drone selected issues DELETE to /api/fleet/missions/{drone_id} exactly once", async () => {
    let deleteCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/roster") return new Response(JSON.stringify(ROSTER_RESPONSE), { status: 200 });
        if (url === "/api/fleet") return new Response(JSON.stringify(FLEET_STATUS), { status: 200 });
        if (url === "/api/fleet/missions/FALCON-01" && init?.method === "DELETE") {
          deleteCalls += 1;
          return new Response(JSON.stringify(RECALLED_MISSION), { status: 200 });
        }
        throw new Error(`Unhandled fetch: ${url} ${init?.method}`);
      }),
    );

    renderDispatchBar();
    await selectFalcon01();
    fireEvent.click(screen.getByRole("button", { name: "Recall" }));

    await waitFor(() => expect(deleteCalls).toBe(1));
  });

  it("Test 2: a 200 recall response is upserted into the mission map as recalled, and refetch is called afterwards", async () => {
    let fleetCallCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/roster") return new Response(JSON.stringify(ROSTER_RESPONSE), { status: 200 });
        if (url === "/api/fleet") {
          fleetCallCount += 1;
          return new Response(JSON.stringify(FLEET_STATUS), { status: 200 });
        }
        if (url === "/api/fleet/missions/FALCON-01" && init?.method === "DELETE") {
          return new Response(JSON.stringify(RECALLED_MISSION), { status: 200 });
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    renderDispatchBar();
    await selectFalcon01();
    await waitFor(() => expect(fleetCallCount).toBe(1));

    fireEvent.click(screen.getByRole("button", { name: "Recall" }));

    await waitFor(() => {
      expect(screen.getByTestId("mission-status").textContent).toContain("m1:recalled");
    });
    await waitFor(() => expect(fleetCallCount).toBe(2));
  });

  it("Test 3: a 404 no_active_mission recall response renders inline, form is not cleared, no dialog appears", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/roster") return new Response(JSON.stringify(ROSTER_RESPONSE), { status: 200 });
        if (url === "/api/fleet") return new Response(JSON.stringify(FLEET_STATUS), { status: 200 });
        if (url === "/api/fleet/missions/FALCON-01" && init?.method === "DELETE") {
          return new Response(JSON.stringify({ detail: { reason: "no_active_mission" } }), { status: 404 });
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    renderDispatchBar();
    await selectFalcon01();
    fillLaunchForm();
    fireEvent.click(screen.getByRole("button", { name: "Recall" }));

    await waitFor(() => {
      expect(screen.getByText(/no_active_mission/)).toBeInTheDocument();
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect((screen.getByLabelText("Zone") as HTMLInputElement).value).toBe("Riverside");
    expect((screen.getByLabelText("Distance (km)") as HTMLInputElement).value).toBe("4.2");
  });

  it("Test 4: a 409 drone_already_en_route response on launch renders that reason inline verbatim", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/roster") return new Response(JSON.stringify(ROSTER_RESPONSE), { status: 200 });
        if (url === "/api/fleet") return new Response(JSON.stringify(FLEET_STATUS), { status: 200 });
        if (url === "/api/fleet/missions" && init?.method === "POST") {
          return new Response(
            JSON.stringify({ detail: { reason: "drone_already_en_route" } }),
            { status: 409 },
          );
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    renderDispatchBar();
    await selectFalcon01();
    fillLaunchForm();
    fireEvent.click(screen.getByRole("button", { name: "Launch Mission" }));

    await waitFor(() => {
      expect(screen.getByText(/drone_already_en_route/)).toBeInTheDocument();
    });
  });

  it("Test 5: a 422 insufficient_budget response on launch renders the reason plus both numerals at fixed precision", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/roster") return new Response(JSON.stringify(ROSTER_RESPONSE), { status: 200 });
        if (url === "/api/fleet") return new Response(JSON.stringify(FLEET_STATUS), { status: 200 });
        if (url === "/api/fleet/missions" && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              detail: { reason: "insufficient_budget", requested_kwh: 3.36, remaining_kwh: 1.2 },
            }),
            { status: 422 },
          );
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    renderDispatchBar();
    await selectFalcon01();
    fillLaunchForm();
    fireEvent.click(screen.getByRole("button", { name: "Launch Mission" }));

    await waitFor(() => {
      expect(screen.getByText(/insufficient_budget/)).toBeInTheDocument();
    });
    const errorText = screen.getByText(/insufficient_budget/).textContent ?? "";
    expect(errorText).toContain("3.36");
    expect(errorText).toContain("1.20");
  });

  it("Test 6: a 404 unknown_drone recall response renders that reason inline", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/roster") return new Response(JSON.stringify(ROSTER_RESPONSE), { status: 200 });
        if (url === "/api/fleet") return new Response(JSON.stringify(FLEET_STATUS), { status: 200 });
        if (url === "/api/fleet/missions/FALCON-01" && init?.method === "DELETE") {
          return new Response(JSON.stringify({ detail: { reason: "unknown_drone" } }), { status: 404 });
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    renderDispatchBar();
    await selectFalcon01();
    fireEvent.click(screen.getByRole("button", { name: "Recall" }));

    await waitFor(() => {
      expect(screen.getByText(/unknown_drone/)).toBeInTheDocument();
    });
  });

  it("Test 7: while a request is in flight both buttons are disabled, so a double-click cannot issue two writes", async () => {
    let deleteCalls = 0;
    const deferred: { resolve: (() => void) | null } = { resolve: null };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/roster") return new Response(JSON.stringify(ROSTER_RESPONSE), { status: 200 });
        if (url === "/api/fleet") return new Response(JSON.stringify(FLEET_STATUS), { status: 200 });
        if (url === "/api/fleet/missions/FALCON-01" && init?.method === "DELETE") {
          deleteCalls += 1;
          await new Promise<void>((resolve) => {
            deferred.resolve = resolve;
          });
          return new Response(JSON.stringify(RECALLED_MISSION), { status: 200 });
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    renderDispatchBar();
    await selectFalcon01();

    fireEvent.click(screen.getByRole("button", { name: "Recall" }));
    await waitFor(() => expect(deleteCalls).toBe(1));

    expect(screen.getByRole("button", { name: "Recall" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Launch Mission" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Recall" }));
    expect(deleteCalls).toBe(1);

    deferred.resolve?.();
    await waitFor(() => expect(screen.getByRole("button", { name: "Recall" })).not.toBeDisabled());
  });

  it("Test 8: a successful action clears any previously displayed error text", async () => {
    let launchAttempts = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/roster") return new Response(JSON.stringify(ROSTER_RESPONSE), { status: 200 });
        if (url === "/api/fleet") return new Response(JSON.stringify(FLEET_STATUS), { status: 200 });
        if (url === "/api/fleet/missions" && init?.method === "POST") {
          launchAttempts += 1;
          if (launchAttempts === 1) {
            return new Response(
              JSON.stringify({ detail: { reason: "drone_already_en_route" } }),
              { status: 409 },
            );
          }
          return new Response(JSON.stringify(LAUNCHED_MISSION), { status: 201 });
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    renderDispatchBar();
    await selectFalcon01();
    fillLaunchForm();
    fireEvent.click(screen.getByRole("button", { name: "Launch Mission" }));

    await waitFor(() => {
      expect(screen.getByText(/drone_already_en_route/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Launch Mission" }));

    await waitFor(() => {
      expect(screen.queryByText(/drone_already_en_route/)).not.toBeInTheDocument();
    });
  });
});
