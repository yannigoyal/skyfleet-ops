import type { ChatTurn } from "@/types/chat";
import { ConfirmationCard } from "./ConfirmationCard";

/**
 * One transcript bubble. Renders `turn.content` as a plain JSX text child
 * only, so React's default text-node escaping applies (T-03-23) — never
 * constructed as DOM from the string, never passed to a raw-HTML rendering
 * prop, never truncated by byte/index arithmetic. A `system` turn (a
 * transport failure — no action was ever executed) is a full-width red
 * inline notice, visually distinct from both operator and assistant
 * bubbles, which cap at ~85% of the container width and let text wrap
 * normally since assistant content is the primary content and is never
 * truncated.
 */
export function ChatMessage({ turn }: { turn: ChatTurn }) {
  if (turn.role === "system") {
    return (
      <div className="w-full rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
        {turn.content}
      </div>
    );
  }

  const hasCards =
    (turn.missions && turn.missions.length > 0) ||
    (turn.roster_changes && turn.roster_changes.length > 0) ||
    (turn.errors && turn.errors.length > 0);

  return (
    <div
      className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
        turn.role === "user"
          ? "ml-auto bg-slate-700/60 text-slate-100"
          : "mr-auto bg-ops-panel text-slate-100"
      }`}
    >
      <p className="whitespace-pre-wrap break-words">{turn.content}</p>
      {hasCards && (
        <div className="mt-2 flex flex-col gap-1.5">
          {turn.missions?.map((mission, index) => (
            <ConfirmationCard key={`mission-${index}`} kind="success" entry={mission} />
          ))}
          {turn.roster_changes?.map((change, index) => (
            <ConfirmationCard key={`roster-${index}`} kind="success" entry={change} />
          ))}
          {turn.errors?.map((error, index) => (
            <ConfirmationCard key={`error-${index}`} kind="failure" message={error} />
          ))}
        </div>
      )}
    </div>
  );
}
