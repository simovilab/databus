from kombu import Connection, Exchange, Producer

connection = Connection("amqp://guest:guest@localhost/")
exchange = Exchange("databus.events", type="direct")
producer = Producer(connection, exchange=exchange)


def publish_event(name: str, data: dict):
    """Publish an event to the databus.events exchange."""
    print(f"Printing event {name} with data: {data}")


"""
runs.submission.requested
runs.submission.succeeded
runs.submission.failed
runs.validation.succeeded
runs.validation.failed
runs.initialization.succeeded
runs.initialization.failed

Client:
runs.*
"""
