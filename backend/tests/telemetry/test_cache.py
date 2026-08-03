"""Tests for TelemetryCache."""

from app.telemetry.cache import TelemetryCache


class TestTelemetryCache:
    def test_empty_cache(self):
        cache = TelemetryCache()
        assert len(cache) == 0
        assert cache.get("FALCON-01") is None
        assert cache.get_all() == {}

    def test_update_returns_reading(self):
        cache = TelemetryCache()
        update = cache.update(
            drone_id="FALCON-01", battery_pct=90.0, altitude_m=100.0, speed_kmh=40.0, status="in_flight"
        )
        assert update.drone_id == "FALCON-01"
        assert update.battery_pct == 90.0

    def test_first_update_previous_equals_current(self):
        cache = TelemetryCache()
        update = cache.update(
            drone_id="FALCON-01", battery_pct=90.0, altitude_m=100.0, speed_kmh=40.0, status="in_flight"
        )
        assert update.previous_battery_pct == 90.0
        assert update.battery_direction == "flat"

    def test_second_update_tracks_previous(self):
        cache = TelemetryCache()
        cache.update(drone_id="FALCON-01", battery_pct=90.0, altitude_m=100.0, speed_kmh=40.0, status="in_flight")
        update = cache.update(
            drone_id="FALCON-01", battery_pct=88.5, altitude_m=101.0, speed_kmh=41.0, status="in_flight"
        )
        assert update.previous_battery_pct == 90.0
        assert update.battery_pct == 88.5
        assert update.battery_direction == "draining"

    def test_get(self):
        cache = TelemetryCache()
        cache.update(drone_id="FALCON-01", battery_pct=90.0, altitude_m=100.0, speed_kmh=40.0, status="in_flight")
        reading = cache.get("FALCON-01")
        assert reading is not None
        assert reading.drone_id == "FALCON-01"

    def test_get_unknown_drone(self):
        cache = TelemetryCache()
        assert cache.get("UNKNOWN") is None

    def test_get_battery(self):
        cache = TelemetryCache()
        cache.update(drone_id="FALCON-01", battery_pct=77.25, altitude_m=100.0, speed_kmh=40.0, status="in_flight")
        assert cache.get_battery("FALCON-01") == 77.25

    def test_get_battery_unknown(self):
        cache = TelemetryCache()
        assert cache.get_battery("UNKNOWN") is None

    def test_get_all_returns_copy(self):
        cache = TelemetryCache()
        cache.update(drone_id="FALCON-01", battery_pct=90.0, altitude_m=100.0, speed_kmh=40.0, status="in_flight")
        snapshot = cache.get_all()
        snapshot["FALCON-99"] = "injected"
        assert "FALCON-99" not in cache.get_all()

    def test_remove(self):
        cache = TelemetryCache()
        cache.update(drone_id="FALCON-01", battery_pct=90.0, altitude_m=100.0, speed_kmh=40.0, status="in_flight")
        cache.remove("FALCON-01")
        assert cache.get("FALCON-01") is None
        assert len(cache) == 0

    def test_remove_unknown_is_noop(self):
        cache = TelemetryCache()
        cache.remove("UNKNOWN")  # should not raise

    def test_version_increments(self):
        cache = TelemetryCache()
        assert cache.version == 0
        cache.update(drone_id="FALCON-01", battery_pct=90.0, altitude_m=100.0, speed_kmh=40.0, status="in_flight")
        assert cache.version == 1
        cache.update(drone_id="FALCON-02", battery_pct=85.0, altitude_m=95.0, speed_kmh=38.0, status="in_flight")
        assert cache.version == 2

    def test_contains(self):
        cache = TelemetryCache()
        cache.update(drone_id="FALCON-01", battery_pct=90.0, altitude_m=100.0, speed_kmh=40.0, status="in_flight")
        assert "FALCON-01" in cache
        assert "FALCON-02" not in cache

    def test_len(self):
        cache = TelemetryCache()
        cache.update(drone_id="FALCON-01", battery_pct=90.0, altitude_m=100.0, speed_kmh=40.0, status="in_flight")
        cache.update(drone_id="FALCON-02", battery_pct=85.0, altitude_m=95.0, speed_kmh=38.0, status="in_flight")
        assert len(cache) == 2

    def test_rounding(self):
        cache = TelemetryCache()
        update = cache.update(
            drone_id="FALCON-01",
            battery_pct=90.12345,
            altitude_m=100.567,
            speed_kmh=40.789,
            status="in_flight",
        )
        assert update.battery_pct == 90.12
        assert update.altitude_m == 100.6
        assert update.speed_kmh == 40.8
