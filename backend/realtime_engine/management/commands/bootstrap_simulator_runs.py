"""
manage.py bootstrap_simulator_runs

Reads the simulator fleet definition from simulator/sim/shapes.json,
creates one Vehicle + Operator + Run per vehicle, advances each run to
CONFIRMED state via the FSM, and sets vehicle:{id}:current_run in Redis.

After this command completes, starting the simulator will cause MQTT pings
to trigger RUN_TRACKING_STARTED automatically.

Usage:
    manage.py bootstrap_simulator_runs
    manage.py bootstrap_simulator_runs --shapes-json /path/to/shapes.json
    manage.py bootstrap_simulator_runs --per-route 2
"""
import json
import logging
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from operations.models import Vehicle, Operator
from runs.models import Run
from runs.services.lifecycle import RunLifecycleService
from runs.domain.events import RunLifecycleEvents
from runs.services.exceptions import RunLifecycleError

logger = logging.getLogger(__name__)

try:
    DEFAULT_SHAPES_JSON = (
        Path(__file__).resolve().parents[5]  # up to git.no_sync/ on host
        / "simulator" / "sim" / "shapes.json"
    )
except IndexError:
    DEFAULT_SHAPES_JSON = Path("/tmp/shapes.json")
PER_ROUTE = 4


class Command(BaseCommand):
    help = "Bootstrap simulator-aligned runs for the MQTT demo"

    def add_arguments(self, parser):
        parser.add_argument(
            "--shapes-json",
            default=str(DEFAULT_SHAPES_JSON),
            help="Path to simulator shapes.json",
        )
        parser.add_argument(
            "--per-route",
            type=int,
            default=PER_ROUTE,
            help="Vehicles per route (must match simulator --per-route, default 4)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing simulator runs before bootstrapping",
        )

    def handle(self, **options):
        shapes_path = Path(options["shapes_json"])
        if not shapes_path.exists():
            raise CommandError(f"shapes.json not found at {shapes_path}")

        data = json.loads(shapes_path.read_text())
        routes = {r["route_id"]: r for r in data.get("routes", [])}

        # Build the same fleet as the simulator
        fleet: list[dict] = []
        unit_num = 1
        for route_id, route in routes.items():
            available_shapes = [
                s for s in route.get("shape_ids", []) if s in data.get("shapes", {})
            ]
            if not available_shapes:
                continue
            for i in range(options["per_route"]):
                shape_id = available_shapes[i % len(available_shapes)]
                fleet.append({
                    "vehicle_id": f"unit-{unit_num:02d}",
                    "route_id": route_id,
                    "shape_id": shape_id,
                })
                unit_num += 1

        if not fleet:
            raise CommandError("No vehicles derived from shapes.json")

        self.stdout.write(f"Fleet: {len(fleet)} vehicles")

        if options["clear"]:
            deleted = Run.objects.filter(
                vehicle__id__in=[v["vehicle_id"] for v in fleet]
            ).delete()
            self.stdout.write(f"Cleared existing runs: {deleted}")

        from feed.models import Feed, Trip

        feed = Feed.objects.filter(is_current=True).first()
        if not feed:
            raise CommandError(
                "No current GTFS feed found. Run: manage.py loaddata gtfs.json"
            )

        service = RunLifecycleService()
        User = get_user_model()

        created_runs = []
        with transaction.atomic():
            for spec in fleet:
                vehicle_id = spec["vehicle_id"]
                route_id = spec["route_id"]
                shape_id = spec["shape_id"]

                # Find a GTFS trip matching this route+shape
                trip = Trip.objects.filter(
                    feed=feed, route_id=route_id, shape_id=shape_id
                ).first()
                if not trip:
                    self.stderr.write(
                        f"  {vehicle_id}: no trip found for route={route_id} "
                        f"shape={shape_id} — skipping"
                    )
                    continue

                # Ensure Vehicle exists
                vehicle, _ = Vehicle.objects.get_or_create(
                    id=vehicle_id,
                    defaults={
                        "label": vehicle_id,
                        "license_plate": vehicle_id,
                    },
                )

                # Ensure a synthetic operator exists for this vehicle
                username = f"sim_{vehicle_id}"
                user, _ = User.objects.get_or_create(
                    username=username,
                    defaults={"first_name": "Sim", "last_name": vehicle_id},
                )
                operator_id = f"op-{vehicle_id}"
                operator, _ = Operator.objects.get_or_create(
                    id=operator_id,
                    defaults={"user": user},
                )

                # Create the run (REQUESTED state by default)
                run = Run.objects.create(
                    route_id=route_id,
                    trip_id=trip.trip_id,
                    direction_id=trip.direction_id,
                    shape_id=shape_id,
                    schedule_relationship="SCHEDULED",
                    start_date=date.today(),
                )
                run.vehicle.set([vehicle])
                run.operator.set([operator])

                payload = {
                    "run_id": run.id,
                    "vehicle_id": vehicle_id,
                    "operator_id": operator.id,
                    "route_id": route_id,
                    "trip_id": trip.trip_id,
                    "direction_id": trip.direction_id,
                    "shape_id": shape_id,
                    "schedule_relationship": "SCHEDULED",
                }

                try:
                    service.process_event(RunLifecycleEvents.VALIDATE_RUN, payload)
                    service.process_event(RunLifecycleEvents.INITIALIZE_RUN, payload)
                    service.process_event(
                        RunLifecycleEvents.RUN_CONFIRMED_BY_OPERATOR, payload
                    )
                except RunLifecycleError as exc:
                    self.stderr.write(
                        f"  {vehicle_id}: FSM error — {exc.errors} — skipping"
                    )
                    run.delete()
                    continue

                created_runs.append((vehicle_id, run.id, trip.trip_id))
                self.stdout.write(
                    f"  ✓ {vehicle_id}  run={run.id}  trip={trip.trip_id}  "
                    f"route={route_id}  shape={shape_id}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nBootstrap complete: {len(created_runs)}/{len(fleet)} runs in CONFIRMED state."
            )
        )
        self.stdout.write("Start the simulator — first MQTT pings will trigger RUN_TRACKING_STARTED.")
