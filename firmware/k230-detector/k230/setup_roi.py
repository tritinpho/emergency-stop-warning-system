"""Setup ROI configuration utility for Yahboom K230.

Coordinates Wi-Fi connection, CoreIoT status telemetry, on-device camera framing
and capture, and serves a premium Web UI to draw ROIs and exclusion zones.
"""

import network
import socket
import time
import os
import ujson
import gc
import sys
import image

# HTML page embedded as a standard string literal (UTF-8 encoded dynamically to prevent CPython compile issues)
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
                    showToast("Configuration saved to K230!", "success");
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

def load_wifi_credentials():
    """Load SSID and PASSWORD dynamically from custom or system configuration."""
    ssid = "ACLAB"
    password = ""  # placeholder — real password comes from config.json / sys_config.json; rotate (README #6)
    
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
                        print("[SETUP_ROI][WIFI] Loaded from config.json")
                        return s, p
    except Exception as e:
        print("[SETUP_ROI][WIFI] config.json load failed or missing:", e)
        
    # Try sys_config.json as secondary fallback
    try:
        with open("/sdcard/configs/sys_config.json", "r") as f:
            data = ujson.load(f)
            if isinstance(data, dict) and "WLAN" in data:
                wlan_sec = data["WLAN"]
                s = wlan_sec.get("SSID", "")
                p = wlan_sec.get("PASSWORD", "")
                if s:
                    print("[SETUP_ROI][WIFI] Loaded from sys_config.json")
                    return s, p
    except Exception as e:
        print("[SETUP_ROI][WIFI] sys_config.json load failed or missing:", e)
        
    print("[SETUP_ROI][WIFI] Using default credentials")
    return ssid, password

def connect_wifi(ssid, password):
    """Ensure K230 is connected to the specified Wi-Fi network."""
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    if sta.isconnected():
        ip = sta.ifconfig()[0]
        print("[SETUP_ROI][WIFI] Already connected. IP:", ip)
        return ip
        
    print("[SETUP_ROI][WIFI] Connecting to SSID: %s ..." % ssid)
    sta.connect(ssid, password)
    
    # 15 seconds timeout with IDE exitpoint checks
    start_time = time.time()
    while not sta.isconnected():
        if time.time() - start_time > 15:
            print("[SETUP_ROI][WIFI] Connection timeout!")
            break
        os.exitpoint()
        time.sleep_ms(200)
        
    if sta.isconnected():
        ip = sta.ifconfig()[0]
        print("[SETUP_ROI][WIFI] Connected! IP:", ip)
        return ip
    else:
        print("[SETUP_ROI][WIFI] Connection failed.")
        return None

def _mqtt_string(value):
    """Format string to conform with MQTT packet specifications."""
    data = value.encode("utf-8") if isinstance(value, str) else value
    length = len(data)
    if length > 65535:
        raise ValueError("MQTT string is too long")
    return bytes((length >> 8, length & 0xFF)) + data

def _mqtt_remaining_length(length):
    """Format length byte field for MQTT header packets."""
    encoded = bytearray()
    while True:
        digit = length % 128
        length //= 128
        if length:
            digit |= 0x80
        encoded.append(digit)
        if not length:
            return bytes(encoded)

def publish_coreiot_status(ip_address):
    """Publish setup status telemetry to the CoreIoT MQTT Broker to prove network connectivity."""
    # Defaults matches main.py
    broker = "app.coreiot.io"
    port = 1883
    client_id = "DEVICE_IOT_01"
    username = "device_iot_01"
    password = "123"
    topic = "v1/devices/me/telemetry"
    
    # Dynamically extract parameters from config if exists
    try:
        with open("/sdcard/config.json", "r") as f:
            cfg = ujson.load(f)
            if isinstance(cfg, dict):
                mqtt_cfg = cfg.get("server", {}) or cfg.get("mqtt", {}) or cfg
                if isinstance(mqtt_cfg, dict):
                    broker = mqtt_cfg.get("broker", mqtt_cfg.get("mqtt_broker", broker))
                    port = int(mqtt_cfg.get("port", mqtt_cfg.get("mqtt_port", port)))
                    client_id = mqtt_cfg.get("client_id", mqtt_cfg.get("mqtt_client_id", client_id))
                    username = mqtt_cfg.get("username", mqtt_cfg.get("mqtt_username", username))
                    password = mqtt_cfg.get("password", mqtt_cfg.get("mqtt_password", password))
                    topic = mqtt_cfg.get("telemetry_topic", mqtt_cfg.get("mqtt_topic", topic))
    except Exception as e:
        print("[SETUP_ROI][MQTT] Skipping custom config loading, using defaults:", e)

    print("[SETUP_ROI][MQTT] Connecting to CoreIoT broker at %s:%d ..." % (broker, port))
    s = socket.socket()
    s.settimeout(5.0)
    
    try:
        addr = socket.getaddrinfo(broker, port)[0][-1]
        s.connect(addr)
        
        # Construct MQTT CONNECT Packet
        variable_header = b"\x00\x04MQTT\x04\xc2" + bytes((0, 60)) # Protocol, username/password flag, keepalive 60s
        payload = _mqtt_string(client_id)
        if username:
            payload += _mqtt_string(username)
        if password:
            payload += _mqtt_string(password)
        body = variable_header + payload
        connect_packet = b"\x10" + _mqtt_remaining_length(len(body)) + body
        s.write(connect_packet)
        
        # Wait for CONNACK response (4 bytes)
        connack = s.read(4)
        if not connack or connack[0] != 0x20 or connack[3] != 0:
            raise OSError("MQTT CONNACK failed or refused")
            
        print("[SETUP_ROI][MQTT] Connected successfully!")
        
        # Publish telemetry status message
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

def capture_phase(ip):
    """Start camera pipeline, display preview and prompt for on-device capture triggers."""
    from libs.PipeLine import PipeLine
    from media.sensor import CAM_CHN_ID_1
    import media.sensor as sensor
    from media.display import Display
    from media.media import MediaManager
    
    # Physical key button initialization
    key_btn = None
    try:
        from ybUtils.YbKey import YbKey
        key_btn = YbKey()
        print("[SETUP_ROI] KEY button helper registered.")
    except Exception as e:
        print("[SETUP_ROI] KEY button is unavailable:", e)
        
    # RGB LED initialization
    k230_rgb = None
    try:
        from ybUtils.YbRGB import YbRGB
        k230_rgb = YbRGB()
    except Exception as e:
        print("[SETUP_ROI] RGB LED module is unavailable:", e)

    # Initialize PipeLine with LCD display (ST7701 640x480) and HDMI fallback
    pl = None
    try:
        pl = PipeLine(display_mode="lcd", display_size=[640, 480])
        pl.create()
        print("[SETUP_ROI] PipeLine started in LCD mode.")
    except Exception as e:
        print("[SETUP_ROI] ST7701 LCD Mode failed, trying HDMI fallback: %s" % e)
        if pl:
            try:
                pl.destroy()
            except:
                pass
        try:
            pl = PipeLine(display_mode="hdmi", display_size=[1920, 1080])
            pl.create()
            print("[SETUP_ROI] PipeLine started in HDMI mode.")
        except Exception as e2:
            print("[SETUP_ROI] Both display modes failed to initialize: %s" % e2)
            raise e2
            
    captured = False
    try:
        print("[SETUP_ROI] Align camera and press the physical KEY button to capture...")
        while True:
            os.exitpoint()
            
            # Draw UI Overlay on OSD layer (Display.LAYER_OSD3 via pl.show_image())
            if pl.osd_img is not None:
                pl.osd_img.clear()
                
                # Draw text prompts in vibrant green (ARGB: 255, 0, 255, 0)
                pl.osd_img.draw_string_advanced(10, 10, 30, "ALIGN CAMERA & PRESS KEY TO CAPTURE", color=(255, 0, 255, 0))
                pl.osd_img.draw_string_advanced(10, 45, 30, "IP WEB: http://" + ip + ":8081", color=(255, 0, 255, 0))
                pl.show_image()
                
            capture_triggered = False
            
            # Check physical KEY button press
            if key_btn is not None:
                if key_btn.is_pressed() == 1:
                    print("[SETUP_ROI] KEY button pressed!")
                    capture_triggered = True
                            
            if capture_triggered:
                # Capture frame on channel 1 (configured for RGB565)
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
                    # Save to SD card
                    img.save("/sdcard/capture.jpg")
                    print("[SETUP_ROI] Reference image saved to /sdcard/capture.jpg")
                    print("[SETUP_ROI] Capture success! Please configure ROI at: http://%s:8081/" % ip)
                    
                    # Draw visual success confirmation and print the URL on display OSD
                    if pl.osd_img is not None:
                        pl.osd_img.clear()
                        pl.osd_img.draw_rectangle(4, 4, pl.display_size[0] - 8, pl.display_size[1] - 8, (255, 0, 255, 0), thickness=8)
                        pl.osd_img.draw_string_advanced(10, 180, 35, "SUCCESSFULLY CAPTURED!", color=(255, 0, 255, 0))
                        pl.osd_img.draw_string_advanced(10, 230, 30, "URL: http://" + ip + ":8081/", color=(255, 0, 255, 0))
                        pl.show_image()
                        
                    # Light LED to green for success status
                    if k230_rgb is not None:
                        try:
                            k230_rgb.show_rgb((0, 255, 0))
                        except:
                            pass
                            
                    time.sleep_ms(3000) # Give user time to see the screen message
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
        # Immediately release camera, media and display layer memory
        print("[SETUP_ROI] Cleaning up camera/display pipeline...")
        if pl:
            try:
                pl.destroy()
            except Exception as exc:
                print("[SETUP_ROI] PipeLine destroy error:", exc)
                
        # Always turn off the onboard indicator LED on exit
        if k230_rgb is not None:
            try:
                k230_rgb.show_rgb((0, 0, 0))
                print("[SETUP_ROI] Onboard RGB LED turned off.")
            except Exception as exc:
                print("[SETUP_ROI] RGB LED cleanup error:", exc)

def start_web_server(ip):
    """Launch the HTTP Web Server on port 8081."""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 8081))
    s.listen(5)
    
    # 1.0 second timeout keeps server accept interruptible by Ctrl+C or IDE
    s.settimeout(1.0)
    
    print("[SETUP_ROI][WEB] HTTP Server listening at http://%s:8081/" % ip)
    
    while True:
        try:
            os.exitpoint()
            try:
                res = s.accept()
            except OSError:
                continue # Timeout happened, loop back to check os.exitpoint
                
            client_sock = res[0]
            client_addr = res[1]
            print("[SETUP_ROI][WEB] Connection accepted from:", client_addr)
            
            # Disable non-blocking inherited timeouts to prevent transmission drops
            client_sock.setblocking(True)
            
            try:
                # Read request header up to 8KB
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
                
                # Fetch content length if present
                content_length = 0
                for line in header_lines[1:]:
                    if line.lower().startswith(b"content-length:"):
                        try:
                            content_length = int(line.split(b":")[1].strip())
                        except:
                            pass
                        break
                        
                # Ensure complete request body is read
                body = bytearray(body_part)
                while len(body) < content_length:
                    chunk = client_sock.recv(min(1024, content_length - len(body)))
                    if not chunk:
                        break
                    body.extend(chunk)
                    
                # Endpoint routing
                if method == "GET" and (path == "/" or path == "/index.html"):
                    html_bytes = HTML_CONTENT.encode("utf-8")
                    client_sock.sendall(b"HTTP/1.0 200 OK\r\n"
                                        b"Content-Type: text/html; charset=utf-8\r\n"
                                        b"Content-Length: " + str(len(html_bytes)).encode() + b"\r\n"
                                        b"Connection: close\r\n\r\n")
                    # Send page in 1KB segments to avoid overflow
                    offset = 0
                    while offset < len(html_bytes):
                        client_sock.sendall(html_bytes[offset : offset + 1024])
                        offset += 1024
                        
                elif method == "GET" and path == "/capture.jpg":
                    try:
                        with open("/sdcard/capture.jpg", "rb") as img_file:
                            # Get image size
                            img_size = 0
                            try:
                                img_size = os.stat("/sdcard/capture.jpg")[6]
                            except:
                                pass
                                
                            client_sock.sendall(b"HTTP/1.0 200 OK\r\n"
                                                b"Content-Type: image/jpeg\r\n"
                                                b"Content-Length: " + str(img_size).encode() + b"\r\n"
                                                b"Connection: close\r\n\r\n")
                            # Stream in 1KB chunks
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
                        # Fallback empty config structure
                        empty_config = b'{"version":1,"camera_id":"k230-01","reference_resolution":[320,320],"regions":[],"exclusion_regions":[]}'
                        client_sock.sendall(b"HTTP/1.0 200 OK\r\n"
                                            b"Content-Type: application/json; charset=utf-8\r\n"
                                            b"Content-Length: " + str(len(empty_config)).encode() + b"\r\n"
                                            b"Connection: close\r\n\r\n")
                        client_sock.sendall(empty_config)
                        
                elif method == "POST" and path == "/save":
                    try:
                        incoming_config = ujson.loads(body.decode("utf-8"))
                        
                        # Preserve existing keys (Wi-Fi settings, MQTT settings, etc.)
                        existing_config = {}
                        try:
                            with open("/sdcard/config.json", "r") as f:
                                existing_config = ujson.load(f)
                        except:
                            print("[SETUP_ROI][WEB] No existing config found, generating new.")
                            
                        # Overwrite specific ROI configuration keys
                        existing_config["version"] = incoming_config.get("version", 1)
                        existing_config["camera_id"] = incoming_config.get("camera_id", existing_config.get("camera_id", "k230-01"))
                        existing_config["reference_resolution"] = incoming_config.get("reference_resolution", [320, 320])
                        existing_config["regions"] = incoming_config.get("regions", [])
                        existing_config["exclusion_regions"] = incoming_config.get("exclusion_regions", [])
                        
                        # Write merged back to config.json
                        with open("/sdcard/config.json", "w") as f:
                            ujson.dump(existing_config, f)
                            
                        print("[SETUP_ROI][WEB] Configuration saved & merged successfully.")
                        resp = b'{"status":"success"}'
                        client_sock.sendall(b"HTTP/1.0 200 OK\r\n"
                                            b"Content-Type: application/json; charset=utf-8\r\n"
                                            b"Content-Length: " + str(len(resp)).encode() + b"\r\n"
                                            b"Connection: close\r\n\r\n")
                        client_sock.sendall(resp)
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

def main():
    try:
        print("[SETUP_ROI] Starting Setup ROI utility...")
        
        # 1. Connect to Wi-Fi
        ssid, password = load_wifi_credentials()
        ip = connect_wifi(ssid, password)
        if not ip:
            print("[SETUP_ROI] Warning: Networking is down. Proceeding offline...")
            ip = "127.0.0.1"
        else:
            # 2. Publish status to CoreIoT MQTT broker
            try:
                publish_coreiot_status(ip)
            except Exception as e:
                print("[SETUP_ROI] MQTT status publish failed:", e)
        
        # 3. Capture reference snapshot (on-device button triggers)
        capture_phase(ip)
        
        # 4. Host Web Server for user drawing configuration
        start_web_server(ip)
        
    except KeyboardInterrupt:
        print("[SETUP_ROI] Interrupted by user.")
    except Exception as e:
        print("[SETUP_ROI] Fatal error:", e)
        sys.print_exception(e)
    finally:
        print("[SETUP_ROI] Finished.")

if __name__ == "__main__":
    main()
