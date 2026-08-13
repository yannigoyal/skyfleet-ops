// Mirrors backend/app/chat/router.py's POST /api/chat response body
// (lines 186-193): {message, missions, roster_changes, errors}, and the
// executed-action shapes _execute_mission/_execute_roster_change return
// (lines 50-96).
export interface ChatMissionAction {
  drone_id: string;
  action: "launch" | "recall";
  zone?: string;
  distance_km?: number;
}

export interface ChatRosterChange {
  drone_id: string;
  action: "add" | "remove";
}

export interface ChatResponse {
  message: string;
  missions: ChatMissionAction[];
  roster_changes: ChatRosterChange[];
  errors: string[];
}

// Client-side transcript record. `system` is a distinct role from
// `assistant` — it marks a transport failure (no action was ever executed),
// never an executed-or-failed action reported by the copilot itself.
export interface ChatTurn {
  role: "user" | "assistant" | "system";
  content: string;
  missions?: ChatMissionAction[];
  roster_changes?: ChatRosterChange[];
  errors?: string[];
}
