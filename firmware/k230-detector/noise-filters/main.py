import os
import sys
import json
import logging
import cv2
import numpy as np

# Configure standard logging to console
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("OfflineRunner")

# Import the local filters
from shaking_filter import ShakingFilter
from light_filter import LightFilter
from overvehicles_filter import OverVehiclesFilter

def load_config():
    """
    Loads configuration from config.json or fallbacks.
    """
    # Look for local config.json first, then fallback to K230 SD card path
    config_paths = ["config.json", "../config.json", "/sdcard/config.json"]
    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    logger.info(f"Loaded configuration from: {path}")
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error reading config at {path}: {e}")
                
    logger.info("No config.json found. Using default internal parameters.")
    return {
        "shaking_params": {
            "maxCorners": 80,
            "qualityLevel": 0.01,
            "minDistance": 10,
            "blockSize": 7,
            "winSize": [21, 21],
            "maxLevel": 3,
            "maxIters": 30,
            "epsilon": 0.01,
            "shakeThresholdX": 2.0,
            "shakeThresholdY": 2.0
        },
        "blob": {
            "MIN_BLOB_AREA": 20,
            "MAX_BLOB_AREA": 3000,
            "ASPECT_RATIO_MIN": 0.7,
            "ASPECT_RATIO_MAX": 1.3,
            "TRACKING_FRAME": 10,
            "MATCH_DISTANCE": 10,
            "V_THRESHOLD": 240,
            "COMPRESSION_CLAMP": 150
        },
        "traffic_control": {
            "MAX_VEHICLE_COUNT": 2,
            "MAX_OCCUPANCY": 0.4,
            "vehicle_classes": ["car", "bus", "truck"]
        }
    }

def simulate_yolo(frame, frame_count):
    """
    Simulates YOLO object detection bounding boxes for testing density control.
    Coordinates shift slowly to simulate vehicle movement.
    """
    # Simulating 2 cars by default. After 150 frames, we simulate a 3rd car to trigger "Scene Busy".
    bboxes = [
        {"bbox": [120, 150 + int(frame_count * 0.5) % 100, 100, 80], "class": "car"},
        {"bbox": [350 - int(frame_count * 0.3) % 80, 200, 120, 95], "class": "car"}
    ]
    if 100 <= (frame_count % 300) < 200:
        # Add a truck to exceed max vehicle count and trigger density control
        bboxes.append({"bbox": [200, 100, 150, 120], "class": "truck"})
    return bboxes

def main():
    logger.info("Starting Offline Vehicle Detection Noise Filters Simulation...")
    
    config = load_config()
    
    # Initialize filters
    shaking_filter = ShakingFilter()
    light_filter = LightFilter()
    overvehicle_filter = OverVehiclesFilter()
    
    shaking_filter.initialize(config)
    light_filter.initialize(config)
    overvehicle_filter.initialize(config)
    
    # Initialize camera/video stream
    # 0 opens default webcam. You can also pass a path to a video file.
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        logger.error("Could not open video capture stream. Exiting.")
        return
        
    frame_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.info("Video source ended or failed to read frame.")
                break
                
            frame_count += 1
            
            # Step 1: Camera stabilization (Module B)
            shake_res = shaking_filter.process(frame)
            
            # Step 2: Lighting noise filtering and highlight compression (Module A)
            light_res = light_filter.process(shake_res.frame)
            
            # Step 3: Run simulated YOLO detector
            bboxes = simulate_yolo(light_res.frame, frame_count)
            
            # Step 4: Traffic density control evaluation (Module C)
            traffic_res = overvehicle_filter.process(light_res.frame, bboxes)
            can_track = traffic_res.scene_available
            
            # Step 5: Visualizations
            display_frame = light_res.frame.copy()
            
            # Draw bboxes
            for item in bboxes:
                x, y, w, h = item["bbox"]
                cls = item["class"]
                color = (0, 255, 0) if can_track else (0, 0, 255)
                cv2.rectangle(display_frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(display_frame, f"{cls}", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                
            # Draw status HUD
            status_text = "Tracking Status: Active" if can_track else f"Tracking Status: Scene Busy ({traffic_res.reason})"
            status_color = (0, 255, 0) if can_track else (0, 0, 255)
            cv2.putText(display_frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
            cv2.putText(display_frame, f"Frame: {frame_count} | Blobs: {light_res.blob_count}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(display_frame, f"Shake Offset: ({shake_res.offset_x:.1f}, {shake_res.offset_y:.1f})", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Show frames in Windows
            cv2.imshow("1. Original Frame", frame)
            cv2.imshow("2. Stabilized & Highlight Compressed Frame", display_frame)
            
            # Handle keypress exit
            key = cv2.waitKey(30) & 0xFF
            if key == ord('q') or key == 27:
                logger.info("Exit requested by user.")
                break
                
    except KeyboardInterrupt:
        logger.info("Simulation interrupted by keyboard.")
    finally:
        # Release resources
        cap.release()
        cv2.destroyAllWindows()
        shaking_filter.release()
        light_filter.release()
        overvehicle_filter.release()
        logger.info("Offline Simulation clean up completed successfully.")

if __name__ == "__main__":
    main()
