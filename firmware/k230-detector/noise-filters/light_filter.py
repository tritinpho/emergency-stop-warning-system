try:
    import ulab.numpy as np
except ImportError:
    import numpy as np

try:
    from .result import LightResult
except ImportError:
    try:
        from result import LightResult
    except ImportError:
        from module.result import LightResult

class SimpleLogger:
    def __init__(self, name):
        self.name = name

    def info(self, msg, *args):
        print("[{}][INFO] {}".format(self.name, msg))

    def warning(self, msg, *args):
        print("[{}][WARN] {}".format(self.name, msg))

    def error(self, msg, *args):
        print("[{}][ERROR] {}".format(self.name, msg))

# Set up logging using standard Unicode strings
logger = SimpleLogger("LightFilter")

class LightFilter:
    """
    MODULE A: LIGHTING NOISE AGENT
    Uses HSV Thresholding proxy and element-wise Highlight Compression
    implemented using ulab.numpy to suppress lighting noise.
    """
    def __init__(self, config=None):
        self.config = {}
        self.tracked_blobs = []  # List of tracked blobs: each is a dict
        
        # Default parameters from docs/module_light_filter.md
        self.min_area = 20
        self.max_area = 3000
        self.aspect_ratio_min = 0.7
        self.aspect_ratio_max = 1.3
        self.tracking_frame = 10
        self.match_distance = 10
        self.v_threshold = 240
        self.compression_clamp = 150
        
        if config is not None:
            self.initialize(config)

    def initialize(self, config: dict) -> None:
        """
        Initializes the filter with dynamic configuration.
        """
        try:
            self.config = config if config is not None else {}
            blob_params = self.config.get("blob", {})
            
            # Load params with safe fallbacks
            self.min_area = blob_params.get("MIN_BLOB_AREA", 20)
            self.max_area = blob_params.get("MAX_BLOB_AREA", 3000)
            self.aspect_ratio_min = blob_params.get("ASPECT_RATIO_MIN", 0.7)
            self.aspect_ratio_max = blob_params.get("ASPECT_RATIO_MAX", 1.3)
            self.tracking_frame = blob_params.get("TRACKING_FRAME", 10)
            self.match_distance = blob_params.get("MATCH_DISTANCE", 10)
            self.v_threshold = blob_params.get("V_THRESHOLD", 240)
            self.compression_clamp = blob_params.get("COMPRESSION_CLAMP", 150)
            
            self.tracked_blobs = []
            logger.info("Light Filter successfully initialized (ulab.numpy)")
        except Exception as e:
            logger.warning("Error during Light Filter initialization: {}".format(e))

    def process(self, frame: np.ndarray) -> LightResult:
        """
        Processes a frame, tracks light blobs, applies highlight compression,
        and returns a LightResult object.
        """
        try:
            if frame is None:
                return LightResult(frame, False, False, 0, [])
            
            # Check 4D or 3D shape
            is_4d = False
            if len(frame.shape) == 4:
                is_4d = True
                img_3d = frame[0]
            else:
                img_3d = frame
                
            channels, h, w = img_3d.shape
            
            # Use Green channel as proxy for brightness (Value channel in HSV)
            # This is fast, efficient and requires no extra libraries or memory allocation
            v_channel = img_3d[1]
            
            # Create masks
            mask = v_channel > self.v_threshold
            inv_mask = v_channel <= self.v_threshold
            
            # Apply element-wise highlight compression to clamp high luminance values
            output_img = img_3d.copy()
            for c in range(3):
                output_img[c] = img_3d[c] * inv_mask + self.compression_clamp * mask
                
            if is_4d:
                output_frame = output_img.reshape((1, channels, h, w))
            else:
                output_frame = output_img
                
            return LightResult(output_frame, True, False, 0, [])
            
        except Exception as e:
            logger.warning("Error during Light Filter processing: {}".format(e))
            return LightResult(frame, False, False, 0, [])

    def release(self) -> None:
        """
        Releases filter resources.
        """
        self.tracked_blobs = []
        logger.info("Light Filter resources released")

