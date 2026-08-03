import type { ConnectionStatus } from "@/lib/useTelemetryStream";
import { ConnectionDot } from "./ConnectionDot";

interface Props {
  connectionStatus: ConnectionStatus;
  energyBudgetKwh: number;
  activeMissionCount: number;
}

export function Header({ connectionStatus, energyBudgetKwh, activeMissionCount }: Props) {
  return (
    <header className="flex items-center justify-between border-b border-ops-border bg-ops-panel px-6 py-3">
      <div className="flex items-center gap-3">
        <span className="text-lg font-bold tracking-tight text-ops-amber">SkyFleet Ops</span>
        <span className="text-xs text-slate-500">Drone Delivery Command Center</span>
      </div>
      <div className="flex items-center gap-6 text-sm">
        <div className="text-slate-300">
          Energy Budget: <span className="font-mono text-ops-teal">{energyBudgetKwh.toFixed(1)} kWh</span>
        </div>
        <div className="text-slate-300">
          Active Missions: <span className="font-mono text-ops-teal">{activeMissionCount}</span>
        </div>
        <ConnectionDot status={connectionStatus} />
      </div>
    </header>
  );
}
