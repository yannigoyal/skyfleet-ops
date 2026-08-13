// Mirrors backend/app/missions/router.py and backend/app/roster/router.py
// response shapes — see missions/models.py::Mission.to_dict() and
// roster/router.py::_entry_response().
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

export interface RosterDrone {
  drone_id: string;
  added_at: string;
  battery_pct?: number;
  altitude_m?: number;
  speed_kmh?: number;
  status?: string;
}
