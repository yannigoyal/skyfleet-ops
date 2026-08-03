"""Tests for TelemetryUpdate model."""

from app.telemetry.models import TelemetryUpdate


class TestTelemetryUpdate:
    def test_basic_fields(self):
        update = TelemetryUpdate(
            drone_id="FALCON-01",
            battery_pct=80.0,
            previous_battery_pct=82.0,
            altitude_m=100.0,
            speed_kmh=40.0,
            status="in_flight",
            timestamp=1000.0,
        )
        assert update.drone_id == "FALCON-01"
        assert update.battery_pct == 80.0
        assert update.status == "in_flight"
        assert update.timestamp == 1000.0

    def test_battery_delta_draining(self):
        update = TelemetryUpdate(
            drone_id="FALCON-01",
            battery_pct=78.5,
            previous_battery_pct=80.0,
            altitude_m=100.0,
            speed_kmh=40.0,
            status="in_flight",
        )
        assert update.battery_delta == -1.5

    def test_battery_delta_charging(self):
        update = TelemetryUpdate(
            drone_id="FALCON-03",
            battery_pct=90.0,
            previous_battery_pct=88.0,
            altitude_m=0.0,
            speed_kmh=0.0,
            status="charging",
        )
        assert update.battery_delta == 2.0

    def test_direction_draining(self):
        update = TelemetryUpdate(
            drone_id="FALCON-01",
            battery_pct=50.0,
            previous_battery_pct=55.0,
            altitude_m=100.0,
            speed_kmh=40.0,
            status="in_flight",
        )
        assert update.battery_direction == "draining"

    def test_direction_charging(self):
        update = TelemetryUpdate(
            drone_id="FALCON-03",
            battery_pct=55.0,
            previous_battery_pct=50.0,
            altitude_m=0.0,
            speed_kmh=0.0,
            status="charging",
        )
        assert update.battery_direction == "charging"

    def test_direction_flat(self):
        update = TelemetryUpdate(
            drone_id="FALCON-06",
            battery_pct=100.0,
            previous_battery_pct=100.0,
            altitude_m=0.0,
            speed_kmh=0.0,
            status="idle",
        )
        assert update.battery_direction == "flat"

    def test_to_dict(self):
        update = TelemetryUpdate(
            drone_id="FALCON-01",
            battery_pct=78.5,
            previous_battery_pct=80.0,
            altitude_m=105.5,
            speed_kmh=42.3,
            status="in_flight",
            timestamp=1234.5,
        )
        d = update.to_dict()
        assert d == {
            "drone_id": "FALCON-01",
            "battery_pct": 78.5,
            "previous_battery_pct": 80.0,
            "altitude_m": 105.5,
            "speed_kmh": 42.3,
            "status": "in_flight",
            "timestamp": 1234.5,
            "battery_delta": -1.5,
            "battery_direction": "draining",
        }

    def test_is_immutable(self):
        update = TelemetryUpdate(
            drone_id="FALCON-01",
            battery_pct=80.0,
            previous_battery_pct=80.0,
            altitude_m=100.0,
            speed_kmh=40.0,
            status="in_flight",
        )
        try:
            update.battery_pct = 50.0
            assert False, "expected FrozenInstanceError"
        except AttributeError:
            pass

    def test_default_timestamp_is_set(self):
        update = TelemetryUpdate(
            drone_id="FALCON-01",
            battery_pct=80.0,
            previous_battery_pct=80.0,
            altitude_m=100.0,
            speed_kmh=40.0,
            status="in_flight",
        )
        assert update.timestamp > 0
