import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { FleetOpsProvider, useFleetOps, mergeMissions } from "./FleetOpsProvider";
import type { Mission } from "@/types/fleet";

function mission(overrides: Partial<Mission> & { id: string }): Mission {
  return {
    drone_id: "FALCON-01",
    zone: "Riverside",
    distance_km: 4.2,
    energy_cost_kwh: 3.36,
    status: "en_route",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("mergeMissions", () => {
  it("Test 1: empty previous map + one active mission yields a one-entry en_route map", () => {
    const next = mergeMissions(new Map(), [mission({ id: "m1" })]);
    expect(next.size).toBe(1);
    expect(next.get("m1")?.status).toBe("en_route");
  });

  it("Test 2: an en_route mission absent from the new active list becomes delivered, not removed", () => {
    const prev = new Map([["m1", mission({ id: "m1", status: "en_route" })]]);
    const next = mergeMissions(prev, []);
    expect(next.has("m1")).toBe(true);
    expect(next.get("m1")?.status).toBe("delivered");
  });

  it("Test 3: a recalled mission absent from the new active list stays recalled", () => {
    const prev = new Map([["m1", mission({ id: "m1", status: "recalled" })]]);
    const next = mergeMissions(prev, []);
    expect(next.get("m1")?.status).toBe("recalled");
  });

  it("Test 4: merging the same active list twice is idempotent", () => {
    const active = [mission({ id: "m1" })];
    const once = mergeMissions(new Map(), active);
    const twice = mergeMissions(once, active);
    expect(Array.from(twice.entries())).toEqual(Array.from(once.entries()));
  });

  it("Test 5: a re-included previously-delivered id is restored to en_route", () => {
    const prev = new Map([["m1", mission({ id: "m1", status: "delivered" })]]);
    const next = mergeMissions(prev, [mission({ id: "m1", status: "en_route" })]);
    expect(next.get("m1")?.status).toBe("en_route");
  });
});

function Probe() {
  const { remainingKwh, loaded } = useFleetOps();
  return <div data-testid="probe">{loaded ? remainingKwh : "loading"}</div>;
}

function Trigger() {
  const { refetch } = useFleetOps();
  return (
    <button onClick={() => refetch()}>refetch</button>
  );
}

// Test 10 (backstop): held out for the FE-07 concurrency condition
// (RESEARCH.md Pitfall 2) — do not delete as "redundant". Test 4 above pins
// mergeMissions's pure-function idempotency; this test drives the guarantee
// through real React state via two overlapping refetch() calls where the
// OLDER (mount-triggered) request resolves AFTER the NEWER
// (action-triggered) request, and asserts the UI never rolls back to the
// stale value the older, later-arriving response carried.
describe("FleetOpsProvider refetch out-of-order resolution (RESEARCH.md Pitfall 2)", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("Test 10 (backstop): a stale response that resolves after a fresher one never rolls remainingKwh backward", async () => {
    let fleetCallCount = 0;
    const stale = { energy_budget_kwh: 500, remaining_kwh: 500.0, active_mission_count: 0, missions: [] };
    const fresh = { energy_budget_kwh: 500, remaining_kwh: 496.6, active_mission_count: 1, missions: [] };

    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      async (input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/roster") {
          return new Response(JSON.stringify({ drones: [] }), { status: 200 });
        }
        if (url === "/api/fleet") {
          fleetCallCount += 1;
          if (fleetCallCount === 1) {
            // Mount-triggered call: issued first, but resolves LAST (slow
            // network) with STALE pre-mutation data.
            await new Promise((resolve) => setTimeout(resolve, 30));
            return new Response(JSON.stringify(stale), { status: 200 });
          }
          // Action-triggered call: issued second, resolves FIRST with FRESH
          // post-mutation data.
          return new Response(JSON.stringify(fresh), { status: 200 });
        }
        throw new Error(`Unhandled fetch: ${url}`);
      },
    );

    render(
      <FleetOpsProvider>
        <Probe />
        <Trigger />
      </FleetOpsProvider>,
    );

    // Fire the second (fresh, fast) refetch while the first (stale, slow)
    // mount-triggered fetch is still in flight.
    await waitFor(() => expect(fleetCallCount).toBe(1));
    screen.getByText("refetch").click();

    await waitFor(() => {
      expect(screen.getByTestId("probe").textContent).toBe("496.6");
    });

    // Give the slow, stale first call time to resolve and confirm it never
    // rolls the settled value backward to the pre-mutation 500.
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.getByTestId("probe").textContent).toBe("496.6");
  });
});
