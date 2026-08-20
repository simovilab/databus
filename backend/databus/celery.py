"""Celery app for databus: task discovery, the MQTT consumer bootstep, and the beat schedule.

Beat schedule entries: `fetch-positions` polls HTTP telemetry sources every 10s (a run
that hasn't started within its own cycle is revoked via `expires=10` rather than queuing
up behind a slow source); `build-vehicle-positions-every-15s` and
`build-trip-updates-every-15s` rebuild the two GTFS-RT feeds every 15s;
`scan-stale-runs-every-30s` sweeps for runs that have gone quiet;
`build-schedule-daily` rebuilds the GTFS Schedule zip once a day; and
`fetch-schedule-hourly-at-30` HEAD-checks each active GTFSProvider's schedule_url ETag
every hour at :30 and imports the GTFS Schedule when it changed.
"""

from datetime import timedelta
import os

from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "databus.settings")

app = Celery("databus")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Register the MQTT consumer bootstep. The class is gated internally by
# MQTT_CONSUMER_ENABLED so only the realtime-engine worker actually starts it.
from realtime_engine.mqtt import MQTTConsumerStep  # noqa: E402

app.steps["worker"].add(MQTTConsumerStep)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Print the current task's request context; used to sanity-check worker connectivity."""
    print(f"Celery request: {self.request!r}")


# --------------------
# Celery Beat Schedule
# --------------------

app.conf.beat_schedule = {
    "build-vehicle-positions-every-15s": {
        "task": "schedule_engine.tasks.build_vehicle_positions",
        "schedule": timedelta(seconds=15),
    },
    "build-trip-updates-every-15s": {
        "task": "schedule_engine.tasks.build_trip_updates",
        "schedule": timedelta(seconds=15),
    },
    "scan-stale-runs-every-30s": {
        "task": "realtime_engine.tasks.scan_stale_runs",
        "schedule": timedelta(seconds=30),
    },
    "fetch-positions": {
        "task": "realtime_engine.tasks.fetch_positions",
        "schedule": timedelta(seconds=10),
        # A task that couldn't even start within its own 10s cycle is stale
        # by the time a worker slot frees up -- revoke it instead of letting
        # queued fetch_positions runs pile up behind a slow/unreachable
        # source (see fetch_positions' soft_time_limit for the in-flight
        # bound on runs that DO start).
        "options": {"expires": 10},
    },
    "build-schedule-daily": {
        "task": "schedule_engine.tasks.build_schedule",
        "schedule": timedelta(days=1),
    },
    "fetch-schedule-hourly-at-30": {
        "task": "schedule_engine.tasks.fetch_schedule",
        "schedule": crontab(minute=30),
    },
}
