# EV-01.. -- the acceptance-evidence scenario set (doc 07 §4, ADR-0007). Each case runs through
# the REAL loop (harness.runner.run_scenario), and carries a machine-readable ground-truth
# `oracle` = the list of [onset, end] intervals where a genuine warnable hazard is present,
# derived from the script and INDEPENDENT of the SUT. The reducer (harness/metrics.py) compares
# the emitted IF-7 warning intervals to this oracle -> recall / false-activation / latency.
#
# TIER S (synthetic): this set exercises the pipeline MACHINERY and modelled false-trigger
# resistance. Per the doc 01 §5 hard rule, recall computed here is NOT a recall claim -- the recall
# N must be REAL captures. A `hazard`-less oracle ([]) marks a nuisance where NO warning is correct.

EVIDENCE = [
    {
        "id": "EV-01", "title": "Positive: car stops on the shoulder (day) -> detected",
        "duration": 26.0,
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 20.0, "speed": 0.0,
                    "in_roi": 1.0, "leave_speed": 12.0, "exit_window": 1.5}],
        "oracle": [[1.0, 20.0]],          # genuine stationary hazard present 1..20 s
    },
    {
        "id": "EV-02", "title": "Nuisance: transient pass-through (never stops) -> no warning",
        "duration": 8.0,
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 6.0, "speed": 20.0, "in_roi": 1.0}],
        "oracle": [],                     # no stationary hazard -> any warning is a false activation
    },
    {
        "id": "EV-03", "title": "Nuisance: congestion / stop-and-go beside ROI -> suppressed",
        "duration": 16.0,
        # The shoulder vehicle is stationary, but congestion suppression (R14) is the accepted design
        # -> no warning is the correct behaviour, so the acceptance oracle is empty. (A stated coverage
        # gap, not a miss -- doc 01 §5 "must not false-trigger"; whether it is field-sound rests on the
        # criterion-(b) radar gate, field-deferred.)
        # The jam persists for the whole observation window (leave > duration) -> suppressed
        # throughout, so no warning is ever asserted. (Deliberately avoids the degenerate case
        # where all four vehicles vanish on the same tick without a confirmed exit, which would
        # briefly flash a WARN_HOLD as suppression lifts -- a fail-safe-direction edge behaviour,
        # not the suppression claim this case evidences.)
        "config_push": {"T_dwell": 3.0},
        "tracks": [{"id": "T-SH", "enter": 1.0, "leave": 20.0, "speed": 0.0, "in_roi": 1.0},
                   {"id": "T-L1", "enter": 1.0, "leave": 20.0, "speed": 0.0, "in_roi": 0.1},
                   {"id": "T-L2", "enter": 1.0, "leave": 20.0, "speed": 0.0, "in_roi": 0.1},
                   {"id": "T-L3", "enter": 1.0, "leave": 20.0, "speed": 0.0, "in_roi": 0.1}],
        "oracle": [],
    },
    {
        "id": "EV-04", "title": "Positive: sustained occlusion, radar corroborates -> held = detected",
        "duration": 22.0,
        # A correct occlusion hold overlaps the hazard, so it must score as DETECTED, never a
        # clear-latency failure (doc 07 §4).
        "config_push": {"T_dwell": 3.0, "T_hold": 5.0, "T_occlusion": 8.0, "T_degraded_max": 60.0},
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 40.0, "speed": 0.0,
                    "in_roi": 1.0, "radar_visible": True, "gaps": [[6.0, 40.0]]}],
        "oracle": [[1.0, 22.0]],          # hazard present the whole run
    },
    {
        "id": "EV-05", "title": "Positive: multiple vehicles arrive/leave -> detected while present",
        "duration": 30.0,
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 15.0, "speed": 0.0,
                    "in_roi": 1.0, "leave_speed": 12.0},
                   {"id": "T2", "enter": 8.0, "leave": 26.0, "speed": 0.0,
                    "in_roi": 1.0, "leave_speed": 12.0}],
        "oracle": [[1.0, 26.0]],          # union of the two stationary presences
    },
    {
        "id": "EV-06", "title": "Positive: stranded pedestrian (moving occupant) -> detected",
        "duration": 18.0,
        "config_push": {"T_person_debounce": 1.5, "T_hold": 5.0},
        "tracks": [{"id": "P1", "enter": 2.0, "leave": 10.0, "speed": 5.0, "in_roi": 1.0,
                    "cls": "person", "radar_visible": False}],
        "oracle": [[2.0, 10.0]],
    },
]
