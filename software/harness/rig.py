# The EdgeApp bench rig: build a real esw.app.EdgeApp with host backends and tick it.
#
# Shared by the Level-H board (run_app_tests.py, which scores the loop's behaviour) and the Level-D
# board (run_metrics.py, which uses it to WRITE a real device log and then score that log offline).
# One rig, so the logs the offline scorer is tested against are produced by the same wiring the
# K230 runs -- not by a fixture written to satisfy the reader.

from esw import crypto
from esw.app import EdgeApp
from esw.params import default_config
from harness.devices import (FakeClock, ListCapture, RamStore, ScriptedCommands, ScriptedDetector,
                             Selftest, SignLink)
from harness.sign import Sign
from scenarios.integration_cases import yolo_frame
from scenarios.perception_cases import CALIB

TICK_DT = 0.1
SITE = "bench-01"
KEY = crypto.derive_key(b"esw-master-secret-v1-0123456789abc", "IF4", SITE)
VERSIONS = {"fw_ver": "bench-fw", "model_ver": "yolov8n_320-unpinned", "calib_ver": "bench-calib"}

# Every COCO label the integration cases index into.
from scenarios.app_cases import LABELS   # noqa: E402  (kept next to its only consumer)


def drive(case, store=None, transport=None, capture=None):
    """Run one case through a real EdgeApp. Returns (app, boot_record, timeline, capture, link)."""
    labels = case.get("labels", LABELS)
    clock = FakeClock(absolute=case.get("absolute_time", True), gnss=case.get("gnss", True))
    det = ScriptedDetector(case, yolo_frame, labels, case.get("blind", ()))
    sign = Sign(default_config(), KEY, can_turn_off=not case.get("sign_stuck", False))
    link = SignLink(sign)
    cap = capture if capture is not None else ListCapture()
    selftest = Selftest(case.get("selftest_fail", ()))

    # A real unit always has durable storage, so the default is a RAM store rather than none --
    # otherwise every case would boot reporting `durable_evidence` degraded and the boot report
    # would stop discriminating.
    backends = {"detector": det, "radio": link, "clock": clock,
                "capture": cap, "selftest": selftest,
                "store": store if store is not None else RamStore()}
    if case.get("sign_readback", True):
        backends["sign_status"] = link.status
    if transport is not None:
        backends["transport"] = transport
    if case.get("config_push"):
        backends["commands"] = ScriptedCommands(config_push=case["config_push"])

    app = EdgeApp(KEY, SITE, VERSIONS, CALIB, backends)
    boot = app.start()

    stop_at = case.get("stop_at")
    timeline = []
    steps = int(case["duration"] / TICK_DT) + 1
    for i in range(steps):
        t = round(i * TICK_DT, 3)
        clock.set(t)
        det.set(t)
        selftest.set(t)
        # A stopped loop is a CRASHED unit: nothing is sent, nothing is cleared. The sign
        # controller keeps running -- that is the whole point of the dead-man's switch.
        if stop_at is None or t < stop_at:
            app.step(t)
        link.tick(t)
        d = app.last_decision or {}
        timeline.append({"t": t, "on": link.on, "state": d.get("state"),
                         "assertion": d.get("assertion"), "mode": d.get("mode"),
                         "congestion_reason": d.get("congestion_reason")})
    return app, boot, timeline, cap, link


def sample_at(timeline, t):
    """The most recent sample at or before t."""
    rec = None
    for r in timeline:
        if r["t"] <= t + 1e-9:
            rec = r
        else:
            break
    return rec
