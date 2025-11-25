import os

from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "realtime.settings")

app = Celery("realtime")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configure periodic tasks for simulator
app.conf.beat_schedule = {
    'update-simulated-positions': {
        'task': 'simulator.update_positions',
        'schedule': 10.0,  # Every 10 seconds
        'options': {
            'expires': 15.0,  # Task expires after 15 seconds
        }
    },
    'cleanup-simulation-logs': {
        'task': 'simulator.cleanup_logs',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2:00 AM
    },
    'update-journey-status': {
        'task': 'feed.tasks.update_journey_status',
        'schedule': 60.0,  # Every 60 seconds
    },
    'update-connection-status': {
        'task': 'feed.tasks.update_conn_status',
        'schedule': 30.0,  # Every 30 seconds
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Celery request: {self.request!r}")
