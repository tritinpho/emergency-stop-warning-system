try:
    import ulab.numpy as np
except ImportError:
    import numpy as np

try:
    from .result import ShakingResult
except ImportError:
    try:
        from result import ShakingResult
    except ImportError:
        from module.result import ShakingResult

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
logger = SimpleLogger("ShakingFilter")

class ShakingFilter:
    """
    MODULE B: CAMERA SHAKING & TRACKING AGENT
    Bypassed/Pass-through under MicroPython (no cv2 support).
    """
    def __init__(self, config=None):
        self.config = {}
        self.prev_features = None
        self.prev_gray = None
        
        # Default parameters from docs/module_shaking_filter.md
        self.max_corners = 80
        self.quality_level = 0.01
        self.min_distance = 10
        self.block_size = 7
        self.win_size = (21, 21)
        self.max_level = 3
        self.max_iters = 30
        self.epsilon = 0.01
        self.shake_threshold_x = 2.0
        self.shake_threshold_y = 2.0
        
        if config is not None:
            self.initialize(config)

    def initialize(self, config: dict) -> None:
        """
        Initializes the filter with dynamic configuration.
        """
        try:
            self.config = config if config is not None else {}
            shaking_params = self.config.get("shaking_params", {})
            
            # Load params from config with defaults
            self.max_corners = shaking_params.get("maxCorners", 80)
            self.quality_level = shaking_params.get("qualityLevel", 0.01)
            self.min_distance = shaking_params.get("minDistance", 10)
            self.block_size = shaking_params.get("blockSize", 7)
            win_size_list = shaking_params.get("winSize", [21, 21])
            self.win_size = (win_size_list[0], win_size_list[1])
            self.max_level = shaking_params.get("maxLevel", 3)
            self.max_iters = shaking_params.get("maxIters", 30)
            self.epsilon = shaking_params.get("epsilon", 0.01)
            self.shake_threshold_x = shaking_params.get("shakeThresholdX", 2.0)
            self.shake_threshold_y = shaking_params.get("shakeThresholdY", 2.0)
            
            logger.info("Shaking Filter successfully initialized (Pass-through)")
        except Exception as e:
            logger.warning("Error during Shaking Filter initialization: {}".format(e))

    def process(self, frame: np.ndarray) -> ShakingResult:
        """
        Processes a frame. Under MicroPython, this acts as a compatible pass-through.
        """
        try:
            if frame is None:
                return ShakingResult(frame, False, True, 0.0, 0.0, 0)
            return ShakingResult(frame, True, True, 0.0, 0.0, 0)
        except Exception as e:
            logger.warning("Error during Shaking Filter processing: {}".format(e))
            return ShakingResult(frame, False, True, 0.0, 0.0, 0)

    def release(self) -> None:
        """
        Releases filter resources.
        """
        self.prev_features = None
        self.prev_gray = None
        logger.info("Shaking Filter resources released")


