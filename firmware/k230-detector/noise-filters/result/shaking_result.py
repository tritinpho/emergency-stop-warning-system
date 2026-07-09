try:
    from dataclasses import dataclass
except ImportError:
    def dataclass(cls):
        return cls

@dataclass
class ShakingResult:
    """
    Result Object for Shaking Filter.
    Contains stabilized frame and debugging metrics.
    """
    frame: any
    success: bool
    is_stable: bool
    offset_x: float
    offset_y: float
    feature_count: int

    def __init__(self, frame, success, is_stable, offset_x, offset_y, feature_count):
        self.frame = frame
        self.success = success
        self.is_stable = is_stable
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.feature_count = feature_count
