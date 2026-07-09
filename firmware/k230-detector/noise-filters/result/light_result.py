try:
    from dataclasses import dataclass
except ImportError:
    def dataclass(cls):
        return cls

@dataclass
class LightResult:
    """
    Result Object for Light Filter.
    Contains highlight compressed frame and tracked light blobs info.
    """
    frame: any
    success: bool
    trigger_detect: bool
    blob_count: int
    blob_list: list

    def __init__(self, frame, success, trigger_detect, blob_count, blob_list):
        self.frame = frame
        self.success = success
        self.trigger_detect = trigger_detect
        self.blob_count = blob_count
        self.blob_list = blob_list
