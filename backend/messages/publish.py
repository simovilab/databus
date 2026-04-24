from kombu import Connection, Exchange, Producer

connection = Connection("amqp://guest:guest@localhost/")
exchange = Exchange("databus.events", type="direct")
producer = Producer(connection, exchange=exchange)


def databus_event(name: str, data: dict):
    """Publish an event to the databus.events exchange."""
    print(f"Printing event {name} with data: {data}")
