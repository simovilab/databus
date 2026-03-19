from dataclasses import dataclass


@dataclass
class VehicleState:
    vehicle_id: str
    label: str
    license_plate: str
    latitude: float
    longitude: float
    speed_ms: float
    odometer: int
    timestamp: int
    current_status: str
