"use client";

import { useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { DispatchBar } from "@/components/DispatchBar";
import { DroneDetailPanel } from "@/components/DroneDetailPanel";
import { EnergyBudgetChart } from "@/components/EnergyBudgetChart";
import { FleetHeatmap } from "@/components/FleetHeatmap";
import { FleetRosterPanel } from "@/components/FleetRosterPanel";
import { Header } from "@/components/Header";
import { MissionsTable } from "@/components/MissionsTable";
import { RosterManager } from "@/components/RosterManager";
import { useFleet } from "@/lib/useFleet";
import { useTelemetryStream } from "@/lib/useTelemetryStream";

export default function Home() {
  const { snapshot, status, history } = useTelemetryStream();
  const { fleet, history: budgetHistory, roster, refresh } = useFleet();
  const [selectedDroneId, setSelectedDroneId] = useState<string | null>(null);

  const selectedReading = selectedDroneId ? (snapshot[selectedDroneId] ?? null) : null;
  const selectedMission =
    fleet.missions.find((m) => m.drone_id === selectedDroneId && m.status === "en_route") ?? null;

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        connectionStatus={status}
        energyBudgetKwh={fleet.remaining_kwh}
        activeMissionCount={fleet.active_mission_count}
      />
      <main className="grid flex-1 grid-cols-1 gap-4 p-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <DispatchBar onDispatched={refresh} />
          <FleetRosterPanel
            snapshot={snapshot}
            history={history}
            selectedDroneId={selectedDroneId}
            onSelect={setSelectedDroneId}
          />
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <FleetHeatmap snapshot={snapshot} missions={fleet.missions} />
            <EnergyBudgetChart snapshots={budgetHistory} />
          </div>
          <MissionsTable missions={fleet.missions} />
        </div>
        <aside className="flex flex-col gap-4">
          <DroneDetailPanel
            reading={selectedReading}
            batteryHistory={selectedDroneId ? (history[selectedDroneId] ?? []) : []}
            mission={selectedMission}
          />
          <RosterManager roster={roster} onChanged={refresh} />
          <div className="min-h-[24rem] flex-1">
            <ChatPanel onActionsExecuted={refresh} />
          </div>
        </aside>
      </main>
    </div>
  );
}
