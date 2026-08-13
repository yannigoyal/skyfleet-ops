"use client";

import { useEffect, useRef, useState } from "react";
import type { TelemetrySnapshot } from "@/types/telemetry";

export type ConnectionStatus = "connecting" | "connected" | "disconnected";

/**
 * Subscribes to GET /api/stream/telemetry via EventSource and keeps the
 * latest snapshot plus per-drone battery/altitude/speed history (for
 * sparklines and the detail panel), all accumulated client-side since mount
 * — the backend only ever sends the latest reading, matching the SSE
 * contract in planning/PLAN.md section 6.
 *
 * All three series share one push-then-shift cap at `maxHistoryPoints`
 * (default 120, roughly one minute at the 500ms SSE cadence) — this is what
 * implements D-03's bounded-history decision. The cap already existed for
 * battery; this hook extends the same guarantee to altitude and speed
 * rather than introducing it anew.
 */
export function useTelemetryStream(maxHistoryPoints = 120) {
  const [snapshot, setSnapshot] = useState<TelemetrySnapshot>({});
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const history = useRef<Record<string, number[]>>({});
  const altitudeHistory = useRef<Record<string, number[]>>({});
  const speedHistory = useRef<Record<string, number[]>>({});

  useEffect(() => {
    const source = new EventSource("/api/stream/telemetry");

    source.onopen = () => setStatus("connected");
    source.onerror = () => setStatus("disconnected");

    source.onmessage = (event) => {
      setStatus("connected");
      const data: TelemetrySnapshot = JSON.parse(event.data);
      setSnapshot(data);

      for (const [droneId, reading] of Object.entries(data)) {
        const batteryPoints = history.current[droneId] ?? [];
        batteryPoints.push(reading.battery_pct);
        if (batteryPoints.length > maxHistoryPoints) batteryPoints.shift();
        history.current[droneId] = batteryPoints;

        const altitudePoints = altitudeHistory.current[droneId] ?? [];
        altitudePoints.push(reading.altitude_m);
        if (altitudePoints.length > maxHistoryPoints) altitudePoints.shift();
        altitudeHistory.current[droneId] = altitudePoints;

        const speedPoints = speedHistory.current[droneId] ?? [];
        speedPoints.push(reading.speed_kmh);
        if (speedPoints.length > maxHistoryPoints) speedPoints.shift();
        speedHistory.current[droneId] = speedPoints;
      }
    };

    return () => source.close();
  }, [maxHistoryPoints]);

  return {
    snapshot,
    status,
    history: history.current,
    altitudeHistory: altitudeHistory.current,
    speedHistory: speedHistory.current,
  };
}
