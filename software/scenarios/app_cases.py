# AP-01.. -- Level-H application cases: the REAL device loop (esw/app.py EdgeApp) driven by host
# backends. Where Level-G proves the adapter seam with an ad-hoc wiring, this proves the wiring
# ITSELF -- the object firmware/k230-detector/esw-app/main.py constructs and calls.
#
# What only this level can catch: an ordering bug between health, perception, the state machine and
# the actuator; a force-safe that fails to inhibit the refresh; a capability the unit lost SILENTLY
# because a backend was absent. The SC/PC/HM/CMD boards each test a component against its oracle;
# nothing tested that they were plugged together in the right order with the right authority.
#
# Objects are raw K230 YOLO boxes (xywh, inference-frame px) fed through scenarios.integration_cases
# .yolo_frame, so a case starts where the KPU's postprocess ends. Timing follows the §7a defaults:
# T_dwell 5.0 -> confirm, T_activate 2.0 -> lamp, T_hold 10.0 -> clear, T_signhold 2.0 -> blank.

from scenarios.integration_cases import COCO_LABELS

# The in-ROI stopped car every case reuses: xywh [360,520,80,80] -> ground (20 m, 30 m) under the
# shared affine CALIB, fully inside the shoulder ROI. Confirms at 6.0 s, lamp by 8.0 s.
_CAR = {"cls_id": 2, "score": 0.90, "xywh": [360, 520, 80, 80], "enter": 1.0, "leave": 60.0}


def _car(leave=60.0):
    d = dict(_CAR)
    d["leave"] = leave
    return d


CASES = [
    {
        "id": "AP-01", "title": "stopped car -> whole app chain lights an AUTHENTICATED sign",
        "duration": 12.0, "objects": [_car()],
        # Every frame the lamp obeys was HMAC-signed by the real actuator and verified by the real
        # dead-man's switch. A wiring bug anywhere in the chain shows up as a lamp that never lights.
        "checks": [{"t": 3.0, "on": False},      # mid-dwell
                   {"t": 10.0, "on": True}],     # confirmed + activated
        "boot": {"degraded": [], "sees_person": True, "per_class_footprint": True},
    },
    {
        "id": "AP-02", "title": "camera dies while warning -> NEITHER -> sign blanks (fail-safe)",
        "duration": 18.0, "objects": [_car()],
        # The bench build is camera-only (ADR-0001 Rejected): no radar can hold the warning up, so a
        # dead camera is NEITHER, not RADAR_ONLY. The warning must drop rather than persist unverified.
        "blind": [[12.0, 99.0]],
        "checks": [{"t": 10.0, "on": True},
                   {"t": 15.0, "on": False}],
    },
    {
        "id": "AP-03", "title": "the loop itself dies -> sign blanks within T_signhold (no off command)",
        "duration": 18.0, "objects": [_car()],
        # step() simply stops being called. Nothing sends a CLEAR, because there is no CLEAR to send:
        # the sign blanks because refreshes stopped arriving. This is the invariant, exercised end to end.
        "stop_at": 12.0,
        "checks": [{"t": 11.9, "on": True},
                   {"t": 15.0, "on": False}],    # 12.0 + T_signhold(2.0), with margin
    },
    {
        "id": "AP-04", "title": "self-test fails -> force-safe blanks the lamp while the SM still asserts",
        "duration": 16.0, "objects": [_car()],
        # IF-5: the health monitor's independent force-safe inhibits the refresh WITHOUT routing
        # through the state machine, which goes on asserting SHOW. Both facts are checked.
        "selftest_fail": [[12.0, 99.0]],
        "checks": [{"t": 10.0, "on": True},
                   {"t": 15.0, "on": False, "assertion": "SHOW"}],
    },
    {
        "id": "AP-05", "title": "single-class model -> car still lights, blindness reported CRITICAL",
        "duration": 12.0, "objects": [{"cls_id": 0, "score": 0.90, "xywh": [360, 520, 80, 80],
                                       "enter": 1.0, "leave": 60.0}],
        # labels = ["vehicle"]: the lamp behaves identically, so NOTHING downstream looks broken --
        # while SC-12 has become unreachable and truck/bus have collapsed onto the car footprint.
        # ADR-0005 forbids that being silent, so the boot record must name both losses.
        "labels": ["vehicle"],
        "checks": [{"t": 10.0, "on": True}],
        "boot": {"degraded": ["sees_person", "per_class_footprint"],
                 "sees_person": False, "per_class_footprint": False, "severity": "CRITICAL"},
    },
    {
        "id": "AP-06", "title": "sign wedged ON + IF-3 read-back -> SAFE_STATE escalation (SC-24)",
        "duration": 32.0, "objects": [_car(leave=12.0)],
        # The one fault the dead-man's switch cannot fix: the lamp is physically stuck. Only a
        # read-back can see it. Car leaves at 12 -> confirmed exit -> T_hold(10) -> commanded OFF
        # at ~22 -> wedged lamp -> SAFE_STATE at ~22 + T_signhold(2) + grace(0.5).
        "sign_stuck": True,
        "checks": [{"t": 10.0, "on": True},
                   {"t": 30.0, "state": "SAFE_STATE"}],
    },
    {
        "id": "AP-07", "title": "no IF-3 read-back -> the same wedged lamp is UNDETECTABLE, reported so",
        "duration": 32.0, "objects": [_car(leave=12.0)],
        # The control for AP-06. Identical fault, read-back removed: the SM cannot reach SAFE_STATE,
        # because it has no way to know. That is not a bug -- it is a lost capability, and the boot
        # record is the only thing standing between it and a silent one.
        "sign_stuck": True, "sign_readback": False,
        # The lamp is still physically lit at t=30 while the state machine has gone back to IDLE.
        # Nothing in the unit is wrong; the unit simply cannot see. Compare AP-06.
        "checks": [{"t": 30.0, "on": True, "state": "IDLE", "state_not": "SAFE_STATE"}],
        "boot": {"degraded": ["sign_readback"], "severity": "CRITICAL"},
    },
    {
        "id": "AP-08", "title": "no GNSS -> lamp still driven (edge-synced), absolute_time reported degraded",
        "duration": 12.0, "objects": [_car()],
        # A drifting clock does not make a stopped car safe (SC-36), so the unit must NOT blank. It
        # falls back to the tick clock for the IF-4 freshness stamp, which only works against a
        # controller in edge-synced / persistent-seq mode (doc 10 "Time") -- hence the loud report.
        "absolute_time": False, "gnss": False,
        "checks": [{"t": 10.0, "on": True}],
        "boot": {"degraded": ["absolute_time"], "severity": "CRITICAL"},
    },
    {
        "id": "AP-09", "title": "runtime config push (IF-8) reaches the live loop: T_dwell 5 -> 3",
        "duration": 8.0, "objects": [_car()],
        # Proves the command backend is wired into the TICK, not just into a test fixture. The car
        # arrives at 1.0, so the default T_dwell 5.0 confirms at 6.0 and a pushed 3.0 confirms at
        # 4.0. t=4.5 is the only kind of instant that can tell those apart: the lamp lights on
        # confirm (T_activate is the NFR-01 latency ceiling, not an added delay), so any checkpoint
        # after 6.1 s is lit either way and proves nothing. The control below pins that.
        "config_push": [[0.5, {"T_dwell": 3.0}]],
        "checks": [{"t": 4.5, "on": True}],
    },
    {
        "id": "AP-11", "title": "IF-4 refreshes at T_assert_refresh (0.5 s), not at the 10 Hz tick",
        "duration": 16.0, "objects": [_car()],
        # The sim can afford to re-transmit every tick; a real bearer cannot. At 10 Hz the ADR-0014
        # 433 MHz duty budget is exceeded five-fold. The lamp is lit from ~6.1 s to 16.0 s (~9.9 s),
        # so ~20 refreshes at 2 Hz -- not the ~99 a per-tick transmit would send. `tx_max` is the
        # regression guard: the dead-man's window only ever needed a 4x margin.
        "checks": [{"t": 15.0, "on": True}],
        "tx_min": 15, "tx_max": 25,
    },
]

# AP-09's non-vacuity control: the SAME case with no push must be dark at 4.5 s, and lit later --
# so the case is discriminating the push, not merely observing that the sign eventually works.
CONTROL_AP09 = {
    "id": "AP-09c", "title": "(control) no push -> dark at 4.5 s, lit by 6.5 s",
    "duration": 8.0, "objects": [_car()],
    "checks": [{"t": 4.5, "on": False}, {"t": 6.5, "on": True}],
}

# The evidence case is scored by the board, not by sign checkpoints: it runs a warning to completion,
# kills the unit, and rebuilds an EdgeApp over the SAME durable store -- the reboot-survival the
# acceptance-evidence spine (ADR-0007, doc 01 §5) rests on. Bench-hours that vanish on a power blip
# are not bench-hours.
EVIDENCE_CASE = {
    "id": "AP-10", "title": "evidence survives a reboot: activation durable, outbox resumes, dets captured",
    "duration": 12.0, "objects": [_car()],
}

LABELS = COCO_LABELS
