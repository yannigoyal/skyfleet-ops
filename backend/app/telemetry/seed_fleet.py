"""Seed telemetry and per-drone parameters for the fleet simulator."""

# Realistic starting telemetry for the default fleet roster (as of project creation)
SEED_TELEMETRY: dict[str, dict[str, float | str]] = {
    "FALCON-01": {"battery_pct": 96.0, "altitude_m": 120.0, "speed_kmh": 42.0, "status": "in_flight"},
    "FALCON-02": {"battery_pct": 88.0, "altitude_m": 110.0, "speed_kmh": 38.0, "status": "in_flight"},
    "FALCON-03": {"battery_pct": 100.0, "altitude_m": 0.0, "speed_kmh": 0.0, "status": "charging"},
    "FALCON-04": {"battery_pct": 72.0, "altitude_m": 95.0, "speed_kmh": 45.0, "status": "in_flight"},
    "FALCON-05": {"battery_pct": 64.0, "altitude_m": 130.0, "speed_kmh": 40.0, "status": "in_flight"},
    "FALCON-06": {"battery_pct": 100.0, "altitude_m": 0.0, "speed_kmh": 0.0, "status": "idle"},
    "FALCON-07": {"battery_pct": 91.0, "altitude_m": 105.0, "speed_kmh": 36.0, "status": "in_flight"},
    "FALCON-08": {"battery_pct": 55.0, "altitude_m": 115.0, "speed_kmh": 41.0, "status": "in_flight"},
    "FALCON-09": {"battery_pct": 100.0, "altitude_m": 0.0, "speed_kmh": 0.0, "status": "idle"},
    "FALCON-10": {"battery_pct": 80.0, "altitude_m": 100.0, "speed_kmh": 39.0, "status": "in_flight"},
}

# Per-drone Ornstein-Uhlenbeck drain parameters.
# drain_rate: percent-per-tick pulled off the battery while in flight (steady cruise drain)
# volatility: standard deviation of the random turbulence term
TICKER_PARAMS: dict[str, dict[str, float]] = {
    "FALCON-01": {"drain_rate": 0.012, "volatility": 0.06},
    "FALCON-02": {"drain_rate": 0.014, "volatility": 0.07},
    "FALCON-03": {"drain_rate": 0.010, "volatility": 0.05},
    "FALCON-04": {"drain_rate": 0.016, "volatility": 0.09},  # older airframe, drains faster
    "FALCON-05": {"drain_rate": 0.013, "volatility": 0.06},
    "FALCON-06": {"drain_rate": 0.011, "volatility": 0.05},
    "FALCON-07": {"drain_rate": 0.012, "volatility": 0.06},
    "FALCON-08": {"drain_rate": 0.018, "volatility": 0.10},  # heavy cargo variant
    "FALCON-09": {"drain_rate": 0.010, "volatility": 0.05},
    "FALCON-10": {"drain_rate": 0.013, "volatility": 0.07},
}

# Default parameters for drones not in the list above (dynamically added)
DEFAULT_PARAMS: dict[str, float] = {"drain_rate": 0.013, "volatility": 0.07}

# Squadron groups for the simulator's Cholesky decomposition.
# Drones in the same group fly through the same weather cells and drain together.
SQUADRON_GROUPS: dict[str, set[str]] = {
    "north": {"FALCON-01", "FALCON-02", "FALCON-03", "FALCON-04"},
    "south": {"FALCON-06", "FALCON-07", "FALCON-08"},
}

# Correlation coefficients
INTRA_NORTH_CORR = 0.55  # North squadron shares a weather cell
INTRA_SOUTH_CORR = 0.45  # South squadron shares a weather cell
CROSS_GROUP_CORR = 0.2  # Between squadrons / unknown drones
SOLO_CORR = 0.15  # FALCON-05, FALCON-09, FALCON-10 fly independent routes

# Battery threshold below which a drone's status flips to "low_battery"
LOW_BATTERY_THRESHOLD = 20.0
