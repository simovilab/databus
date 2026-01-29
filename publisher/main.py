import os
from celery import Celery

rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
rabbitmq_pass = os.getenv("RABBITMQ_PASS", "guest")
rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
rabbitmq_port = os.getenv("RABBITMQ_PORT", "5672")

broker_url = f"amqp://{rabbitmq_user}:{rabbitmq_pass}@{rabbitmq_host}:{rabbitmq_port}/"

app = Celery("publisher", broker=broker_url)


@app.task
def build_vehicle_positions(url, group):
    return "Vehicle positions built."
