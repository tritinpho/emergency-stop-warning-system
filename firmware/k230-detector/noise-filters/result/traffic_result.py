try:
    from dataclasses import dataclass
except ImportError:
    def dataclass(cls):
        return cls

@dataclass
class TrafficResult:
    """
    Result Object for OverVehicle Traffic Density Control.
    Contains evaluation details and reason for blocking tracking.
    """
    success: bool
    scene_available: bool
    vehicle_count: int
    occupancy: float
    reason: str

    def __init__(self, success, scene_available, vehicle_count, occupancy, reason):
        self.success = success
        self.scene_available = scene_available
        self.vehicle_count = vehicle_count
        self.occupancy = occupancy
        self.reason = reason
