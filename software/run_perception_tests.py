#!/usr/bin/env python3
# Level-B perception board: drive the REAL perception pipeline (esw/perception.py) with
# scripted detections and score its IF-2 output, plus a closed-loop check that the pipeline
# feeds the state machine correctly (detections -> perception -> state machine -> sign).
#
#   python software/run_perception_tests.py     (from the repo root)
#
# Exit 0 when every case matches its oracle and the closed loop lights the sign; 1 otherwise.
# Complements run_tests.py (the Level-A SC-01..30 state-machine board).

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scenarios.perception_cases import CASES, CALIB
from esw.perception import Perception
from esw.params import default_config
from esw.state_machine import StateMachine, MESSAGE_STOPPED
from harness.frames import detections_at
from harness.sign import Sign

TICK_DT = 0.1
ROI_GATE = default_config()["roi_overlap_gate"]


def _run(case):
    perc = Perception(case.get("calib", CALIB))       # a case may supply its own calibration
    steps = int(case["duration"] / TICK_DT) + 1
    timeline = []
    for i in range(steps):
        t = round(i * TICK_DT, 3)
        timeline.append((t, perc.step(detections_at(case, t), t)))
    return timeline


def _events_at(timeline, t):
    ev = []
    for (tt, e) in timeline:
        if tt <= t + 1e-9:
            ev = e
        else:
            break
    return ev


def _score(case, timeline):
    fails = []
    for c in case["checks"]:
        ev = _events_at(timeline, c["t"])
        in_roi = [e for e in ev if e["in_roi"] >= ROI_GATE]
        max_roi = max([e["in_roi"] for e in ev], default=0.0)
        max_sp = max([e["speed_kph"] for e in in_roi], default=0.0)
        if "n_detected" in c and len(ev) != c["n_detected"]:
            fails.append((c["t"], "n_detected", c["n_detected"], len(ev)))
        if "n_in_roi" in c and len(in_roi) != c["n_in_roi"]:
            fails.append((c["t"], "n_in_roi", c["n_in_roi"], len(in_roi)))
        if "speed_max" in c and max_sp > c["speed_max"] + 1e-6:
            fails.append((c["t"], "speed_max", c["speed_max"], round(max_sp, 2)))
        if "speed_min" in c and max_sp < c["speed_min"] - 1e-6:
            fails.append((c["t"], "speed_min", c["speed_min"], round(max_sp, 2)))
        if "max_in_roi_lt" in c and not (max_roi < c["max_in_roi_lt"]):
            fails.append((c["t"], "max_in_roi_lt", c["max_in_roi_lt"], round(max_roi, 2)))
        if "max_in_roi_gt" in c and not (max_roi > c["max_in_roi_gt"]):
            fails.append((c["t"], "max_in_roi_gt", c["max_in_roi_gt"], round(max_roi, 2)))
    # Whole-run ID-switch metric: distinct track_ids the pipeline ever emitted. A single
    # real object under dropout / jitter / class-confusion must stay ONE id (no switch).
    if "n_ids" in case:
        all_ids = set()
        for (tt, e) in timeline:
            for ev in e:
                all_ids.add(ev["track_id"])
        if len(all_ids) != case["n_ids"]:
            fails.append(("run", "n_ids", case["n_ids"], len(all_ids)))
    return fails


def _score_loop(case):
    """Closed-loop checks: run detections -> perception -> state machine -> sign and assert
    the sign state at each loop checkpoint (a false detection must never light it; a real
    track must not be spuriously cleared)."""
    on_at = _closed_loop(case)
    fails = []
    for c in case.get("loop_checks", []):
        got = on_at.get(round(c["t"], 3))
        if got != c["on"]:
            fails.append((c["t"], "sign_on", c["on"], got))
    return fails


def _closed_loop(case):
    """End-to-end Level B: scripted detections -> REAL perception -> REAL state machine ->
    sign. Returns the sign on/off state at each tick."""
    perc = Perception(case.get("calib", CALIB))
    sm = StateMachine(default_config())
    sign = Sign(default_config())
    steps = int(case["duration"] / TICK_DT) + 1
    on_at = {}
    for i in range(steps):
        t = round(i * TICK_DT, 3)
        decision = sm.tick(t, perc.step(detections_at(case, t), t),
                           {"camera": True, "radar": True})
        if decision.get("assertion") == "SHOW":
            sign.refresh(t, decision.get("message_id", MESSAGE_STOPPED))
        on_at[t] = sign.update(t)
    return on_at


def main():
    print("")
    print("ESW Level-B perception board -- IF-1 -> IF-2 pipeline")
    print("-" * 68)
    surprises = []
    n_pass = 0
    for case in CASES:
        fails = _score(case, _run(case))
        if "loop_checks" in case:
            fails = fails + _score_loop(case)
        if fails:
            surprises.append((case["id"], fails))
            print("{:<7} {:<6} {}".format(case["id"], "FAIL", case["title"]))
        else:
            n_pass += 1
            print("{:<7} {:<6} {}".format(case["id"], "PASS", case["title"]))

    # Closed-loop sanity: PC-01 (static car in ROI) must light the sign after the dwell.
    on_at = _closed_loop(CASES[0])
    loop_ok = on_at.get(10.0) is True
    print("-" * 68)
    print("{:<7} {:<6} {}".format("LOOP", "PASS" if loop_ok else "FAIL",
          "closed loop: detections -> perception -> state machine -> sign ON"))
    if not loop_ok:
        surprises.append(("LOOP", [(10.0, "sign_on", True, on_at.get(10.0))]))

    print("-" * 68)
    print("{} / {} perception cases pass; closed loop {}".format(
        n_pass, len(CASES), "OK" if loop_ok else "FAILED"))
    if surprises:
        print("")
        print("SURPRISES:")
        for sid, fs in surprises:
            print("  {}:".format(sid))
            for f in fs:
                print("     t={}s {} expected={} got={}".format(f[0], f[1], f[2], f[3]))
        return 1
    print("perception board OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
