"""Unified main.py for Yahboom K230 Emergency Lane Monitoring.

Integrates:
1. Dynamic Wi-Fi & MQTT configuration from config.json.
2. Web UI ROI Setup Mode (captured using KEY button, Web Server on port 8081, Auto-Reboot).
3. Production Warning Loop (YOLOv8 vehicle detection, ROI checking, MQTT reporting, RGB LED indicator).
"""

from libs.PipeLine import PipeLine, ScopedTiming
from libs.AIBase import AIBase
from libs.AI2D import Ai2d
from libs.Utils import *
from media.sensor import CAM_CHN_ID_1
import media.sensor as sensor
from media.display import Display
from media.media import MediaManager, ALIGN_UP
import os
import ujson
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
import aicube

# Add noise filter module path
sys.path.append("/sdcard/noise_filter_module")
from shaking_filter import ShakingFilter
from light_filter import LightFilter
from overvehicles_filter import OverVehiclesFilter

# Runtime defaults. Secrets removed (ADR-0016 backlog #6): the Wi-Fi password and
# CoreIoT token below are empty placeholders; load_wifi_credentials() /
# load_mqtt_config() read the real values from config.json / sys_config.json. The
# old public values must be rotated by ACLAB ELMS (see README "Local modifications").
WIFI_SSID = "ACLAB"
WIFI_PASSWORD = ""

MODEL_PATH = "/sdcard/kmodel/yolov8n_320.kmodel"
MODEL_INPUT_SIZE = [320, 320]
MODEL_CONFIDENCE_THRESHOLD = 0.5
MODEL_NMS_THRESHOLD = 0.2
MODEL_MAX_BOXES = 20

MQTT_BROKER = "app.coreiot.io"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "DEVICE_IOT_01"
MQTT_ACCESS_TOKEN = ""  # placeholder — real token loaded via load_mqtt_config(); rotate (README #6)
MQTT_USERNAME = MQTT_ACCESS_TOKEN
MQTT_TOPIC = "v1/devices/me/telemetry"
MQTT_QOS = 1
MQTT_RECONNECT_SECONDS = 5

DEVICE_ID = "k230-01"
VEHICLE_CLASSES = ["car", "truck", "bus", "motorcycle", "motorbike", "vehicle"]
VEHICLE_CONFIDENCE_THRESHOLD = 0.5
ROI_OVERLAP_THRESHOLD = 0.2
MIN_CONFIRM_FRAMES = 1
PRESENCE_THRESHOLD_SECONDS = 0
ABSENCE_THRESHOLD_SECONDS = 3

# Global Onboard RGB LED initialization
k230_rgb = None
try:
    from ybUtils.YbRGB import YbRGB
    k230_rgb = YbRGB()
    k230_rgb.show_rgb((0, 0, 0)) # Off on startup
    print("[INFO] Onboard RGB LED registered successfully.")
except Exception as e:
    print("[WARN] RGB LED module is unavailable:", e)

# HTML page for Web Drawing UI (UTF-8 encoded dynamically when served)
HTML_CONTENT = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>K230 ROI Configuration</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Outfit', sans-serif;
            background-color: #0c0d12;
            color: #f1f2f6;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }
        header {
            background: rgba(255, 255, 255, 0.02);
            backdrop-filter: blur(8px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding: 15px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        header h1 {
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        header .status {
            font-size: 0.85rem;
            background: rgba(0, 242, 254, 0.1);
            color: #00f2fe;
            padding: 6px 12px;
            border-radius: 20px;
            border: 1px solid rgba(0, 242, 254, 0.2);
        }
        .main-container {
            display: flex;
            flex: 1;
            padding: 20px;
            gap: 20px;
            max-width: 1600px;
            margin: 0 auto;
            width: 100%;
        }
        .workspace {
            flex: 1.5;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 15px;
            display: flex;
            justify-content: center;
            align-items: center;
            position: relative;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            backdrop-filter: blur(10px);
            overflow: hidden;
            min-height: 500px;
        }
        .canvas-container {
            position: relative;
            display: inline-block;
            border-radius: 8px;
            overflow: hidden;
            border: 2px solid rgba(255, 255, 255, 0.1);
        }
        canvas {
            display: block;
            cursor: crosshair;
            max-width: 100%;
            height: auto;
        }
        .sidebar {
            flex: 0.8;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            backdrop-filter: blur(10px);
            max-height: calc(100vh - 120px);
            overflow-y: auto;
        }
        h2 {
            font-size: 1.15rem;
            font-weight: 600;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding-bottom: 8px;
            margin-bottom: 5px;
        }
        .mode-selector {
            display: flex;
            gap: 10px;
        }
        .mode-btn {
            flex: 1;
            padding: 12px;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            background: rgba(255, 255, 255, 0.02);
            color: #a4b0be;
            cursor: pointer;
            font-family: inherit;
            font-weight: 600;
            transition: all 0.3s;
            text-align: center;
        }
        .mode-btn.active[data-mode="regions"] {
            background: rgba(0, 242, 254, 0.15);
            border-color: #00f2fe;
            color: #00f2fe;
            box-shadow: 0 0 15px rgba(0, 242, 254, 0.25);
        }
        .mode-btn.active[data-mode="exclusion_regions"] {
            background: rgba(255, 78, 80, 0.15);
            border-color: #ff4e50;
            color: #ff4e50;
            box-shadow: 0 0 15px rgba(255, 78, 80, 0.25);
        }
        .control-btns {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .btn {
            padding: 10px 15px;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            background: rgba(255, 255, 255, 0.05);
            color: #fff;
            cursor: pointer;
            font-family: inherit;
            font-weight: 600;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
        }
        .btn:hover {
            background: rgba(255, 255, 255, 0.1);
        }
        .btn-primary {
            background: linear-gradient(135deg, #00ff87 0%, #60efff 100%);
            border: none;
            color: #050608;
            font-size: 1.05rem;
            padding: 14px;
            box-shadow: 0 4px 15px rgba(0, 255, 135, 0.2);
        }
        .btn-primary:hover {
            background: linear-gradient(135deg, #00ff87 20%, #60efff 100%);
            box-shadow: 0 6px 20px rgba(0, 255, 135, 0.35);
            transform: translateY(-1px);
        }
        .btn-danger {
            background: rgba(255, 78, 80, 0.1);
            border-color: rgba(255, 78, 80, 0.3);
            color: #ff4e50;
        }
        .btn-danger:hover {
            background: rgba(255, 78, 80, 0.25);
            color: #fff;
        }
        .polygon-list {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 8px;
            overflow-y: auto;
            max-height: 250px;
            padding-right: 5px;
        }
        .polygon-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 12px;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            font-size: 0.9rem;
            transition: all 0.2s;
        }
        .polygon-item:hover {
            background: rgba(255, 255, 255, 0.05);
        }
        .polygon-item.regions {
            border-left: 4px solid #00f2fe;
        }
        .polygon-item.exclusion_regions {
            border-left: 4px solid #ff4e50;
        }
        .polygon-item .delete-btn {
            background: none;
            border: none;
            color: #a4b0be;
            cursor: pointer;
            font-size: 1.1rem;
            transition: color 0.2s;
        }
        .polygon-item .delete-btn:hover {
            color: #ff4e50;
        }
        .instructions {
            background: rgba(255, 255, 255, 0.01);
            border: 1px dashed rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 12px;
            font-size: 0.8rem;
            line-height: 1.4;
            color: #a4b0be;
        }
        .instructions ul {
            padding-left: 15px;
            margin-top: 5px;
        }
        .instructions li {
            margin-bottom: 4px;
        }
        #toast {
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%) translateY(100px);
            background: rgba(13, 14, 18, 0.9);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 12px 24px;
            border-radius: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            font-weight: 600;
            transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            opacity: 0;
            pointer-events: none;
            z-index: 1000;
        }
        #toast.show {
            transform: translateX(-50%) translateY(0);
            opacity: 1;
        }
        #toast.success {
            border-color: #00ff87;
            color: #00ff87;
        }
        #toast.error {
            border-color: #ff4e50;
            color: #ff4e50;
        }
        /* Custom scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: rgba(0, 0, 0, 0.1); }
        ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }
    </style>
</head>
<body>
    <header>
        <h1>K230 EMERGENCY LANE ROI SETUP</h1>
        <div class="status">Device ID: k230-01</div>
    </header>
    <div class="main-container">
        <div class="workspace">
            <div class="canvas-container">
                <canvas id="roiCanvas"></canvas>
            </div>
        </div>
        <div class="sidebar">
            <div>
                <h2>1. Draw Mode</h2>
                <div class="mode-selector">
                    <button class="mode-btn active" data-mode="regions">Emergency Lane (ROI)</button>
                    <button class="mode-btn" data-mode="exclusion_regions">Exclusion Zone</button>
                </div>
            </div>

            <div>
                <h2>2. Active Actions</h2>
                <div class="control-btns">
                    <button class="btn" id="undoBtn">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 7v6h6M21 17a9 9 0 00-9-9 9 9 0 00-6 2.3L3 13"/></svg>
                        Undo Point
                    </button>
                    <button class="btn btn-danger" id="clearBtn">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
                        Clear Active
                    </button>
                </div>
            </div>

            <div style="flex: 1; display: flex; flex-direction: column;">
                <h2>3. Configured Polygons</h2>
                <div class="polygon-list" id="polygonList">
                    <!-- Items populated dynamically -->
                </div>
            </div>

            <div class="instructions">
                <strong>How to draw:</strong>
                <ul>
                    <li>Click to place boundary vertices.</li>
                    <li>Click the <b>first vertex</b> to close and complete the polygon.</li>
                    <li>Drag existing vertices to adjust them.</li>
                    <li>You can draw multiple polygons of each type.</li>
                </ul>
            </div>

            <button class="btn btn-primary" id="saveBtn">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
                Save Configuration
            </button>
        </div>
    </div>
    <div id="toast">Saved successfully!</div>

    <script>
        const canvas = document.getElementById('roiCanvas');
        const ctx = canvas.getContext('2d');
        const img = new Image();

        let config = {
            version: 1,
            camera_id: "k230-01",
            reference_resolution: [320, 320],
            regions: [],
            exclusion_regions: []
        };

        let currentMode = 'regions'; // 'regions' or 'exclusion_regions'
        let activePolygon = [];
        let draggedVertex = null; // {type, polyIndex, vertIndex}
        let hoveredVertex = null; // {type, polyIndex, vertIndex}

        // Load configuration and capture image
        img.src = '/capture.jpg';
        img.onload = function() {
            canvas.width = img.naturalWidth;
            canvas.height = img.naturalHeight;
            loadConfig();
        };

        async function loadConfig() {
            try {
                const response = await fetch('/config');
                if (response.ok) {
                    const data = await response.json();
                    if (data.regions) config.regions = data.regions;
                    if (data.exclusion_regions) config.exclusion_regions = data.exclusion_regions;
                    if (data.camera_id) config.camera_id = data.camera_id;
                    updatePolygonList();
                    draw();
                }
            } catch (err) {
                console.error("Failed to load config:", err);
            }
        }

        // Draw mode toggle
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentMode = btn.dataset.mode;
                if (activePolygon.length > 0) {
                    if (confirm("Discard active drawing?")) {
                        activePolygon = [];
                    } else {
                        // Revert active button
                        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
                        document.querySelector(`.mode-btn[data-mode="${currentMode === 'regions' ? 'exclusion_regions' : 'regions'}"]`).classList.add('active');
                        currentMode = currentMode === 'regions' ? 'exclusion_regions' : 'regions';
                    }
                }
                draw();
            });
        });

        // Map normalized point [0..1] to canvas pixels
        function toCanvas(point) {
            return {
                x: point[0] * canvas.width,
                y: point[1] * canvas.height
            };
        }

        // Map canvas pixels to normalized coordinates [0..1]
        function toNormalized(x, y) {
            return [
                parseFloat((x / canvas.width).toFixed(7)),
                parseFloat((y / canvas.height).toFixed(7))
            ];
        }

        function draw() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0);

            // Draw saved regions (ROI)
            config.regions.forEach((region, index) => {
                drawPolygon(region.polygon, '#00f2fe', 'rgba(0, 242, 254, 0.15)', index === hoveredVertex?.polyIndex && hoveredVertex.type === 'regions' ? hoveredVertex.vertIndex : null);
            });

            // Draw saved exclusion regions
            config.exclusion_regions.forEach((region, index) => {
                drawPolygon(region.polygon, '#ff4e50', 'rgba(255, 78, 80, 0.15)', index === hoveredVertex?.polyIndex && hoveredVertex.type === 'exclusion_regions' ? hoveredVertex.vertIndex : null);
            });

            // Draw active polygon
            if (activePolygon.length > 0) {
                const color = currentMode === 'regions' ? '#00f2fe' : '#ff4e50';
                ctx.beginPath();
                const start = toCanvas(activePolygon[0]);
                ctx.moveTo(start.x, start.y);
                for(let i=1; i<activePolygon.length; i++) {
                    const pt = toCanvas(activePolygon[i]);
                    ctx.lineTo(pt.x, pt.y);
                }
                ctx.strokeStyle = color;
                ctx.lineWidth = 3;
                ctx.stroke();

                // Draw active points
                activePolygon.forEach((p, idx) => {
                    const pt = toCanvas(p);
                    ctx.beginPath();
                    ctx.arc(pt.x, pt.y, idx === 0 ? 8 : 5, 0, 2*Math.PI);
                    ctx.fillStyle = idx === 0 ? '#fffa65' : '#ffffff';
                    ctx.fill();
                    ctx.strokeStyle = color;
                    ctx.lineWidth = 2;
                    ctx.stroke();
                });
            }
        }

        function drawPolygon(poly, color, fillColor, activeVertIdx) {
            if (poly.length < 2) return;
            ctx.beginPath();
            const start = toCanvas(poly[0]);
            ctx.moveTo(start.x, start.y);
            for(let i=1; i<poly.length; i++) {
                const pt = toCanvas(poly[i]);
                ctx.lineTo(pt.x, pt.y);
            }
            ctx.closePath();
            ctx.fillStyle = fillColor;
            ctx.fill();
            ctx.strokeStyle = color;
            ctx.lineWidth = 3;
            ctx.stroke();

            // Draw vertices
            poly.forEach((p, idx) => {
                const pt = toCanvas(p);
                ctx.beginPath();
                const isHovered = (idx === activeVertIdx);
                ctx.arc(pt.x, pt.y, isHovered ? 8 : 5, 0, 2*Math.PI);
                ctx.fillStyle = isHovered ? color : '#ffffff';
                ctx.fill();
                ctx.strokeStyle = color;
                ctx.lineWidth = 2;
                ctx.stroke();
            });
        }

        // Mouse handlers
        function getCoords(e) {
            const rect = canvas.getBoundingClientRect();
            return {
                x: (e.clientX - rect.left) * (canvas.width / rect.width),
                y: (e.clientY - rect.top) * (canvas.height / rect.height)
            };
        }

        function findVertex(coords) {
            const types = ['regions', 'exclusion_regions'];
            for (let type of types) {
                const arr = config[type];
                for (let i = 0; i < arr.length; i++) {
                    const poly = arr[i].polygon;
                    for (let j = 0; j < poly.length; j++) {
                        const pt = toCanvas(poly[j]);
                        const dist = Math.hypot(pt.x - coords.x, pt.y - coords.y);
                        if (dist < 10) {
                            return { type, polyIndex: i, vertIndex: j };
                        }
                    }
                }
            }
            return null;
        }

        canvas.addEventListener('mousedown', (e) => {
            const coords = getCoords(e);
            const vert = findVertex(coords);
            if (vert) {
                draggedVertex = vert;
                canvas.style.cursor = 'grabbing';
            }
        });

        canvas.addEventListener('mousemove', (e) => {
            const coords = getCoords(e);
            if (draggedVertex) {
                const norm = toNormalized(coords.x, coords.y);
                config[draggedVertex.type][draggedVertex.polyIndex].polygon[draggedVertex.vertIndex] = norm;
                draw();
                return;
            }

            const hover = findVertex(coords);
            if (hover) {
                hoveredVertex = hover;
                canvas.style.cursor = 'grab';
                draw();
            } else {
                if (hoveredVertex) {
                    hoveredVertex = null;
                    canvas.style.cursor = 'crosshair';
                    draw();
                }
            }
        });

        window.addEventListener('mouseup', () => {
            if (draggedVertex) {
                draggedVertex = null;
                canvas.style.cursor = 'crosshair';
                updatePolygonList();
            }
        });

        canvas.addEventListener('click', (e) => {
            if (draggedVertex) return;
            const coords = getCoords(e);

            // Check if clicking near the first point of the active polygon to close it
            if (activePolygon.length >= 3) {
                const startPt = toCanvas(activePolygon[0]);
                const dist = Math.hypot(startPt.x - coords.x, startPt.y - coords.y);
                if (dist < 15) {
                    // Close polygon
                    const polyId = (currentMode === 'regions' ? 'roi-' : 'ex-') + Date.now().toString().slice(-4);
                    config[currentMode].push({
                        id: polyId,
                        polygon: [...activePolygon]
                    });
                    activePolygon = [];
                    updatePolygonList();
                    draw();
                    showToast("Polygon completed", "success");
                    return;
                }
            }

            // Otherwise, add point
            const norm = toNormalized(coords.x, coords.y);
            activePolygon.push(norm);
            draw();
        });

        // Undo last point
        document.getElementById('undoBtn').addEventListener('click', () => {
            if (activePolygon.length > 0) {
                activePolygon.pop();
                draw();
            } else {
                showToast("No active points to undo", "error");
            }
        });

        // Clear active drawing
        document.getElementById('clearBtn').addEventListener('click', () => {
            if (activePolygon.length > 0) {
                activePolygon = [];
                draw();
                showToast("Active drawing cleared", "success");
            }
        });

        // Update UI sidebar list
        function updatePolygonList() {
            const list = document.getElementById('polygonList');
            list.innerHTML = '';

            const types = ['regions', 'exclusion_regions'];
            types.forEach(type => {
                config[type].forEach((item, index) => {
                    const div = document.createElement('div');
                    div.className = `polygon-item ${type}`;

                    const labelName = type === 'regions' ? 'Emergency Lane' : 'Exclusion';
                    div.innerHTML = `
                        <span><b>${labelName}</b> (#${item.id}) - ${item.polygon.length} pts</span>
                        <button class="delete-btn" onclick="deletePolygon('${type}', ${index})">&times;</button>
                    `;
                    list.appendChild(div);
                });
            });
        }

        window.deletePolygon = function(type, index) {
            config[type].splice(index, 1);
            updatePolygonList();
            draw();
            showToast("Polygon deleted", "success");
        };

        // Toast feedback
        function showToast(msg, type = 'success') {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.className = `show ${type}`;
            setTimeout(() => {
                toast.classList.remove('show');
            }, 2500);
        }

        // Save config to K230
        document.getElementById('saveBtn').addEventListener('click', async () => {
            if (activePolygon.length > 0) {
                if (!confirm("You have an unfinished polygon. Save anyway?")) {
                    return;
                }
            }
            if (config.regions.length === 0) {
                showToast("Please draw at least one Emergency Lane (ROI)!", "error");
                return;
            }

            try {
                const response = await fetch('/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
                const result = await response.json();
                if (response.ok && result.status === 'success') {
                    showToast("Configuration saved! K230 will reboot in 2 seconds...", "success");
                } else {
                    showToast("Save failed: " + (result.message || "Unknown error"), "error");
                }
            } catch (err) {
                showToast("Error connecting to K230", "error");
            }
        });
    </script>
</body>
</html>
"""

# Config management helper functions
def _required(mapping, key, path):
    if not isinstance(mapping, dict) or key not in mapping:
        raise ValueError("Missing required config: " + path)
    return mapping[key]

def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("Config root must be an object")

    regions = _required(config, "regions", "regions")
    if not isinstance(regions, list) or not regions:
        raise ValueError("regions must contain at least one ROI")
    for region in regions:
        polygon = region.get("polygon", []) if isinstance(region, dict) else []
        if not isinstance(polygon, list) or len(polygon) < 3:
            raise ValueError("regions must contain polygons with at least 3 points")

def load_and_merge_config(config_path):
    default_config = {
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
            "vehicle_classes": ["vehicle"]
        }
    }

    config = {}
    try:
        with open(config_path, "r") as config_file:
            config = ujson.load(config_file)
    except OSError:
        # File does not exist or is unreadable
        config = {}
    except Exception as e:
        print("[CONFIG] Error parsing config.json, using defaults:", e)
        config = {}

    # Merge default values
    for key, val in default_config.items():
        if key not in config:
            config[key] = val
        else:
            if isinstance(val, dict) and isinstance(config[key], dict):
                for subkey, subval in val.items():
                    if subkey not in config[key]:
                        config[key][subkey] = subval

    validate_config(config)
    return config

def load_model_config(mode):
    """Load kmodel path, confidence, and NMS thresholds from the mode config (YOLOv8)."""
    config_path = f"/sdcard/model/mp_deployment_source_{mode}/deploy_config.json"
    try:
        with open(config_path, "r") as f:
            deploy_conf = ujson.load(f)

        kmodel_path = f"/sdcard/model/mp_deployment_source_{mode}/{deploy_conf['kmodel_path']}"

        # Force YOLOv8 model if config points to old AnchorBaseDet model
        if "AnchorBaseDet" in kmodel_path or "best_" in kmodel_path:
            print("[MODEL] Config points to AnchorBaseDet model. Forcing YOLOv8 fallback.")
            raise ValueError("AnchorBaseDet not supported, forcing fallback")

        labels = deploy_conf.get("categories", [
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
        ])
        confidence_threshold = deploy_conf.get("confidence_threshold", 0.5)
        nms_threshold = deploy_conf.get("nms_threshold", 0.2)

        print("[MODEL] Loaded %s config: %s, conf=%f" % (mode, kmodel_path, confidence_threshold))
        return {
            "kmodel_path": kmodel_path,
            "labels": labels,
            "confidence_threshold": confidence_threshold,
            "nms_threshold": nms_threshold
        }
    except Exception as e:
        print("[MODEL] Error loading %s config, using hardcoded fallback: %s" % (mode, str(e)))
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
        fallback_kmodel = "/sdcard/kmodel/yolov8n_320.kmodel"

        return {
            "kmodel_path": fallback_kmodel,
            "labels": labels,
            "confidence_threshold": 0.5,
            "nms_threshold": 0.2
        }

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

def connect_wifi(ssid, password, timeout=15):
    """Establish connection to the specified Wi-Fi network."""
    print("[WIFI] Connecting to SSID: %s (timeout=%d) ..." % (ssid, timeout))
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    if sta.isconnected():
        ip = sta.ifconfig()[0]
        print("[WIFI] Already connected. IP:", ip)
        return ip

    sta.connect(ssid, password)

    # Wait for connection up to 'timeout' seconds
    start_time = time.time()
    while not sta.isconnected():
        if time.time() - start_time > timeout:
            print("[WIFI] Connection timeout/deferred!")
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
        print("[WIFI] Connection deferred in background.")
        return None

def load_mqtt_config(cfg):
    """Load MQTT configuration dynamically from ROI config if available, fallback to defaults."""
    broker = MQTT_BROKER
    port = MQTT_PORT
    client_id = MQTT_CLIENT_ID
    username = MQTT_USERNAME
    password = ""
    topic = MQTT_TOPIC

    if isinstance(cfg, dict):
        mqtt_cfg = cfg.get("server", {}) or cfg.get("mqtt", {}) or cfg
        if isinstance(mqtt_cfg, dict):
            broker = mqtt_cfg.get("broker", mqtt_cfg.get("mqtt_broker", broker))
            port = int(mqtt_cfg.get("port", mqtt_cfg.get("mqtt_port", port)))
            client_id = mqtt_cfg.get("client_id", mqtt_cfg.get("mqtt_client_id", client_id))
            username = mqtt_cfg.get("username", mqtt_cfg.get("mqtt_access_token", username))
            password = mqtt_cfg.get("password", "")
            topic = mqtt_cfg.get("telemetry_topic", mqtt_cfg.get("mqtt_topic", topic))
            print("[MQTT] Loaded settings from config.json: broker=%s, client_id=%s, token=%s" % (broker, client_id, username))

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
        # Ignore small blobs (noise/false detections)
        if width < 25 or height < 25:
            continue
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

# MQTT formatting functions
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

# Geometry helper functions
def _polygon_area(polygon):
    area = 0.0
    for index in range(len(polygon)):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % len(polygon)]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5

def bbox_roi_intersection_area(bbox, roi_polygon):
    """Return intersection area of an x1,y1,x2,y2 bbox and a polygon."""
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

# -----------------------------------------------------------------
# Wi-Fi selection screen (OSD + KEY button, no LVGL required)
# -----------------------------------------------------------------

# Popular networks: (display_name, ssid, password_or_None)
# password=None => no baked-in password; the operator supplies it via the touch
# UI or config.json. The lab password was removed here (ADR-0016 backlog #6).
WIFI_PRESETS = [
    ("ACLAB       (saved lab)",   "ACLAB",      None),
    ("iPhone",                    "iPhone",     None),
    ("AndroidAP",                 "AndroidAP",  None),
    ("[Use saved / skip]",        None,         None),   # sentinel: skip selection
]

def save_wifi_to_sys_config(ssid, password):
    """Write SSID/PASSWORD into /sdcard/configs/sys_config.json (WLAN section only)."""
    cfg_path = "/sdcard/configs/sys_config.json"
    data = {}
    try:
        with open(cfg_path, "r") as f:
            data = ujson.load(f)
        if not isinstance(data, dict):
            data = {}
    except Exception:
        pass
    wlan = data.setdefault("WLAN", {})
    wlan["SSID"] = ssid
    wlan["PASSWORD"] = password if password else ""
    wlan["status"] = 1
    try:
        with open(cfg_path, "w") as f:
            f.write(ujson.dumps(data))
        print("[WIFI] Saved to sys_config.json: SSID=%s" % ssid)
    except Exception as e:
        print("[WIFI] Failed to save sys_config.json:", e)

def scan_wifi_networks(pl=None):
    """Scan for surrounding Wi-Fi networks and print/display them."""
    print("[WIFI_SCAN] Scanning for surrounding networks...")
    if pl:
        show_status_on_screen(
            pl,
            "SCANNING WI-FI...",
            ["Scanning surrounding networks...", "Please wait..."],
            color=(255, 80, 200, 80)
        )
    try:
        import network
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        networks = sta.scan()
        print("[WIFI_SCAN] Found %d networks:" % len(networks))
        unique_ssids = []
        for item in networks:
            ssid = item[0].decode("utf-8") if isinstance(item[0], bytes) else item[0]
            rssi = item[3]
            if ssid and ssid not in [x[0] for x in unique_ssids]:
                unique_ssids.append((ssid, rssi))
                print("  - SSID: %s (RSSI: %d)" % (ssid, rssi))

        # Display top 5 networks on screen
        if pl:
            msgs = ["Found networks in range:"]
            for ssid, rssi in unique_ssids[:5]:
                msgs.append("• %s (%d dBm)" % (ssid, rssi))
            msgs.append("Continuing boot in 3s...")
            show_status_on_screen(
                pl,
                "WI-FI SCAN COMPLETED",
                msgs,
                color=(255, 80, 200, 80)
            )
            time.sleep_ms(3000)
        return unique_ssids
    except Exception as e:
        print("[WIFI_SCAN] Scan failed:", e)
        if pl:
            show_status_on_screen(
                pl,
                "WI-FI SCAN FAILED",
                [str(e), "Continuing boot..."],
                color=(255, 255, 0, 0)
            )
            time.sleep_ms(2000)
    return []

def update_mode_from_mqtt(msg_str):
    try:
        data = ujson.loads(msg_str)
        # 1. Check if direct mode is specified
        for key in ("mode", "day_night", "state"):
            if key in data:
                val = str(data[key]).lower()
                if "day" in val:
                    return "day", None
                elif "night" in val:
                    return "night", None

        # 2. Check if time or hour is specified
        hour = None
        time_str = None
        
        raw_time = None
        if "hour" in data:
            hour = int(data["hour"])
            time_str = "%02d:00" % hour
        elif "time" in data:
            raw_time = str(data["time"])
        elif "currentTime" in data:
            raw_time = str(data["currentTime"])
            
        if raw_time is not None:
            time_str = raw_time.strip()
            # If date is included before the time (e.g. "7/8/26, 1:40:31 PM")
            if "," in time_str:
                time_str = time_str.split(",")[-1].strip()
            
            # Handle AM/PM
            is_pm = False
            is_am = False
            lower_time = time_str.lower()
            if "pm" in lower_time:
                is_pm = True
            elif "am" in lower_time:
                is_am = True
                
            # Split by colon
            parts = time_str.split(":")
            if parts:
                # Strip non-digit characters to extract hour
                hour_part = "".join([c for c in parts[0] if c.isdigit()])
                if hour_part:
                    hour = int(hour_part)
                    # Convert 12-hour format to 24-hour format
                    if is_pm and hour < 12:
                        hour += 12
                    elif is_am and hour == 12:
                        hour = 0
                        
        if hour is not None:
            if 6 <= hour < 18:
                return "day", time_str
            else:
                return "night", time_str
    except Exception as e:
        print("[MQTT_TIME] Error parsing day/night payload:", e)
    return None, None

def wifi_selection_screen(pl, key_btn):
    """OSD-based Wi-Fi selection at boot.

    Controls (KEY button):
      - Short press  (<1.5s)  : move cursor to next preset
      - Hold 2-4s            : confirm selected preset and save to sys_config
      - Hold 5s+             : skip this screen (keep whatever is already saved)

    If key_btn is None the function returns immediately (no hardware).
    Returns (ssid, password) of the chosen preset, or (None, None) to skip.
    """
    if key_btn is None:
        print("[WIFI_SEL] No key button available, skipping Wi-Fi selection screen.")
        return None, None

    idx = 0
    n = len(WIFI_PRESETS)

    def _draw(idx, hint):
        if pl is None or not hasattr(pl, "osd_img") or pl.osd_img is None:
            return
        try:
            pl.osd_img.clear()
            w = pl.osd_img.width()
            h = pl.osd_img.height()
            accent = (255, 80, 200, 80)   # green
            dim    = (255, 160, 160, 160)  # grey
            pl.osd_img.draw_rectangle(2, 2, w - 4, h - 4, color=accent, thickness=3)
            pl.osd_img.draw_string_advanced(20, 18, 28, "SELECT WI-FI NETWORK", color=accent)
            pl.osd_img.draw_string_advanced(20, 54, 20, "Short press=next  Hold 2s=confirm  Hold 5s=skip", color=dim)
            y = 100
            for i, (label, ssid, _) in enumerate(WIFI_PRESETS):
                if i == idx:
                    # highlight bar
                    pl.osd_img.draw_rectangle(12, y - 4, w - 24, 36, color=accent, thickness=2)
                    pl.osd_img.draw_string_advanced(20, y, 26, "> " + label, color=accent)
                else:
                    pl.osd_img.draw_string_advanced(20, y, 24, "  " + label, color=dim)
                y += 46
            pl.osd_img.draw_string_advanced(20, h - 40, 20, hint, color=dim)
            pl.show_image()
        except Exception as e:
            print("[WIFI_SEL][OSD] error:", e)

    HOLD_CONFIRM_MS = 2000   # hold this long to confirm
    HOLD_SKIP_MS    = 5000   # hold this long to skip
    DEBOUNCE_MS     = 80

    _draw(idx, "Waiting for KEY press...")
    print("[WIFI_SEL] Screen shown. Waiting for KEY button...")

    # Wait for any activity (up to 30s idle timeout → skip)
    IDLE_TIMEOUT_MS = 60000
    idle_start = time.ticks_ms()

    while True:
        try:
            os.exitpoint()
        except:
            pass

        # Idle timeout: just skip
        if time.ticks_diff(time.ticks_ms(), idle_start) > IDLE_TIMEOUT_MS:
            print("[WIFI_SEL] Idle timeout. Skipping Wi-Fi selection.")
            return None, None

        if not key_btn.is_pressed():
            time.sleep_ms(DEBOUNCE_MS)
            continue

        # Button just went down — measure hold duration
        press_start = time.ticks_ms()
        _draw(idx, "Holding...")
        while key_btn.is_pressed():
            try:
                os.exitpoint()
            except:
                pass
            time.sleep_ms(DEBOUNCE_MS)
        hold_ms = time.ticks_diff(time.ticks_ms(), press_start)

        idle_start = time.ticks_ms()  # reset idle timer on any key event

        if hold_ms >= HOLD_SKIP_MS:
            print("[WIFI_SEL] Long hold — skipping selection (use saved credentials).")
            _draw(idx, "Skipped. Using saved credentials.")
            time.sleep_ms(800)
            return None, None

        elif hold_ms >= HOLD_CONFIRM_MS:
            label, ssid, password = WIFI_PRESETS[idx]
            if ssid is None:   # user explicitly picked the skip sentinel
                print("[WIFI_SEL] Skip sentinel selected.")
                _draw(idx, "Using saved credentials.")
                time.sleep_ms(800)
                return None, None
            pw = password if password else ""
            print("[WIFI_SEL] Confirmed: SSID=%s" % ssid)
            save_wifi_to_sys_config(ssid, pw)
            _draw(idx, "Saved! SSID: " + ssid)
            time.sleep_ms(1000)
            return ssid, pw

        else:
            # Short press — advance to next option
            idx = (idx + 1) % n
            _draw(idx, "KEY short press — cycle options")
            time.sleep_ms(100)

# -----------------------------------------------------------------

def show_status_on_screen(pl, title, messages, color=(255, 0, 255, 0)):
    """Draw a status page on the OSD layer to guide the operator."""
    if pl and hasattr(pl, "osd_img") and pl.osd_img is not None:
        try:
            pl.osd_img.clear()
            width = pl.osd_img.width()
            height = pl.osd_img.height()
            # Draw a nice neon border within the canvas bounds
            pl.osd_img.draw_rectangle(2, 2, width - 4, height - 4, color=color, thickness=4)
            # Title
            pl.osd_img.draw_string_advanced(20, 30, 32, title, color=color)
            # Sub-messages
            y_offset = 100
            for msg in messages:
                pl.osd_img.draw_string_advanced(20, y_offset, 24, msg, color=(255, 240, 240, 240))
                y_offset += 40
            pl.show_image()
        except Exception as e:
            print("[OSD] Error drawing status on screen:", e)

# Custom classes
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

    def subscribe(self, topic):
        self.packet_id = (self.packet_id % 65535) + 1
        variable_header = bytes((self.packet_id >> 8, self.packet_id & 0xFF))
        body = variable_header + _mqtt_string(topic) + b"\x00" # QoS 0
        self._write_all(b"\x82" + _mqtt_remaining_length(len(body)) + body)
        packet_type, response = self._read_packet()
        if packet_type != 0x90 or len(response) != 3:
            raise OSError("Invalid MQTT SUBACK")

    def check_msg(self):
        if self.sock is None:
            return None
        self.sock.settimeout(0)
        try:
            packet_type_byte = self.sock.recv(1)
            if not packet_type_byte:
                return None
            packet_type = packet_type_byte[0]

            remaining = 0
            multiplier = 1
            for _ in range(4):
                digit_byte = self.sock.recv(1)
                if not digit_byte:
                    raise OSError("MQTT closed reading remaining length")
                digit = digit_byte[0]
                remaining += (digit & 0x7F) * multiplier
                if not digit & 0x80:
                    break
                multiplier *= 128

            payload = bytearray()
            self.sock.settimeout(0.2)
            while len(payload) < remaining:
                chunk = self.sock.recv(remaining - len(payload))
                if not chunk:
                    raise OSError("MQTT socket closed while reading payload")
                payload.extend(chunk)

            if (packet_type & 0xF0) == 0x30:
                topic_len = (payload[0] << 8) | payload[1]
                topic = payload[2 : 2 + topic_len].decode("utf-8")
                msg = payload[2 + topic_len :]
                return topic, msg
        except Exception:
            pass
        finally:
            try:
                self.sock.settimeout(self.timeout)
            except Exception:
                pass
        return None

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
            except Exception:
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
                try:
                    self.client.subscribe("v1/devices/me/attributes")
                    print("[INFO] MQTT subscribed to attributes topic")
                except Exception as sub_err:
                    print("[WARN] MQTT subscription to attributes failed:", sub_err)
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
            if detection.get("class") in self.vehicle_classes
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

class ObjectDetectionApp(AIBase):
    def __init__(
        self,
        kmodel_path,
        labels,
        model_input_size,
        max_boxes_num=20,
        confidence_threshold=0.5,
        nms_threshold=0.2,
        rgb888p_size=[320, 320],
        display_size=[640, 480],
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
        self.color_four = [
            (255, 0, 226, 252),  # Neon Cyan
            (255, 255, 77, 255),  # Neon Pink
            (255, 255, 220, 0),   # Neon Yellow
        ]
        self.ai2d = Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(
            nn.ai2d_format.NCHW_FMT, nn.ai2d_format.NCHW_FMT, np.uint8, np.uint8
        )
        self.roi_polygons = []
        self.exclusion_polygons = []

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

    def preprocess(self, input_np):
        with ScopedTiming("preprocess", self.debug_mode > 0):
            return [self.ai2d.run(input_np)]

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

    def draw_result(self, pl, dets, occupied=False, ip=None, mqtt_connected=False, mode="day", brightness=100.0):
        with ScopedTiming("display_draw", self.debug_mode > 0):
            pl.osd_img.clear()

            width = pl.osd_img.width()
            height = pl.osd_img.height()

            # Draw Emergency Lane regions in Cyan Neon (ARGB: 255, 0, 255, 255)
            if hasattr(self, "roi_polygons") and self.roi_polygons:
                for poly in self.roi_polygons:
                    n = len(poly)
                    for i in range(n):
                        p1 = poly[i]
                        p2 = poly[(i + 1) % n]
                        x1 = int(p1[0] * width)
                        y1 = int(p1[1] * height)
                        x2 = int(p2[0] * width)
                        y2 = int(p2[1] * height)
                        pl.osd_img.draw_line(
                            x1, y1, x2, y2, color=(255, 0, 255, 255), thickness=4
                        )

            # Draw Exclusion zones in Red Neon (ARGB: 255, 255, 0, 0)
            if hasattr(self, "exclusion_polygons") and self.exclusion_polygons:
                for poly in self.exclusion_polygons:
                    n = len(poly)
                    for i in range(n):
                        p1 = poly[i]
                        p2 = poly[(i + 1) % n]
                        x1 = int(p1[0] * width)
                        y1 = int(p1[1] * height)
                        x2 = int(p2[0] * width)
                        y2 = int(p2[1] * height)
                        pl.osd_img.draw_line(
                            x1, y1, x2, y2, color=(255, 255, 0, 0), thickness=4
                        )

            # Draw detected objects inside ROI only
            if dets and len(dets) >= 3 and dets[0]:
                boxes = dets[0]
                classes = dets[1]
                confidences = dets[2]
                for i in range(len(boxes)):
                    x, y, w, h = map(lambda val: int(round(val, 0)), boxes[i])
                    class_id = int(classes[i])
                    conf = confidences[i]

                    label = self.labels[class_id] if class_id < len(self.labels) else "unknown"

                    # Check if center-bottom point of box is inside ROI
                    px = x + w / 2.0
                    py = y + h
                    norm_x = px / self.display_size[0]
                    norm_y = py / self.display_size[1]

                    is_in_roi = False
                    if hasattr(self, "roi_polygons") and self.roi_polygons:
                        is_in_roi = is_point_in_roi(norm_x, norm_y, self.roi_polygons, self.exclusion_polygons)

                    # Check if it is a vehicle class, not a small blob, and has high confidence
                    vehicle_set = {"car", "truck", "bus", "motorcycle", "motorbike", "vehicle"}
                    is_vehicle = label.lower() in vehicle_set and w >= 25 and h >= 25 and conf >= VEHICLE_CONFIDENCE_THRESHOLD

                    # Color choice: Neon Cyan for valid vehicles inside ROI, Red for others (outside ROI, non-vehicle, or low-conf)
                    if is_vehicle and is_in_roi:
                        color = (255, 0, 226, 252) # Neon Cyan
                    else:
                        color = (255, 255, 0, 0) # Red (Drawn so the user can verify all detections)

                    pl.osd_img.draw_rectangle(x, y, w, h, color=color, thickness=4)
                    pl.osd_img.draw_string_advanced(
                        x,
                        y - 50,
                        32,
                        " " + label + " " + str(round(conf, 2)),
                        color=color,
                    )

            # Draw Heads-Up Display (HUD) Banner at the top
            try:
                if occupied:
                    status_text = "LANE OCCUPIED - ALERT!"
                    status_color = (255, 255, 0, 0) # Red
                else:
                    status_text = "LANE STATUS: SAFE"
                    status_color = (255, 0, 255, 0) # Green

                pl.osd_img.draw_string_advanced(10, 10, 30, status_text, color=status_color)

                net_text = "IP: %s | MQTT: %s | Mode: %s (Luma: %d)" % (
                    ip if ip else "Offline",
                    "Connected" if mqtt_connected else "Disconnected",
                    mode.upper(),
                    int(brightness),
                )
                pl.osd_img.draw_string_advanced(10, 45, 20, net_text, color=(255, 200, 200, 200))

                # Draw a dedicated synced clock box in the top right corner of the screen
                clock_x = width - 195
                clock_y = 10
                clock_w = 185
                clock_h = 45
                
                # Draw Neon Cyan border for the clock box
                pl.osd_img.draw_rectangle(clock_x, clock_y, clock_w, clock_h, color=(255, 0, 226, 252), thickness=2)
                
                time_str = self.real_time_str if (hasattr(self, "real_time_str") and self.real_time_str) else "Syncing..."
                pl.osd_img.draw_string_advanced(
                    clock_x + 15,
                    clock_y + 8,
                    24,
                    time_str,
                    color=(255, 255, 255, 255)
                )
            except Exception as e:
                pass

    def get_color(self, idx):
        return self.color_four[idx % len(self.color_four)]

# Setup mode specific publisher
def publish_setup_status(ip_address, cfg):
    """Publish setup status telemetry to the CoreIoT MQTT Broker to prove network connectivity."""
    broker, port, client_id, username, password, topic = load_mqtt_config(cfg)
    print("[SETUP_ROI][MQTT] Connecting to CoreIoT broker at %s:%d ..." % (broker, port))
    s = socket.socket()
    s.settimeout(5.0)
    try:
        addr = socket.getaddrinfo(broker, port)[0][-1]
        s.connect(addr)

        variable_header = b"\x00\x04MQTT\x04\xc2" + bytes((0, 60))
        payload = _mqtt_string(client_id)
        if username:
            payload += _mqtt_string(username)
        if password:
            payload += _mqtt_string(password)
        body = variable_header + payload
        connect_packet = b"\x10" + _mqtt_remaining_length(len(body)) + body
        s.write(connect_packet)

        connack = s.read(4)
        if not connack or connack[0] != 0x20 or connack[3] != 0:
            raise OSError("MQTT CONNACK failed or refused")

        print("[SETUP_ROI][MQTT] Connected successfully!")

        payload_dict = {
            "status": "setup_roi_mode",
            "device_id": client_id,
            "ip": ip_address
        }
        payload_bytes = ujson.dumps(payload_dict).encode("utf-8")
        var_header = _mqtt_string(topic)
        body = var_header + payload_bytes
        publish_packet = b"\x30" + _mqtt_remaining_length(len(body)) + body
        s.write(publish_packet)
        print("[SETUP_ROI][MQTT] Status published:", payload_dict)
    except Exception as e:
        print("[SETUP_ROI][MQTT] Telemetry status failed to send:", e)
    finally:
        try:
            s.close()
        except:
            pass

def capture_phase(pl, ip):
    """Display preview and prompt for on-device capture triggers."""
    key_btn = None
    try:
        from ybUtils.YbKey import YbKey
        key_btn = YbKey()
        print("[SETUP_ROI] KEY button helper registered.")
    except Exception as e:
        print("[SETUP_ROI] KEY button is unavailable:", e)

    captured = False
    try:
        print("[SETUP_ROI] Align camera and press the physical KEY button to capture...")
        while True:
            try:
                os.exitpoint()
            except:
                pass

            if pl.osd_img is not None:
                pl.osd_img.clear()
                pl.osd_img.draw_string_advanced(10, 10, 30, "ALIGN CAMERA & PRESS KEY TO CAPTURE", color=(255, 0, 255, 0))
                pl.osd_img.draw_string_advanced(10, 45, 30, "IP WEB: http://" + ip + ":8081", color=(255, 0, 255, 0))
                pl.show_image()

            capture_triggered = False
            if key_btn is not None and key_btn.is_pressed() == 1:
                print("[SETUP_ROI] KEY button pressed!")
                capture_triggered = True

            if capture_triggered:
                img = None
                for attempt in range(20):
                    try:
                        img = pl.sensor.snapshot(chn=CAM_CHN_ID_1)
                        if img is not None:
                            break
                    except Exception as exc:
                        print("[SETUP_ROI] Snapshot attempt %d failed: %s" % (attempt+1, exc))
                    time.sleep_ms(100)

                if img is not None:
                    img.save("/sdcard/capture.jpg")
                    print("[SETUP_ROI] Reference image saved to /sdcard/capture.jpg")
                    print("[SETUP_ROI] Capture success! Please configure ROI at: http://%s:8081/" % ip)

                    if pl.osd_img is not None:
                        pl.osd_img.clear()
                        w_canvas = pl.osd_img.width()
                        h_canvas = pl.osd_img.height()
                        pl.osd_img.draw_rectangle(4, 4, w_canvas - 8, h_canvas - 8, (255, 0, 255, 0), thickness=8)
                        pl.osd_img.draw_string_advanced(10, 180, 35, "SUCCESSFULLY CAPTURED!", color=(255, 0, 255, 0))
                        pl.osd_img.draw_string_advanced(10, 230, 30, "URL: http://" + ip + ":8081/", color=(255, 0, 255, 0))
                        pl.show_image()

                    if k230_rgb is not None:
                        try:
                            k230_rgb.show_rgb((0, 255, 0))
                        except:
                            pass

                    time.sleep_ms(3000)
                    captured = True
                    break
                else:
                    print("[SETUP_ROI] Snapshot capture failed after multiple attempts!")
                    if pl.osd_img is not None:
                        pl.osd_img.clear()
                        pl.osd_img.draw_string_advanced(10, 200, 35, "CAPTURE FAILED! TRY AGAIN.", color=(255, 255, 0, 0))
                        pl.show_image()
                    time.sleep_ms(1500)

            time.sleep_ms(10)

        if not captured:
            raise RuntimeError("Failed to capture reference image.")

    finally:
        print("[SETUP_ROI] Cleaning up camera/display pipeline...")
        if pl:
            try:
                pl.destroy()
            except Exception as exc:
                print("[SETUP_ROI] PipeLine destroy error:", exc)

        if k230_rgb is not None:
            try:
                k230_rgb.show_rgb((0, 0, 0))
            except Exception as exc:
                print("[SETUP_ROI] RGB LED cleanup error:", exc)

def start_web_server(ip):
    """Launch the HTTP Web Server on port 8081. Breaks and returns True to request a reboot."""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 8081))
    s.listen(5)
    s.settimeout(1.0)

    print("[SETUP_ROI][WEB] HTTP Server listening at http://%s:8081/" % ip)

    should_reboot = False
    while not should_reboot:
        try:
            try:
                os.exitpoint()
            except:
                pass
            try:
                res = s.accept()
            except OSError:
                continue

            client_sock = res[0]
            client_addr = res[1]
            print("[SETUP_ROI][WEB] Connection accepted from:", client_addr)
            client_sock.setblocking(True)

            try:
                req_data = bytearray()
                while b"\r\n\r\n" not in req_data:
                    chunk = client_sock.recv(1024)
                    if not chunk:
                        break
                    req_data.extend(chunk)
                    if len(req_data) > 8192:
                        break

                if not req_data:
                    client_sock.close()
                    continue

                headers_part, _, body_part = req_data.partition(b"\r\n\r\n")
                header_lines = headers_part.split(b"\r\n")
                req_line = header_lines[0].decode("utf-8")
                parts = req_line.split()
                if len(parts) < 2:
                    client_sock.close()
                    continue
                method, path = parts[0], parts[1]

                content_length = 0
                for line in header_lines[1:]:
                    if line.lower().startswith(b"content-length:"):
                        try:
                            content_length = int(line.split(b":")[1].strip())
                        except:
                            pass
                        break

                body = bytearray(body_part)
                while len(body) < content_length:
                    chunk = client_sock.recv(min(1024, content_length - len(body)))
                    if not chunk:
                        break
                    body.extend(chunk)

                if method == "GET" and (path == "/" or path == "/index.html"):
                    html_bytes = HTML_CONTENT.encode("utf-8")
                    client_sock.sendall(b"HTTP/1.0 200 OK\r\n"
                                        b"Content-Type: text/html; charset=utf-8\r\n"
                                        b"Content-Length: " + str(len(html_bytes)).encode() + b"\r\n"
                                        b"Connection: close\r\n\r\n")
                    offset = 0
                    while offset < len(html_bytes):
                        client_sock.sendall(html_bytes[offset : offset + 1024])
                        offset += 1024

                elif method == "GET" and path == "/capture.jpg":
                    try:
                        with open("/sdcard/capture.jpg", "rb") as img_file:
                            img_size = 0
                            try:
                                img_size = os.stat("/sdcard/capture.jpg")[6]
                            except:
                                pass

                            client_sock.sendall(b"HTTP/1.0 200 OK\r\n"
                                                b"Content-Type: image/jpeg\r\n"
                                                b"Content-Length: " + str(img_size).encode() + b"\r\n"
                                                b"Connection: close\r\n\r\n")
                            while True:
                                chunk = img_file.read(1024)
                                if not chunk:
                                    break
                                client_sock.sendall(chunk)
                    except Exception as e:
                        print("[SETUP_ROI][WEB] Image file not found:", e)
                        client_sock.sendall(b"HTTP/1.0 404 Not Found\r\n\r\n")

                elif method == "GET" and path == "/config":
                    try:
                        with open("/sdcard/config.json", "r") as f:
                            config_bytes = f.read().encode("utf-8")
                        client_sock.sendall(b"HTTP/1.0 200 OK\r\n"
                                            b"Content-Type: application/json; charset=utf-8\r\n"
                                            b"Content-Length: " + str(len(config_bytes)).encode() + b"\r\n"
                                            b"Connection: close\r\n\r\n")
                        client_sock.sendall(config_bytes)
                    except:
                        empty_config = b'{"version":1,"camera_id":"k230-01","reference_resolution":[320,320],"regions":[],"exclusion_regions":[]}'
                        client_sock.sendall(b"HTTP/1.0 200 OK\r\n"
                                            b"Content-Type: application/json; charset=utf-8\r\n"
                                            b"Content-Length: " + str(len(empty_config)).encode() + b"\r\n"
                                            b"Connection: close\r\n\r\n")
                        client_sock.sendall(empty_config)

                elif method == "POST" and path == "/save":
                    try:
                        incoming_config = ujson.loads(body.decode("utf-8"))
                        existing_config = {}
                        try:
                            with open("/sdcard/config.json", "r") as f:
                                existing_config = ujson.load(f)
                        except:
                            print("[SETUP_ROI][WEB] No existing config found.")

                        existing_config["version"] = incoming_config.get("version", 1)
                        existing_config["camera_id"] = incoming_config.get("camera_id", existing_config.get("camera_id", "k230-01"))
                        existing_config["reference_resolution"] = incoming_config.get("reference_resolution", [320, 320])
                        existing_config["regions"] = incoming_config.get("regions", [])
                        existing_config["exclusion_regions"] = incoming_config.get("exclusion_regions", [])

                        with open("/sdcard/config.json", "w") as f:
                            ujson.dump(existing_config, f)

                        print("[SETUP_ROI][WEB] Configuration saved & merged successfully.")
                        resp = b'{"status":"success"}'
                        client_sock.sendall(b"HTTP/1.0 200 OK\r\n"
                                            b"Content-Type: application/json; charset=utf-8\r\n"
                                            b"Content-Length: " + str(len(resp)).encode() + b"\r\n"
                                            b"Connection: close\r\n\r\n")
                        client_sock.sendall(resp)
                        should_reboot = True
                    except Exception as exc:
                        print("[SETUP_ROI][WEB] JSON parse or save error:", exc)
                        resp = b'{"status":"error","message":"' + str(exc).encode() + b'"}'
                        client_sock.sendall(b"HTTP/1.0 500 Internal Server Error\r\n"
                                            b"Content-Type: application/json; charset=utf-8\r\n"
                                            b"Content-Length: " + str(len(resp)).encode() + b"\r\n"
                                            b"Connection: close\r\n\r\n")
                        client_sock.sendall(resp)
                else:
                    client_sock.sendall(b"HTTP/1.0 404 Not Found\r\n"
                                        b"Content-Length: 0\r\n"
                                        b"Connection: close\r\n\r\n")
            except Exception as e:
                print("[SETUP_ROI][WEB] Connection socket error:", e)
            finally:
                try:
                    client_sock.close()
                except:
                    pass
        except KeyboardInterrupt:
            print("[SETUP_ROI][WEB] Stopping web server via user request...")
            break
        except Exception as e:
            print("[SETUP_ROI][WEB] Server loop error:", e)

    try:
        s.close()
    except:
        pass
    return should_reboot

def setup_roi_main(pl):
    """Run snapshot capture and Web UI server, then trigger auto-reboot."""
    try:
        print("[SETUP_ROI] Starting Setup ROI utility...")
        ssid, password = load_wifi_credentials()

        show_status_on_screen(
            pl,
            "CONNECTING WI-FI...",
            ["SSID: %s" % ssid, "Waiting for local network IP address..."],
            color=(255, 255, 0, 255) # Yellow
        )

        ip = connect_wifi(ssid, password, timeout=15)
        if not ip:
            print("[SETUP_ROI] Warning: Networking is down. Proceeding offline...")
            ip = "127.0.0.1"
            show_status_on_screen(
                pl,
                "NETWORK OFFLINE",
                ["Failed to connect to SSID: %s" % ssid, "Running offline mode on localhost.", "Wait 3 seconds..."],
                color=(255, 255, 0, 0) # Red
            )
            time.sleep(3)
        else:
            show_status_on_screen(
                pl,
                "WI-FI CONNECTED",
                ["SSID: %s" % ssid, "IP Address: %s" % ip, "Publishing status to MQTT..."],
                color=(255, 0, 255, 0) # Green
            )
            try:
                temp_cfg = {}
                try:
                    with open("/sdcard/config.json", "r") as f:
                        temp_cfg = ujson.load(f)
                except:
                    pass
                publish_setup_status(ip, temp_cfg)
            except Exception as e:
                print("[SETUP_ROI] MQTT status publish failed:", e)
            time.sleep(1)

        # 3. Capture reference snapshot (on-device button triggers)
        capture_phase(pl, ip)

        # 4. Host Web Server for user drawing configuration
        reboot_triggered = start_web_server(ip)
        if reboot_triggered:
            print("[SETUP_ROI] Setup completed! Rebooting in 2 seconds to enter Production Mode...")
            time.sleep(2)
            try:
                import machine
                machine.reset()
            except Exception as e:
                print("[SETUP_ROI] machine.reset() failed, please manual reboot:", e)
    except KeyboardInterrupt:
        print("[SETUP_ROI] Interrupted by user.")
    except Exception as e:
        print("[SETUP_ROI] Fatal error:", e)
        sys.print_exception(e)
    finally:
        print("[SETUP_ROI] Finished.")

def production_main(cfg, pl):
    """Run warning detection camera loop."""
    print("[MAIN] Starting production warning camera loop...")

    show_status_on_screen(
        pl,
        "PRODUCTION MODE",
        ["1. Configuration loaded successfully", "2. Connecting to Wi-Fi network (timeout=2s)..."],
        color=(255, 0, 255, 255) # Cyan
    )

    ob_det = None
    mqtt_publisher = None
    shaking_filter = None
    light_filter = None
    overvehicles_filter = None

    roi_polygons = [region["polygon"] for region in cfg["regions"]]
    exclusion_polygons = []
    for region in cfg.get("exclusion_regions", []):
        polygon = region.get("polygon", []) if isinstance(region, dict) else region
        if len(polygon) >= 3:
            exclusion_polygons.append(polygon)

    # Initialize noise filters
    shaking_filter = ShakingFilter()
    light_filter = LightFilter()
    overvehicles_filter = OverVehiclesFilter()

    shaking_filter.initialize(cfg)
    light_filter.initialize(cfg)
    overvehicles_filter.initialize(cfg)

    # 2. Wi-Fi setup
    wifi_ssid, wifi_password = load_wifi_credentials()
    ip = connect_wifi(wifi_ssid, wifi_password, timeout=4)

    show_status_on_screen(
        pl,
        "LOADING AI MODEL",
        [
            "SSID: %s" % wifi_ssid,
            "IP Address: %s" % (ip if ip else "deferred (offline)"),
            "Loading day/night models...",
            "Please wait, starting hardware accelerator..."
        ],
        color=(255, 0, 255, 255) # Cyan
    )

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

    display_size = pl.display_size if pl is not None else [640, 480]

    # 4. Pipeline creation check
    if pl is None:
        try:
            display_mode = "lcd"
            display_size = [640, 480]
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

    # Determine initial Day/Night mode based on brightness
    initial_mode = "day"
    print("[BOOT] Determining initial day/night mode...")
    for _ in range(10):
        img = pl.get_frame()
        if img is not None:
            try:
                img_np = img
                brightness = float(np.mean(img_np))
                print("[BOOT] Initial image brightness: %.2f" % brightness)
                if brightness < 80.0:
                    initial_mode = "night"
                else:
                    initial_mode = "day"
                break
            except Exception as e:
                print("[BOOT] Error calculating initial brightness: %s" % e)
                initial_mode = "day"
                break
        time.sleep_ms(100)

    current_mode = initial_mode
    model_conf = load_model_config(current_mode)

    ob_det = ObjectDetectionApp(
        kmodel_path=model_conf["kmodel_path"],
        labels=model_conf["labels"],
        model_input_size=[320, 320],
        max_boxes_num=MODEL_MAX_BOXES,
        confidence_threshold=model_conf["confidence_threshold"],
        nms_threshold=model_conf["nms_threshold"],
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
    brightness = 100.0
    mode_switch_counter = 0
    REQUIRED_SWITCH_FRAMES = 15  # Number of consecutive frames needed to switch

    # Publish initial safe status telemetry
    mqtt_publisher.queue(build_telemetry_payload(False, mqtt_client_id, 0, []))
    mqtt_publisher.service(boot_ms)

    if k230_rgb:
        try:
            k230_rgb.show_rgb((0, 255, 0)) # Green (Safe) initially
        except:
            pass

    print("[INFO] Inference loop started successfully.")

    remote_mode_trigger = None
    current_real_time = None
    ob_det.real_time_str = None

    try:
        while True:
            try:
                os.exitpoint()
            except:
                pass
            with ScopedTiming("total", 0):
                img = pl.get_frame()
                if img is None:
                    continue

                img_np = img

                # Check for day/night mode updates from MQTT (attribute sync)
                if mqtt_publisher.connected and mqtt_publisher.client is not None:
                    try:
                        msg = mqtt_publisher.client.check_msg()
                        if msg:
                            topic, payload = msg
                            print("[MQTT_RECV] Received on %s: %s" % (topic, payload))
                            new_mode, r_time = update_mode_from_mqtt(payload.decode("utf-8"))

                            # Store and display time string if available
                            if r_time:
                                current_real_time = r_time
                                ob_det.real_time_str = r_time

                            # Publish acknowledgment signal back to CoreIoT telemetry topic
                            try:
                                ack_payload = ujson.dumps({
                                    "status": "time_synced",
                                    "synced_time": r_time if r_time else "N/A",
                                    "synced_mode": new_mode if new_mode else current_mode
                                })
                                mqtt_publisher.client.publish("v1/devices/me/telemetry", ack_payload)
                                print("[MQTT_SEND] Sent ack back to CoreIoT:", ack_payload)
                            except Exception as ack_err:
                                print("[MQTT_SEND] Failed to send ack:", ack_err)

                            if new_mode and new_mode != current_mode:
                                print("[MQTT_RECV] Remote override day/night mode ->", new_mode)
                                remote_mode_trigger = new_mode
                    except Exception as msg_err:
                        print("[MQTT_RECV] Error checking messages:", msg_err)

                # Dynamic day/night mode switching check with temporal debouncing
                try:
                    brightness = float(np.mean(img_np))

                    target_mode = current_mode
                    if remote_mode_trigger is not None:
                        target_mode = remote_mode_trigger
                        remote_mode_trigger = None
                        # Force transition immediately
                        mode_switch_counter = REQUIRED_SWITCH_FRAMES
                    else:
                        if current_mode == "day" and brightness < 70.0:
                            target_mode = "night"
                        elif current_mode == "night" and brightness > 90.0:
                            target_mode = "day"

                    if target_mode != current_mode:
                        mode_switch_counter += 1
                        if mode_switch_counter >= REQUIRED_SWITCH_FRAMES:
                            next_mode = target_mode
                            print("[MODEL] Switching mode: %s -> %s (brightness=%.2f, stable for %d frames)" %
                                  (current_mode, next_mode, brightness, REQUIRED_SWITCH_FRAMES))
                            show_status_on_screen(
                                pl,
                                "SWITCHING MODEL...",
                                [
                                    "Brightness: %.2f" % brightness,
                                    "Switching to %s mode model..." % next_mode.upper(),
                                    "Please wait..."
                                ],
                                color=(255, 255, 165, 0)
                            )

                            try:
                                ob_det.deinit()
                            except Exception as deinit_err:
                                print("[MODEL] Error deinitializing old model:", deinit_err)

                            # Explicitly collect garbage to free memory
                            gc.collect()

                            current_mode = next_mode
                            model_conf = load_model_config(current_mode)

                            ob_det = ObjectDetectionApp(
                                kmodel_path=model_conf["kmodel_path"],
                                labels=model_conf["labels"],
                                model_input_size=[320, 320],
                                max_boxes_num=MODEL_MAX_BOXES,
                                confidence_threshold=model_conf["confidence_threshold"],
                                nms_threshold=model_conf["nms_threshold"],
                                rgb888p_size=MODEL_INPUT_SIZE,
                                display_size=display_size,
                                debug_mode=0,
                            )
                            ob_det.config_preprocess()
                            ob_det.roi_polygons = roi_polygons
                            ob_det.exclusion_polygons = exclusion_polygons

                            # Collect garbage again after model loading
                            gc.collect()

                            # Preserve real-time string on the new ObjectDetectionApp instance
                            ob_det.real_time_str = current_real_time

                            pl.osd_img.clear()
                            pl.show_image()
                            mode_switch_counter = 0
                    else:
                        mode_switch_counter = 0
                except Exception as luma_err:
                    print("[LUMA] Error in day/night check:", luma_err)

                # Chaining the filters
                res = None
                try:
                    # 1. Model Inference on raw camera frame for maximum accuracy
                    res = ob_det.run(img_np)

                    # 2. ShakingFilter & LightFilter for environmental logging/tracking
                    shake_res = shaking_filter.process(img_np)
                    light_res = light_filter.process(img_np)

                    # 3. OverVehiclesFilter for density control
                    overvehicles_bboxes = []
                    if res and len(res) >= 3 and res[0]:
                        boxes = res[0]
                        classes = res[1]
                        for i in range(len(boxes)):
                            class_id = classes[i]
                            label = ob_det.labels[class_id] if class_id < len(ob_det.labels) else "unknown"
                            overvehicles_bboxes.append([boxes[i][0], boxes[i][1], boxes[i][2], boxes[i][3], label])

                    overvehicles_res = overvehicles_filter.process(img_np, overvehicles_bboxes)
                except Exception as filter_err:
                    print("[FILTER] Error during filter pipeline execution:", filter_err)
                    res = ob_det.run(img_np)

                # Filter boxes: keep only valid vehicles inside ROI
                res_raw = res
                filtered_boxes = []
                filtered_classes = []
                filtered_confidences = []

                if res_raw and len(res_raw) >= 3 and res_raw[0]:
                    boxes = res_raw[0]
                    classes = res_raw[1]
                    confidences = res_raw[2]

                    for i in range(len(boxes)):
                        x, y, w, h = boxes[i]
                        class_id = classes[i]
                        conf = confidences[i]

                        label = ob_det.labels[class_id] if class_id < len(ob_det.labels) else "unknown"
                        is_vehicle = label.lower() in {"car", "truck", "bus", "motorcycle", "motorbike", "vehicle"} and w >= 25 and h >= 25 and conf >= VEHICLE_CONFIDENCE_THRESHOLD

                        px = x + w / 2.0
                        py = y + h

                        norm_x = px / display_size[0]
                        norm_y = py / display_size[1]

                        if is_vehicle and is_point_in_roi(
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

                # Debounce and filter class
                if res:
                    latest_detections = collect_vehicle_detections(
                        res[0], res[1], res[2], ob_det.labels, VEHICLE_CLASSES
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
                        occupied, mqtt_client_id, uptime_ms, presence.get("valid_detections", [])
                    )
                    mqtt_publisher.queue(payload)
                    previous_occupied = occupied
                    print("[INFO] Vehicle state changed. Lane occupied:", occupied)

                # Keepalive and queue publisher servicing
                mqtt_publisher.service(now_ms)

                # Draw to OSD using raw detections so non-vehicles/outside objects are shown in red
                ob_det.draw_result(pl, res_raw, occupied=occupied, ip=ip, mqtt_connected=mqtt_publisher.connected, mode=current_mode, brightness=brightness)

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
        if shaking_filter:
            try:
                shaking_filter.release()
            except:
                pass
        if light_filter:
            try:
                light_filter.release()
            except:
                pass
        if overvehicles_filter:
            try:
                overvehicles_filter.release()
            except:
                pass
        if k230_rgb:
            try:
                k230_rgb.show_rgb((0, 0, 0)) # Turn off LED
            except:
                pass
        print("[INFO] Standalone warning loop stopped.")

if __name__ == "__main__":
    # Startup boot sequence
    enter_setup = False
    key_btn = None
    try:
        from ybUtils.YbKey import YbKey
        key_btn = YbKey()
    except Exception as e:
        print("[BOOT] KEY button helper is unavailable:", e)

    # Indicate boot/polling phase with Blue light on onboard RGB LED
    if k230_rgb:
        try:
            k230_rgb.show_rgb((0, 0, 255)) # Blue
        except:
            pass

    # Initialize high-quality camera sensor (1280x960 resolution downscaled by ISP)
    my_sensor = None
    try:
        from media.sensor import Sensor
        my_sensor = Sensor(width=1280, height=960, fps=30)
        print("[BOOT] High-resolution camera sensor initialized.")
    except Exception as e:
        print("[BOOT] Failed to initialize high-resolution sensor, using default:", e)

    # Initialize PipeLine early for boot visualization (LCD mode with HDMI fallback)
    pl = None
    display_size = [640, 480]
    display_mode = "lcd"
    try:
        pl = PipeLine(rgb888p_size=MODEL_INPUT_SIZE, display_size=display_size, display_mode=display_mode)
        pl.create(sensor=my_sensor)
        print("[BOOT] PipeLine initialized in LCD mode.")
    except Exception as e:
        print("[BOOT] LCD init failed, trying HDMI fallback:", e)
        if pl:
            try:
                pl.destroy()
            except:
                pass
        try:
            display_size = [1920, 1080]
            display_mode = "hdmi"
            pl = PipeLine(rgb888p_size=MODEL_INPUT_SIZE, display_size=display_size, display_mode=display_mode)
            pl.create(sensor=my_sensor)
            print("[BOOT] PipeLine initialized in HDMI mode.")
        except Exception as e2:
            print("[BOOT] Both display modes failed to initialize:", e2)
            pl = None

    # Wi-Fi selection screen (runs before ROI key-poll, uses OSD + KEY button)
    print("[BOOT] Showing Wi-Fi selection screen...")
    try:
        # Scan surrounding Wi-Fi networks first
        try:
            scan_wifi_networks(pl)
        except Exception as scan_err:
            print("[BOOT] Wi-Fi scanning failed:", scan_err)

        wifi_sel_ssid, wifi_sel_password = wifi_selection_screen(pl, key_btn)
        if wifi_sel_ssid:
            show_status_on_screen(
                pl,
                "WI-FI PRESET SAVED",
                ["SSID: " + wifi_sel_ssid, "Credentials saved to sys_config.json", "Continuing boot..."],
                color=(255, 0, 200, 80)
            )
            time.sleep_ms(1200)
    except Exception as e:
        print("[BOOT] Wi-Fi selection screen error:", e)

    print("[BOOT] Polling physical KEY button. Press KEY now to enter ROI Setup...")
    enter_setup = False

    try:
        show_status_on_screen(
            pl,
            "SYSTEM BOOTING...",
            [
                "Checking hardware & config...",
                "Press KEY now to enter ROI Setup."
            ],
            color=(255, 0, 100, 255) # Blue
        )

        # Robust 5-second countdown loop (100 * 50ms) independent of clock changes
        for _ in range(100):
            try:
                os.exitpoint()
            except:
                pass
            if key_btn is not None and key_btn.is_pressed():
                enter_setup = True
                print("[BOOT] KEY button press detected! Entering Setup mode.")
                show_status_on_screen(
                    pl,
                    "ROI SETUP SELECTED",
                    [
                        "Entering ROI Drawing Setup Mode...",
                        "Release the KEY button now."
                    ],
                    color=(255, 255, 0, 255) # Purple
                )
                while key_btn.is_pressed():
                    time.sleep_ms(50)
                break
            time.sleep_ms(50)
    except Exception as e:
        print("[BOOT] Key polling error:", e)

    config_path = "/sdcard/config.json"
    cfg = None

    # Only try to load config if we are not entering setup mode
    if not enter_setup:
        try:
            cfg = load_and_merge_config(config_path)
            print("[BOOT] Valid ROI configuration loaded successfully.")
        except Exception as e:
            print("[BOOT] ROI config missing or invalid: %s." % e)
            print("[BOOT] Standing by. Waiting for KEY button press to enter Setup mode...")

            show_status_on_screen(
                pl,
                "ROI CONFIG MISSING",
                [
                    "No valid ROI config found.",
                    "Press KEY button to enter Setup Mode."
                ],
                color=(255, 255, 0, 0) # Red
            )

            # Wait indefinitely until the user presses the button
            while True:
                try:
                    os.exitpoint()
                except:
                    pass
                if key_btn is not None and key_btn.is_pressed():
                    enter_setup = True
                    print("[BOOT] KEY button press detected! Transitioning to Setup mode.")
                    show_status_on_screen(
                        pl,
                        "ROI SETUP SELECTED",
                        [
                            "Entering ROI Drawing Setup Mode...",
                            "Release the KEY button now."
                        ],
                        color=(255, 255, 0, 255) # Purple
                    )
                    while key_btn.is_pressed():
                        time.sleep_ms(50)
                    break
                time.sleep_ms(50)

    # Turn off LED after boot-checking before running either mode
    if k230_rgb:
        try:
            k230_rgb.show_rgb((0, 0, 0))
        except:
            pass

    if enter_setup:
        setup_roi_main(pl)
    else:
        production_main(cfg, pl)
