"""Standalone test module for Wi-Fi connection, ROI loading, YOLOv8n_320 detection, and CoreIoT MQTT publishing.

This file can be run directly from CanMV IDE to verify the entire warning loop (Camera, Model, LED, MQTT)
independently of the main production system.
"""

from libs.PipeLine import PipeLine, ScopedTiming
from libs.AIBase import AIBase
from libs.AI2D import Ai2d
from libs.Utils import *
import os
import ujson
from media.media import *
from time import *
import nncase_runtime as nn
import ulab.numpy as np
import time
import utime
import image
import random
import gc
import sys
import aidemo
import network
import socket

# Default fallback configurations. Secret removed (ADR-0016 backlog #6): the
# password is an empty placeholder; load_wifi_credentials() reads the real value
# from config.json / sys_config.json. Rotate the old public value (see README #6).
WIFI_SSID = "ACLAB"
WIFI_PASSWORD = ""

MODEL_PATH = "/sdcard/kmodel/yolov8n_320.kmodel"
MODEL_INPUT_SIZE = [320, 320]
MODEL_CONFIDENCE_THRESHOLD = 0.3
MODEL_NMS_THRESHOLD = 0.2
MODEL_MAX_BOXES = 20

MQTT_BROKER = "app.coreiot.io"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "DEVICE_IOT_01"
MQTT_USERNAME = "device_iot_01"
MQTT_ACCESS_TOKEN = "123"
MQTT_TOPIC = "v1/devices/me/telemetry"
MQTT_QOS = 1
MQTT_RECONNECT_SECONDS = 5

DEVICE_ID = "k230-01"
VEHICLE_CLASSES = ["car", "truck", "bus", "motorcycle", "motorbike"]
VEHICLE_CONFIDENCE_THRESHOLD = 0.5
ROI_OVERLAP_THRESHOLD = 0.2
MIN_CONFIRM_FRAMES = 1
PRESENCE_THRESHOLD_SECONDS = 0
ABSENCE_THRESHOLD_SECONDS = 3


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("Config root must be an object")

    regions = config.get("regions", [])
    if not isinstance(regions, list) or not regions:
        raise ValueError("regions must contain at least one ROI")
    for region in regions:
        polygon = region.get("polygon", []) if isinstance(region, dict) else []
        if not isinstance(polygon, list) or len(polygon) < 3:
            raise ValueError("regions must contain polygons with at least 3 points")


def load_config(config_path):
    with open(config_path, "r") as config_file:
        config = ujson.load(config_file)
    validate_config(config)
    return config


def load_wifi_credentials():
    """Load SSID and PASSWORD dynamically from custom config or system fallback config."""
    ssid = WIFI_SSID
    password = WIFI_PASSWORD
    
    # Try custom config.json first
    try:
        with open("/sdcard/config.json", "r") as f:
            data = ujson.load(f)
            if isinstance(data, dict):
                wifi_sec = data.get("wifi", {}) or data.get("WLAN", {})
                if isinstance(wifi_sec, dict):
                    s = wifi_sec.get("ssid", wifi_sec.get("SSID", ""))
                    p = wifi_sec.get("password", wifi_sec.get("PASSWORD", ""))
                    if s:
                        print("[WIFI] Loaded credentials from config.json")
                        return s, p
    except Exception as e:
        print("[WIFI] config.json WiFi config missing or invalid:", e)
        
    # Try sys_config.json as secondary fallback
    try:
        with open("/sdcard/configs/sys_config.json", "r") as f:
            data = ujson.load(f)
            if isinstance(data, dict) and "WLAN" in data:
                wlan_sec = data["WLAN"]
                s = wlan_sec.get("SSID", "")
                p = wlan_sec.get("PASSWORD", "")
                if s:
                    print("[WIFI] Loaded credentials from sys_config.json")
                    return s, p
    except Exception as e:
        print("[WIFI] sys_config.json WiFi config missing or invalid:", e)
        
    print("[WIFI] Using default fallback credentials")
    return ssid, password


def connect_wifi(ssid, password):
    """Establish connection to the specified Wi-Fi network."""
    print("[WIFI] Connecting to SSID: %s ..." % ssid)
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    if sta.isconnected():
        ip = sta.ifconfig()[0]
        print("[WIFI] Already connected. IP:", ip)
        return ip
        
    sta.connect(ssid, password)
    
    # 15 seconds timeout
    start_time = time.time()
    while not sta.isconnected():
        if time.time() - start_time > 15:
            print("[WIFI] Connection timeout!")
            break
        try:
            os.exitpoint()
        except:
            pass
        time.sleep_ms(200)
        
    if sta.isconnected():
        ip = sta.ifconfig()[0]
        print("[WIFI] Connected successfully! IP:", ip)
        return ip
    else:
        print("[WIFI] Connection failed.")
        return None


def load_mqtt_config(cfg):
    """Load MQTT configuration dynamically from ROI config if available, fallback to defaults."""
    broker = MQTT_BROKER
    port = MQTT_PORT
    client_id = MQTT_CLIENT_ID
    username = MQTT_USERNAME
    password = MQTT_ACCESS_TOKEN
    topic = MQTT_TOPIC
    
    if isinstance(cfg, dict):
        mqtt_cfg = cfg.get("server", {}) or cfg.get("mqtt", {}) or cfg
        if isinstance(mqtt_cfg, dict):
            broker = mqtt_cfg.get("broker", mqtt_cfg.get("mqtt_broker", broker))
            port = int(mqtt_cfg.get("port", mqtt_cfg.get("mqtt_port", port)))
            client_id = mqtt_cfg.get("client_id", mqtt_cfg.get("mqtt_client_id", client_id))
            username = mqtt_cfg.get("username", mqtt_cfg.get("mqtt_username", username))
            password = mqtt_cfg.get("password", mqtt_cfg.get("mqtt_password", password))
            topic = mqtt_cfg.get("telemetry_topic", mqtt_cfg.get("mqtt_topic", topic))
            print("[MQTT] Loaded settings from config.json")
            
    return broker, port, client_id, username, password, topic


def collect_vehicle_detections(boxes, classes, confidences, labels, vehicle_classes):
    vehicle_set = set(vehicle_classes)
    detections = []
    for index in range(len(boxes)):
        class_id = int(classes[index])
        if class_id < 0 or class_id >= len(labels):
            continue
        label = labels[class_id]
        if label not in vehicle_set:
            continue
        x, y, width, height = boxes[index]
        detections.append(
            {
                "class": label,
                "confidence": round(float(confidences[index]), 4),
                "bbox": [
                    int(round(x)),
                    int(round(y)),
                    int(round(x + width)),
                    int(round(y + height)),
                ],
            }
        )
    return detections


def build_telemetry_payload(vehicle_detected, device_id, uptime_ms, detections):
    return {
        "vehicle_detected": bool(vehicle_detected),
        "device_id": device_id,
        "uptime_ms": int(uptime_ms),
        "detections": detections if vehicle_detected else [],
    }


def _mqtt_string(value):
    data = value.encode("utf-8") if isinstance(value, str) else value
    length = len(data)
    if length > 65535:
        raise ValueError("MQTT string is too long")
    return bytes((length >> 8, length & 0xFF)) + data


def _mqtt_remaining_length(length):
    encoded = bytearray()
    while True:
        digit = length % 128
        length //= 128
        if length:
            digit |= 0x80
        encoded.append(digit)
        if not length:
            return bytes(encoded)


class SocketMqttClient:
    """Minimal MQTT 3.1.1 publisher implemented on the firmware socket module."""

    def __init__(
        self,
        client_id,
        host,
        port,
        username,
        password,
        keepalive,
        socket_module=socket,
        timeout=5,
    ):
        self.client_id = client_id
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.keepalive_seconds = keepalive
        self.socket_module = socket_module
        self.timeout = timeout
        self.sock = None
        self.packet_id = 0
        self.last_keepalive_ms = None

    def _write_all(self, data):
        offset = 0
        while offset < len(data):
            written = self.sock.write(data[offset : offset + 1024])
            if not written:
                raise OSError("MQTT socket closed while writing")
            offset += written

    def _read_exact(self, length):
        data = bytearray()
        while len(data) < length:
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                raise OSError("MQTT socket closed while reading")
            data.extend(chunk)
        return bytes(data)

    def _read_packet(self):
        packet_type = self._read_exact(1)[0]
        remaining = 0
        multiplier = 1
        for _ in range(4):
            digit = self._read_exact(1)[0]
            remaining += (digit & 0x7F) * multiplier
            if not digit & 0x80:
                return packet_type, self._read_exact(remaining)
            multiplier *= 128
        raise OSError("Invalid MQTT remaining length")

    def connect(self):
        self.close()
        address = self.socket_module.getaddrinfo(self.host, self.port)[0][-1]
        self.sock = self.socket_module.socket()
        self.sock.settimeout(self.timeout)
        try:
            self.sock.connect(address)
            variable_header = b"\x00\x04MQTT\x04\xc2" + bytes(
                (
                    self.keepalive_seconds >> 8,
                    self.keepalive_seconds & 0xFF,
                )
            )
            payload = (
                _mqtt_string(self.client_id)
                + _mqtt_string(self.username)
                + _mqtt_string(self.password)
            )
            body = variable_header + payload
            self._write_all(b"\x10" + _mqtt_remaining_length(len(body)) + body)
            packet_type, response = self._read_packet()
            if packet_type != 0x20 or len(response) != 2:
                raise OSError("Invalid MQTT CONNACK")
            if response[1] != 0:
                raise OSError("MQTT CONNACK refused: " + str(response[1]))
            self.last_keepalive_ms = None
        except Exception:
            self.close()
            raise

    def publish(self, topic, payload, retain=False, qos=0):
        if qos not in (0, 1):
            raise ValueError("Socket MQTT supports QoS 0 or 1")
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        variable_header = _mqtt_string(topic)
        expected_packet_id = None
        if qos == 1:
            self.packet_id = (self.packet_id % 65535) + 1
            expected_packet_id = self.packet_id
            variable_header += bytes((self.packet_id >> 8, self.packet_id & 0xFF))
        header = 0x30 | (qos << 1) | (1 if retain else 0)
        body = variable_header + payload
        self._write_all(bytes((header,)) + _mqtt_remaining_length(len(body)) + body)
        if qos == 1:
            while True:
                packet_type, response = self._read_packet()
                if packet_type == 0xD0:  # Ignore a queued PINGRESP.
                    continue
                if packet_type != 0x40 or len(response) != 2:
                    raise OSError("Invalid MQTT PUBACK")
                received_id = (response[0] << 8) | response[1]
                if received_id != expected_packet_id:
                    raise OSError("MQTT PUBACK packet id mismatch")
                break

    def keepalive(self, now_ms):
        if self.last_keepalive_ms is None:
            self.last_keepalive_ms = now_ms
            return
        elapsed = ((now_ms - self.last_keepalive_ms + (1 << 29)) % (1 << 30)) - (
            1 << 29
        )
        if elapsed < self.keepalive_seconds * 500:
            return
        self._write_all(b"\xc0\x00")
        packet_type, response = self._read_packet()
        if packet_type != 0xD0 or response:
            raise OSError("Invalid MQTT PINGRESP")
        self.last_keepalive_ms = now_ms

    def disconnect(self):
        if self.sock is not None:
            try:
                self._write_all(b"\xe0\x00")
            except Exception:
                pass
        self.close()

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None


class MqttStatePublisher:
    def __init__(
        self,
        client_factory,
        topic,
        qos,
        reconnect_interval_ms,
        serializer,
        ticks_period=1 << 30,
    ):
        self.client_factory = client_factory
        self.topic = topic
        self.qos = qos
        self.reconnect_interval_ms = int(reconnect_interval_ms)
        self.serializer = serializer
        self.ticks_period = ticks_period
        self.client = None
        self.connected = False
        self.pending = None
        self.last_attempt_ms = None

    def _ticks_diff(self, current, previous):
        half_period = self.ticks_period // 2
        return ((current - previous + half_period) % self.ticks_period) - half_period

    def queue(self, payload):
        self.pending = payload

    def _close_client(self):
        if self.client is not None:
            try:
                self.client.disconnect()
            except:
                pass
        self.client = None
        self.connected = False

    def service(self, now_ms):
        if self.pending is None:
            if self.connected:
                try:
                    self.client.keepalive(now_ms)
                except Exception as error:
                    print("[WARN] MQTT keepalive failed:", error)
                    self.last_attempt_ms = now_ms
                    self._close_client()
            return self.connected
        if not self.connected:
            if (
                self.last_attempt_ms is not None
                and self._ticks_diff(now_ms, self.last_attempt_ms)
                < self.reconnect_interval_ms
            ):
                return False
            self.last_attempt_ms = now_ms
            try:
                self.client = self.client_factory()
                self.client.connect()
                self.connected = True
                print("[INFO] MQTT connected")
            except Exception as error:
                print("[WARN] MQTT connect failed:", error)
                self._close_client()
                return False
        try:
            self.client.publish(
                self.topic, self.serializer(self.pending), retain=False, qos=self.qos
            )
            self.pending = None
            return True
        except Exception as error:
            print("[WARN] MQTT publish failed:", error)
            self.last_attempt_ms = now_ms
            self._close_client()
            return False

    def close(self):
        self._close_client()


def is_vehicle_detection(detection, vehicle_classes):
    class_name = detection.get("class_name", detection.get("class"))
    return class_name in vehicle_classes


def _polygon_area(polygon):
    area = 0.0
    for index in range(len(polygon)):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % len(polygon)]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def bbox_roi_intersection_area(bbox, roi_polygon):
    x1, y1, x2, y2 = bbox
    polygon = [(float(point[0]), float(point[1])) for point in roi_polygon]

    def clip(points, inside, intersect):
        if not points:
            return []
        output = []
        previous = points[-1]
        previous_inside = inside(previous)
        for current in points:
            current_inside = inside(current)
            if current_inside != previous_inside:
                output.append(intersect(previous, current))
            if current_inside:
                output.append(current)
            previous = current
            previous_inside = current_inside
        return output

    def vertical_intersection(a, b, x):
        if b[0] == a[0]:
            return (x, a[1])
        ratio = (x - a[0]) / (b[0] - a[0])
        return (x, a[1] + ratio * (b[1] - a[1]))

    def horizontal_intersection(a, b, y):
        if b[1] == a[1]:
            return (a[0], y)
        ratio = (y - a[1]) / (b[1] - a[1])
        return (a[0] + ratio * (b[0] - a[0]), y)

    polygon = clip(
        polygon, lambda p: p[0] >= x1, lambda a, b: vertical_intersection(a, b, x1)
    )
    polygon = clip(
        polygon, lambda p: p[0] <= x2, lambda a, b: vertical_intersection(a, b, x2)
    )
    polygon = clip(
        polygon, lambda p: p[1] >= y1, lambda a, b: horizontal_intersection(a, b, y1)
    )
    polygon = clip(
        polygon, lambda p: p[1] <= y2, lambda a, b: horizontal_intersection(a, b, y2)
    )
    return _polygon_area(polygon) if len(polygon) >= 3 else 0.0


def detection_is_in_roi(
    detection, roi_polygons, confidence_threshold=0.5, roi_overlap_threshold=0.2
):
    if float(detection.get("confidence", 0)) <= confidence_threshold:
        return False
    bbox = detection.get("bbox")
    if not bbox or len(bbox) != 4:
        return False
    x1, y1, x2, y2 = bbox
    bbox_area = max(0, x2 - x1) * max(0, y2 - y1)
    if bbox_area <= 0:
        return False
    for polygon in roi_polygons:
        if (
            bbox_roi_intersection_area(bbox, polygon) / bbox_area
            > roi_overlap_threshold
        ):
            return True
    return False


class VehiclePresenceFilter:
    NO_VEHICLE = "NO_VEHICLE"
    VEHICLE_PRESENT = "VEHICLE_PRESENT"
    TEMP_LOST = "TEMP_LOST"

    def __init__(
        self,
        vehicle_classes,
        confidence_threshold=0.5,
        missing_timeout_ms=700,
        min_confirm_frames=2,
        roi_overlap_threshold=0.2,
        presence_ms=0,
        ticks_period=1 << 30,
    ):
        self.vehicle_classes = set(vehicle_classes)
        self.confidence_threshold = float(confidence_threshold)
        self.missing_timeout_ms = int(missing_timeout_ms)
        self.min_confirm_frames = int(min_confirm_frames)
        self.roi_overlap_threshold = float(roi_overlap_threshold)
        self.presence_ms = int(presence_ms)
        self.state = self.NO_VEHICLE
        self.confirm_frames = 0
        self.confirm_since = None
        self.last_seen_time = None
        self.ticks_period = ticks_period

    def _ticks_diff(self, current, previous):
        half_period = self.ticks_period // 2
        return ((current - previous + half_period) % self.ticks_period) - half_period

    def update(self, detections, roi_polygons, now_ms):
        valid = [
            detection
            for detection in detections
            if is_vehicle_detection(detection, self.vehicle_classes)
            and detection_is_in_roi(
                detection,
                roi_polygons,
                self.confidence_threshold,
                self.roi_overlap_threshold,
            )
        ]

        if valid:
            self.last_seen_time = now_ms
            if self.state == self.NO_VEHICLE:
                if self.confirm_frames == 0:
                    self.confirm_since = now_ms
                self.confirm_frames += 1
                enough_time = (
                    self._ticks_diff(now_ms, self.confirm_since) >= self.presence_ms
                )
                if self.confirm_frames >= self.min_confirm_frames and enough_time:
                    self.state = self.VEHICLE_PRESENT
            else:
                self.state = self.VEHICLE_PRESENT
            self.confirm_frames = (
                0 if self.state == self.VEHICLE_PRESENT else self.confirm_frames
            )
        elif self.state == self.NO_VEHICLE:
            self.confirm_frames = 0
            self.confirm_since = None
        elif self.state == self.VEHICLE_PRESENT:
            self.state = self.TEMP_LOST
        elif self._ticks_diff(now_ms, self.last_seen_time) > self.missing_timeout_ms:
            self.state = self.NO_VEHICLE
            self.confirm_frames = 0
            self.confirm_since = None

        return {
            "emergency_lane_occupied": 0 if self.state == self.NO_VEHICLE else 1,
            "state": self.state,
            "valid_detection_count": len(valid),
            "valid_detections": valid,
        }


# Custom YOLOv8 detection class matching Yahboom device-tested baseline
class ObjectDetectionApp(AIBase):
    def __init__(
        self,
        kmodel_path,
        labels,
        model_input_size,
        max_boxes_num,
        confidence_threshold=0.5,
        nms_threshold=0.2,
        rgb888p_size=[224, 224],
        display_size=[1920, 1080],
        debug_mode=0,
    ):
        super().__init__(kmodel_path, model_input_size, rgb888p_size, debug_mode)
        self.kmodel_path = kmodel_path
        self.labels = labels
        self.model_input_size = model_input_size
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.max_boxes_num = max_boxes_num
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0], 16), rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0], 16), display_size[1]]
        self.debug_mode = debug_mode
        self.color_four = get_colors(len(self.labels))
        self.x_factor = float(self.rgb888p_size[0]) / self.model_input_size[0]
        self.y_factor = float(self.rgb888p_size[1]) / self.model_input_size[1]
        
        # Ai2d instance for model preprocessing
        self.ai2d = Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(
            nn.ai2d_format.NCHW_FMT, nn.ai2d_format.NCHW_FMT, np.uint8, np.uint8
        )
        self.roi_polygons = []
        self.exclusion_polygons = []

    # Preprocessing with padding to match device-tested YOLOv8 examples
    def config_preprocess(self, input_image_size=None):
        with ScopedTiming("set preprocess config", self.debug_mode > 0):
            ai2d_input_size = (
                input_image_size if input_image_size else self.rgb888p_size
            )
            top, bottom, left, right, self.scale = letterbox_pad_param(
                self.rgb888p_size, self.model_input_size
            )
            self.ai2d.pad([0, 0, 0, 0, top, bottom, left, right], 0, [128, 128, 128])
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build(
                [1, 3, ai2d_input_size[1], ai2d_input_size[0]],
                [1, 3, self.model_input_size[1], self.model_input_size[0]],
            )

    # Hardware-accelerated postprocessing in C/C++
    def postprocess(self, results):
        with ScopedTiming("postprocess", self.debug_mode > 0):
            new_result = results[0][0].transpose()
            det_res = aidemo.yolov8_det_postprocess(
                new_result.copy(),
                [self.rgb888p_size[1], self.rgb888p_size[0]],
                [self.model_input_size[1], self.model_input_size[0]],
                [self.display_size[1], self.display_size[0]],
                len(self.labels),
                self.confidence_threshold,
                self.nms_threshold,
                self.max_boxes_num,
            )
            return det_res

    # Draw OSD boxes, ROI, and exclusion zones
    def draw_result(self, pl, dets):
        with ScopedTiming("display_draw", self.debug_mode > 0):
            pl.osd_img.clear()

            # Draw active ROI (Neon Cyan: ARGB 255, 0, 255, 255)
            if hasattr(self, "roi_polygons") and self.roi_polygons:
                for poly in self.roi_polygons:
                    n = len(poly)
                    for i in range(n):
                        p1 = poly[i]
                        p2 = poly[(i + 1) % n]
                        x1 = int(p1[0] * self.display_size[0])
                        y1 = int(p1[1] * self.display_size[1])
                        x2 = int(p2[0] * self.display_size[0])
                        y2 = int(p2[1] * self.display_size[1])
                        pl.osd_img.draw_line(
                            x1, y1, x2, y2, color=(255, 0, 255, 255), thickness=4
                        )

            # Draw Exclusion regions (Neon Red: ARGB 255, 255, 0, 0)
            if hasattr(self, "exclusion_polygons") and self.exclusion_polygons:
                for poly in self.exclusion_polygons:
                    n = len(poly)
                    for i in range(n):
                        p1 = poly[i]
                        p2 = poly[(i + 1) % n]
                        x1 = int(p1[0] * self.display_size[0])
                        y1 = int(p1[1] * self.display_size[1])
                        x2 = int(p2[0] * self.display_size[0])
                        y2 = int(p2[1] * self.display_size[1])
                        pl.osd_img.draw_line(
                            x1, y1, x2, y2, color=(255, 255, 0, 0), thickness=4
                        )

            # Draw bounding boxes of vehicles in ROI
            if dets and len(dets) >= 3 and dets[0]:
                boxes = dets[0]
                classes = dets[1]
                confidences = dets[2]
                for i in range(len(boxes)):
                    x, y, w, h = map(lambda val: int(round(val, 0)), boxes[i])
                    class_id = int(classes[i])
                    conf = confidences[i]
                    color = self.color_four[class_id % len(self.color_four)]
                    pl.osd_img.draw_rectangle(x, y, w, h, color=color, thickness=4)
                    pl.osd_img.draw_string_advanced(
                        x,
                        y - 50,
                        32,
                        " " + self.labels[class_id] + " " + str(round(conf, 2)),
                        color=color,
                    )


# Ray-casting algorithm
def is_point_in_polygon(x, y, polygon):
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def is_point_in_roi(x, y, roi_polygons, exclusion_polygons):
    for ep in exclusion_polygons:
        if is_point_in_polygon(x, y, ep):
            return False
    for rp in roi_polygons:
        if is_point_in_polygon(x, y, rp):
            return True
    return False


def main():
    print("[MAIN] Starting standalone warning camera loop...")
    ob_det = None
    pl = None
    mqtt_publisher = None
    k230_rgb = None

    # Onboard RGB LED initialization
    try:
        from ybUtils.YbRGB import YbRGB
        k230_rgb = YbRGB()
        k230_rgb.show_rgb((0, 0, 0)) # Off on startup
        print("[INFO] Onboard RGB LED registered successfully.")
    except Exception as e:
        print("[WARN] RGB LED module is unavailable:", e)

    # 1. Load config
    config_path = "/sdcard/config.json"
    try:
        cfg = load_config(config_path)
    except Exception as e:
        print("[FATAL] ROI configuration load failed or is invalid:", e)
        if k230_rgb:
            try:
                k230_rgb.show_rgb((0, 0, 0))
            except:
                pass
        sys.exit(1)

    roi_polygons = [region["polygon"] for region in cfg["regions"]]
    exclusion_polygons = []
    for region in cfg.get("exclusion_regions", []):
        polygon = region.get("polygon", []) if isinstance(region, dict) else region
        if len(polygon) >= 3:
            exclusion_polygons.append(polygon)

    print("[INFO] Configuration loaded successfully.")
    print("  - Model:", MODEL_PATH)
    print("  - ROI regions:", len(roi_polygons))

    # 2. Wi-Fi setup
    wifi_ssid, wifi_password = load_wifi_credentials()
    ip = connect_wifi(wifi_ssid, wifi_password)

    # 3. MQTT setup
    mqtt_broker, mqtt_port, mqtt_client_id, mqtt_username, mqtt_password, mqtt_topic = load_mqtt_config(cfg)
    
    def create_mqtt_client():
        return SocketMqttClient(
            mqtt_client_id,
            mqtt_broker,
            mqtt_port,
            mqtt_username,
            mqtt_password,
            60,
        )

    mqtt_publisher = MqttStatePublisher(
        create_mqtt_client,
        mqtt_topic,
        MQTT_QOS,
        int(MQTT_RECONNECT_SECONDS * 1000),
        ujson.dumps,
    )

    # 4. Pipeline & Model initialization
    display_mode = "lcd"
    display_size = [640, 480]
    
    labels = [
        "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", 
        "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", 
        "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", 
        "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", 
        "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", 
        "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", 
        "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", 
        "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", 
        "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", 
        "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
    ]
    
    try:
        pl = PipeLine(
            rgb888p_size=MODEL_INPUT_SIZE,
            display_size=display_size,
            display_mode=display_mode,
        )
        pl.create()
        print("[INFO] PipeLine started in LCD mode.")
    except Exception as e:
        print("[WARN] ST7701 LCD mode failed, trying HDMI fallback: %s" % e)
        if pl:
            try:
                pl.destroy()
            except:
                pass
        try:
            display_size = [1920, 1080]
            display_mode = "hdmi"
            pl = PipeLine(
                rgb888p_size=MODEL_INPUT_SIZE,
                display_size=display_size,
                display_mode=display_mode,
            )
            pl.create()
            print("[INFO] PipeLine started in HDMI mode.")
        except Exception as e2:
            print("[FATAL] Both display modes failed to initialize: %s" % e2)
            sys.exit(1)

    ob_det = ObjectDetectionApp(
        MODEL_PATH,
        labels=labels,
        model_input_size=MODEL_INPUT_SIZE,
        max_boxes_num=MODEL_MAX_BOXES,
        confidence_threshold=MODEL_CONFIDENCE_THRESHOLD,
        nms_threshold=MODEL_NMS_THRESHOLD,
        rgb888p_size=MODEL_INPUT_SIZE,
        display_size=display_size,
        debug_mode=0,
    )
    ob_det.config_preprocess()
    ob_det.roi_polygons = roi_polygons
    ob_det.exclusion_polygons = exclusion_polygons

    presence_filter = VehiclePresenceFilter(
        VEHICLE_CLASSES,
        confidence_threshold=VEHICLE_CONFIDENCE_THRESHOLD,
        missing_timeout_ms=int(ABSENCE_THRESHOLD_SECONDS * 1000),
        min_confirm_frames=MIN_CONFIRM_FRAMES,
        roi_overlap_threshold=ROI_OVERLAP_THRESHOLD,
        presence_ms=int(PRESENCE_THRESHOLD_SECONDS * 1000),
    )
    
    previous_occupied = False
    latest_detections = []
    frame_index = 0
    boot_ms = utime.ticks_ms()

    # Publish initial safe status telemetry
    mqtt_publisher.queue(build_telemetry_payload(False, mqtt_client_id, 0, []))
    mqtt_publisher.service(boot_ms)
    
    if k230_rgb:
        try:
            k230_rgb.show_rgb((0, 255, 0)) # Green (Safe) initially
        except:
            pass

    print("[INFO] Inference loop started successfully.")

    try:
        while True:
            os.exitpoint()
            with ScopedTiming("total", 0):
                # 1. Fetch frame
                img = pl.get_frame()
                if img is None:
                    continue

                # 2. Inference
                res = ob_det.run(img)

                # 3. Filter boxes outside ROI or inside exclusion zones
                filtered_boxes = []
                filtered_classes = []
                filtered_confidences = []

                if res and len(res) >= 3 and res[0]:
                    boxes = res[0]
                    classes = res[1]
                    confidences = res[2]

                    for i in range(len(boxes)):
                        x, y, w, h = boxes[i]
                        class_id = classes[i]
                        conf = confidences[i]

                        # Calculate bottom-center coordinate of bbox
                        px = x + w / 2.0
                        py = y + h

                        norm_x = px / display_size[0]
                        norm_y = py / display_size[1]

                        if is_point_in_roi(
                            norm_x, norm_y, roi_polygons, exclusion_polygons
                        ):
                            filtered_boxes.append([x, y, w, h])
                            filtered_classes.append(class_id)
                            filtered_confidences.append(conf)

                if filtered_boxes:
                    res_filtered = [
                        filtered_boxes,
                        filtered_classes,
                        filtered_confidences,
                    ]
                else:
                    res_filtered = None

                res = res_filtered

                # 4. Debounce and filter class
                if res:
                    latest_detections = collect_vehicle_detections(
                        res[0], res[1], res[2], labels, VEHICLE_CLASSES
                    )
                else:
                    latest_detections = []

                now_ms = utime.ticks_ms()
                frame_index += 1
                for detection in latest_detections:
                    detection["frame_index"] = frame_index
                
                pixel_rois = [
                    [
                        [point[0] * display_size[0], point[1] * display_size[1]]
                        for point in polygon
                    ]
                    for polygon in roi_polygons
                ]
                
                presence = presence_filter.update(latest_detections, pixel_rois, now_ms)
                occupied = bool(presence["emergency_lane_occupied"])
                
                # Update LED indicator (Red if occupied, Green if safe)
                if k230_rgb:
                    try:
                        if occupied:
                            k230_rgb.show_rgb((255, 0, 0)) # Red (Warning)
                        else:
                            k230_rgb.show_rgb((0, 255, 0)) # Green (Safe)
                    except:
                        pass

                # Publish to MQTT on state changes
                if occupied != previous_occupied:
                    uptime_ms = utime.ticks_diff(now_ms, boot_ms)
                    payload = build_telemetry_payload(
                        occupied, mqtt_client_id, uptime_ms, presence["valid_detections"]
                    )
                    mqtt_publisher.queue(payload)
                    previous_occupied = occupied
                    print("[INFO] Vehicle state changed. Lane occupied:", occupied)

                # Keepalive and queue publisher servicing
                mqtt_publisher.service(now_ms)

                # Draw to OSD
                ob_det.draw_result(pl, res)

                # Show frame
                pl.show_image()
                gc.collect()

    except KeyboardInterrupt:
        print("[INFO] Stop request received via KeyboardInterrupt.")
    except Exception as e:
        sys.print_exception(e)
    finally:
        print("[INFO] Cleaning up resources...")
        if ob_det:
            try:
                ob_det.deinit()
            except:
                pass
        if pl:
            pl.destroy()
        if mqtt_publisher:
            mqtt_publisher.close()
        if k230_rgb:
            try:
                k230_rgb.show_rgb((0, 0, 0)) # Turn off LED
            except:
                pass
        print("[INFO] Standalone warning loop stopped.")


if __name__ == "__main__":
    main()
