import os
from celery import Celery
from datetime import timedelta

rabbitmq_user = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
rabbitmq_pass = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")
rabbitmq_host = os.getenv("RABBITMQ_HOST", "message-broker")
rabbitmq_port = os.getenv("RABBITMQ_PORT", "5672")

broker_url = f"amqp://{rabbitmq_user}:{rabbitmq_pass}@{rabbitmq_host}:{rabbitmq_port}/"

app = Celery("scheduler", broker=broker_url)

app.conf.beat_schedule = {
    "build-vehicle-positions-every-15s": {
        "task": "publisher.build_vehicle_positions",
        "schedule": timedelta(seconds=15),
    },
    "build-trip-updates-every-15s": {
        "task": "publisher.build_trip_updates",
        "schedule": timedelta(seconds=15),
    },
}
