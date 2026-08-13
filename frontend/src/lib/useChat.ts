"use client";

import { useCallback, useState } from "react";
import { useFleetOps } from "@/lib/FleetOpsProvider";
import type { ChatResponse, ChatTurn } from "@/types/chat";

const TRANSPORT_ERROR_COPY = "Connection error — try sending your message again.";

/**
 * Owns one flight-director chat turn at a time (POST /api/chat).
 *
 * - D-07: after a turn whose response actually executed a mission or roster
 *   action, calls the same `refetch()` from `FleetOpsProvider` the dispatch
 *   bar uses — chat-driven and manual actions can never drift out of sync
 *   through a separate optimistic-merge path.
 * - D-08: `sending` guards the whole request body. The endpoint returns one
 *   complete JSON response per request with no token streaming, so a second
 *   send while a request is in flight is a no-op rather than queueing —
 *   interleaving two turns would produce out-of-order transcript entries.
 */
export function useChat() {
  const { refetch } = useFleetOps();
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [sending, setSending] = useState(false);

  const send = useCallback(
    async (message: string) => {
      const trimmed = message.trim();
      if (!trimmed || sending) return;

      setTurns((prev) => [...prev, { role: "user", content: trimmed }]);
      setSending(true);

      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: trimmed }),
        });

        if (!res.ok) {
          setTurns((prev) => [...prev, { role: "system", content: TRANSPORT_ERROR_COPY }]);
          return;
        }

        const body: ChatResponse = await res.json();
        setTurns((prev) => [
          ...prev,
          {
            role: "assistant",
            content: body.message,
            missions: body.missions,
            roster_changes: body.roster_changes,
            errors: body.errors,
          },
        ]);

        if (body.missions.length > 0 || body.roster_changes.length > 0) {
          await refetch();
        }
      } catch {
        setTurns((prev) => [...prev, { role: "system", content: TRANSPORT_ERROR_COPY }]);
      } finally {
        setSending(false);
      }
    },
    [sending, refetch],
  );

  return { turns, sending, send };
}
