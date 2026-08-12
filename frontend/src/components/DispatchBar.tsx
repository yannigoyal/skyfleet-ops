"use client";

import { useState } from "react";
import { launchMission, recallMission } from "@/lib/api";

const INPUT_CLASS =
  "rounded border border-ops-border bg-ops-bg px-2 py-1 font-mono text-sm text-slate-200 outline-none focus:border-ops-teal";

export function DispatchBar({ onDispatched }: { onDispatched: () => void }) {
  const [droneId, setDroneId] = useState("");
  const [zone, setZone] = useState("");
  const [distanceKm, setDistanceKm] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      onDispatched();
    } catch (err) {
      setError(err instanceof Error ? err.message : "dispatch failed");
    }
  }

  return (
    <div className="rounded-lg border border-ops-border bg-ops-panel p-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs uppercase text-slate-500" htmlFor="dispatch-drone">
          Drone
        </label>
        <input
          id="dispatch-drone"
          className={INPUT_CLASS}
          value={droneId}
          onChange={(e) => setDroneId(e.target.value)}
          placeholder="FALCON-01"
        />
        <label className="text-xs uppercase text-slate-500" htmlFor="dispatch-zone">
          Zone
        </label>
        <input
          id="dispatch-zone"
          className={INPUT_CLASS}
          value={zone}
          onChange={(e) => setZone(e.target.value)}
          placeholder="Riverside"
        />
        <label className="text-xs uppercase text-slate-500" htmlFor="dispatch-distance">
          Distance km
        </label>
        <input
          id="dispatch-distance"
          className={`${INPUT_CLASS} w-24`}
          type="number"
          min="0"
          step="0.1"
          value={distanceKm}
          onChange={(e) => setDistanceKm(e.target.value)}
        />
        <button
          type="button"
          className="rounded bg-ops-signal px-3 py-1 text-sm font-semibold text-ops-bg hover:opacity-90"
          onClick={() => run(() => launchMission(droneId, zone, Number(distanceKm)))}
        >
          Launch
        </button>
        <button
          type="button"
          className="rounded border border-ops-border px-3 py-1 text-sm text-slate-300 hover:bg-white/5"
          onClick={() => run(() => recallMission(droneId))}
        >
          Recall
        </button>
      </div>
      {error && <div className="mt-2 text-xs text-red-400">{error}</div>}
    </div>
  );
}
