try:
    import ulab.numpy as np
except ImportError:
    import numpy as np

try:
    from .result import TrafficResult
except ImportError:
    try:
        from result import TrafficResult
    except ImportError:
        from module.result import TrafficResult

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
logger = SimpleLogger("OverVehiclesFilter")

class OverVehiclesFilter:
    """
    MODULE C: TRAFFIC DENSITY CONTROL AGENT
    Evaluates traffic density based on YOLO vehicle counts and ROI occupancy.
    Returns a TrafficResult object.
    """
    def __init__(self, config=None):
        self.config = {}
        
        # Default parameters from docs/module_overvehicle_filter.md
        self.max_vehicle_count = 2
        self.max_occupancy = 0.4
        self.roi_width = 640
        self.roi_height = 480
        self.target_classes = {"car", "bus", "truck"}
        
        if config is not None:
            self.initialize(config)

    def initialize(self, config: dict) -> None:
        """
        Initializes the filter with dynamic configuration.
        """
        try:
            self.config = config if config is not None else {}
            traffic_params = self.config.get("traffic_control", {})
            
            # Load params with safe fallbacks
            self.max_vehicle_count = traffic_params.get("MAX_VEHICLE_COUNT", 2)
            self.max_occupancy = traffic_params.get("MAX_OCCUPANCY", 0.4)
            
            # Load ROI dims if available in config
            roi_params = self.config.get("roi", {})
            self.roi_width = roi_params.get("width", 640)
            self.roi_height = roi_params.get("height", 480)
            
            # Target classes to count
            classes_list = traffic_params.get("vehicle_classes", ["car", "bus", "truck"])
            self.target_classes = set(c.lower() for c in classes_list)
            
            logger.info("Traffic Density Control Filter successfully initialized")
        except Exception as e:
            logger.warning(f"Error during Traffic Density Control Filter initialization: {e}")

    def process(self, frame_or_bboxes, bboxes=None) -> TrafficResult:
        """
        Evaluates the scene density and returns a TrafficResult object.
        Accepts:
            - process(frame, bboxes)
            - process(bboxes)
        """
        try:
            target_bboxes = []
            frame_shape = None
            
            # 1. Parse inputs
            if bboxes is not None:
                # process(frame, bboxes) pattern
                target_bboxes = bboxes
                if hasattr(frame_or_bboxes, "shape"):
                    frame_shape = frame_or_bboxes.shape
            else:
                # process(bboxes) pattern or process(frame) where no bboxes detected
                if isinstance(frame_or_bboxes, (list, tuple)):
                    target_bboxes = frame_or_bboxes
                elif hasattr(frame_or_bboxes, "shape"):
                    frame_shape = frame_or_bboxes.shape
                    target_bboxes = []
            
            # 2. Estimate ROI Area
            if frame_shape is not None:
                roi_area = frame_shape[1] * frame_shape[0]
            else:
                roi_area = self.roi_width * self.roi_height
                
            if roi_area <= 0:
                roi_area = 640 * 480
                
            # 3. Analyze bounding boxes
            vehicle_count = 0
            total_bbox_area = 0.0
            
            for item in target_bboxes:
                box = None
                cls_name = "car"  # Default class
                
                # Handle dictionary format (e.g. {'bbox': [x, y, w, h], 'class': 'car'})
                if isinstance(item, dict):
                    box = item.get("bbox")
                    cls_name = item.get("class", item.get("label", "car"))
                # Handle tuple/list format (e.g. [x, y, w, h, class_id/name] or [x, y, w, h])
                elif isinstance(item, (list, tuple, np.ndarray)):
                    if len(item) >= 4:
                        box = item[:4]
                        if len(item) >= 5:
                            cls_name = item[4]
                            
                if box is not None:
                    # Clean coordinates
                    x, y, w, h = box
                    # Ensure class matches targets
                    if str(cls_name).lower() in self.target_classes:
                        vehicle_count += 1
                        total_bbox_area += (w * h)
            
            # Calculate occupancy ratio
            occupancy = total_bbox_area / roi_area
            
            # Determine if scene is busy and assign reason
            scene_available = True
            reason = "Normal"
            
            if vehicle_count > self.max_vehicle_count:
                scene_available = False
                reason = "TooManyVehicles"
            elif occupancy >= self.max_occupancy:
                scene_available = False
                reason = "HighOccupancy"
                
            if not scene_available:
                logger.warning(f"Scene Busy: reason={reason}, count={vehicle_count} (max={self.max_vehicle_count}), occupancy={occupancy:.2f} (max={self.max_occupancy})")
                
            return TrafficResult(True, scene_available, vehicle_count, occupancy, reason)
                
        except Exception as e:
            logger.warning(f"Error during Traffic Density Control processing: {e}")
            # Fallback values to avoid freezing pipeline
            return TrafficResult(False, True, 0, 0.0, f"Error: {e}")

    def release(self) -> None:
        """
        Releases filter resources.
        """
        pass

