import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useTelemetryStream } from "./useTelemetryStream";
import type { TelemetrySnapshot } from "@/types/telemetry";

/** Controllable fake EventSource: records the assigned handlers and lets a
 * test drive them directly, plus tracks close() calls. */
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  closed = false;

  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }

  emit(data: TelemetrySnapshot) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }

  close() {
    this.closed = true;
  }
}

function reading(overrides: Partial<TelemetrySnapshot[string]> & { drone_id: string; battery_pct: number }) {
  return {
    previous_battery_pct: overrides.battery_pct,
    altitude_m: 100,
    speed_kmh: 30,
    status: "in_flight" as const,
    timestamp: Date.now(),
    battery_delta: 0,
    battery_direction: "flat" as const,
    ...overrides,
  };
}

describe("useTelemetryStream — widened with capped altitude and speed history", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);
  });

  it("Test 1: after three SSE messages for one drone, battery/altitude/speed histories each have 3 points", () => {
    const { result } = renderHook(() => useTelemetryStream());
    const source = FakeEventSource.instances[0];

    act(() => {
      source.emit({ "FALCON-01": reading({ drone_id: "FALCON-01", battery_pct: 90, altitude_m: 100, speed_kmh: 30 }) });
      source.emit({ "FALCON-01": reading({ drone_id: "FALCON-01", battery_pct: 89, altitude_m: 101, speed_kmh: 31 }) });
      source.emit({ "FALCON-01": reading({ drone_id: "FALCON-01", battery_pct: 88, altitude_m: 102, speed_kmh: 32 }) });
    });

    expect(result.current.history["FALCON-01"]).toHaveLength(3);
    expect(result.current.altitudeHistory["FALCON-01"]).toHaveLength(3);
    expect(result.current.speedHistory["FALCON-01"]).toHaveLength(3);
  });

  it("Test 2: with maxHistoryPoints=2, a fourth message caps all three series at length 2", () => {
    const { result } = renderHook(() => useTelemetryStream(2));
    const source = FakeEventSource.instances[0];

    act(() => {
      for (let i = 0; i < 4; i++) {
        source.emit({
          "FALCON-01": reading({ drone_id: "FALCON-01", battery_pct: 90 - i, altitude_m: 100 + i, speed_kmh: 30 + i }),
        });
      }
    });

    expect(result.current.history["FALCON-01"]).toHaveLength(2);
    expect(result.current.altitudeHistory["FALCON-01"]).toHaveLength(2);
    expect(result.current.speedHistory["FALCON-01"]).toHaveLength(2);
  });

  // Test 3 (backstop): held-out for the FE-01 ordering condition — appending
  // readings must never reorder already-stored points.
  it("Test 3 (backstop): appending strictly increasing battery readings preserves chronological order", () => {
    const { result } = renderHook(() => useTelemetryStream());
    const source = FakeEventSource.instances[0];

    act(() => {
      source.emit({ "FALCON-01": reading({ drone_id: "FALCON-01", battery_pct: 10 }) });
      source.emit({ "FALCON-01": reading({ drone_id: "FALCON-01", battery_pct: 20 }) });
      source.emit({ "FALCON-01": reading({ drone_id: "FALCON-01", battery_pct: 30 }) });
    });

    expect(result.current.history["FALCON-01"]).toEqual([10, 20, 30]);
  });

  it("Test 4: the existing history key still holds Record<string, number[]> battery percentages", () => {
    const { result } = renderHook(() => useTelemetryStream());
    const source = FakeEventSource.instances[0];

    act(() => {
      source.emit({ "FALCON-01": reading({ drone_id: "FALCON-01", battery_pct: 77 }) });
    });

    expect(result.current.history["FALCON-01"][0]).toBe(77);
  });

  it("Test 5: the hook closes its EventSource on unmount", () => {
    const { unmount } = renderHook(() => useTelemetryStream());
    const source = FakeEventSource.instances[0];
    expect(source.closed).toBe(false);

    unmount();

    expect(source.closed).toBe(true);
  });
});
