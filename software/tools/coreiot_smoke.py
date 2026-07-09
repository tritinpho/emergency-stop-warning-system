#!/usr/bin/env python3
"""CoreIOT connectivity smoke test -- the IF-6 uplink's first real transport probe.

The oversight plane (doc 08 §4: IF-6 heartbeat / IF-7 audit events over MQTT-TLS,
store-and-forward) is NON-critical by design (ADR-0002): the safety loop never
waits on it. In the harness the uplink is a fake (harness/store.py); the project's
chosen TMC platform is **CoreIOT** (coreiot.io, ThingsBoard-based). This script is
the smallest honest proof that the real transport binding can work:

  1. reachability -- DNS + TCP to the broker (no credentials needed);
  2. with a device access token: MQTT connect, publish ONE REAL IF-6 heartbeat
     (built by the real esw/telemetry.py emitter, cfg_ver = the real §7a config
     fingerprint), and subscribe to the server->device RPC topic (the direction
     the IF-8/9/10 command channel will ride).

It is a SMOKE TEST, not the outbox binding: the durable store-and-forward pump
(esw/sink.py) gets its MQTT backend in its own workstream; this only proves the
path is open and the record shape lands.

Usage:
    python software/tools/coreiot_smoke.py                       # reachability only
    python software/tools/coreiot_smoke.py --token <DEVICE_TOKEN>
    COREIOT_TOKEN=... python software/tools/coreiot_smoke.py --tls

Get a token: CoreIOT dashboard -> Devices -> add device -> copy access token
(docs/11-dev-environment-setup.md walks through it).

Exit 0 = every attempted step passed (token absent -> reachability only, said loudly).
"""

import argparse
import json
import os
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from esw import params                    # noqa: E402
from esw.telemetry import Telemetry       # noqa: E402

DEFAULT_HOST = os.environ.get("COREIOT_HOST", "app.coreiot.io")
TELEMETRY_TOPIC = "v1/devices/me/telemetry"      # ThingsBoard device API
RPC_TOPIC = "v1/devices/me/rpc/request/+"


def build_heartbeat(site_id):
    """One REAL IF-6 heartbeat record from the real emitter -- not a hand-rolled
    lookalike, so a schema drift in esw/telemetry.py shows up here too."""
    cfg = params.default_config()
    versions = {"fw_ver": "sim-0", "cfg_ver": params.cfg_fingerprint(cfg),
                "model_ver": "none", "calib_ver": "none"}
    telem = Telemetry(site_id, versions)
    decision = {"state": "IDLE", "mode": "FULL", "posture": "NORMAL",
                "alert": None, "alarm_count": 0}
    records = telem.step(0.0, decision, "OK", False)
    beats = [r for r in records if r.get("if") == 6]
    assert len(beats) == 1, "telemetry emitter did not produce exactly one heartbeat"
    return beats[0]


def _wire_safe(o):
    """cfg_ver is raw bytes in the record (the honest limit harness/store.py also
    handles): hex-encode for the wire, identically to the durable store."""
    if isinstance(o, (bytes, bytearray)):
        return bytes(o).hex()
    raise TypeError("unserializable: %r" % (o,))


def step_reachability(host, port):
    print("[1/3] reachability: %s:%d" % (host, port))
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        addrs = sorted(set(i[4][0] for i in infos))
        print("      DNS ok: %s" % ", ".join(addrs))
    except socket.gaierror as e:
        print("      FAIL: DNS lookup failed (%s). Wrong host? Offline? Captive portal?" % e)
        return False
    try:
        with socket.create_connection((host, port), timeout=6):
            pass
        print("      TCP ok: port %d is open" % port)
        return True
    except OSError as e:
        print("      FAIL: TCP connect failed (%s). Firewall blocking %d? "
              "(Note: CoreIOT served plaintext 1883 only as of 2026-07-09 -- "
              "8883/TLS was closed; see docs/11 §3.)" % (e, port))
        return False


def step_mqtt(host, port, use_tls, token, site_id, wait_rpc):
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("      FAIL: paho-mqtt missing -- python -m pip install paho-mqtt")
        return False

    got = {"connected": False, "reason": None, "rpc": None}

    def on_connect(client, userdata, flags, reason_code, properties=None):
        got["connected"] = not reason_code.is_failure
        got["reason"] = str(reason_code)

    def on_message(client, userdata, msg):
        got["rpc"] = (msg.topic, msg.payload[:200])

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id="esw-smoke-%d" % int(time.time()),
                         protocol=mqtt.MQTTv311)
    client.username_pw_set(token)            # ThingsBoard: device token as username
    client.on_connect = on_connect
    client.on_message = on_message
    if use_tls:
        client.tls_set()

    print("[2/3] MQTT connect as device (token auth)")
    try:
        client.connect(host, port, keepalive=30)
    except OSError as e:
        print("      FAIL: %s" % e)
        return False
    client.loop_start()
    deadline = time.time() + 10
    while time.time() < deadline and got["reason"] is None:
        time.sleep(0.1)
    if not got["connected"]:
        print("      FAIL: CONNACK %s" % (got["reason"] or "timeout"))
        print("      (\"not authorized\" almost always means a wrong/copied-with-spaces "
              "device access token)")
        client.loop_stop()
        return False
    print("      connected (%s)" % got["reason"])

    beat = build_heartbeat(site_id)
    payload = json.dumps({"ts": int(time.time() * 1000),
                          "values": beat}, default=_wire_safe)
    print("[3/3] publish one real IF-6 heartbeat -> %s" % TELEMETRY_TOPIC)
    print("      %s" % payload)
    info = client.publish(TELEMETRY_TOPIC, payload, qos=1)
    try:
        info.wait_for_publish(timeout=10)
        acked = info.is_published()
    except (ValueError, RuntimeError) as e:
        print("      FAIL: publish error: %s" % e)
        acked = False
    if acked:
        print("      PUBACK ok -- check the device's 'Latest telemetry' on the "
              "CoreIOT dashboard: the if/site_id/sensor_mode/posture/state fields "
              "should be there.")

    r, _mid = client.subscribe(RPC_TOPIC, qos=1)
    rpc_sub_ok = (r == mqtt.MQTT_ERR_SUCCESS)
    print("      subscribed %s (server->device RPC: the future IF-8/9/10 direction)"
          % RPC_TOPIC if rpc_sub_ok else "      FAIL: RPC subscribe refused")
    if rpc_sub_ok and wait_rpc:
        print("      waiting %ds for an RPC (dashboard: device -> 'Send RPC')..." % wait_rpc)
        deadline = time.time() + wait_rpc
        while time.time() < deadline and got["rpc"] is None:
            time.sleep(0.2)
        if got["rpc"]:
            print("      RPC received: %s %s" % got["rpc"])
        else:
            print("      (none arrived -- fine, the subscribe itself already proved the path)")

    client.loop_stop()
    client.disconnect()
    return acked and rpc_sub_ok


def main():
    ap = argparse.ArgumentParser(description="CoreIOT (ThingsBoard) IF-6 uplink smoke test")
    ap.add_argument("--host", default=DEFAULT_HOST, help="broker host (default %s)" % DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=None,
                    help="broker port (default 1883, or 8883 with --tls)")
    ap.add_argument("--tls", action="store_true",
                    help="MQTT over TLS -- the doc 08 production posture. NOTE: as of "
                         "2026-07-09 CoreIOT did not expose 8883 (plaintext 1883 only); "
                         "the flag is here for when it does -- see docs/11 §3")
    ap.add_argument("--token", default=os.environ.get("COREIOT_TOKEN"),
                    help="device access token (or env COREIOT_TOKEN)")
    ap.add_argument("--site-id", default="SITE-DEV")
    ap.add_argument("--wait-rpc", type=int, default=0, metavar="SECS",
                    help="after subscribing, wait this long for a test RPC from the dashboard")
    args = ap.parse_args()
    port = args.port if args.port else (8883 if args.tls else 1883)

    print("CoreIOT smoke -- broker %s:%d tls=%s token=%s"
          % (args.host, port, args.tls, "yes" if args.token else "NO"))
    if not step_reachability(args.host, port):
        sys.exit(1)
    if not args.token:
        print("\nPARTIAL PASS: broker reachable. No device token given, so the MQTT")
        print("auth + publish steps were skipped. Create a device on the CoreIOT")
        print("dashboard, then rerun with --token <ACCESS_TOKEN> (or COREIOT_TOKEN=...)")
        print("-- see docs/11-dev-environment-setup.md.")
        sys.exit(0)
    ok = step_mqtt(args.host, port, args.tls, args.token, args.site_id, args.wait_rpc)
    print("\n%s" % ("PASS: the IF-6 record landed on CoreIOT." if ok else "FAIL"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
