import { act } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useChat } from "./useChat";
import { FleetOpsProvider } from "./FleetOpsProvider";
import type { ReactNode } from "react";

const EMPTY_ROSTER = { drones: [] };
const EMPTY_FLEET = {
  energy_budget_kwh: 500,
  remaining_kwh: 500,
  active_mission_count: 0,
  missions: [],
};

class NoOpEventSource {
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  close() {}
}

function wrapper({ children }: { children: ReactNode }) {
  return <FleetOpsProvider>{children}</FleetOpsProvider>;
}

/** Stubs GET /api/fleet and GET /api/roster (required for FleetOpsProvider's
 * mount-triggered refetch) plus a caller-supplied handler for POST /api/chat. */
function stubFetch(chatHandler: (init?: RequestInit) => Promise<Response> | Response) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/roster") return new Response(JSON.stringify(EMPTY_ROSTER), { status: 200 });
      if (url === "/api/fleet") return new Response(JSON.stringify(EMPTY_FLEET), { status: 200 });
      if (url === "/api/chat") return chatHandler(init);
      throw new Error(`Unhandled fetch: ${url}`);
    }),
  );
}

describe("useChat — one turn at a time, with the D-07 shared refetch", () => {
  beforeEach(() => {
    vi.stubGlobal("EventSource", NoOpEventSource as unknown as typeof EventSource);
  });

  it("Test 1: sending a message appends a user turn immediately, before the response resolves", async () => {
    const deferred: { resolve: (() => void) | null } = { resolve: null };
    stubFetch(async () => {
      await new Promise<void>((resolve) => {
        deferred.resolve = resolve;
      });
      return new Response(
        JSON.stringify({ message: "ok", missions: [], roster_changes: [], errors: [] }),
        { status: 200 },
      );
    });

    const { result } = renderHook(() => useChat(), { wrapper });

    act(() => {
      result.current.send("status report");
    });

    await waitFor(() => {
      expect(result.current.turns).toHaveLength(1);
    });
    expect(result.current.turns[0]).toMatchObject({ role: "user", content: "status report" });

    deferred.resolve?.();
    await waitFor(() => expect(result.current.sending).toBe(false));
  });

  it("Test 2: a successful response appends one assistant turn carrying message, missions, roster_changes, and errors", async () => {
    stubFetch(
      () =>
        new Response(
          JSON.stringify({
            message: "Launching now.",
            missions: [{ drone_id: "FALCON-03", action: "launch", zone: "Riverside", distance_km: 4.2 }],
            roster_changes: [],
            errors: ["Could not recall FALCON-09: no_active_mission."],
          }),
          { status: 200 },
        ),
    );

    const { result } = renderHook(() => useChat(), { wrapper });

    await act(async () => {
      await result.current.send("launch falcon 3 to riverside");
    });

    await waitFor(() => {
      expect(result.current.turns).toHaveLength(2);
    });
    expect(result.current.turns[1]).toMatchObject({
      role: "assistant",
      content: "Launching now.",
      missions: [{ drone_id: "FALCON-03", action: "launch", zone: "Riverside", distance_km: 4.2 }],
      roster_changes: [],
      errors: ["Could not recall FALCON-09: no_active_mission."],
    });
  });

  it("Test 3 (D-08): sending is true until the response settles, and a second send while true is a no-op", async () => {
    let chatCalls = 0;
    const deferred: { resolve: (() => void) | null } = { resolve: null };
    stubFetch(async () => {
      chatCalls += 1;
      await new Promise<void>((resolve) => {
        deferred.resolve = resolve;
      });
      return new Response(
        JSON.stringify({ message: "ok", missions: [], roster_changes: [], errors: [] }),
        { status: 200 },
      );
    });

    const { result } = renderHook(() => useChat(), { wrapper });

    act(() => {
      result.current.send("first");
    });
    await waitFor(() => expect(result.current.sending).toBe(true));

    act(() => {
      result.current.send("second");
    });
    expect(chatCalls).toBe(1);
    expect(result.current.turns).toHaveLength(1);

    deferred.resolve?.();
    await waitFor(() => expect(result.current.sending).toBe(false));
  });

  it("Test 4 (D-07): a response with non-empty missions or roster_changes triggers refetch exactly once; both-empty does not", async () => {
    let fleetCallCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/roster") return new Response(JSON.stringify(EMPTY_ROSTER), { status: 200 });
        if (url === "/api/fleet") {
          fleetCallCount += 1;
          return new Response(JSON.stringify(EMPTY_FLEET), { status: 200 });
        }
        if (url === "/api/chat") {
          return new Response(
            JSON.stringify({
              message: "no actions",
              missions: [],
              roster_changes: [],
              errors: [],
            }),
            { status: 200 },
          );
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    const { result } = renderHook(() => useChat(), { wrapper });
    await waitFor(() => expect(fleetCallCount).toBe(1)); // provider's mount-triggered refetch

    await act(async () => {
      await result.current.send("what's the status");
    });

    // No missions/roster_changes were returned -> refetch must not fire again.
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(fleetCallCount).toBe(1);

    // Now a response that does execute an action.
    stubFetch(
      () =>
        new Response(
          JSON.stringify({
            message: "Launched.",
            missions: [{ drone_id: "FALCON-01", action: "launch", zone: "Downtown", distance_km: 2 }],
            roster_changes: [],
            errors: [],
          }),
          { status: 200 },
        ),
    );

    await act(async () => {
      await result.current.send("launch falcon 1");
    });

    await waitFor(() => expect(result.current.turns).toHaveLength(4));
  });

  it("Test 5 (backstop, transport failure): a rejected fetch appends one system turn with the exact copy, sending false, no assistant turn, no refetch", async () => {
    let fleetCallCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/roster") return new Response(JSON.stringify(EMPTY_ROSTER), { status: 200 });
        if (url === "/api/fleet") {
          fleetCallCount += 1;
          return new Response(JSON.stringify(EMPTY_FLEET), { status: 200 });
        }
        if (url === "/api/chat") throw new TypeError("Failed to fetch");
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    const { result } = renderHook(() => useChat(), { wrapper });
    await waitFor(() => expect(fleetCallCount).toBe(1));

    await act(async () => {
      await result.current.send("hello?");
    });

    await waitFor(() => expect(result.current.turns).toHaveLength(2));
    expect(result.current.turns[1]).toMatchObject({
      role: "system",
      content: "Connection error — try sending your message again.",
    });
    expect(result.current.sending).toBe(false);
    expect(fleetCallCount).toBe(1);
  });

  it("Test 6: a non-2xx HTTP response is handled the same way as a rejected fetch — a system turn, not a thrown error", async () => {
    stubFetch(() => new Response(JSON.stringify({ detail: "bad gateway" }), { status: 502 }));

    const { result } = renderHook(() => useChat(), { wrapper });

    await act(async () => {
      await result.current.send("hello?");
    });

    await waitFor(() => expect(result.current.turns).toHaveLength(2));
    expect(result.current.turns[1]).toMatchObject({
      role: "system",
      content: "Connection error — try sending your message again.",
    });
    expect(result.current.sending).toBe(false);
  });

  it("Test 7: an empty or whitespace-only input is not sent at all", async () => {
    let chatCalls = 0;
    stubFetch(() => {
      chatCalls += 1;
      return new Response(
        JSON.stringify({ message: "ok", missions: [], roster_changes: [], errors: [] }),
        { status: 200 },
      );
    });

    const { result } = renderHook(() => useChat(), { wrapper });

    await act(async () => {
      await result.current.send("   ");
    });

    expect(chatCalls).toBe(0);
    expect(result.current.turns).toHaveLength(0);
  });
});
