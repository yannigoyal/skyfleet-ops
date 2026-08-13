"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BudgetSnapshot } from "@/types/fleet";

const CHART_WIDTH = 640;
const CHART_HEIGHT = 220;

// Matches FleetOpsProvider's FLEET_POLL_INTERVAL_MS so the chart's trailing
// edge keeps pace with the header's live remaining-kWh figure rather than
// freezing at the mount-time history. This endpoint serves only this one
// component, so it deliberately fetches directly instead of widening
// FleetOpsProvider with a second concern.
const HISTORY_POLL_INTERVAL_MS = 5000;

function formatTimeOfDay(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatKwh(value: number): string {
  return `${value.toFixed(1)} kWh`;
}

interface BudgetTooltipProps {
  active?: boolean;
  payload?: { value: number }[];
  label?: string;
}

function BudgetTooltip({ active, payload, label }: BudgetTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded border border-ops-border bg-ops-panel px-2 py-1 text-xs text-slate-300">
      <div>{formatTimeOfDay(label ?? "")}</div>
      <div className="font-mono text-ops-teal">{formatKwh(payload[0].value)}</div>
    </div>
  );
}

/**
 * Energy-budget line chart (FE-04): remaining kWh over time, plotted from
 * the backend's own budget_snapshots via GET /api/fleet/history. Static
 * export (Pitfall 4) means this must be a client component doing its own
 * fetch. Guards the fetching effect against unmount with a cancelled flag
 * plus AbortController so a fast unmount or navigation never produces a
 * state update on an unmounted component.
 */
export function EnergyBudgetChart() {
  const [snapshots, setSnapshots] = useState<BudgetSnapshot[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function load() {
      try {
        const res = await fetch("/api/fleet/history", { signal: controller.signal });
        if (cancelled) return;
        if (!res.ok) {
          setError(`Failed to load budget history (${res.status})`);
          return;
        }
        const data: { snapshots: BudgetSnapshot[] } = await res.json();
        if (cancelled) return;
        setSnapshots(data.snapshots);
        setError(null);
      } catch {
        if (!cancelled) setError("Failed to load budget history");
      }
    }

    load();
    const id = setInterval(load, HISTORY_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      controller.abort();
      clearInterval(id);
    };
  }, []);

  return (
    <div className="rounded-lg border border-ops-border bg-ops-panel">
      <div className="border-b border-ops-border px-4 py-2 text-sm font-semibold text-slate-300">
        Energy Budget
      </div>
      <div className="p-4">
        {error && <p className="text-sm text-red-400">{error}</p>}
        {!error && snapshots !== null && snapshots.length === 0 && (
          <p className="text-sm text-slate-500">No budget history yet.</p>
        )}
        {!error && snapshots !== null && snapshots.length > 0 && (
          <ResponsiveContainer width={CHART_WIDTH} height={CHART_HEIGHT}>
            <LineChart data={snapshots}>
              <CartesianGrid stroke="#232a38" strokeDasharray="3 3" />
              <XAxis
                dataKey="recorded_at"
                tickFormatter={formatTimeOfDay}
                stroke="#64748b"
                fontSize={11}
                interval={0}
              />
              <YAxis tickFormatter={(value: number) => value.toFixed(1)} stroke="#64748b" fontSize={11} />
              <Tooltip content={<BudgetTooltip />} />
              <Line
                type="monotone"
                dataKey="remaining_kwh"
                stroke="#17a2b8"
                dot={false}
                strokeWidth={1.5}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
