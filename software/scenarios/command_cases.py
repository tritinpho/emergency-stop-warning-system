# CMD-01.. -- Level-F executable spec for the authenticated IF-8/9/10 command channel
# (esw/command.py, ADR-0010, ADR-0012, ICD §5). Each case runs through the REAL loop with
# `auth_commands: True`, so the override / OTA / ack the state machine consumes come ONLY from
# command frames the edge CommandReceiver verified -- forged, replayed, and stale frames are
# rejected upstream and never reach the SM. The receive-side twin of SC-33/34 (the IF-4 sign-link).
#
# A checkpoint may assert the sign (`on`) / disposition as usual, plus `cmd_rejects` (how many
# frames the receiver rejected so far) and `cmd_last_reject` (auth | replay | stale | len | proto |
# payload) -- so a case pins WHICH guard fired, not merely that the attack had no effect.

_OVR_ON = {"action": "force_on", "issued": 2.0, "expiry": 60.0,
           "message_id": "STOPPED_VEHICLE_AHEAD", "reason": "ops-drill"}
_STOPPED_CAR = [{"id": "T1", "enter": 1.0, "leave": 40.0, "speed": 0.0, "in_roi": 1.0}]

COMMAND_CASES = [
    {
        "id": "CMD-01", "status": "impl",
        "title": "Valid override force-on lights an otherwise-dark sign",
        "duration": 8.0, "auth_commands": True, "tracks": [],
        "commands": [{"t": 2.0, "ctype": "override", "payload": _OVR_ON}],
        "checks": [{"t": 1.0, "on": False},                                    # before the command
                   {"t": 4.0, "on": True, "posture": "OVERRIDDEN", "override": "FORCE_ON"}],
    },
    {
        "id": "CMD-02", "status": "impl",
        "title": "Forged override cannot light the sign (auth)",
        "duration": 8.0, "auth_commands": True, "tracks": [],
        "inject_commands": [{"t": 2.0, "kind": "forged", "ctype": "override", "payload": _OVR_ON}],
        "checks": [{"t": 4.0, "on": False, "cmd_rejects": 1, "cmd_last_reject": "auth"}],
    },
    {
        "id": "CMD-03", "status": "impl",
        "title": "Replayed override frame is rejected (anti-replay)",
        "duration": 10.0, "auth_commands": True, "tracks": [],
        "commands": [{"t": 2.0, "ctype": "override", "payload": _OVR_ON}],
        "inject_commands": [{"t": 5.0, "kind": "replay"}],                     # re-send the captured frame
        "checks": [{"t": 4.0, "on": True, "override": "FORCE_ON"},             # genuine force-on active
                   {"t": 6.0, "on": True, "cmd_rejects": 1, "cmd_last_reject": "replay"}],
    },
    {
        "id": "CMD-04", "status": "impl",
        "title": "Stale override frame is rejected (freshness)",
        "duration": 9.0, "auth_commands": True, "tracks": [],
        # Genuine key, but a ts 7 s in the past at delivery (> 5 s replay window) -> stale, not auth.
        "inject_commands": [{"t": 7.0, "kind": "stale", "ctype": "override", "ts": 0.0, "payload": _OVR_ON}],
        "checks": [{"t": 8.0, "on": False, "cmd_rejects": 1, "cmd_last_reject": "stale"}],
    },
    {
        "id": "CMD-05", "status": "impl",
        "title": "Valid OTA request is deferred while a warning is active (IF-9)",
        "duration": 12.0, "auth_commands": True, "config_push": {"T_dwell": 3.0},
        "tracks": _STOPPED_CAR,
        "commands": [{"t": 7.0, "ctype": "ota", "payload": {}}],
        "checks": [{"t": 6.0, "on": True},                                     # warning up (dwell 3 s)
                   {"t": 8.0, "on": True, "ota_deferred": True}],              # OTA deferred behind it
    },
    {
        "id": "CMD-06", "status": "impl",
        "title": "Forged OTA request cannot trigger a deferral (auth)",
        "duration": 12.0, "auth_commands": True, "config_push": {"T_dwell": 3.0},
        "tracks": _STOPPED_CAR,
        "inject_commands": [{"t": 7.0, "kind": "forged", "ctype": "ota", "payload": {}}],
        "checks": [{"t": 8.0, "on": True, "ota_deferred": False,
                    "cmd_rejects": 1, "cmd_last_reject": "auth"}],
    },
    {
        "id": "CMD-07", "status": "impl",
        "title": "Valid operator ack freezes alarm re-escalation (IF-10 ack)",
        "duration": 26.0, "auth_commands": True,
        # Both sensors die -> sustained CRITICAL -> alarm 1 -> re-escalate 2; a verified ack of
        # count 2 freezes it (mirrors SC-32's ack half, delivered over the authenticated channel).
        "health_events": [{"t": 2.0, "health": {"camera": False, "radar": False}}],
        "tracks": _STOPPED_CAR,
        "commands": [{"t": 13.0, "ctype": "ack", "payload": {"count": 2}}],
        "checks": [{"t": 6.0, "alert": "CRITICAL", "alarm_count": 1},
                   {"t": 18.0, "alarm_count": 2},                              # re-escalated (unacked)
                   {"t": 24.0, "alarm_count": 2}],                             # ack froze the climb
    },
    {
        "id": "CMD-08", "status": "impl",
        "title": "Forged operator ack cannot silence alarms (auth, NFR-15)",
        "duration": 26.0, "auth_commands": True,
        # Same alarm ladder, but the ack is FORGED -> rejected -> the count keeps climbing, so an
        # attacker cannot mute the operator escalation.
        "health_events": [{"t": 2.0, "health": {"camera": False, "radar": False}}],
        "tracks": _STOPPED_CAR,
        "inject_commands": [{"t": 13.0, "kind": "forged", "ctype": "ack", "payload": {"count": 2}}],
        "checks": [{"t": 18.0, "alarm_count": 2},
                   {"t": 24.0, "alarm_count": 3, "cmd_last_reject": "auth"}],  # not frozen; forged ack caught
    },
]
