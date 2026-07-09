from yolo_uno import *
from pins import *

import network
import time
import ujson

try:
    from umqtt.simple import MQTTClient
except ImportError:
    print("Missing umqtt.simple library")


# =========================
# 1. WiFi configuration
# =========================

# NOTE: secrets were removed from this vendored ACLAB ELMS baseline (ADR-0016
# backlog #6). The Wi-Fi password and CoreIoT device token now load from a
# co-located config.json at startup (see _load_secrets below) and fall back to
# the empty placeholders here when it is absent, so this reference script stays
# runnable without embedding a live credential. The previously hardcoded values
# are already public and MUST be rotated by ACLAB ELMS — see
# firmware/k230-detector/README.md ("Local modifications — secrets").
WIFI_SSID = "ACLAB"
WIFI_PASSWORD = ""          # placeholder — config.json: {"wifi": {"password": ...}}


# =========================
# 2. CoreIoT MQTT configuration
# =========================

MQTT_SERVER = "app.coreiot.io"
MQTT_PORT = 1883

# Token của DEVICE_IOT_02, tức ESP32/YoloUNO — nạp từ config.json (placeholder rỗng).
ACCESS_TOKEN = ""           # placeholder — config.json: {"server": {"access_token": ...}}

CLIENT_ID = "yolouno_device_iot_02"


# =========================
# 2b. Load secrets from config.json
# =========================
# Secrets exception to the "do not modify the vendored baseline" rule (ADR-0016
# backlog #6): read the Wi-Fi password and CoreIoT token from a co-located
# config.json, matching the key tolerance of the K230 app's load_wifi_credentials
# / load_mqtt_config. If config.json is missing or invalid the placeholders above
# are kept and the script still runs (Wi-Fi/MQTT just won't authenticate).


def _load_secrets():
    global WIFI_SSID, WIFI_PASSWORD, ACCESS_TOKEN
    try:
        with open("config.json", "r") as config_file:
            data = ujson.load(config_file)
    except Exception as error:
        print("config.json missing/invalid, using placeholders:", error)
        return
    if not isinstance(data, dict):
        return
    wifi = data.get("wifi", {}) or data.get("WLAN", {})
    if isinstance(wifi, dict):
        WIFI_SSID = wifi.get("ssid", wifi.get("SSID", WIFI_SSID)) or WIFI_SSID
        WIFI_PASSWORD = wifi.get("password", wifi.get("PASSWORD", WIFI_PASSWORD))
    server = data.get("server", {}) or data.get("mqtt", {}) or data
    if isinstance(server, dict):
        ACCESS_TOKEN = server.get(
            "access_token",
            server.get("mqtt_access_token", server.get("username", ACCESS_TOKEN)),
        )


_load_secrets()


# =========================
# 3. MQTT RPC topics
# =========================

RPC_REQUEST_TOPIC = b"v1/devices/me/rpc/request/+"
RPC_RESPONSE_PREFIX = "v1/devices/me/rpc/response/"


# =========================
# 4. LED D13 configuration
# =========================

led_d13 = Pins(D13_PIN)
led_state = False


# =========================
# 5. WiFi connection
# =========================


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        while not wlan.isconnected():
            print(".")
            time.sleep(0.5)

    print("WiFi connected")
    print("IP:", wlan.ifconfig()[0])


# =========================
# 6. LED D13 control
# =========================


def set_led_d13(state):
    global led_state

    led_state = bool(state)

    if led_state:
        led_d13.write_digital(1)
        print("LED D13: ON")
    else:
        led_d13.write_digital(0)
        print("LED D13: OFF")


# =========================
# 7. Parse RPC params
# =========================


def parse_output_state(params):
    if params is True:
        return True

    if params is False:
        return False

    if params == 1:
        return True

    if params == 0:
        return False

    if params == "true" or params == "True" or params == "1":
        return True

    if params == "false" or params == "False" or params == "0":
        return False

    if isinstance(params, dict):
        if "state" in params:
            return parse_output_state(params["state"])

        if "value" in params:
            return parse_output_state(params["value"])

    return False


# =========================
# 8. Extract RPC request id
# =========================


def get_rpc_request_id(topic):
    topic_str = topic.decode()

    # Topic dạng:
    # v1/devices/me/rpc/request/12
    return topic_str.split("/")[-1]


# =========================
# 9. Send RPC response
# =========================


def send_rpc_response(client, request_id, success=True):
    response_topic = RPC_RESPONSE_PREFIX + request_id

    response_payload = {"success": success, "led_state": led_state}

    client.publish(response_topic, ujson.dumps(response_payload))
    print("RPC response sent:", response_payload)


# =========================
# 10. MQTT callback
# =========================


def on_mqtt_message(topic, msg):
    print("MQTT message received")
    print("Topic:", topic)
    print("Payload:", msg)

    request_id = get_rpc_request_id(topic)

    try:
        data = ujson.loads(msg)

        method = data.get("method", "")
        params = data.get("params", False)

        if method == "setOutput":
            state = parse_output_state(params)
            set_led_d13(state)
            send_rpc_response(mqtt_client, request_id, True)

        else:
            print("Unknown RPC method:", method)
            send_rpc_response(mqtt_client, request_id, False)

    except Exception as e:
        print("RPC handling error:", e)
        send_rpc_response(mqtt_client, request_id, False)


# =========================
# 11. MQTT connection
# =========================


def connect_mqtt():
    global mqtt_client

    print("Connecting to CoreIoT MQTT...")

    mqtt_client = MQTTClient(
        client_id=CLIENT_ID,
        server=MQTT_SERVER,
        port=MQTT_PORT,
        user=ACCESS_TOKEN,
        password="",
    )

    mqtt_client.set_callback(on_mqtt_message)
    mqtt_client.connect()

    print("MQTT connected")

    mqtt_client.subscribe(RPC_REQUEST_TOPIC)
    print("Subscribed:", RPC_REQUEST_TOPIC)

    return mqtt_client


# =========================
# 12. Main program
# =========================

print("YoloUNO CoreIoT RPC D13 LED test started")

connect_wifi()
mqtt_client = connect_mqtt()

# Tắt LED lúc khởi động
set_led_d13(False)

while True:
    try:
        mqtt_client.check_msg()
        time.sleep(0.05)

    except Exception as e:
        print("MQTT error:", e)
        print("Reconnecting...")

        try:
            mqtt_client.disconnect()
        except:
            pass

        time.sleep(2)
        connect_wifi()
        mqtt_client = connect_mqtt()
