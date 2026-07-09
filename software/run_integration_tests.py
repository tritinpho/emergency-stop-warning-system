#!/usr/bin/env python3
# Level-G integration board (ADR-0016): the MERGED K230 pipeline end to end. Starts from RAW
# YOLO postprocess output, runs it through the on-device adapter (esw/k230_adapter.py), then the
# REAL perception + REAL state machine + REAL IF-4 sign:
#
#   raw YOLO (boxes,class_ids,confidences) -> detections_from_yolo -> perception -> SM -> sign
#
#   python software/run_integration_tests.py     (from the repo root)
#
# Exit 0 when the adapter unit checks and every closed-loop case match; 1 otherwise. This is the
# seam ADR-0016 defines: their device-tested detector feeding our verified safety stack.

import sys

# Put software/ on the import path on CPython and MicroPython alike (see run_tests.py).
_here = __file__
_cut = _here.rfind("/")
_bs = _here.rfind("\\")
if _bs > _cut:
    _cut = _bs
sys.path.insert(0, _here[:_cut] if _cut >= 0 else ".")

from scenarios.integration_cases import CASES, COCO_LABELS, yolo_frame
from scenarios.perception_cases import CALIB
from esw.k230_adapter import detections_from_yolo
from esw.perception import Perception
from esw.params import default_config
from esw.state_machine import StateMachine
from esw.actuator import Actuator
from esw import crypto, if4
from harness.sign import Sign

TICK_DT = 0.1
_KEY = crypto.derive_key(b"esw-master-secret-v1-0123456789abc", "IF4", "bench-01")


def _adapter_units():
    """Direct checks on the adapter transform -- the class mapping, the person-kept fix, the
    xywh->xyxy conversion, and the two drop rules -- independent of the state machine."""
    fails = []
    # Mixed frame: car, person, truck, bicycle (drop), motorbike-alias -> motorcycle.
    boxes = [[360, 520, 80, 80], [100, 100, 40, 90], [200, 200, 50, 50],
             [10, 10, 30, 30], [300, 300, 60, 60]]
    cids = [2, 0, 7, 1, 3]
    confs = [0.9, 0.8, 0.7, 0.6, 0.55]
    dets = detections_from_yolo(boxes, cids, confs, COCO_LABELS)
    names = [d["cls"] for d in dets]
    if names != ["car", "person", "truck", "motorcycle"]:
        fails.append(("class-map", ["car", "person", "truck", "motorcycle"], names))
    if "person" not in names:                                   # the key ADR-0016 fix
        fails.append(("person-kept", True, False))
    if dets and dets[0]["bbox"] != [360, 520, 440, 600]:        # xywh -> xyxy
        fails.append(("bbox-xyxy", [360, 520, 440, 600], dets[0]["bbox"] if dets else None))
    if detections_from_yolo([[370, 540, 20, 20]], [2], [0.9], COCO_LABELS) != []:
        fails.append(("tiny-dropped", [], "kept"))              # sub-25px noise floor
    if detections_from_yolo([[360, 520, 80, 80]], [999], [0.9], COCO_LABELS) != []:
        fails.append(("badid-dropped", [], "kept"))             # out-of-range class id
    d4 = detections_from_yolo([[360, 520, 80, 80]], [0], [0.9], ["vehicle"])
    if len(d4) != 1 or d4[0]["cls"] != "car":                   # single-class model -> car
        fails.append(("vehicle-alias", "car", d4))
    d5 = detections_from_yolo([[360, 520, 80, 80]], [0], [0.9], ["CAR"])   # upper-case label
    if len(d5) != 1 or d5[0]["cls"] != "car":                   # case-insensitive normalisation
        fails.append(("case-insensitive", "car", d5))
    return fails


def _closed_loop(case):
    """raw YOLO -> adapter -> REAL perception -> REAL state machine -> IF-4 sign. Returns the
    public sign on/off state at each tick (the same rig as the Level-B closed loop)."""
    perc = Perception(CALIB)
    cfg = default_config()
    sm = StateMachine(cfg)
    actuator = Actuator(_KEY, if4.cfg_fingerprint(cfg))
    sign = Sign(cfg, _KEY)
    steps = int(case["duration"] / TICK_DT) + 1
    on_at = {}
    for i in range(steps):
        t = round(i * TICK_DT, 3)
        boxes, cids, confs = yolo_frame(case, t)
        dets = detections_from_yolo(boxes, cids, confs, COCO_LABELS)
        decision = sm.tick(t, perc.step(dets, t), {"camera": True, "radar": True})
        frame = actuator.step(t, decision)
        if frame is not None:
            sign.receive(t, frame)
        on_at[t] = sign.update(t)
    return on_at


def _score_loop(case):
    on_at = _closed_loop(case)
    fails = []
    for c in case.get("loop_checks", []):
        got = on_at.get(round(c["t"], 3))
        if got != c["on"]:
            fails.append((c["t"], "sign_on", c["on"], got))
    return fails


def main():
    print("")
    print("ESW Level-G integration board -- raw K230 YOLO -> adapter -> perception -> SM -> sign")
    print("-" * 76)
    surprises = []

    unit_fails = _adapter_units()
    print("{:<7} {:<6} {}".format("ADAPT", "PASS" if not unit_fails else "FAIL",
          "esw.k230_adapter: class map + person kept + xywh->xyxy + drop rules"))
    if unit_fails:
        surprises.append(("ADAPT", unit_fails))

    n_pass = 0
    for case in CASES:
        fails = _score_loop(case)
        if fails:
            surprises.append((case["id"], fails))
            print("{:<7} {:<6} {}".format(case["id"], "FAIL", case["title"]))
        else:
            n_pass += 1
            print("{:<7} {:<6} {}".format(case["id"], "PASS", case["title"]))

    print("-" * 76)
    print("{} / {} integration cases pass; adapter units {}".format(
        n_pass, len(CASES), "OK" if not unit_fails else "FAILED"))
    if surprises:
        print("")
        print("SURPRISES:")
        for sid, fs in surprises:
            print("  {}:".format(sid))
            for f in fs:
                print("     {}".format(f))
        return 1
    print("integration board OK -- the merged pipeline is closed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
