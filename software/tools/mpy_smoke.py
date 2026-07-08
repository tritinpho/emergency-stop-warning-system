#!/usr/bin/env python3
# MicroPython smoke test for the SHIPPED esw/ modules that the Level-A/C boards do NOT
# import -- perception.py, geometry.py, and sink.py (Level A scripts IF-2 events directly and
# reduces in-process, so those never load under `micropython run_tests.py`). This closes the mpy
# coverage gap: it imports every esw module and exercises the IF-1->IF-2 perception path, the
# geometry primitives, and the durable outbox policy, so CI proves all ten shipped modules load
# and run under MicroPython, not just parse clean (mp_safe_check.py) or run under CPython.
#
#   python software/tools/mpy_smoke.py       # CPython
#   micropython tools/mpy_smoke.py           # from software/, MicroPython unix port
#
# Exit 0 when every check holds; 1 (with a listed report) otherwise. Kept inside the
# MicroPython-safe subset itself (no f-strings/comprehensions/lambdas).

import sys

# Put software/ on the import path from software/tools/, on both CPython and MicroPython
# (mpy has no os.path). This file is two levels below software/, so climb twice from
# __file__, handling relative (mpy) and absolute (CPython 3.14 main-script) forms.
_here = __file__
_c1 = _here.rfind("/")
_b1 = _here.rfind("\\")
if _b1 > _c1:
    _c1 = _b1
_toolsdir = _here[:_c1] if _c1 >= 0 else ""          # .../software/tools | "tools" | ""
_c2 = _toolsdir.rfind("/")
_b2 = _toolsdir.rfind("\\")
if _b2 > _c2:
    _c2 = _b2
if _c2 >= 0:
    _swdir = _toolsdir[:_c2]                          # .../software  (absolute form)
elif _toolsdir == "":
    _swdir = ".."                                     # ran as `micropython mpy_smoke.py` in tools/
else:
    _swdir = "."                                      # ran as `micropython tools/mpy_smoke.py` in software/
sys.path.insert(0, _swdir if _swdir != "" else ".")

# Every shipped esw module must at least LOAD under MicroPython.
from esw import state_machine, params, actuator, if4, health, telemetry, perception, geometry, sink
from esw.geometry import bbox_ground_point, footprint_box, overlap_fraction, is_convex_ccw
from esw.perception import Perception
from esw.sink import Outbox

_fails = []


def check(name, cond):
    if cond:
        print("  ok   " + name)
    else:
        print("  FAIL " + name)
        _fails.append(name)


def approx(a, b, tol):
    d = a - b
    if d < 0:
        d = -d
    return d <= tol


# --- geometry primitives ------------------------------------------------------
# Affine 0.05 m/px homography (matches the Level-B CALIB): ground = 0.05*(cx, bottom_y).
H = [[0.05, 0.0, 0.0], [0.0, 0.05, 0.0], [0.0, 0.0, 1.0]]
ROI = [(10.0, 20.0), (25.0, 20.0), (25.0, 40.0), (10.0, 40.0)]   # CCW ground quad

check("is_convex_ccw(ROI) is True", is_convex_ccw(ROI) is True)

gx, gy = bbox_ground_point(H, [360, 520, 440, 600])              # centre x=400, bottom y=600
check("bbox_ground_point -> (20,30)", approx(gx, 20.0, 0.01) and approx(gy, 30.0, 0.01))

fp_in = footprint_box(20.0, 30.0, 2.0, 4.5)                      # car box well inside ROI
check("overlap_fraction inside ROI > 0.9", overlap_fraction(fp_in, ROI) > 0.9)

fp_out = footprint_box(100.0, 100.0, 2.0, 4.5)                   # far outside ROI
check("overlap_fraction outside ROI == 0.0", overlap_fraction(fp_out, ROI) == 0.0)

# --- perception IF-1 -> IF-2 --------------------------------------------------
# A stopped car detected inside the ROI over several ticks: exactly one stable track,
# high ROI overlap, near-zero smoothed speed, camera-sourced -- the core IF-2 contract.
P = Perception({"H": H, "roi": ROI, "score_min": 0.4, "score_low": 0.1,
                "assoc_gate_m": 3.0, "track_max_age_s": 2.0,
                "speed_window_s": 0.5, "speed_alpha": 0.3})
dets = [{"cls": "car", "bbox": [360, 520, 440, 600], "score": 0.9}]
last = []
t = 0.0
i = 0
while i < 9:                      # 9 ticks @ 0.1s -- fills the 0.5s speed window
    last = P.step(dets, t)
    t += 0.1
    i += 1

check("perception emits exactly one track", len(last) == 1)
if last:
    ev = last[0]
    check("track_id is camera-prefixed 'P*'", isinstance(ev["track_id"], str) and ev["track_id"][:1] == "P")
    check("in_roi > 0.5 (stopped car inside ROI)", ev["in_roi"] > 0.5)
    check("speed_kph < 2.0 (stationary, jitter-robust)", ev["speed_kph"] < 2.0)
    check("sensor_source == 'camera'", ev["sensor_source"] == "camera")

# A detection whose ground point is outside the ROI must never gate in.
P2 = Perception({"H": H, "roi": ROI})
out = []
t = 0.0
i = 0
while i < 6:
    out = P2.step([{"cls": "car", "bbox": [40, 40, 120, 120], "score": 0.9}], t)  # ground (4,6), outside
    t += 0.1
    i += 1
check("outside-ROI detection -> in_roi below gate", len(out) == 1 and out[0]["in_roi"] < 0.5)


# --- sink (durable evidence outbox) -------------------------------------------
# The store-and-forward Outbox POLICY must load + run on-target. Durability is proven on the host
# FileStore in the Level-E board (host-only); here a tiny in-RAM store + link show the policy runs
# under MicroPython: monotonic seq, hold-while-down, forward-on-reconnect, reboot-resume.
class _MemStore:
    def __init__(self):
        self.entries = []
        self._ack = -1

    def append(self, entry):
        self.entries.append(entry)

    def load(self):
        return self.entries

    def ack(self, seq):
        self._ack = seq

    def acked(self):
        return self._ack


class _MemLink:
    def __init__(self):
        self.got = []

    def send(self, entry):
        self.got.append(entry)
        return True


_ms = _MemStore()
_ln = _MemLink()
_ob = Outbox(_ms, _ln)
_ob.record([{"if": 7, "type": "activation", "ts": 1.0}, {"if": 7, "type": "clear", "ts": 5.0}])
check("outbox assigns monotonic seq", _ms.entries[0]["seq"] == 0 and _ms.entries[1]["seq"] == 1)
check("outbox holds while uplink down (pending==2)", _ob.pump(False) == 0 and _ob.pending() == 2)
check("outbox forwards both on reconnect", _ob.pump(True) == 2 and len(_ln.got) == 2)
check("outbox backlog clears", _ob.pending() == 0)
_ob2 = Outbox(_ms, _ln)                 # reboot: fresh outbox over the same store
check("outbox next_seq resumes after reboot", _ob2.next_seq() == 2)

print("-" * 60)
if _fails:
    print("mpy_smoke: %d CHECK(S) FAILED" % len(_fails))
    sys.exit(1)
print("mpy_smoke OK -- all esw modules load; perception + geometry + sink run under this runtime.")
sys.exit(0)
