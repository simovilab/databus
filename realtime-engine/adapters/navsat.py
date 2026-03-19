"""
Navsat HTTP telemetry adapter.

Polls the Navsat laststatenavmi API at a configurable interval and writes
vehicle state to Redis using the shared redis_writer module.

Implements the TelemetrySource protocol — swap for an MQTT adapter later
by implementing the same start()/stop() interface.
"""
import threading
import time
import zoneinfo
from datetime import datetime

import httpx

from models import VehicleState
from redis_writer import sync_active_runs, write_vehicle_state

COSTA_RICA_TZ = zoneinfo.ZoneInfo("America/Costa_Rica")


def speed_kmh_to_ms(kmh: float) -> float:
    return round(kmh / 3.6, 4)


def estado_to_gtfs_status(estado: str) -> str:
    return "STOPPED_AT" if estado == "detenido" else "IN_TRANSIT_TO"


def parse_timestamp(cr_datetime: str) -> int:
    dt = datetime.strptime(cr_datetime, "%Y-%m-%d %H:%M:%S")
    dt = dt.replace(tzinfo=COSTA_RICA_TZ)
    return int(dt.timestamp())


def map_vehicle(raw: dict) -> VehicleState:
    plate = raw["plateNumber"]
    return VehicleState(
        vehicle_id=plate,
        label=plate,
        license_plate=plate,
        latitude=raw["latitude"],
        longitude=raw["longitude"],
        speed_ms=speed_kmh_to_ms(raw.get("speed", 0)),
        odometer=raw.get("odometer", 0),
        timestamp=parse_timestamp(raw["crDateTime"]),
        current_status=estado_to_gtfs_status(raw.get("estado", "")),
    )


class NavsatAdapter:
    """Polls the Navsat API and writes vehicle state to Redis."""

    def __init__(self, url: str, redis_client, poll_interval: int = 15) -> None:
        self._url = url
        self._redis = redis_client
        self._poll_interval = poll_interval
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _poll_loop(self) -> None:
        while self._running:
            try:
                self._poll_once()
            except Exception as exc:
                print(f"[navsat] poll error: {exc}")
            time.sleep(self._poll_interval)

    def _poll_once(self) -> None:
        response = httpx.get(self._url, timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0))
        response.raise_for_status()
        vehicles = response.json()

        seen_ids: set[str] = set()
        for raw in vehicles:
            state = map_vehicle(raw)
            write_vehicle_state(self._redis, state)
            seen_ids.add(state.vehicle_id)

        sync_active_runs(self._redis, seen_ids)
