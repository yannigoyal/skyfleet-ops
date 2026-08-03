// Mirrors backend/app/telemetry/models.py::TelemetryUpdate.to_dict()
export type DroneStatus = "idle" | "in_flight" | "charging" | "low_battery" | "offline";

export interface TelemetryReading {
  drone_id: string;
  battery_pct: number;
  previous_battery_pct: number;
  altitude_m: number;
  speed_kmh: number;
  status: DroneStatus;
  timestamp: number;
  battery_delta: number;
  battery_direction: "draining" | "charging" | "flat";
}

export type TelemetrySnapshot = Record<string, TelemetryReading>;
