import type { ChatMissionAction, ChatRosterChange } from "@/types/chat";

type ExecutedAction = "launch" | "recall" | "add" | "remove";

const ACTION_VERB: Record<ExecutedAction, string> = {
  launch: "LAUNCH",
  recall: "RECALL",
  add: "ADD",
  remove: "REMOVE",
};

const OUTCOME_BADGE: Record<ExecutedAction, string> = {
  launch: "Dispatched",
  recall: "Recalled",
  add: "Added",
  remove: "Removed",
};

type SuccessEntry = ChatMissionAction | ChatRosterChange;

type Props = { kind: "success"; entry: SuccessEntry } | { kind: "failure"; message: string };

function isLaunch(entry: SuccessEntry): entry is ChatMissionAction & { action: "launch" } {
  return entry.action === "launch";
}

/**
 * Compact action-outcome card (FE-09, D-06). A success card renders only for
 * an entry the backend actually returned in `missions`/`roster_changes`; a
 * failure card renders one `errors` string. The two are never conflated —
 * an unexecuted action must never carry a success badge (T-03-25) — and both
 * shapes carry equal visual weight so a failure is never quieter than an
 * adjacent success. Zone truncation is CSS ellipsis on a max-width, never
 * index/byte arithmetic, so a multi-byte zone name can never be split
 * mid-character (T-03-24).
 */
export function ConfirmationCard(props: Props) {
  if (props.kind === "failure") {
    return (
      <div
        data-testid="confirmation-card"
        className="rounded border border-ops-border bg-ops-bg px-3 py-1.5 text-xs"
      >
        <span className="mr-2 rounded bg-red-500/20 px-1.5 py-0.5 font-semibold text-red-400">
          Failed:
        </span>
        <span className="text-slate-300">{props.message}</span>
      </div>
    );
  }

  const { entry } = props;
  const verb = ACTION_VERB[entry.action];
  const badge = OUTCOME_BADGE[entry.action];
  const showRoute = isLaunch(entry) && entry.zone !== undefined && entry.distance_km !== undefined;

  return (
    <div
      data-testid="confirmation-card"
      className="rounded border border-ops-border bg-ops-bg px-3 py-1.5 text-xs"
    >
      <span className="font-mono text-slate-200">
        {verb} {entry.drone_id}
        {showRoute && isLaunch(entry) && (
          <>
            {" "}
            &rarr;{" "}
            <span
              className="inline-block max-w-[8rem] truncate align-bottom"
              title={entry.zone}
            >
              {entry.zone}
            </span>{" "}
            ({entry.distance_km?.toFixed(1)}km)
          </>
        )}
      </span>
      <span className="ml-2 rounded bg-emerald-500/20 px-1.5 py-0.5 font-semibold text-emerald-400">
        {badge}
      </span>
    </div>
  );
}
