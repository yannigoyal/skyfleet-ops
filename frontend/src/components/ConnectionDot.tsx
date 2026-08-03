import type { ConnectionStatus } from "@/lib/useTelemetryStream";

const COLORS: Record<ConnectionStatus, string> = {
  connected: "bg-emerald-500",
  connecting: "bg-ops-amber",
  disconnected: "bg-red-500",
};

const LABELS: Record<ConnectionStatus, string> = {
  connected: "Live",
  connecting: "Connecting",
  disconnected: "Disconnected",
};

export function ConnectionDot({ status }: { status: ConnectionStatus }) {
  return (
    <div className="flex items-center gap-2 text-xs text-slate-400">
      <span className={`h-2 w-2 rounded-full ${COLORS[status]}`} />
      {LABELS[status]}
    </div>
  );
}
