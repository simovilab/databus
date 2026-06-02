from enum import Enum


class RunProgressStates(str, Enum):
    """The vehicle's micro-state *during* a run.

    These mirror the three GTFS-RT ``VehiclePosition.VehicleStopStatus`` values
    (and the ``Progression.current_status`` choices), so the reported
    ``current_status`` maps directly onto a state.
    """

    IN_TRANSIT_TO = "IN_TRANSIT_TO"
    INCOMING_AT = "INCOMING_AT"
    STOPPED_AT = "STOPPED_AT"


def choices():
    return [(status.value, status.name) for status in RunProgressStates]
