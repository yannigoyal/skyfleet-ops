"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useChat } from "@/lib/useChat";
import { ChatMessage } from "./ChatMessage";

function CollapseChevronIcon({ collapsed }: { collapsed: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      className={`h-4 w-4 transition-transform ${collapsed ? "rotate-180" : ""}`}
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 5l-5 5 5 5" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      className="h-4 w-4"
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h14M11 4l6 6-6 6" />
    </svg>
  );
}

/**
 * Docked, collapsible AI flight-director sidebar (FE-08, D-05, D-08). Fixed
 * right-hand column filling the available height — explicitly not a modal
 * and not left-docked. Collapsed state is pure view state with no
 * cross-component consumer, so it lives here rather than in
 * FleetOpsProvider. The input is disabled (not queued) while a turn is in
 * flight, matching the non-streaming one-response-per-request contract from
 * Phase 2 (D-08).
 */
export function ChatPanel() {
  const { turns, sending, send } = useChat();
  const [collapsed, setCollapsed] = useState(false);
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView();
  }, [turns.length]);

  function submitDraft() {
    const value = draft;
    if (!value.trim() || sending) return;
    setDraft("");
    void send(value);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    submitDraft();
  }

  return (
    <aside
      data-testid="chat-panel"
      className="flex h-full min-h-[28rem] flex-col rounded-lg border border-ops-border bg-ops-panel"
    >
      <div className="flex items-center justify-between border-b border-ops-border px-4 py-3">
        <span className="text-sm font-semibold text-slate-300">Flight Director</span>
        <button
          type="button"
          onClick={() => setCollapsed((prev) => !prev)}
          aria-label={collapsed ? "Expand chat panel" : "Collapse chat panel"}
          className="text-slate-400 transition-colors hover:text-slate-200"
        >
          <CollapseChevronIcon collapsed={collapsed} />
        </button>
      </div>

      {!collapsed && (
        <>
          <div className="flex-1 space-y-3 overflow-y-auto p-4">
            {turns.length === 0 ? (
              <div className="text-sm text-slate-400">
                <div className="font-semibold text-slate-300">Flight Director standing by</div>
                <p className="mt-1 text-xs">
                  Ask about fleet status or dispatch a mission — e.g. &quot;Launch FALCON-03 to
                  Riverside&quot;.
                </p>
              </div>
            ) : (
              turns.map((turn, index) => <ChatMessage key={index} turn={turn} />)
            )}
            <div ref={bottomRef} />
          </div>

          <form
            onSubmit={handleSubmit}
            className="flex items-center gap-2 border-t border-ops-border p-3"
          >
            <input
              type="text"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              disabled={sending}
              placeholder="Ask the flight director..."
              className="flex-1 rounded border border-ops-border bg-ops-bg px-2 py-1.5 text-sm text-slate-200 disabled:opacity-50"
            />
            {sending && (
              <span data-testid="chat-loading" className="text-xs text-slate-400">
                Thinking&hellip;
              </span>
            )}
            <button
              type="submit"
              disabled={sending}
              aria-label="Send message"
              className="rounded border border-ops-border p-1.5 text-slate-300 transition-colors hover:text-ops-teal disabled:opacity-50"
            >
              <SendIcon />
            </button>
          </form>
        </>
      )}
    </aside>
  );
}
