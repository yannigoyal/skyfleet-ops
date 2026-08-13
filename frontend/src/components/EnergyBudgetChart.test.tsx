import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { EnergyBudgetChart } from "./EnergyBudgetChart";
import type { BudgetSnapshot } from "@/types/fleet";

function snapshot(overrides: Partial<BudgetSnapshot> = {}): BudgetSnapshot {
  return {
    remaining_kwh: 487.36,
    recorded_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function historyResponse(snapshots: BudgetSnapshot[], status = 200) {
  return new Response(JSON.stringify({ snapshots }), { status });
}

describe("EnergyBudgetChart — remaining kWh over time from GET /api/fleet/history", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("Test 1: given three snapshots the chart renders a path and the axis reflects three data points", async () => {
    const snapshots = [
      snapshot({ remaining_kwh: 500, recorded_at: "2026-01-01T00:00:00Z" }),
      snapshot({ remaining_kwh: 495, recorded_at: "2026-01-01T00:00:30Z" }),
      snapshot({ remaining_kwh: 490, recorded_at: "2026-01-01T00:01:00Z" }),
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => historyResponse(snapshots)),
    );

    const { container } = render(<EnergyBudgetChart />);

    await waitFor(() => {
      expect(container.querySelectorAll(".recharts-line-curve").length).toBe(1);
    });
    expect(
      container.querySelectorAll(".recharts-xAxis .recharts-cartesian-axis-tick").length,
    ).toBe(3);
  });

  it("Test 2: given an empty snapshots array the component renders an empty-state message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => historyResponse([])),
    );

    render(<EnergyBudgetChart />);

    await waitFor(() => {
      expect(screen.getByText(/no budget history/i)).toBeInTheDocument();
    });
  });

  it("Test 3: a snapshot whose remaining_kwh is 0 renders without collapsing the chart or producing NaN coordinates", async () => {
    const snapshots = [
      snapshot({ remaining_kwh: 0, recorded_at: "2026-01-01T00:00:00Z" }),
      snapshot({ remaining_kwh: 10, recorded_at: "2026-01-01T00:00:30Z" }),
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => historyResponse(snapshots)),
    );

    const { container } = render(<EnergyBudgetChart />);

    await waitFor(() => {
      expect(container.querySelectorAll(".recharts-line-curve").length).toBe(1);
    });
    const path = container.querySelector(".recharts-line-curve");
    expect(path?.getAttribute("d") ?? "").not.toContain("NaN");
  });

  it("Test 4 (backstop, concurrency): unmounting while the fetch promise is pending produces no state update and no warning", async () => {
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    let resolveFetch: (value: Response) => void = () => {};
    const pending = new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => pending),
    );

    const { unmount } = render(<EnergyBudgetChart />);
    unmount();
    resolveFetch(historyResponse([snapshot()]));
    // Flush the resolved promise's microtask/macrotask queue.
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(consoleErrorSpy).not.toHaveBeenCalled();
  });

  it("Test 5: a non-2xx response from the history endpoint renders an inline error message instead of throwing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => historyResponse([], 500)),
    );

    render(<EnergyBudgetChart />);

    await waitFor(() => {
      expect(screen.getByText(/failed to load budget history/i)).toBeInTheDocument();
    });
  });
});
