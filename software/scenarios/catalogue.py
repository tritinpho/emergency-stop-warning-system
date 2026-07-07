# SC-01..30 -- the shared, ID'd scenario catalogue from doc 07 §5.
# SC-31+ extend it with regression oracles found in code review (not in doc 07 §5).
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
        "id": "SC-03", "status": "impl",
        "title": "Creep-along-shoulder (< speed gate, not stopping) -> per dwell rule",
        "duration": 20.0,
        # Crawls at 2 kph -- below the 3 kph gate for the whole dwell, so the dwell
        # rule treats sustained sub-gate motion as stopped and confirms (doc 07 SC-03).
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 20.0, "speed": 2.0,
                    "in_roi": 1.0, "leave_speed": 12.0}],
        "checks": [{"t": 5.0, "on": False},   # still within T_dwell (enter@1 -> confirm ~6)
                   {"t": 8.0, "on": True},    # sub-gate creep confirmed per dwell rule
                   {"t": 15.0, "on": True}],
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
        "id": "SC-14", "status": "impl",
        "title": "Vehicle present at boot (cold start) -> new track, full dwell",
        "duration": 16.0,
        # Present from t=0: must be treated as a NEW track and serve the full dwell,
        # never assumed already-confirmed at boot (doc 07 SC-14).
        "tracks": [{"id": "T1", "enter": 0.0, "leave": 16.0, "speed": 0.0,
                    "in_roi": 1.0, "leave_speed": 12.0}],
        "checks": [{"t": 3.0, "on": False},   # before a full dwell from boot
                   {"t": 7.0, "on": True},    # confirmed after a full T_dwell (~5 s)
                   {"t": 14.0, "on": True}],
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

    # ---- config-clamp guard (SC-19): clamp_config wired into StateMachine.__init__ ----
    {
        "id": "SC-19", "status": "impl",
        "title": "Out-of-bounds config push (T_dwell=900 s) -> clamp per doc-02 7a",
        "duration": 16.0,
        "config_push": {"T_dwell": 900.0},          # clamped to 10 s (FR-20)
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 16.0, "speed": 0.0,
                    "in_roi": 1.0, "leave_speed": 12.0}],
        "checks": [{"t": 5.0, "on": False},
                   {"t": 14.0, "on": True}],        # ON iff T_dwell was clamped to 10 s
    },

    # ---- degraded modes, override, and the rest of the doc 07 §5 catalogue (all authored) ----
    {
        "id": "SC-06", "status": "impl",
        "title": "Sustained occlusion, radar corroborates -> CAMERA_OCCLUDED_DEGRADED",
        "duration": 22.0,
        # Confirmed car, then a long camera occlusion (gap) while radar keeps corroborating:
        # held (WARN_HOLD) up to T_occlusion, then -> CAMERA_OCCLUDED_DEGRADED (still ON +
        # investigate alert). T_degraded_max kept large -- this tests the *entry*, not the
        # forced clear (SC-07). Timers shrunk within FR-20 bounds for a fast run.
        "config_push": {"T_dwell": 3.0, "T_hold": 5.0, "T_occlusion": 8.0, "T_degraded_max": 60.0},
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 40.0, "speed": 0.0,
                    "in_roi": 1.0, "radar_visible": True, "gaps": [[6.0, 40.0]]}],
        "checks": [{"t": 5.0, "on": True, "state": "WARN_ON"},                    # confirmed, seen
                   {"t": 10.0, "on": True, "state": "WARN_HOLD"},                 # occluded < T_occlusion
                   {"t": 16.0, "on": True, "state": "CAMERA_OCCLUDED_DEGRADED",   # past T_occlusion
                    "alert": "DEGRADED"},
                   {"t": 20.0, "on": True, "state": "CAMERA_OCCLUDED_DEGRADED"}], # still held, bounded
    },
    {
        "id": "SC-07", "status": "impl",
        "title": "Sustained occlusion -> T_degraded_max forced loud clear",
        "duration": 30.0,
        # As SC-06 but T_degraded_max is short and the camera never re-acquires: at
        # T_degraded_max in CAMERA_OCCLUDED_DEGRADED the unit forces a loud low-confidence
        # clear (sign OFF) + max-severity escalation -- the one state the watchdog can't reach.
        "config_push": {"T_dwell": 3.0, "T_hold": 5.0, "T_occlusion": 8.0, "T_degraded_max": 10.0},
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 60.0, "speed": 0.0,
                    "in_roi": 1.0, "radar_visible": True, "gaps": [[6.0, 60.0]]}],
        "checks": [{"t": 16.0, "on": True, "state": "CAMERA_OCCLUDED_DEGRADED",
                    "alert": "DEGRADED"},
                   {"t": 22.0, "on": True, "state": "CAMERA_OCCLUDED_DEGRADED"},  # 22-14=8 < 10
                   {"t": 26.0, "on": False, "alert": "CRITICAL"},                 # forced clear + escalation
                   {"t": 29.0, "on": False}],
    },
    {
        "id": "SC-08", "status": "impl",
        "title": "Camera fault while warning active -> bounded camera-unverified hold",
        "duration": 32.0,
        # Warning up under FULL; the camera then FAULTS (RADAR-ONLY). The already-confirmed
        # track routes into the SAME bounded camera-unverified hold (ADR-0013 §A): held while
        # radar corroborates, bounded by T_degraded_max -> forced loud clear, and -- unlike
        # occlusion -- NO re-acquire (a dead camera cannot come back in software).
        "config_push": {"T_dwell": 3.0, "T_hold": 5.0, "T_occlusion": 8.0, "T_degraded_max": 10.0},
        "health_events": [{"t": 8.0, "health": {"camera": False, "radar": True}}],
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 60.0, "speed": 0.0,
                    "in_roi": 1.0, "radar_visible": True}],
        "checks": [{"t": 6.0, "on": True, "mode": "FULL"},               # warning active, healthy
                   {"t": 12.0, "on": True, "mode": "RADAR_ONLY"},        # camera dead -> bounded hold
                   {"t": 20.0, "on": True, "state": "CAMERA_OCCLUDED_DEGRADED"},
                   {"t": 28.0, "on": False},                             # forced clear, no re-acquire
                   {"t": 31.0, "on": False}],
    },
    {
        "id": "SC-09", "status": "impl",
        "title": "Weak-(b): radar corroborates the occluding truck -> stays bounded",
        "duration": 30.0,
        # Shoulder car confirmed, then camera-occluded by a through-lane truck. The car
        # departs (t=13) but the camera never sees the exit; under weak criterion (b) radar
        # mis-attributes the *truck's* return to the car's track (radar_ghosts) -> the warning
        # would be a stale-ON keyed to through-traffic. T_degraded_max still forces a loud
        # clear: the bound does NOT depend on criterion (b) being sound (R12 inversion guard).
        "config_push": {"T_dwell": 3.0, "T_hold": 5.0, "T_occlusion": 8.0, "T_degraded_max": 10.0},
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 13.0, "speed": 0.0,
                    "in_roi": 1.0, "radar_visible": True, "gaps": [[6.0, 13.0]]}],
        "radar_ghosts": [{"track_id": "T1", "from": 6.0, "to": 100.0}],
        "checks": [{"t": 16.0, "on": True, "state": "CAMERA_OCCLUDED_DEGRADED"},  # held on ghost corrob
                   {"t": 22.0, "on": True},
                   {"t": 26.0, "on": False, "alert": "CRITICAL"},                 # bounded, not indefinite
                   {"t": 29.0, "on": False}],
    },
    {
        "id": "SC-11", "status": "impl",
        "title": "Congestion / stop-and-go beside ROI -> no false-trigger (suppressed)",
        "duration": 16.0,
        # Stop-and-go jam: four stationary vehicles span the shoulder ROI (T-SH) and the
        # through lanes (T-L1..3, low in_roi). Fragile ROI geometry can't reliably separate a
        # shoulder breakdown from queued traffic, so the shoulder warning is SUPPRESSED (R14,
        # doc 02 §4): the machine still detects (state WARN_ON) but the sign stays OFF.
        "config_push": {"T_dwell": 3.0},
        "tracks": [{"id": "T-SH", "enter": 1.0, "leave": 16.0, "speed": 0.0, "in_roi": 1.0},
                   {"id": "T-L1", "enter": 1.0, "leave": 16.0, "speed": 0.0, "in_roi": 0.1},
                   {"id": "T-L2", "enter": 1.0, "leave": 16.0, "speed": 0.0, "in_roi": 0.1},
                   {"id": "T-L3", "enter": 1.0, "leave": 16.0, "speed": 0.0, "in_roi": 0.1}],
        "checks": [{"t": 8.0, "on": False, "state": "WARN_ON"},   # shoulder confirmed but suppressed
                   {"t": 14.0, "on": False}],                     # stays suppressed while the jam persists
    },
    {
        "id": "SC-12", "status": "impl",
        "title": "Pedestrian presence-onset incl. moving stranded occupant",
        "duration": 18.0,
        # A stranded occupant walks around the vehicle at 5 km/h -- ABOVE the 3 km/h stationarity
        # gate, so the vehicle dwell path would systematically miss them. The person warrant
        # fires on DEBOUNCED PRESENCE in/beside the ROI (T_person_debounce), camera-only (no
        # radar corroboration), and clears via the brief T_hold on departure (FR-08, ADR-0003).
        "config_push": {"T_person_debounce": 1.5, "T_hold": 5.0},
        "tracks": [{"id": "P1", "enter": 2.0, "leave": 10.0, "speed": 5.0, "in_roi": 1.0,
                    "cls": "person", "radar_visible": False}],
        "checks": [{"t": 2.5, "on": False},                      # present < T_person_debounce
                   {"t": 5.0, "on": True, "state": "WARN_ON"},   # presence-debounced warrant fires
                   {"t": 9.0, "on": True},                       # still present (moving, but present)
                   {"t": 17.0, "on": False}],                    # departed -> camera-only clear (T_hold)
    },
    {
        "id": "SC-13", "status": "impl",
        "title": "Stopped motorcycle (small RCS) -> camera-only persistence, no radar hold",
        "duration": 24.0,
        # A motorcycle has a negligible radar cross-section (radar_visible False), so it gets
        # NO radar-corroborated occlusion hold -- only the brief T_hold camera hysteresis
        # (ADR-0008 scope). Camera confirms it; on a sustained occlusion it clears at T_hold
        # (loud low-confidence clear), NOT the vehicle-grade CAMERA_OCCLUDED_DEGRADED.
        "config_push": {"T_dwell": 3.0, "T_hold": 5.0, "T_occlusion": 8.0},
        "tracks": [{"id": "M1", "enter": 1.0, "leave": 40.0, "speed": 0.0, "in_roi": 1.0,
                    "cls": "motorcycle", "radar_visible": False, "gaps": [[6.0, 40.0]]}],
        "checks": [{"t": 5.0, "on": True, "state": "WARN_ON"},   # camera confirmed
                   {"t": 8.0, "on": True, "state": "WARN_HOLD"}, # occluded, brief camera hysteresis
                   {"t": 13.0, "on": False}],                    # no radar -> clears at T_hold, not held
    },
    {
        "id": "SC-15", "status": "impl",
        "title": "Warm reboot during active warning -> blank during downtime, re-confirm",
        "duration": 26.0,
        # A vehicle is confirmed and warning; the edge box warm-reboots (Q7 re-exposure). During
        # downtime the SM is dead -> the dead-man's switch blanks the sign. On restart the SM
        # comes up IDLE and must RE-RUN the full dwell on the still-present vehicle (never assume
        # it was already confirmed) -> the warning returns only after a fresh T_dwell.
        "config_push": {"T_dwell": 5.0},
        "faults": [{"kind": "reboot", "t": 10.0, "downtime": 3.0}],
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 30.0, "speed": 0.0, "in_roi": 1.0}],
        "checks": [{"t": 8.0, "on": True},     # confirmed + warning before reboot
                   {"t": 12.5, "on": False},   # reboot downtime -> sign blanked (dead-man's switch)
                   {"t": 16.0, "on": False},   # back up but re-dwelling (fresh T_dwell from restart)
                   {"t": 20.0, "on": True}],   # re-confirmed -> warning restored
    },
    {
        "id": "SC-16", "status": "impl",
        "title": "Operator force-on, then kill edge box -> non-latching, blanks",
        "duration": 22.0,
        # Operator asserts a warning for an incident the detector cannot see (no track). The
        # force-on is carried by the SAME refreshed SHOW as autonomous warnings (ADR-0010 §3),
        # so killing the edge box blanks it within T_signhold -- it never latches over the WAN.
        "overrides": [{"issued": 2.0, "action": "force_on", "expiry": 60.0,
                       "message_id": "STOPPED_VEHICLE_AHEAD", "reason": "operator-observed incident"}],
        "faults": [{"t": 10.0, "kind": "kill_box"}],
        "checks": [{"t": 1.0, "on": False},                              # before the override
                   {"t": 6.0, "on": True, "posture": "OVERRIDDEN", "override": "FORCE_ON"},
                   {"t": 12.5, "on": False}],                            # box killed -> blanked (non-latching)
    },
    {
        "id": "SC-17", "status": "impl",
        "title": "Operator mute over a live hazard -> OVERRIDDEN, auto-expiry re-evaluates",
        "duration": 24.0,
        # A confirmed hazard is warning; the operator mutes (force-off). The sign blanks but
        # detection continues underneath (state stays WARN_ON -- operator-accepted exposure,
        # logged) and posture is OVERRIDDEN. The mute AUTO-EXPIRES (ADR-0010 §2); normal logic
        # resumes and -- the hazard still present -- the warning returns. A mute cannot persist.
        "overrides": [{"issued": 8.0, "action": "force_off", "expiry": 14.0, "reason": "maintenance"}],
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 30.0, "speed": 0.0, "in_roi": 1.0}],
        "checks": [{"t": 7.0, "on": True, "posture": "NORMAL"},          # autonomous warning up
                   {"t": 11.0, "on": False, "posture": "OVERRIDDEN",     # muted, but still detecting
                    "override": "FORCE_OFF", "state": "WARN_ON"},
                   {"t": 18.0, "on": True, "posture": "NORMAL"}],        # mute expired, hazard remains -> ON
    },
    {
        "id": "SC-18", "status": "impl",
        "title": "Out-of-policy override -> rejected / clamped at the unit (FR-20 mechanism)",
        "duration": 24.0,
        # Overrides are bounded like config (ADR-0010 §5). (1) A force-on with NO operator
        # reason is REJECTED -> sign stays OFF, posture NORMAL. (2) A later force-on whose
        # expiry exceeds the T_override_max ceiling is CLAMPED to issued+ceiling, so it
        # auto-expires on schedule. T_override_max shrunk to 6 s to make the clamp observable.
        "config_push": {"T_override_max": 6.0},
        "overrides": [
            {"issued": 2.0, "action": "force_on", "expiry": 60.0,
             "message_id": "STOPPED_VEHICLE_AHEAD", "reason": None},          # no reason -> reject
            {"issued": 10.0, "action": "force_on", "expiry": 1000.0,
             "message_id": "STOPPED_VEHICLE_AHEAD", "reason": "asserted"},    # huge expiry -> clamp to 16
        ],
        "checks": [{"t": 6.0, "on": False, "posture": "NORMAL",              # reason-less force-on rejected
                    "override_rejected": "no_reason"},
                   {"t": 13.0, "on": True, "posture": "OVERRIDDEN"},         # valid force-on, within clamp
                   {"t": 20.0, "on": False}],                               # clamped expiry (10+6=16) -> expired
    },
    {
        "id": "SC-20", "status": "impl",
        "title": "OTA / restart requested while warning active -> deferred, never silent-drop",
        "duration": 20.0,
        # A signed OTA (or restart) request arrives while a warning is ON. Applying it would drop
        # the warning mid-incident (a silent miss), so it is DEFERRED until the warning clears
        # (FR-21, ADR-0009): the sign stays ON and the deferral is flagged loud to ops.
        "ota_requests": [10.0],
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 30.0, "speed": 0.0, "in_roi": 1.0}],
        "checks": [{"t": 8.0, "on": True, "ota_deferred": False},   # warning up, no OTA yet
                   {"t": 12.0, "on": True, "ota_deferred": True},   # OTA requested -> deferred, still ON
                   {"t": 18.0, "on": True, "ota_deferred": True}],  # remains deferred while warning active
    },
    {
        "id": "SC-24", "status": "impl",
        "title": "CLEAR vs wedged-ON sign -> SAFE_STATE + sign-stuck escalation",
        "duration": 24.0,
        # The sign is a stuck-ON hardware fault (cannot blank). A car warns, then departs, so the
        # SM commands CLEAR -- but the IF-3 status read-back shows the sign still ON past
        # T_signhold. The one fault the dead-man's switch can't fix: the SM leaves CLEARING to
        # SAFE_STATE and raises a sign-stuck maintenance escalation (ADR-0013 §C.3).
        "sign_stuck": True,
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 12.0, "speed": 0.0,
                    "in_roi": 1.0, "leave_speed": 12.0}],
        "checks": [{"t": 8.0, "on": True, "state": "WARN_ON"},        # warning up
                   {"t": 20.0, "on": True, "state": "SAFE_STATE",     # car gone, sign stuck -> SAFE_STATE
                    "alert": "CRITICAL"}],
    },
    {
        "id": "SC-25", "status": "impl",
        "title": "Radar dead (CAMERA-ONLY) -> initiate OK, no occlusion hold",
        "duration": 16.0,
        # Radar down from boot. The camera alone still classifies + ROI-gates + tracks,
        # so a new stop is still confirmed; posture DEGRADED + alert (ADR-0009 §B).
        "health_events": [{"t": 0.0, "health": {"camera": True, "radar": False}}],
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 16.0, "speed": 0.0,
                    "in_roi": 1.0, "leave_speed": 12.0}],
        "checks": [{"t": 5.0, "on": False, "mode": "CAMERA_ONLY"},   # dwelling
                   {"t": 9.0, "on": True, "mode": "CAMERA_ONLY",     # initiated while degraded
                    "posture": "DEGRADED", "alert": "DEGRADED"},
                   {"t": 14.0, "on": True}],
    },
    {
        "id": "SC-26", "status": "impl",
        "title": "Camera dead idle (RADAR-ONLY) -> BLIND-TO-NEW, cannot initiate",
        "duration": 16.0,
        # Camera dead from boot, unit idle. A vehicle then stops: radar alone MUST NOT
        # initiate a confirm (no class, no image-ROI gate) and cannot even form a camera
        # track -> stays IDLE, never ON, CRITICAL alert (ADR-0009 §B BLIND-TO-NEW).
        "health_events": [{"t": 0.0, "health": {"camera": False, "radar": True}}],
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 16.0, "speed": 0.0, "in_roi": 1.0}],
        "checks": [{"t": 9.0, "on": False, "mode": "RADAR_ONLY", "alert": "CRITICAL"},
                   {"t": 14.0, "on": False, "mode": "RADAR_ONLY", "state": "IDLE"}],
    },
    {
        "id": "SC-27", "status": "impl",
        "title": "Both sensors dead -> SAFE_STATE (blank) + critical alert",
        "duration": 16.0,
        # A warning is up under FULL health; both sensors then die -> NEITHER forces
        # SAFE_STATE and the sign blanks within T_signhold (ADR-0009 §B / ADR-0013 matrix).
        "health_events": [{"t": 9.0, "health": {"camera": False, "radar": False}}],
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 16.0, "speed": 0.0, "in_roi": 1.0}],
        "checks": [{"t": 8.0, "on": True, "mode": "FULL"},           # warning active while healthy
                   {"t": 12.0, "on": False, "mode": "NEITHER",       # both dead -> blank + safe
                    "state": "SAFE_STATE", "alert": "CRITICAL"}],
    },
    {
        "id": "SC-28", "status": "impl",
        "title": "Watchdog: wedged logic, no corroboration -> clear + fault",
        "duration": 18.0,
        # A confirmed warning goes ON, then the camera detection FREEZES (stale/wedged) with
        # NO radar corroboration (radar_visible False -> small-RCS object radar can't hold).
        # The stuck frame keeps the sign asserted (stale-ON) but provides no FRESH evidence,
        # so after T_watchdog the watchdog clears it and raises a fault (ADR-0008 §4).
        "config_push": {"T_dwell": 3.0, "T_watchdog": 8.0},
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 14.0, "speed": 0.0, "in_roi": 1.0,
                    "radar_visible": False, "stale": [[6.0, 14.0]]}],
        "checks": [{"t": 5.0, "on": True, "state": "WARN_ON"},   # fresh warning
                   {"t": 12.0, "on": True},                      # wedged stale-ON, within T_watchdog
                   {"t": 16.0, "on": False, "alert": "CRITICAL"}],  # watchdog cleared + faulted
    },
    {
        "id": "SC-29", "status": "impl",
        "title": "Calibration-drift: inject synthetic homography shift -> degraded + alert",
        "duration": 16.0,
        # A synthetic homography shift is injected from t=4: the drift monitor sees the fixed
        # reference-point residual exceed tolerance and, past its debounce, marks the unit
        # DEGRADED and raises a calibration-drift alarm (FR-10, R15). The detection logic is
        # bench-testable; real pole-sway / thermal drift is field-deferred.
        "drift": [[4.0, 16.0]],
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 30.0, "speed": 0.0, "in_roi": 1.0}],
        "checks": [{"t": 3.0, "posture": "NORMAL"},                          # pre-drift, healthy
                   {"t": 8.0, "posture": "DEGRADED", "alert": "DEGRADED"}],  # drift debounced -> degraded
    },
    {
        "id": "SC-30", "status": "impl",
        "title": "Alarm dedup / priority / re-escalate-on-non-ack",
        "duration": 26.0,
        # A sustained CRITICAL condition (both sensors dead -> SAFE_STATE) must raise ONE alarm,
        # not a per-tick storm (dedup). With no operator ack modelled, the unacked critical
        # RE-ESCALATES once per re-escalate window (NFR-15, ADR-0011) -> alarm_count climbs
        # 1 -> 2 over time rather than exploding every tick.
        "health_events": [{"t": 2.0, "health": {"camera": False, "radar": False}}],
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 30.0, "speed": 0.0, "in_roi": 1.0}],
        "checks": [{"t": 6.0, "alert": "CRITICAL", "alarm_count": 1},    # one deduped alarm
                   {"t": 18.0, "alarm_count": 2}],                       # unacked -> re-escalated once
    },
    {
        "id": "SC-31", "status": "impl",
        "title": "Transient >gate blip on a confirmed car, then occlusion -> still HELD (no false clear)",
        "duration": 26.0,
        # Regression for the seen_leaving latch: a confirmed stopped car reads one brief
        # >gate blip while still in-ROI and camera-seen (a centroid jump / door-open /
        # fused Doppler tick), stops again, then a genuine camera occlusion with radar
        # still corroborating. The blip must NOT be remembered as an exit: the occlusion
        # HOLDS the warning (WARN_HOLD -> CAMERA_OCCLUDED_DEGRADED), never a fast clear.
        # Pre-fix this fast-cleared at occlusion onset (sign wrongly OFF).
        "config_push": {"T_dwell": 3.0, "T_hold": 5.0, "T_occlusion": 8.0, "T_degraded_max": 60.0},
        "tracks": [{"id": "T1", "enter": 1.0, "leave": 40.0, "speed": 0.0, "in_roi": 1.0,
                    "radar_visible": True,
                    "speed_windows": [[8.0, 8.3, 5.0]],   # brief >gate blip, still present
                    "gaps": [[12.0, 40.0]]}],             # genuine occlusion after the blip
        "checks": [{"t": 7.0, "on": True, "state": "WARN_ON"},                    # confirmed
                   {"t": 8.2, "on": True},                                        # blip, still present
                   {"t": 11.0, "on": True, "state": "WARN_ON"},                   # stopped again, seen
                   {"t": 16.0, "on": True, "state": "WARN_HOLD"},                 # occluded < T_occlusion
                   {"t": 22.0, "on": True, "state": "CAMERA_OCCLUDED_DEGRADED"}], # held, bounded
    },
]
