#!/usr/bin/env python3
# MicroPython smoke test for the SHIPPED esw/ modules that the Level-A/C boards do NOT
# import -- perception.py, geometry.py, sink.py, command.py, and k230_adapter.py (Level A scripts
# IF-2 events directly and reduces in-process, so those never load under `micropython run_tests.py`;
# crypto.py IS covered transitively, since if4.py imports it). This closes the mpy coverage gap: it
# imports every esw module and exercises the IF-1->IF-2 perception path, the K230 detector adapter,
# the geometry primitives, the durable outbox policy, and the authenticated command codec, so CI
# proves all thirteen shipped modules load and run under MicroPython, not just parse clean
# (mp_safe_check.py) or run on CPython.
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
from esw import (state_machine, params, actuator, if4, health, telemetry, perception, geometry,
                 sink, crypto, command, app)
from esw.geometry import bbox_ground_point, footprint_box, overlap_fraction, is_convex_ccw
from esw.perception import Perception
from esw.sink import Outbox
from esw.command import CommandReceiver, encode_command, verify_command, CMD_OVERRIDE
from esw.crypto import derive_key
from esw.k230_adapter import detections_from_yolo
from esw.app import EdgeApp

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


# --- K230 detector adapter (raw YOLO -> IF-1 detections, ADR-0016) ------------
# The on-device caller glue must load + run on-target: xywh->xyxy, class aliasing, `person`
# kept (their vendored vehicle-only filter dropped it -> SC-12), and the drop rules. Full
# behavioural coverage is the host Level-G board; this proves the shipped module runs under mpy.
_adlabels = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck"]
_ad = detections_from_yolo([[360, 520, 80, 80], [10, 10, 30, 30], [100, 100, 40, 90]],
                           [2, 1, 0], [0.9, 0.6, 0.8], _adlabels)   # car, bicycle(drop), person
_adnames = []
_ak = 0
while _ak < len(_ad):
    _adnames.append(_ad[_ak]["cls"])
    _ak += 1
check("adapter: car + person kept, bicycle dropped", _adnames == ["car", "person"])
check("adapter: xywh -> xyxy bbox", len(_ad) > 0 and _ad[0]["bbox"] == [360, 520, 440, 600])
check("adapter: sub-25px blob dropped", detections_from_yolo([[1, 1, 20, 20]], [2], [0.9], _adlabels) == [])
_adv = detections_from_yolo([[360, 520, 80, 80]], [0], [0.9], ["vehicle"])   # single-class model
check("adapter: single-class 'vehicle' -> car footprint", len(_adv) == 1 and _adv[0]["cls"] == "car")
_adc = detections_from_yolo([[360, 520, 80, 80]], [0], [0.9], ["CAR"])       # upper-case label (.lower())
check("adapter: case-insensitive label -> car", len(_adc) == 1 and _adc[0]["cls"] == "car")


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


# --- command channel (authenticated IF-8/9/10) --------------------------------
# The auth codec + receiver must load + run on-target: encode -> verify round-trips (JSON payload
# decoded only after auth); a wrong-key frame fails auth; a replayed seq is rejected. (Full
# behavioural coverage is the host Level-F board; this proves the shipped module runs under mpy.)
_ck = b"smoke-cmd-key-0000000000000000000000"
_wk = b"smoke-wrong-key-000000000000000000000"
_win = 5000
_cf = encode_command(_ck, CMD_OVERRIDE, 1, 1, 10000, {"action": "force_on", "reason": "x"})
_cr = verify_command(_ck, _cf, None, 10000, _win)
check("command verify ok + JSON payload decoded", _cr["ok"] and _cr["payload"]["action"] == "force_on")
_forged = encode_command(_wk, CMD_OVERRIDE, 2, 2, 10000, {})
check("forged command fails auth", verify_command(_ck, _forged, None, 10000, _win)["reason"] == "auth")
_rx = CommandReceiver(_ck, _win)
_okc = _rx.submit(_cf, 10000)["ok"]
_rep = _rx.submit(_cf, 10010)["ok"]                 # same seq re-submitted -> anti-replay
check("receiver accepts then rejects a replay", _okc and (not _rep) and _rx.rejects == 1)
_unk = encode_command(_ck, 99, 3, 3, 10000, {})     # genuine key, unmapped ctype (version skew)
check("unknown ctype rejected loud", verify_command(_ck, _unk, None, 10000, _win)["reason"] == "ctype")
_nd = encode_command(_ck, CMD_OVERRIDE, 4, 4, 10000, [1, 2])   # authenticated, but not an OBJECT
check("non-object payload rejected (payload)",
      verify_command(_ck, _nd, None, 10000, _win)["reason"] == "payload")
_rx2 = CommandReceiver(_ck, _win, 5)                # a persisted anti-replay watermark, restored
_r5 = _rx2.submit(encode_command(_ck, CMD_OVERRIDE, 5, 5, 10000, {}), 10000)
_r6 = _rx2.submit(encode_command(_ck, CMD_OVERRIDE, 6, 6, 10000, {}), 10000)
check("restored watermark blocks seq<=5, accepts 6, exposes last_seq",
      _r5["reason"] == "replay" and _r6["ok"] and _rx2.last_seq == 6)

# --- per-site / per-channel key derivation (esw/crypto.derive_key, ADR-0012) ---
_dk_if4 = derive_key(b"master-secret", "IF4", "site-A")
_dk_cmd = derive_key(b"master-secret", "CMD", "site-A")
_dk_b = derive_key(b"master-secret", "IF4", "site-B")
check("derive_key: 32 bytes, channel- and site-separated",
      len(_dk_if4) == 32 and _dk_if4 != _dk_cmd and _dk_if4 != _dk_b)
check("derive_key deterministic", derive_key(b"master-secret", "IF4", "site-A") == _dk_if4)


# --- runtime config push (IF-8: params.clamp_update / StateMachine.apply_config) ---------------
# The runtime-config path runs only in Level-F (host-only), so cover it here so real mpy exercises
# it: a runtime param clamps to its bound, a bounded backstop and an unknown name are refused.
_acc, _rej = params.clamp_update({"T_dwell": 99.0, "T_signhold": 0.5, "bogus": 1})
check("clamp_update clamps a runtime param to bound", _acc.get("T_dwell") == 10.0 and ("T_dwell" in _rej))
check("clamp_update refuses a bounded backstop (boot-only)", ("T_signhold" not in _acc) and ("T_signhold" in _rej))
check("clamp_update refuses an unknown name", ("bogus" not in _acc) and ("bogus" in _rej))
_csm = state_machine.StateMachine()
_ver0 = _csm.cfg_ver
_csm.apply_config({"T_dwell": 3.0, "T_watchdog": 1.0})
check("apply_config applies runtime, keeps backstop", _csm.cfg["T_dwell"] == 3.0 and _csm.cfg["T_watchdog"] == 30.0)
check("apply_config re-fingerprints cfg_ver (R10 audit binding)", _csm.cfg_ver != _ver0)

# NaN is unclampable (every bound comparison is False), so the FR-20 surface must catch it:
# boot restores + flags the vetted default; a runtime push is refused outright (keep last-good).
_nan = float("nan")
_cv, _cw = params.clamp("T_watchdog", _nan)
check("clamp: NaN -> vetted default, flagged", _cv == 30.0 and _cw is True)
_cfgn, _rejn = params.clamp_config({"T_watchdog": _nan})
check("clamp_config: NaN cannot disable a backstop", _cfgn["T_watchdog"] == 30.0 and ("T_watchdog" in _rejn))
_accn, _rejn2 = params.clamp_update({"T_dwell": _nan})
check("clamp_update: NaN refused, keep last-good", ("T_dwell" not in _accn) and ("T_dwell" in _rejn2))
_iv, _iw = params.clamp("congestion_min_tracks", 4.5)   # counts hold integers (doc 02 s7a)
check("clamp: count param truncates 4.5 -> 4, flagged", _iv == 4 and _iw is True)
_iv2, _iw2 = params.clamp("congestion_min_tracks", 4.0)
check("clamp: exact 4.0 normalizes to int silently", _iv2 == 4 and isinstance(_iv2, int) and _iw2 is False)

# --- actuator clock contract (wall_ms carries the wire ts; `now` stays tick time) ---
_act = actuator.Actuator(_ck, b"\x00\x00\x00\x00")
_afr = _act.step(1.0, {"assertion": "SHOW", "message_id": "STOPPED_VEHICLE_AHEAD"},
                 nonce=1, wall_ms=123456)
check("actuator wall_ms sets the wire timestamp",
      _afr is not None and int.from_bytes(_afr[15:21], "big") == 123456)


# --- esw.app: the DEVICE LOOP itself runs here, not just the parts it wires ---------------
# The K230 entrypoint (firmware/k230-detector/esw-app/main.py) cannot run on this box, but the
# object it constructs can. Backends are the four things a bench has no version of: a camera, a
# radio, a clock, storage. Everything between them is the code that ships.
class _SmokeDetector:
    labels = ["person", "bicycle", "car"]

    def read(self):
        return [[360, 520, 80, 80]], [2], [0.9]      # one stopped car, every frame


class _SmokeRadio:
    def __init__(self):
        self.frames = []

    def send(self, frame):
        self.frames.append(frame)


class _SmokeClock:
    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        return self.t

    def wall_ms(self):
        return None                                   # no GNSS -> absolute_time degraded

    def gnss_lock(self):
        return False


class _SmokeStore:
    def __init__(self):
        self.entries = []
        self.w = -1

    def append(self, e):
        self.entries.append(e)

    def load(self):
        return self.entries

    def ack(self, s):
        self.w = s

    def acked(self):
        return self.w


_scal = {"H": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
         "roi": [[300.0, 500.0], [500.0, 500.0], [500.0, 700.0], [300.0, 700.0]]}
_srad = _SmokeRadio()
_sclk = _SmokeClock()
_sst = _SmokeStore()
_sapp = EdgeApp(derive_key(b"m" * 32, "IF4", "mpy"), "mpy",
                {"fw_ver": "t", "model_ver": "t", "calib_ver": "t"}, _scal,
                {"detector": _SmokeDetector(), "radio": _srad, "clock": _sclk, "store": _sst})
_sboot = _sapp.start()
check("app boot names its degraded capabilities",
      ("sign_readback" in _sboot["degraded"]) and ("absolute_time" in _sboot["degraded"]))
check("app boot record is CRITICAL when degraded", _sboot["severity"] == "CRITICAL")
_i = 0
while _i < 120:                                       # 12 s at 10 Hz; T_dwell 5.0 -> confirm at 5.0
    _sclk.t = round(_i * 0.1, 3)
    _sapp.step()
    _i += 1
check("app drives the sign after dwell (IF-4 frames transmitted)", len(_srad.frames) > 0)
# ~7 s of assertion at T_assert_refresh 0.5 s is ~15 frames. A per-tick transmit would be ~70 --
# five-fold over the ADR-0014 433 MHz duty budget, with the lamp looking identical.
check("app throttles IF-4 to T_assert_refresh, not the 10 Hz tick", len(_srad.frames) < 30)
check("app persists evidence to the durable store", len(_sst.entries) > 0)

print("-" * 60)
if _fails:
    print("mpy_smoke: %d CHECK(S) FAILED" % len(_fails))
    sys.exit(1)
print("mpy_smoke OK -- all esw modules load; perception + geometry + sink + command + the app loop run here.")
sys.exit(0)
