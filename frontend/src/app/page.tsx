"use client";

import { Header } from "@/components/Header";
import { FleetRosterPanel } from "@/components/FleetRosterPanel";
import { DetailPanel } from "@/components/DetailPanel";
import { DispatchBar } from "@/components/DispatchBar";
import { MissionsTable } from "@/components/MissionsTable";
import { FleetHeatmap } from "@/components/FleetHeatmap";
import { EnergyBudgetChart } from "@/components/EnergyBudgetChart";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { useTelemetryStream } from "@/lib/useTelemetryStream";
import { FleetOpsProvider, useFleetOps } from "@/lib/FleetOpsProvider";

// Mission control and roster CRUD are specified in planning/PLAN.md
// (sections 8-10). The dispatch bar, live fleet header, and AI flight
// director chat sidebar are all wired up through FleetOpsProvider — this is
// the phase's final mount (plan 06).
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
        <ChatPanel />
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
