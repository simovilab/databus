from datetime import timedelta
import os

from celery import Celery

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
    "build-alerts-every-10s": {
        "task": "schedule_engine.tasks.build_alerts",
        "schedule": timedelta(seconds=10),
    },
    "scan-stale-runs-every-30s": {
        "task": "realtime_engine.tasks.scan_stale_runs",
        "schedule": timedelta(seconds=30),
    },
    "fetch-positions": {
        "task": "realtime_engine.tasks.fetch_positions",
        "schedule": timedelta(seconds=10),
    },
}
