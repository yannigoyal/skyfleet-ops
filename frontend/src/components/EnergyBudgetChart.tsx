"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { BudgetSnapshot } from "@/types/fleet";

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function EnergyBudgetChart({ snapshots }: { snapshots: BudgetSnapshot[] }) {
  const data = snapshots.map((snapshot) => ({
    time: formatTime(snapshot.recorded_at),
    remaining_kwh: snapshot.remaining_kwh,
  }));

  return (
    <div data-testid="energy-budget-chart" className="rounded-lg border border-ops-border bg-ops-panel">
      <div className="border-b border-ops-border px-4 py-2 text-sm font-semibold text-slate-300">
        Energy Budget
      </div>
      <div className="h-56 p-2">
        {data.length === 0 ? (
          <p className="p-4 text-sm text-slate-500">No budget snapshots yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
              <CartesianGrid stroke="#232a38" />
              <XAxis dataKey="time" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} unit=" kWh" width={70} />
              <Tooltip
                contentStyle={{ background: "#12161f", border: "1px solid #232a38", fontSize: 12 }}
              />
              <Line
                type="monotone"
                dataKey="remaining_kwh"
                stroke="#17a2b8"
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
