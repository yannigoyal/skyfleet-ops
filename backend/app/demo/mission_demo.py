"""Terminal demo of the mission scheduler.

Runs the real scheduling code (app.missions.service / scheduler) against an
isolated temp SQLite database and the fleet simulator, firing randomized
launch requests and rendering live drone/mission/queue state with Rich.
No server, no HTTP — just the scheduler doing its job in-process.
"""

from __future__ import annotations

import asyncio
import random
import shutil
import tempfile
from pathlib import Path

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from app.db import Database
from app.missions import (
    MissionQueue,
    run_assignment_scheduler,
    run_budget_snapshot_loop,
    run_delivery_scheduler,
)
from app.missions import repository, service
from app.missions.models import DEFAULT_CRUISE_SPEED_KMH, MissionError
from app.telemetry import TelemetryCache, create_telemetry_source

FLEET = [f"FALCON-{i:02d}" for i in range(1, 11)]
ZONES = ["Riverside", "Downtown", "Harborview", "Old Town", "Sunset Ridge"]


async def mission_generator(db: Database, cache: TelemetryCache, queue: MissionQueue) -> None:
    """Fire randomized launch requests faster than the fleet can always absorb,
    so both immediate auto-assignment and the retry queue get exercised."""
    while True:
        await asyncio.sleep(random.uniform(2.0, 3.5))
        zone = random.choice(ZONES)
        distance_km = round(random.uniform(0.3, 1.8), 1)
        try:
            await service.auto_assign_mission(db, cache, zone=zone, distance_km=distance_km)
        except MissionError:
            queue.enqueue(zone, distance_km)


def _build_display(
    db_snapshot: dict, cache: TelemetryCache, queue: MissionQueue
) -> Group:
    missions_by_drone = {m.drone_id: m for m in db_snapshot["active_missions"]}

    fleet_table = Table(title="Fleet", expand=True)
    fleet_table.add_column("Drone")
    fleet_table.add_column("Status")
    fleet_table.add_column("Battery")
    fleet_table.add_column("Zone")
    fleet_table.add_column("Dist (km)")
    fleet_table.add_column("ETA (min)")

    for drone_id in FLEET:
        reading = cache.get(drone_id)
        battery = f"{reading.battery_pct:.0f}%" if reading else "-"
        mission = missions_by_drone.get(drone_id)
        if mission:
            eta = round((mission.distance_km / DEFAULT_CRUISE_SPEED_KMH) * 60, 1)
            fleet_table.add_row(
                drone_id, "[orange3]en_route[/]", battery, mission.zone,
                f"{mission.distance_km:.1f}", f"{eta}"
            )
        else:
            fleet_table.add_row(drone_id, "[green]idle[/]", battery, "-", "-", "-")

    queue_table = Table(title="Assignment Queue", expand=True)
    queue_table.add_column("Zone")
    queue_table.add_column("Dist (km)")
    queue_table.add_column("Attempts")
    queue_table.add_column("Last Error")

    for entry in queue.pending():
        queue_table.add_row(entry.zone, f"{entry.distance_km:.1f}", str(entry.attempts), entry.last_error or "-")
    for entry in queue.failed():
        queue_table.add_row(
            f"[red]{entry.zone} (failed)[/]", f"{entry.distance_km:.1f}", str(entry.attempts), entry.last_error or "-"
        )
    if not queue.pending() and not queue.failed():
        queue_table.add_row("-", "-", "-", "-")

    budget_line = (
        f"Energy budget: {db_snapshot['remaining_kwh']:.1f} / {db_snapshot['budget']:.1f} kWh remaining"
    )

    return Group(Panel(budget_line, title="Operator Budget"), fleet_table, queue_table)


async def render_loop(db: Database, cache: TelemetryCache, queue: MissionQueue, live: Live) -> None:
    while True:
        active_missions = await repository.list_active_missions(db)
        remaining_kwh = await repository.get_remaining_kwh(db)
        budget = await repository.get_energy_budget(db)
        snapshot = {
            "active_missions": active_missions,
            "remaining_kwh": remaining_kwh,
            "budget": budget,
        }
        live.update(_build_display(snapshot, cache, queue))
        await asyncio.sleep(0.5)


async def run_demo() -> None:
    console = Console()
    tmp_dir = Path(tempfile.mkdtemp(prefix="skyfleet-mission-demo-"))
    database = Database(tmp_dir / "demo.db")
    database.ensure_initialized()

    cache = TelemetryCache()
    queue = MissionQueue()
    source = create_telemetry_source(cache)
    await source.start(FLEET)

    console.print(
        "[bold cyan]SkyFleet mission scheduler demo[/] — isolated demo database, "
        "randomized launches. Press Ctrl+C to stop.\n"
    )

    tasks = [
        asyncio.create_task(run_assignment_scheduler(database, cache, queue, interval=2.0)),
        asyncio.create_task(run_delivery_scheduler(database, interval=2.0)),
        asyncio.create_task(run_budget_snapshot_loop(database, interval=10.0)),
        asyncio.create_task(mission_generator(database, cache, queue)),
    ]

    try:
        with Live(console=console, refresh_per_second=2, screen=False) as live:
            await render_loop(database, cache, queue, live)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await source.stop()
        database.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main() -> None:
    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
