from enum import Enum


class RunProgressEvents(str, Enum):
    """Events that drive the progress FSM — one per reported vehicle status.

    A progress event is fired when the vehicle's reported ``current_status``
    changes; the event names the status the vehicle moved *into*.
    """

    VEHICLE_IN_TRANSIT = "vehicle_in_transit"
    VEHICLE_INCOMING = "vehicle_incoming"
    VEHICLE_STOPPED = "vehicle_stopped"
