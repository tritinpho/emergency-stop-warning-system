# SC-01..30 -- the shared, ID'd scenario catalogue from doc 07 §5.
#
# This IS the executable specification of the state machine (ADR-0015): the code
# is correct when its sign-over-time matches every scenario's oracle. Each entry:
#   status "impl"  -> authored timeline + oracle; expected to PASS
#          "xfail" -> authored; expected to FAIL until a named TODO is implemented
#          "todo"  -> registered from doc 07 but not yet authored (the backlog)
#
# `checks` are oracle checkpoints: {"t": seconds, "on": expected sign state}.
# Grow the harness/SUT to move `todo` -> `impl`; see README.md.

SCENARIOS = [
    # ---- implemented (expected green) ----
    {
        "id": "SC-01", "status": "impl",
        "title": "Stop -> dwell -> warn -> depart -> clear (happy path)",
        "duration": 25.0,
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 20.0, "speed": 0.0,
                    "in_roi": 1.0, "leave_speed": 12.0, "exit_window": 1.5}],
        "checks": [{"t": 3.0, "on": False},   # dwelling, not yet confirmed
                   {"t": 9.0, "on": True},    # confirmed (~6 s) + activated
                   {"t": 15.0, "on": True},   # still present
                   {"t": 24.0, "on": False}], # cleared after confirmed exit
    },
    {
        "id": "SC-02", "status": "impl",
        "title": "Transient pass-through along shoulder (never stops)",
        "duration": 8.0,
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 6.0, "speed": 20.0, "in_roi": 1.0}],
        "checks": [{"t": 3.0, "on": False}, {"t": 5.0, "on": False}, {"t": 7.0, "on": False}],
    },
    {
        "id": "SC-04", "status": "impl",
        "title": "Dwell sweep -- confirm only after T_dwell",
        "duration": 20.0,
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 20.0, "speed": 0.0,
                    "in_roi": 1.0, "leave_speed": 12.0}],
        "checks": [{"t": 5.0, "on": False},   # before T_dwell (5 s from enter@1 -> ~6)
                   {"t": 8.0, "on": True}, {"t": 15.0, "on": True}],
    },
    {
        "id": "SC-05", "status": "impl",
        "title": "Brief occlusion (< T_hold) -- stays ON, no flap",
        "duration": 30.0,
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 25.0, "speed": 0.0, "in_roi": 1.0,
                    "leave_speed": 12.0, "gaps": [[9.0, 12.0]]}],
        "checks": [{"t": 8.0, "on": True},    # confirmed before the gap
                   {"t": 10.5, "on": True},   # occluded (< T_hold) -> held ON
                   {"t": 14.0, "on": True},   # re-acquired
                   {"t": 28.0, "on": False}], # cleared after exit
    },
    {
        "id": "SC-10", "status": "impl",
        "title": "Multi-vehicle arrive/leave -- ON while set non-empty",
        "duration": 30.0,
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 15.0, "speed": 0.0,
                    "in_roi": 1.0, "leave_speed": 12.0},
                   {"id": "T2", "enter": 8.0, "leave": 26.0, "speed": 0.0,
                    "in_roi": 1.0, "leave_speed": 12.0}],
        "checks": [{"t": 7.0, "on": True},    # T1 confirmed
                   {"t": 14.0, "on": True},   # both present
                   {"t": 20.0, "on": True},   # T1 gone, T2 holds it ON (no early clear)
                   {"t": 29.0, "on": False}], # both gone -> cleared
    },
    {
        "id": "SC-21", "status": "impl",
        "title": "Fault-inject: kill SM process -> sign blanks <= T_signhold",
        "duration": 20.0,
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 20.0, "speed": 0.0, "in_roi": 1.0}],
        "faults": [{"t": 10.0, "kind": "kill_sm"}],
        "checks": [{"t": 8.0, "on": True},    # warning up
                   {"t": 12.5, "on": False}], # blanked within T_signhold (2 s) of the kill
    },
    {
        "id": "SC-22", "status": "impl",
        "title": "Fault-inject: kill edge box -> sign-controller blanks <= T_signhold",
        "duration": 20.0,
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 20.0, "speed": 0.0, "in_roi": 1.0}],
        "faults": [{"t": 10.0, "kind": "kill_box"}],
        "checks": [{"t": 8.0, "on": True}, {"t": 12.5, "on": False}],
    },
    {
        "id": "SC-23", "status": "impl",
        "title": "Fault-inject: cut sign link -> sign-controller blanks <= T_signhold",
        "duration": 20.0,
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 20.0, "speed": 0.0, "in_roi": 1.0}],
        "faults": [{"t": 10.0, "kind": "cut_link"}],
        "checks": [{"t": 8.0, "on": True}, {"t": 12.5, "on": False}],
    },

    # ---- intentional red: the first TDD target (see README) ----
    {
        "id": "SC-19", "status": "xfail",
        "title": "Out-of-bounds config push (T_dwell=900 s) -> clamp per doc-02 7a",
        "reason": "SUT does not yet clamp config; wire esw.params.clamp_config in StateMachine.__init__",
        "duration": 16.0,
        "config_push": {"T_dwell": 900.0},          # must be clamped to 10 s (FR-20)
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 16.0, "speed": 0.0,
                    "in_roi": 1.0, "leave_speed": 12.0}],
        "checks": [{"t": 5.0, "on": False},
                   {"t": 14.0, "on": True}],        # ON iff T_dwell was clamped to 10 s
    },

    # ---- registered from doc 07 §5 but not yet authored (the backlog) ----
    {"id": "SC-03", "status": "todo", "title": "Creep-along-shoulder (< speed gate, not stopping)"},
    {"id": "SC-06", "status": "todo", "title": "Sustained occlusion, radar corroborates -> CAMERA_OCCLUDED_DEGRADED"},
    {"id": "SC-07", "status": "todo", "title": "Sustained occlusion -> T_degraded_max forced loud clear"},
    {"id": "SC-08", "status": "todo", "title": "Camera fault while warning active -> bounded camera-unverified hold"},
    {"id": "SC-09", "status": "todo", "title": "Weak-(b): radar corroborates the occluding truck -> stays bounded"},
    {"id": "SC-11", "status": "todo", "title": "Congestion / stop-and-go beside ROI -> no false-trigger"},
    {"id": "SC-12", "status": "todo", "title": "Pedestrian presence-onset incl. moving stranded occupant"},
    {"id": "SC-13", "status": "todo", "title": "Stopped motorcycle (small RCS)"},
    {"id": "SC-14", "status": "todo", "title": "Vehicle present at boot (cold start) -> new track, full dwell"},
    {"id": "SC-15", "status": "todo", "title": "Warm reboot during active warning (re-exposure, Q7)"},
    {"id": "SC-16", "status": "todo", "title": "Operator force-on, then kill edge box / expiry"},
    {"id": "SC-17", "status": "todo", "title": "Operator force-off / mute -> auto-expiry"},
    {"id": "SC-18", "status": "todo", "title": "Out-of-policy override -> rejected/clamped"},
    {"id": "SC-20", "status": "todo", "title": "OTA / restart requested while warning active -> deferred"},
    {"id": "SC-24", "status": "todo", "title": "CLEAR vs wedged-ON sign -> SAFE_STATE + escalation"},
    {"id": "SC-25", "status": "todo", "title": "Radar dead (CAMERA-ONLY) -> initiate OK, no occlusion hold"},
    {"id": "SC-26", "status": "todo", "title": "Camera dead idle (RADAR-ONLY) -> BLIND-TO-NEW"},
    {"id": "SC-27", "status": "todo", "title": "Both sensors dead -> SAFE_STATE + critical alert"},
    {"id": "SC-28", "status": "todo", "title": "Watchdog: wedged logic, no corroboration -> clear + fault"},
    {"id": "SC-29", "status": "todo", "title": "Calibration-drift: inject synthetic homography shift"},
    {"id": "SC-30", "status": "todo", "title": "Alarm dedup / priority / re-escalate-on-non-ack"},
]
