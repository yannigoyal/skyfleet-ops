"use client";

import { useState } from "react";
import { Header } from "@/components/Header";
import { FleetRosterPanel } from "@/components/FleetRosterPanel";
import { useTelemetryStream } from "@/lib/useTelemetryStream";

// Mission control, chat, and roster CRUD are specified in planning/PLAN.md
// (sections 8-10) but not yet built — this page wires up the one thing that
// is fully implemented end-to-end today: the live telemetry stream.
export default function Home() {
  const { snapshot, status } = useTelemetryStream();
  const [selectedDroneId, setSelectedDroneId] = useState<string | null>(null);

  return (
    <div className="flex min-h-screen flex-col">
      <Header connectionStatus={status} energyBudgetKwh={500.0} activeMissionCount={0} />
      <main className="grid flex-1 grid-cols-1 gap-4 p-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <FleetRosterPanel
            snapshot={snapshot}
            selectedDroneId={selectedDroneId}
            onSelect={setSelectedDroneId}
          />
        </div>
        <aside className="rounded-lg border border-ops-border bg-ops-panel p-4 text-sm text-slate-400">
          <div className="mb-2 font-semibold text-slate-300">AI Flight Director</div>
          <p>Chat integration is specified in planning/PLAN.md section 9 — not yet implemented.</p>
        </aside>
      </main>
    </div>
  );
}
