"use client";

import { useState } from "react";
import { sendChatMessage } from "@/lib/api";
import type { ChatMessage } from "@/types/fleet";

function ActionList({ message }: { message: ChatMessage }) {
  const missions = message.missions ?? [];
  const rosterChanges = message.roster_changes ?? [];
  if (missions.length === 0 && rosterChanges.length === 0) return null;

  return (
    <ul className="mt-2 space-y-1 border-t border-ops-border pt-2 text-xs font-mono text-ops-amber">
      {missions.map((mission, index) => (
        <li key={`m${index}`}>
          {mission.action === "launch"
            ? `LAUNCH ${mission.drone_id} → ${mission.zone} (${mission.distance_km} km)`
            : `RECALL ${mission.drone_id}`}
        </li>
      ))}
      {rosterChanges.map((change, index) => (
        <li key={`r${index}`} className="text-ops-teal">
          {change.action === "add" ? "ADD" : "REMOVE"} {change.drone_id}
        </li>
      ))}
    </ul>
  );
}

export function ChatPanel({ onActionsExecuted }: { onActionsExecuted: () => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setLoading(true);
    try {
      const response = await sendChatMessage(text);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.message,
          missions: response.missions,
          roster_changes: response.roster_changes,
        },
      ]);
      onActionsExecuted();
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: err instanceof Error ? err.message : "chat failed" },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div data-testid="chat-panel" className="flex h-full flex-col rounded-lg border border-ops-border bg-ops-panel">
      <div className="border-b border-ops-border px-4 py-2 text-sm font-semibold text-slate-300">
        AI Flight Director
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-4 text-sm">
        {messages.length === 0 && (
          <p className="text-slate-500">Ask about fleet health, or tell me to dispatch a drone.</p>
        )}
        {messages.map((message, index) => (
          <div
            key={index}
            className={
              message.role === "user"
                ? "rounded bg-white/5 p-2 text-slate-200"
                : "rounded border border-ops-border p-2 text-slate-300"
            }
          >
            <div className="mb-1 text-xs uppercase tracking-wide text-slate-500">
              {message.role === "user" ? "Dispatcher" : "Flight Director"}
            </div>
            <div className="whitespace-pre-wrap">{message.content}</div>
            <ActionList message={message} />
          </div>
        ))}
        {loading && <div className="text-xs text-ops-amber">Flight director is thinking…</div>}
      </div>
      <form onSubmit={submit} className="flex gap-2 border-t border-ops-border p-3">
        <input
          aria-label="Message the flight director"
          className="flex-1 rounded border border-ops-border bg-ops-bg px-2 py-1 text-sm text-slate-200 outline-none focus:border-ops-teal"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Which drones need recall?"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-ops-teal px-3 py-1 text-sm font-semibold text-ops-bg hover:opacity-90 disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </div>
  );
}
