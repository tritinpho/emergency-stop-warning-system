# ESW edge unit -- the K230 device entrypoint (ADR-0015 D3, ADR-0016).
#
# This is the first thing that runs the shipped `esw/` subset on real hardware. It constructs the
# same esw.app.EdgeApp the Level-H board constructs, hands it device backends instead of host
# fakes, and ticks it at 10 Hz. Every safety decision in this file is made by code that has already
# been scored against the SC-01..43 / PC / HM / CMD / AP oracles -- main.py itself decides nothing.
#
# On-card layout:
#   /sdcard/esw/            <- copy of software/esw/ (the shipped subset)
#   /sdcard/esw-app/        <- this directory
#   /sdcard/esw/calib.json  <- {"H": [[..]], "roi": [[x,y],..], ...}   REQUIRED, no default
#   /sdcard/esw/secrets.json<- {"master": "<64 hex>", "site_id": "..."}  REQUIRED, never in git
#   /sdcard/kmodel/yolov8n_320.kmodel
#
# Run:  mpremote connect <port> run main.py     (or copy to /sdcard and let CanMV autostart it)

import sys
import time

sys.path.insert(0, "/sdcard")
sys.path.insert(0, "/sdcard/esw-app")

from libs.PipeLine import PipeLine
import ujson

from esw import crypto
from esw.app import EdgeApp
from backends import CaptureLog, EdgeClock, FlashStore, UartRadio, UartSignStatus
from detector import EswDetector, K230Detector, load_model_config

from machine import UART

TICK_DT = 0.1                 # 10 Hz (ADR-0015 D2 fixed-rate tick)
SYNC_EVERY_S = 30.0           # re-sync the controller's clock (doc 10 edge-synced mode)
MODEL_INPUT_SIZE = [320, 320]
UART_ID = 1
UART_BAUD = 115200


def _load_json(path):
    f = open(path, "r")
    try:
        return ujson.load(f)
    finally:
        f.close()


def load_calibration():
    """The homography + ground ROI, from the survey. There is NO default.

    esw.perception.default_calibration() uses an identity H, which is meaningful only for a
    synthetic top-down scene. Silently falling back to it on a real camera would put the ROI gate
    in image pixels while the footprint model works in metres -- every gate decision wrong, nothing
    visibly broken. Perception additionally raises on a non-convex or clockwise ROI. Both are
    commissioning-time fail-loud checks; refusing to boot is the correct response to a missing survey."""
    calib = _load_json("/sdcard/esw/calib.json")
    if "H" not in calib or "roi" not in calib:
        raise ValueError("calib.json needs H (3x3 image->ground homography) and roi (CCW ground polygon)")
    return calib


def load_key():
    """The IF-4 link key, derived per site and per channel from an out-of-band master secret
    (doc 10 §5). Never hardcoded, never committed: the vendored ESP32 code shipped a Wi-Fi password
    and a CoreIoT token in git and both are now public (ADR-0016 backlog #6)."""
    s = _load_json("/sdcard/esw/secrets.json")
    master = bytes(bytearray.fromhex(s["master"]))
    site_id = s["site_id"]
    return crypto.derive_key(master, "IF4", site_id), site_id


def announce(boot):
    """The boot capability report. A degraded capability nobody sees is exactly the silent loss of
    coverage ADR-0005 forbids -- so this prints, loudly, before the first tick."""
    print("")
    print("=" * 72)
    print("ESW edge unit -- boot capability report")
    print("  classes seen by the loaded model : %s" % (boot["classes"],))
    print("  sees_person (SC-12 reachable)    : %s" % boot["sees_person"])
    print("  per_class_footprint              : %s" % boot["per_class_footprint"])
    print("  sign_readback (SC-24 detectable) : %s" % boot["sign_readback"])
    print("  absolute_time (GNSS/PPS)         : %s" % boot["absolute_time"])
    print("  durable_evidence                 : %s" % boot["durable_evidence"])
    print("  oversight_uplink                 : %s" % boot["oversight_uplink"])
    if boot["degraded"]:
        print("")
        print("  *** DEGRADED: %s" % (boot["degraded"],))
        print("  *** This unit CANNOT make the safety claims above that read False.")
    print("=" * 72)
    print("")


def main():
    key, site_id = load_key()
    calib = load_calibration()
    model = load_model_config("day")

    pl = PipeLine(rgb888p_size=MODEL_INPUT_SIZE, display_size=[640, 480], display_mode="lcd")
    pl.create()
    det = EswDetector(model["kmodel_path"], model["labels"],
                      model_input_size=[320, 320], rgb888p_size=MODEL_INPUT_SIZE,
                      confidence_threshold=model["confidence_threshold"],
                      nms_threshold=model["nms_threshold"])
    det.config_preprocess()

    uart = UART(UART_ID, UART_BAUD)
    radio = UartRadio(uart)
    clock = EdgeClock()
    radio.sync(clock.ms())                       # put the controller on our clock before the first frame

    versions = {"fw_ver": "esw-app-0.1",
                "model_ver": model["kmodel_path"],   # unpinned: no SHA is recorded anywhere (models/README.md)
                "calib_ver": calib.get("version", "unversioned")}

    backends = {"detector": K230Detector(pl, det),
                "radio": radio,
                "clock": clock,
                "sign_status": UartSignStatus(uart),
                "store": FlashStore(),
                "capture": CaptureLog()}

    app = EdgeApp(key, site_id, versions, calib, backends)
    announce(app.start())

    # Tick accounting IS the ADR-0015 D3 evidence: a MicroPython GC pause that pushes the loop past
    # T_assert_refresh (0.5 s) eats into the 4x margin before T_signhold (2.0 s) blanks the sign.
    # An overrun is fail-safe, never a silent miss -- but a soak that reports overruns near 2.0 s
    # is the FAIL condition in software/spikes/README.md, so the numbers are printed, not swallowed.
    period_ms = int(TICK_DT * 1000)
    next_ms = time.ticks_ms()
    last_sync = 0.0
    worst_overrun_ms = 0
    overruns = 0
    ticks = 0

    while True:
        app.step()
        ticks += 1

        now = clock.monotonic()
        if (now - last_sync) >= SYNC_EVERY_S:
            radio.sync(clock.ms())
            last_sync = now

        next_ms = time.ticks_add(next_ms, period_ms)
        late = time.ticks_diff(time.ticks_ms(), next_ms)
        if late > 0:
            overruns += 1
            if late > worst_overrun_ms:
                worst_overrun_ms = late
            next_ms = time.ticks_ms()            # do not spiral: re-base rather than chase
        else:
            time.sleep_ms(-late)

        if (ticks % 600) == 0:                   # once a minute
            print("[TICK] n=%d overruns=%d worst=%dms tx=%d frames=%d misses=%d" %
                  (ticks, overruns, worst_overrun_ms, radio.sent,
                   backends["detector"].frames, backends["detector"].misses))


if __name__ == "__main__":
    main()
