#!/usr/bin/env python3
# Level-H application board: the REAL device loop (esw/app.py EdgeApp) under host backends.
#
#   detector -> health -> adapter -> perception -> state machine -> actuator -> IF-4 sign
#                                                        |-> telemetry -> durable outbox
#                                                        |-> capture (acceptance evidence)
#
#   python software/run_app_tests.py     (from the repo root)
#
# This is the object firmware/k230-detector/esw-app/main.py constructs. Levels A-G test the parts
# against their oracles; this tests that they are PLUGGED TOGETHER with the right ordering and the
# right authority -- and that every capability the unit lacks is reported LOUDLY at boot (ADR-0005).
# Exit 0 when every case and the evidence checks pass; 1 otherwise.

import shutil
import sys
import tempfile

# Put software/ on the import path on CPython and MicroPython alike (see run_tests.py).
_here = __file__
_cut = _here.rfind("/")
_bs = _here.rfind("\\")
if _bs > _cut:
    _cut = _bs
sys.path.insert(0, _here[:_cut] if _cut >= 0 else ".")

from esw.app import EdgeApp
from esw.params import default_config
from harness.devices import FakeClock, ScriptedDetector, SignLink
from harness.rig import KEY, SITE, VERSIONS, drive, sample_at
from harness.sign import Sign
from harness.store import FakeTransport, FileStore
from scenarios.app_cases import CASES, CONTROL_AP09, EVIDENCE_CASE, LABELS
from scenarios.integration_cases import yolo_frame
from scenarios.perception_cases import CALIB


def score(case, boot, timeline, link=None):
    fails = []
    if link is not None and "tx_min" in case:
        if not (case["tx_min"] <= link.sent <= case["tx_max"]):
            fails.append(("tx-count", (case["tx_min"], case["tx_max"]), link.sent))
    for c in case.get("checks", []):
        rec = sample_at(timeline, c["t"])
        for key in ("on", "state", "assertion", "mode"):
            if key in c:
                got = rec.get(key) if rec else None
                if got != c[key]:
                    fails.append((c["t"], (key, c[key]), (key, got)))
        if "state_not" in c:
            got = rec.get("state") if rec else None
            if got == c["state_not"]:
                fails.append((c["t"], ("state_not", c["state_not"]), ("state", got)))
    exp = case.get("boot")
    if exp:
        for key in exp:
            got = boot.get(key)
            if got != exp[key]:
                fails.append(("boot", (key, exp[key]), (key, got)))
    return fails


def evidence_checks():
    """The acceptance-evidence spine, end to end: a real activation is durably logged, the raw
    detections are captured for offline scoring, and a unit that dies mid-run resumes its outbox
    from the durable watermark instead of re-shipping or losing the log (ADR-0007, doc 01 s5)."""
    fails = []
    tmp = tempfile.mkdtemp()
    try:
        store = FileStore(tmp + "/evidence")
        transport = FakeTransport()
        transport.up = False                      # uplink down for the whole first life
        app, boot, timeline, cap, link = drive(EVIDENCE_CASE, store, transport)

        entries = store.load()
        types = []
        for e in entries:
            types.append(e["rec"].get("type"))
        if "capability" not in types:
            fails.append(("boot-record-durable", "capability", types[:4]))
        if "activation" not in types:
            fails.append(("activation-durable", "activation", types[:8]))
        if transport.delivered:
            fails.append(("no-forward-while-down", 0, len(transport.delivered)))

        ticks = cap.ticks()
        if len(ticks) < 100:
            fails.append(("capture-ticks", ">=100", len(ticks)))
        with_dets = 0
        for r in ticks:
            if r["dets"]:
                with_dets += 1
        if with_dets < 90:                        # car present 1.0..12.0 of a 12.0 s run
            fails.append(("capture-raw-detections", ">=90", with_dets))
        if not ticks or "bbox" not in ticks[-1]["dets"][0]:
            fails.append(("capture-keeps-bbox", True, False))

        # The unit dies. A fresh EdgeApp over the SAME store must resume, not restart: no record is
        # re-numbered, and the backlog the dead unit never forwarded is still pending.
        pending_before = app.outbox.pending()
        store2 = FileStore(tmp + "/evidence")
        transport.up = True
        app2 = EdgeApp(KEY, SITE, VERSIONS, CALIB,
                       {"detector": ScriptedDetector(EVIDENCE_CASE, yolo_frame, LABELS),
                        "radio": SignLink(Sign(default_config(), KEY)),
                        "clock": FakeClock(), "store": store2, "transport": transport})
        if app2.outbox.next_seq() <= 1:
            fails.append(("outbox-resumes-seq", ">1", app2.outbox.next_seq()))
        if app2.outbox.pending() < pending_before:
            fails.append(("backlog-survives-reboot", pending_before, app2.outbox.pending()))
        app2.outbox.pump(True)                    # uplink back -> the backlog drains, in order
        seqs = []
        for e in transport.delivered:
            seqs.append(e["seq"])
        if seqs != sorted(seqs):
            fails.append(("forward-in-order", "sorted", seqs[:8]))
        if not seqs:
            fails.append(("backlog-forwards-on-reconnect", ">0", 0))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return fails


def main():
    print("")
    print("ESW Level-H application board -- the real EdgeApp loop under host backends")
    print("-" * 84)
    surprises = []
    n_pass = 0

    cases = list(CASES)
    cases.append(CONTROL_AP09)
    for case in cases:
        app, boot, timeline, cap, link = drive(case)
        fails = score(case, boot, timeline, link)
        if fails:
            surprises.append((case["id"], fails))
            print("{:<8} {:<6} {}".format(case["id"], "FAIL", case["title"]))
        else:
            n_pass += 1
            print("{:<8} {:<6} {}".format(case["id"], "PASS", case["title"]))

    ev = evidence_checks()
    if ev:
        surprises.append((EVIDENCE_CASE["id"], ev))
        print("{:<8} {:<6} {}".format(EVIDENCE_CASE["id"], "FAIL", EVIDENCE_CASE["title"]))
    else:
        n_pass += 1
        print("{:<8} {:<6} {}".format(EVIDENCE_CASE["id"], "PASS", EVIDENCE_CASE["title"]))

    total = len(cases) + 1
    print("-" * 84)
    print("{} / {} application cases pass".format(n_pass, total))
    if surprises:
        print("")
        print("SURPRISES:")
        for sid, fs in surprises:
            print("  {}:".format(sid))
            for f in fs:
                print("     {}".format(f))
        return 1
    print("application board OK -- the device loop is wired, and every missing capability is loud.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
