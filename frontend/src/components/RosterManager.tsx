"use client";

import { useState } from "react";
import { addDrone, removeDrone } from "@/lib/api";
import type { RosterEntry } from "@/types/fleet";

interface Props {
  roster: RosterEntry[];
  onChanged: () => void;
}

export function RosterManager({ roster, onChanged }: Props) {
  const [droneId, setDroneId] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "roster update failed");
    }
  }

  return (
    <div data-testid="roster-manager" className="rounded-lg border border-ops-border bg-ops-panel">
      <div className="border-b border-ops-border px-4 py-2 text-sm font-semibold text-slate-300">
        Roster Management
      </div>
      <div className="space-y-3 p-4">
        <div className="flex gap-2">
          <input
            aria-label="New drone ID"
            className="flex-1 rounded border border-ops-border bg-ops-bg px-2 py-1 font-mono text-sm text-slate-200 outline-none focus:border-ops-teal"
            value={droneId}
            onChange={(e) => setDroneId(e.target.value)}
            placeholder="FALCON-11"
          />
          <button
            type="button"
            className="rounded bg-ops-teal px-3 py-1 text-sm font-semibold text-ops-bg hover:opacity-90"
            onClick={() => run(async () => { await addDrone(droneId); setDroneId(""); })}
          >
            Add
          </button>
        </div>
        <ul className="max-h-48 space-y-1 overflow-y-auto text-sm">
          {roster.map((entry) => (
            <li key={entry.drone_id} className="flex items-center justify-between">
              <span className="font-mono text-slate-300">{entry.drone_id}</span>
              <button
                type="button"
                aria-label={`Remove ${entry.drone_id}`}
                className="text-xs text-slate-500 hover:text-red-400"
                onClick={() => run(() => removeDrone(entry.drone_id))}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
        {error && <div className="text-xs text-red-400">{error}</div>}
      </div>
    </div>
  );
}
