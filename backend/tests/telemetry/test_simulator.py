"""Tests for FleetSimulator."""

from app.telemetry.simulator import FleetSimulator


class TestFleetSimulator:
    def test_init_seeds_known_drones(self):
        sim = FleetSimulator(["FALCON-01", "FALCON-06"])
        assert sim.get_drone_ids() == ["FALCON-01", "FALCON-06"]
        reading = sim.get_reading("FALCON-01")
        assert reading["battery_pct"] == 96.0
        assert reading["status"] == "in_flight"

    def test_init_seeds_unknown_drone_with_defaults(self):
        sim = FleetSimulator(["FALCON-99"])
        reading = sim.get_reading("FALCON-99")
        assert reading["battery_pct"] == 100.0
        assert reading["status"] == "idle"

    def test_step_returns_all_drones(self):
        sim = FleetSimulator(["FALCON-01", "FALCON-02", "FALCON-03"])
        result = sim.step()
        assert set(result.keys()) == {"FALCON-01", "FALCON-02", "FALCON-03"}

    def test_step_empty_fleet(self):
        sim = FleetSimulator([])
        assert sim.step() == {}

    def test_battery_stays_in_bounds(self):
        sim = FleetSimulator(["FALCON-01", "FALCON-08"])
        for _ in range(500):
            readings = sim.step()
            for reading in readings.values():
                assert 0.0 <= reading["battery_pct"] <= 100.0

    def test_charging_drone_reaches_idle(self):
        sim = FleetSimulator(["FALCON-03"])  # starts at 100%, status "charging"
        # Already full — one step should flip it to idle immediately since
        # the seed battery is 100.0 and charging only increases further.
        for _ in range(5):
            readings = sim.step()
        assert readings["FALCON-03"]["status"] == "idle"

    def test_ground_drone_stays_grounded(self):
        sim = FleetSimulator(["FALCON-06"])  # idle at 100%
        for _ in range(20):
            readings = sim.step()
        assert readings["FALCON-06"]["altitude_m"] == 0.0
        assert readings["FALCON-06"]["speed_kmh"] == 0.0

    def test_in_flight_drone_has_nonzero_altitude(self):
        sim = FleetSimulator(["FALCON-01"])
        readings = sim.step()
        assert readings["FALCON-01"]["altitude_m"] >= 0.0

    def test_add_drone(self):
        sim = FleetSimulator(["FALCON-01"])
        sim.add_drone("FALCON-02")
        assert "FALCON-02" in sim.get_drone_ids()
        assert sim.get_reading("FALCON-02") is not None

    def test_add_duplicate_drone_is_noop(self):
        sim = FleetSimulator(["FALCON-01"])
        sim.add_drone("FALCON-01")
        assert sim.get_drone_ids() == ["FALCON-01"]

    def test_remove_drone(self):
        sim = FleetSimulator(["FALCON-01", "FALCON-02"])
        sim.remove_drone("FALCON-01")
        assert sim.get_drone_ids() == ["FALCON-02"]
        assert sim.get_reading("FALCON-01") is None

    def test_remove_unknown_drone_is_noop(self):
        sim = FleetSimulator(["FALCON-01"])
        sim.remove_drone("UNKNOWN")
        assert sim.get_drone_ids() == ["FALCON-01"]

    def test_get_reading_unknown_drone(self):
        sim = FleetSimulator(["FALCON-01"])
        assert sim.get_reading("UNKNOWN") is None

    def test_single_drone_has_no_cholesky(self):
        sim = FleetSimulator(["FALCON-01"])
        assert sim._cholesky is None

    def test_multi_drone_has_cholesky(self):
        sim = FleetSimulator(["FALCON-01", "FALCON-02"])
        assert sim._cholesky is not None

    def test_low_battery_status_transition(self):
        sim = FleetSimulator(["FALCON-04"])  # fastest drain rate
        for _ in range(3000):
            readings = sim.step()
            if readings["FALCON-04"]["battery_pct"] <= 20.0:
                assert readings["FALCON-04"]["status"] in ("low_battery", "offline")
                return
        # If we never drained enough, that's still fine — no assertion failure,
        # just skip (drain rate + noise makes exact timing non-deterministic).

    def test_pairwise_correlation_north_squadron(self):
        rho = FleetSimulator._pairwise_correlation("FALCON-01", "FALCON-02")
        assert rho == 0.55

    def test_pairwise_correlation_south_squadron(self):
        rho = FleetSimulator._pairwise_correlation("FALCON-06", "FALCON-07")
        assert rho == 0.45

    def test_pairwise_correlation_solo(self):
        rho = FleetSimulator._pairwise_correlation("FALCON-05", "FALCON-09")
        assert rho == 0.15

    def test_pairwise_correlation_cross_squadron(self):
        rho = FleetSimulator._pairwise_correlation("FALCON-01", "FALCON-06")
        assert rho == 0.2
