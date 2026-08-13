"use client";

import { Header } from "@/components/Header";
import { FleetRosterPanel } from "@/components/FleetRosterPanel";
import { DetailPanel } from "@/components/DetailPanel";
import { DispatchBar } from "@/components/DispatchBar";
import { MissionsTable } from "@/components/MissionsTable";
import { FleetHeatmap } from "@/components/FleetHeatmap";
import { EnergyBudgetChart } from "@/components/EnergyBudgetChart";
import { useTelemetryStream } from "@/lib/useTelemetryStream";
import { FleetOpsProvider, useFleetOps } from "@/lib/FleetOpsProvider";

// Mission control, chat, and roster CRUD are specified in planning/PLAN.md
// (sections 8-10). The dispatch bar and live fleet header are wired up
// through FleetOpsProvider; chat remains a placeholder — see plan 06.
function Console() {
  const { snapshot, status, history, altitudeHistory, speedHistory } = useTelemetryStream();
  const { remainingKwh, energyBudgetKwh, activeMissionCount, selectedDroneId, select } =
    useFleetOps();

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        connectionStatus={status}
        remainingKwh={remainingKwh}
        energyBudgetKwh={energyBudgetKwh}
        activeMissionCount={activeMissionCount}
      />
      <main className="grid flex-1 grid-cols-1 gap-4 p-6 lg:grid-cols-3">
        <div className="flex flex-col gap-4 lg:col-span-2">
          <DispatchBar />
          <FleetRosterPanel
            snapshot={snapshot}
            history={history}
            selectedDroneId={selectedDroneId}
            onSelect={select}
          />
          <DetailPanel
            snapshot={snapshot}
            history={history}
            altitudeHistory={altitudeHistory}
            speedHistory={speedHistory}
          />
          <FleetHeatmap snapshot={snapshot} />
          <EnergyBudgetChart />
          <MissionsTable />
        </div>
        <aside className="rounded-lg border border-ops-border bg-ops-panel p-4 text-sm text-slate-400">
          <div className="mb-2 font-semibold text-slate-300">AI Flight Director</div>
          <p>Chat integration is specified in planning/PLAN.md section 9 — not yet implemented.</p>
        </aside>
      </main>
    </div>
  );
}

export default function Home() {
  return (
    <FleetOpsProvider>
      <Console />
    </FleetOpsProvider>
  );
}
