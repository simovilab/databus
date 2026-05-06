def has_valid_gtfs(run, payload):
    return True


def has_valid_telemetry(run, payload):
    return payload["timestamp"] is not None


def is_vehicle_moving(run, payload):
    return payload["speed"] > 5


def telemetry_lost(run, payload, now):
    return (now - run.last_seen_at).seconds > 60
