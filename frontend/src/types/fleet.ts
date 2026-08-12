// Mirrors backend/app/missions/router.py response shapes.
export type MissionStatus = "en_route" | "delivered" | "recalled";

export interface Mission {
  id: string;
  drone_id: string;
  zone: string;
  distance_km: number;
  energy_cost_kwh: number;
  status: MissionStatus;
  updated_at: string;
  eta_minutes?: number;
}

export interface FleetStatus {
  energy_budget_kwh: number;
  remaining_kwh: number;
  active_mission_count: number;
  missions: Mission[];
}

export interface BudgetSnapshot {
  remaining_kwh: number;
  recorded_at: string;
}

export interface RosterEntry {
  drone_id: string;
  added_at?: string;
}

// planning/PLAN.md section 9 structured-output schema.
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
  missions?: ChatMissionAction[];
  roster_changes?: ChatRosterChange[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  missions?: ChatMissionAction[];
  roster_changes?: ChatRosterChange[];
}
