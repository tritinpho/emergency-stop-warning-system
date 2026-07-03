# Decision state machine -- the safety loop's "brain" (doc 02 §4, ADR-0008/0013).
#
# EXECUTION MODEL (ADR-0015): fixed-rate tick. The harness/target calls tick()
# every cycle (e.g. 10 Hz) with (now, observations, health); the machine
# recomputes the SET of confirmed-stopped in-ROI tracks atomically and returns
# the sign assertion for this tick. Timers are evaluated as deadlines against
# `now` -- no wall-clock is read inside here (determinism; doc 07 §8).
#
# EXECUTABLE SPEC (ADR-0015): behaviour is defined by the SC-01..30 oracles in
# scenarios/catalogue.py. Grow this file to turn `todo` scenarios green; the
# `# TODO(SC-xx)` markers below map each gap to the scenario that will prove it.
#
# This is the SUT: byte-identical in sim and on the K230. MicroPython-safe subset.

from esw.params import default_config

# Warning-lifecycle states (doc 02 §4 diagram).
IDLE = "IDLE"
TRACKING = "TRACKING"
CONFIRMED = "CONFIRMED"
WARN_ON = "WARN_ON"
WARN_HOLD = "WARN_HOLD"
CAMERA_OCCLUDED_DEGRADED = "CAMERA_OCCLUDED_DEGRADED"
CLEARING = "CLEARING"
SAFE_STATE = "SAFE_STATE"

# Sensor-health mode -- the orthogonal region (doc 02 §4 matrix, ADR-0013 §B).
FULL = "FULL"
CAMERA_ONLY = "CAMERA_ONLY"
RADAR_ONLY = "RADAR_ONLY"
NEITHER = "NEITHER"

MESSAGE_STOPPED = "STOPPED_VEHICLE_AHEAD"  # message_id; QCVN-41 set is ADR-0004


class StateMachine:
    def __init__(self, config=None):
        # NOTE(SC-19, TODO): config is used raw. Wire esw.params.clamp_config here
        # to enforce the FR-20 bounds -- that turns SC-19 (out-of-bounds push) green.
        self.cfg = config if config is not None else default_config()
        self.state = IDLE
        self.mode = FULL
        # track_id -> per-track record
        self.tracks = {}

    def _mode(self, health):
        cam = health.get("camera", True)
        rad = health.get("radar", True)
        if cam and rad:
            return FULL
        if cam and not rad:
            return CAMERA_ONLY
        if rad and not cam:
            return RADAR_ONLY
        return NEITHER

    def _new_track(self, now, speed):
        return {"stationary_since": None, "confirmed": False,
                "absent_since": None, "seen_leaving": False, "last_speed": speed}

    def tick(self, now, observations, health=None):
        """One fixed-rate cycle. Returns a decision dict:
        {assertion: "SHOW"|"NONE", message_id, state, posture, mode}."""
        if health is None:
            health = {"camera": True, "radar": True}
        self.mode = self._mode(health)
        cfg = self.cfg
        gate = cfg["speed_gate_kph"]
        roi_gate = cfg["roi_overlap_gate"]

        # NEITHER sensor -> unconditional safe state (doc 02 §4 matrix bottom row).
        # TODO(SC-25/26/27): the CAMERA_ONLY / RADAR_ONLY cells (degraded+alert,
        # BLIND-TO-NEW, bounded camera-unverified hold) are not modelled yet.
        if self.mode == NEITHER:
            self.state = SAFE_STATE
            return self._decision("NONE")

        seen = set()
        for o in observations:
            if o.get("in_roi", 0.0) < roi_gate:
                continue  # ROI gating: footprint overlap must clear the gate
            tid = o["track_id"]
            speed = o.get("speed_kph", 0.0)
            seen.add(tid)
            tr = self.tracks.get(tid)
            if tr is None:
                tr = self._new_track(now, speed)
                self.tracks[tid] = tr
            tr["absent_since"] = None
            tr["last_speed"] = speed
            if speed < gate:
                if tr["stationary_since"] is None:
                    tr["stationary_since"] = now
                if not tr["confirmed"] and (now - tr["stationary_since"]) >= cfg["T_dwell"]:
                    tr["confirmed"] = True  # dwell satisfied -> confirmed-stopped
            else:
                tr["stationary_since"] = None
                if tr["confirmed"]:
                    tr["seen_leaving"] = True  # moving while confirmed = observed exit

        # Tracks not seen this tick: distinguish confirmed-exit from lost-in-place.
        for tid in list(self.tracks.keys()):
            tr = self.tracks[tid]
            if tid in seen:
                continue
            if tr["absent_since"] is None:
                tr["absent_since"] = now
            absent = now - tr["absent_since"]
            if tr["confirmed"] and tr["seen_leaving"]:
                del self.tracks[tid]                      # confirmed exit -> fast clear
            elif absent >= cfg["T_hold"]:
                del self.tracks[tid]                      # lost, no corroboration -> clear
            # else: within T_hold -> keep (brief hysteresis / occlusion hold)
            # TODO(SC-06/07/08/09): once radar corroboration is modelled, a lost-in-place
            # confirmed track past T_occlusion (radar still corroborating) must enter
            # CAMERA_OCCLUDED_DEGRADED bounded by T_degraded_max, not silently clear.

        present = False
        held = False
        for tr in self.tracks.values():
            if tr["confirmed"]:
                if tr["absent_since"] is None:
                    present = True
                else:
                    held = True

        # TODO(SC-28): watchdog. Bound any WARN_* by T_watchdog when no channel
        # confirms/corroborates -> clear + FAULT. Absent here on purpose: SC-28 is
        # the intentional red test in the scaffold.
        # TODO(SC-11): congestion suppression (multiple stationary through-lane tracks).
        # TODO(SC-12): pedestrian presence-onset (T_person_debounce, not the speed gate).
        # TODO(SC-16/17/18): operator override (non-latching, auto-expiry).

        if present:
            self.state = WARN_ON
        elif held:
            self.state = WARN_HOLD
        elif self.state in (WARN_ON, WARN_HOLD, CAMERA_OCCLUDED_DEGRADED):
            self.state = CLEARING
        elif self.state == CLEARING:
            self.state = IDLE
        elif self.tracks:
            self.state = TRACKING
        else:
            self.state = IDLE

        asserting = self.state in (WARN_ON, WARN_HOLD, CAMERA_OCCLUDED_DEGRADED)
        return self._decision("SHOW" if asserting else "NONE")

    def _decision(self, assertion):
        return {"assertion": assertion, "message_id": MESSAGE_STOPPED,
                "state": self.state, "posture": ("NORMAL" if self.mode == FULL else "DEGRADED"),
                "mode": self.mode}
