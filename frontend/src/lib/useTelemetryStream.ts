"use client";

import { useEffect, useRef, useState } from "react";
import type { TelemetrySnapshot } from "@/types/telemetry";

export type ConnectionStatus = "connecting" | "connected" | "disconnected";

/**
 * Subscribes to GET /api/stream/telemetry via EventSource and keeps the
 * latest snapshot plus a per-drone battery history (for sparklines), both
 * accumulated client-side since mount — the backend only ever sends the
 * latest reading, matching the SSE contract in planning/PLAN.md section 6.
 */
export function useTelemetryStream(maxHistoryPoints = 120) {
  const [snapshot, setSnapshot] = useState<TelemetrySnapshot>({});
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const history = useRef<Record<string, number[]>>({});

  useEffect(() => {
    const source = new EventSource("/api/stream/telemetry");

    source.onopen = () => setStatus("connected");
    source.onerror = () => setStatus("disconnected");

    source.onmessage = (event) => {
      setStatus("connected");
      const data: TelemetrySnapshot = JSON.parse(event.data);
      setSnapshot(data);

      for (const [droneId, reading] of Object.entries(data)) {
        const points = history.current[droneId] ?? [];
        points.push(reading.battery_pct);
        if (points.length > maxHistoryPoints) points.shift();
        history.current[droneId] = points;
      }
    };

    return () => source.close();
  }, [maxHistoryPoints]);

  return { snapshot, status, history: history.current };
}
