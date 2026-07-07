#!/usr/bin/env python3
# Level-C health board: unit-test the health monitor (esw/health.py) in ISOLATION -- the stage
# that DERIVES {camera, radar} health (FR-10), time integrity (NFR-16), and the independent
# force-safe (IF-5) from raw per-subsystem liveness.
#
#   python software/run_health_tests.py     (from the repo root)
#
# Exit 0 when every HM case matches its oracle; 1 otherwise. Complements run_tests.py (the
# Level-A closed-loop side, SC-35/36/37) and run_perception_tests.py.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from esw.health import HealthMonitor
from esw.params import default_config
from scenarios.health_cases import CASES

TICK_DT = 0.1
_OUT_KEYS = ("camera", "radar", "time_valid", "force_safe", "status")


def _in_windows(windows, t):
    for w in windows:
        if w[0] <= t < w[1]:
            return True
    return False


def _merge(base, over):
    out = dict(base)
    for k in over:
        out[k] = over[k]
    return out


def _run(case):
    cfg = _merge(default_config(), case.get("config_push", {}))
    mon = HealthMonitor(cfg)
    live = case.get("live", {})
    steps = int(case["duration"] / TICK_DT) + 1
    timeline = {}
    for i in range(steps):
        t = round(i * TICK_DT, 3)
        sensor_live = {}
        for s in ("camera", "radar"):
            w = live.get(s, None)
            sensor_live[s] = True if w is None else _in_windows(w, t)
        gnss = not _in_windows(case.get("gnss_loss", []), t)
        selftest = not _in_windows(case.get("hm_fault", []), t)
        timeline[t] = mon.step(t, sensor_live, gnss, selftest)
    return timeline


def _sample(timeline, t):
    rec = None
    for k in sorted(timeline.keys()):
        if k <= t + 1e-9:
            rec = timeline[k]
        else:
            break
    return rec


def _score(case, timeline):
    fails = []
    for c in case.get("checks", []):
        rec = _sample(timeline, c["t"])
        for key in _OUT_KEYS:
            if key in c:
                got = rec.get(key) if rec else None
                if got != c[key]:
                    fails.append((c["t"], key, c[key], got))
    return fails


def main():
    print("")
    print("ESW Level-C health board -- HealthMonitor (FR-10 / NFR-16 / IF-5)")
    print("-" * 68)
    surprises = []
    n_pass = 0
    for case in CASES:
        fails = _score(case, _run(case))
        if fails:
            surprises.append((case["id"], fails))
            print("{:<7} {:<6} {}".format(case["id"], "FAIL", case["title"]))
        else:
            n_pass += 1
            print("{:<7} {:<6} {}".format(case["id"], "PASS", case["title"]))
    print("-" * 68)
    if surprises:
        for sid, fails in surprises:
            for f in fails:
                print("  {} t={} {}: expected {!r} got {!r}".format(sid, f[0], f[1], f[2], f[3]))
        print("{} / {} health cases pass".format(n_pass, len(CASES)))
        return 1
    print("{} / {} health cases pass".format(n_pass, len(CASES)))
    print("health board OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
