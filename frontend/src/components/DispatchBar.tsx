"use client";

import { useState } from "react";
import { useFleetOps } from "@/lib/FleetOpsProvider";

interface DispatchError {
  reason: string;
  requested_kwh?: number;
  remaining_kwh?: number;
}

/**
 * Manual mission launch and recall form (FE-06). Renders a roster dropdown
 * (D-15 — an invalid drone id is impossible to type), a free-text zone
 * field, a distance input, and Launch/Recall controls sharing the selected
 * drone. Launch submits POST to the missions collection; Recall issues a
 * DELETE against the selected drone's mission — the only path that ever
 * puts a mission into `recalled` status (D-01). Both surface the backend's
 * reason-coded error verbatim (D-14) — no client-side eligibility/budget/
 * roster re-validation is duplicated here, and neither path shows a
 * confirmation dialog (an explicitly ratified Out of Scope item).
 */
export function DispatchBar() {
  const { roster, upsertMission, refetch } = useFleetOps();
  const [droneId, setDroneId] = useState("");
  const [zone, setZone] = useState("");
  const [distanceKm, setDistanceKm] = useState("");
  const [error, setError] = useState<DispatchError | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(request: () => Promise<Response>) {
    setError(null);
    setSubmitting(true);
    try {
      const res = await request();
      const body = await res.json();
      if (!res.ok) {
        setError(body.detail ?? { reason: "dispatch_failed" });
        return;
      }
      upsertMission(body);
      await refetch();
    } catch {
      setError({ reason: "connection_error" });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLaunch(event: React.FormEvent) {
    event.preventDefault();
    await submit(() =>
      fetch("/api/fleet/missions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          drone_id: droneId,
          zone,
          distance_km: Number(distanceKm),
        }),
      }),
    );
  }

  async function handleRecall() {
    if (!droneId) return;
    await submit(() => fetch(`/api/fleet/missions/${droneId}`, { method: "DELETE" }));
  }

  return (
    <div className="rounded-lg border border-ops-border bg-ops-panel">
      <div className="border-b border-ops-border px-4 py-2 text-sm font-semibold text-slate-300">
        Dispatch
      </div>
      <form onSubmit={handleLaunch} className="flex flex-wrap items-end gap-3 p-4">
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Drone
          <select
            value={droneId}
            onChange={(event) => setDroneId(event.target.value)}
            required
            className="rounded border border-ops-border bg-ops-bg px-2 py-1 text-sm text-slate-200"
          >
            <option value="" disabled>
              Select drone
            </option>
            {roster.map((drone) => (
              <option key={drone.drone_id} value={drone.drone_id}>
                {drone.drone_id}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Zone
          <input
            type="text"
            value={zone}
            onChange={(event) => setZone(event.target.value)}
            required
            className="rounded border border-ops-border bg-ops-bg px-2 py-1 text-sm text-slate-200"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Distance (km)
          <input
            type="number"
            min="0.1"
            step="0.1"
            value={distanceKm}
            onChange={(event) => setDistanceKm(event.target.value)}
            required
            className="w-24 rounded border border-ops-border bg-ops-bg px-2 py-1 text-sm text-slate-200"
          />
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-ops-signal px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          Launch Mission
        </button>
        <button
          type="button"
          onClick={handleRecall}
          disabled={submitting || !droneId}
          className="rounded border border-ops-border px-4 py-1.5 text-sm font-semibold text-slate-300 disabled:opacity-50"
        >
          Recall
        </button>
      </form>
      {error && (
        <div className="px-4 pb-4 text-sm text-red-400">
          {error.reason}
          {error.requested_kwh !== undefined && error.remaining_kwh !== undefined && (
            <>
              {" "}
              (requested {error.requested_kwh.toFixed(2)} kWh, remaining{" "}
              {error.remaining_kwh.toFixed(2)} kWh)
            </>
          )}
        </div>
      )}
    </div>
  );
}
