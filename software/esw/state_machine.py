# Decision state machine -- the safety loop's "brain" (doc 02 §4, ADR-0008/0013).
#
# EXECUTION MODEL (ADR-0015): fixed-rate tick. The harness/target calls tick()
# every cycle (e.g. 10 Hz) with (now, observations, health); the machine
# recomputes the SET of confirmed-stopped in-ROI tracks atomically and returns
# the sign assertion for this tick. Timers are evaluated as deadlines against
# `now` -- no wall-clock is read inside here (determinism; doc 07 §8).
#
# EXECUTABLE SPEC (ADR-0015): behaviour is defined by the SC-NN oracles in
# scenarios/catalogue.py -- the code is correct when its sign/disposition-over-time
# matches every oracle. All are green (python run_tests.py -> exit 0).
#
# This is the SUT: byte-identical in sim and on the K230. MicroPython-safe subset.

from esw.params import default_config, clamp_config, clamp_update, cfg_fingerprint

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

# Operator-alert severity ladder (ADR-0011): None/NONE < DEGRADED < CRITICAL.
_ALERT_RANK = {None: 0, "NONE": 0, "DEGRADED": 1, "CRITICAL": 2}

# The congestion threshold (R14), alarm re-escalation window (NFR-15), drift debounce (FR-10),
# and sign-stuck grace (ADR-0013 §C.3) all live in the doc 02 §7a surface now (esw/params.py:
# congestion_min_tracks / T_reescalate / T_drift_debounce / T_sign_stuck_grace) -- bounded,
# clamped, boot-only -- so "nothing safety-relevant is tunable outside the table" stays true.


def _max_alert(a, b):
    """Return the higher-severity of two alert levels."""
    return a if _ALERT_RANK.get(a, 0) >= _ALERT_RANK.get(b, 0) else b


class StateMachine:
    def __init__(self, config=None):
        # FR-20 (doc 02 §7a): a pushed config is clamped to its [lo, hi] bounds so no
        # value can defeat a safety invariant -- e.g. T_dwell=900 s clamps to 10 s (SC-19).
        # Rejected names are retained for the fail-loud config-rejected report (FR-21).
        if config is None:
            self.cfg = default_config()
            self.rejected_cfg = []
        else:
            self.cfg, self.rejected_cfg = clamp_config(config)
        # R10 audit binding: fingerprint the config ACTUALLY IN FORCE (post-clamp), and
        # recompute on every runtime push (apply_config) so IF-4 frames and IF-6/7 records
        # never stamp a stale cfg_ver after a live reconfiguration.
        self.cfg_ver = cfg_fingerprint(self.cfg)
        self.state = IDLE
        self.mode = FULL
        self.escalation = None        # latched max-severity escalation (e.g. forced clear)
        self.config_rejected = None   # latched fail-loud report of the last runtime config push (FR-21)
        self.override_active = None    # applied operator override this tick (IF-10, ADR-0010)
        self.override_rejected = None  # reason an override was rejected/clamped, if any
        self.warn_evidence_since = None  # last tick a warning had FRESH evidence (watchdog)
        self.clear_since = None          # when the SM last commanded OFF but read-back was ON
        self.ota_deferred = False        # an OTA/restart is deferred behind an active warning
        self.drift_since = None          # onset of a calibration-drift residual (debounce)
        self.drift_degraded = False      # drift monitor has marked the unit degraded
        self.time_degraded = False       # health monitor reports absolute time untrustworthy (NFR-16)
        self.alarm_count = 0             # deduped alarm count (raise once + re-escalate)
        self.alarm_since = None          # when the current CRITICAL alarm was (re-)raised
        self.alarm_acked = False         # operator ack'd the current alarm epoch (freezes re-escalate)
        self._now = 0.0                  # this tick's time, cached for _decision
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

    def _new_track(self, speed):
        return {"stationary_since": None, "person_since": None, "confirmed": False,
                "absent_since": None, "degraded_since": None, "stale_now": False,
                "seen_leaving": False, "suppressed_last_seen": False,
                "last_speed": speed, "radar_last": None}

    def apply_config(self, partial):
        """Merge a runtime IF-8 config push into the LIVE config (clamp_update: §7a-clamped, with
        the bounded safety backstops refused as boot-only). Latches the fail-loud rejected/adjusted
        set for the decision report (FR-21). Mutates self.cfg in place so shared readers stay valid,
        and re-fingerprints cfg_ver so subsequent frames/audit records bind to the live config."""
        accepted, rejected = clamp_update(partial)
        for name in accepted:
            self.cfg[name] = accepted[name]
        if accepted:
            self.cfg_ver = cfg_fingerprint(self.cfg)
        self.config_rejected = rejected if rejected else None

    def tick(self, now, observations, health=None, override=None, inputs=None):
        """One fixed-rate cycle. Returns a decision dict: {assertion: "SHOW"|"NONE",
        message_id, state, posture, mode, alert, override, override_rejected, ota_deferred,
        alarm_count}. `inputs` carries the non-IF-2 channels: {sign_status (IF-3 read-back),
        ota (IF-9 request), drift (FR-10 monitor)}."""
        if health is None:
            health = {"camera": True, "radar": True}
        if inputs is None:
            inputs = {}
        self._now = now
        self.override_active = None
        self.override_rejected = None
        self.ota_deferred = False
        self.mode = self._mode(health)

        # Runtime config push (IF-8): an authenticated TMC config command reconfigures the RUNNING
        # unit. clamp_update enforces the §7a bounds AND refuses the boot-only safety backstops, so
        # no live push (or a compromised uplink) can move the dead-man's-switch window / watchdog /
        # degraded-hold ceiling (ADR-0012 R16). Applied BEFORE this tick reads cfg, so it governs
        # from now on; fail-loud refused/clamped names latch in config_rejected (FR-21).
        cp = inputs.get("config_push")
        if cp:
            self.apply_config(cp)

        # Calibration-drift monitor (FR-10, R15): a reference-point residual over tolerance
        # (injected here as inputs["drift"]) for longer than the debounce marks the unit
        # DEGRADED and raises a drift alarm. Real drift is field-deferred; the logic is not.
        if inputs.get("drift", False):
            if self.drift_since is None:
                self.drift_since = now
            if (now - self.drift_since) >= self.cfg["T_drift_debounce"]:
                self.drift_degraded = True
        else:
            self.drift_since = None
            self.drift_degraded = False

        # Time integrity (NFR-16): the health monitor reports whether absolute time is
        # trustworthy (health["time_valid"], derived from GNSS/PPS). Losing it degrades AUDIT
        # timestamps and inter-sensor fusion -> the unit goes DEGRADED + alert, but it must NOT
        # blank a live warning: a stopped vehicle is still a hazard when the clock drifts. (The
        # independent force-safe on a critical fault is the health monitor's own path, IF-5.)
        self.time_degraded = not health.get("time_valid", True)
        cfg = self.cfg
        gate = cfg["speed_gate_kph"]
        roi_gate = cfg["roi_overlap_gate"]

        # Operator acknowledgement (NFR-15, ADR-0011 §2): the operator acks the alarm they
        # currently see, keyed by its alarm_count. An ack clears the LATCHED escalation (the
        # memory of a past forced-clear / watchdog / sign-stuck event) and freezes re-escalation
        # of this alarm epoch -- but never suppresses a condition-derived CRITICAL (a still-blind
        # unit stays CRITICAL from mode), and a persistent fault re-raises the latch next tick.
        # Epoch-scoped: acking N does not ack a later N+1 (a stale ack is ignored).
        if (inputs.get("ack") is not None and self.alarm_count > 0
                and inputs["ack"] == self.alarm_count):
            self.alarm_acked = True
            self.escalation = None

        # NEITHER sensor -> unconditional safe state (doc 02 §4 matrix bottom row);
        # CAMERA_ONLY / RADAR_ONLY are handled inline (BLIND-TO-NEW guard + alert severity).
        if self.mode == NEITHER:
            self.state = SAFE_STATE
            # Nothing is asserted in NEITHER, so the watchdog's evidence clock must not keep
            # aging across the blackout: left stale, the first recovery tick that re-holds a
            # pre-blackout track (> T_watchdog later) would fire a spurious watchdog CRITICAL
            # instead of a quiet WARN_HOLD -> T_hold clear (pinned by SC-40).
            self.warn_evidence_since = None
            # An override cannot lift the both-sensors-dead safe state, but it must never be
            # silently dropped (FR-21): report why it did not apply. A malformed override
            # surfaces its own reason; a well-formed one is rejected as safe-state-suppressed.
            applied, rejected = self._eval_override(now, override)
            if rejected is not None:
                self.override_rejected = rejected
            elif applied is not None:
                self.override_rejected = "safe_state_neither"
            return self._decision("NONE")

        # Congestion pre-scan (R14, doc 02 §4): count stationary VEHICLE tracks across the
        # WHOLE scene (through lanes included, before ROI gating). A jam is many stationary
        # vehicles; a shoulder breakdown is one. Persons are excluded from the count: R14's
        # distrust is shoulder-vs-through ROI geometry for queued TRAFFIC -- three bystanders
        # standing near the road are not a jam and must not suppress a genuine shoulder
        # warning (SC-43). Used below to suppress a shoulder warning in stop-and-go.
        stationary_ids = set()
        for o in observations:
            if (o.get("sensor_source", "fused") in ("camera", "fused")
                    and o.get("cls", "car") != "person"
                    and o.get("speed_kph", 0.0) < gate):
                stationary_ids.add(o["track_id"])
        congestion = len(stationary_ids) >= cfg["congestion_min_tracks"]

        # Split IF-2 events by corroboration source (ICD IF-2 sensor_source). Camera
        # (or fused) events drive dwell / confirm / exit -- the camera owns class + image
        # ROI geometry (ADR-0009 §B). Radar (or fused) events only corroborate an existing
        # track; radar alone never creates or confirms one (BLIND-TO-NEW).
        cam_seen = set()
        radar_corr = set()
        for o in observations:
            if o.get("in_roi", 0.0) < roi_gate:
                continue  # ROI gating: footprint overlap must clear the gate
            tid = o["track_id"]
            src = o.get("sensor_source", "fused")
            if src in ("radar", "fused"):
                radar_corr.add(tid)
            if src not in ("camera", "fused"):
                continue  # radar-only: corroboration recorded above; no camera track
            cam_seen.add(tid)
            speed = o.get("speed_kph", 0.0)
            cls = o.get("cls", "car")
            tr = self.tracks.get(tid)
            if tr is None:
                tr = self._new_track(speed)
                self.tracks[tid] = tr
            tr["absent_since"] = None
            tr["degraded_since"] = None    # camera re-acquired -> leave any degraded hold
            tr["last_speed"] = speed
            tr["stale_now"] = o.get("stale", False)  # frozen/repeated frame -> not fresh evidence
            tr["suppressed_last_seen"] = congestion  # was the shoulder warning R14-suppressed when last seen?
            if cls == "person":
                # Pedestrian presence-onset (FR-08, ADR-0003): a stranded occupant typically
                # MOVES, so the stationarity gate would miss them -> confirm on debounced
                # PRESENCE in/beside the ROI (T_person_debounce), not speed. Camera-only warrant
                # (negligible RCS -> no radar corroboration / occlusion hold, ADR-0008 scope).
                # The presence clock is person_since -- its OWN onset, never the vehicle
                # stationarity clock: one relabelled tick on an already-stationary car must
                # not let T_person_debounce stand in for T_dwell (SC-42). And a person seen
                # again is PRESENT, not leaving: clear any exit latched by a person->vehicle
                # relabel blip, so a later occlusion still holds for T_hold (SC-41).
                tr["seen_leaving"] = False
                if tr["person_since"] is None:
                    tr["person_since"] = now   # presence-onset time
                if (not tr["confirmed"] and self.mode != RADAR_ONLY
                        and (now - tr["person_since"]) >= cfg["T_person_debounce"]):
                    tr["confirmed"] = True
            else:
                tr["person_since"] = None      # presence evidence is class-gated: stops accruing
            if speed < gate:
                # Seen stopped again -> it did not leave. Without this reset a single
                # >gate blip (centroid jump / door-open / fused Doppler) would latch
                # seen_leaving for good and a later genuine occlusion would fast-clear a
                # still-present car instead of holding the warning (SC-31). Stationarity is
                # class-INDEPENDENT (a standing person accrues dwell too); only the person
                # presence warrant above is class-gated.
                tr["seen_leaving"] = False
                if tr["stationary_since"] is None:
                    tr["stationary_since"] = now
                # RADAR_ONLY is BLIND-TO-NEW (ADR-0009 §B): radar alone cannot initiate a
                # confirm, so a NEW track is never promoted while the camera is dead.
                if (not tr["confirmed"] and self.mode != RADAR_ONLY
                        and (now - tr["stationary_since"]) >= cfg["T_dwell"]):
                    tr["confirmed"] = True  # dwell satisfied -> confirmed-stopped
            else:
                tr["stationary_since"] = None
                if tr["confirmed"] and cls != "person":
                    tr["seen_leaving"] = True  # moving VEHICLE while confirmed = observed exit
                #   (a walking person is presence, not an exit -- FR-08 exists exactly
                #    because stranded occupants move; SC-41)

        # Stamp radar corroboration on the tracks it renews. Corroboration is treated as
        # LIVE for T_corr_tolerance after its last return (checked below): a real radar /
        # fusion pipeline misses individual scans, and requiring a return on EVERY tick made
        # one missed beat past T_hold silently clear a live occlusion hold (SC-39).
        for tid in radar_corr:
            tr = self.tracks.get(tid)
            if tr is not None:
                tr["radar_last"] = now

        # Camera-absent confirmed tracks -> the clearing paths (ADR-0009 §C), none silent,
        # none unbounded: confirmed exit (fast); corroboration lost for T_hold -> loud clear
        # (or, if it was R14-suppressed when last seen, a quiet clear -- no assert to hold,
        # SC-38); corroborated occlusion -> WARN_HOLD until T_occlusion then
        # CAMERA_OCCLUDED_DEGRADED, itself bounded by T_degraded_max -> forced loud clear.
        for tid in list(self.tracks.keys()):
            tr = self.tracks[tid]
            if tid in cam_seen:
                continue
            if tr["absent_since"] is None:
                tr["absent_since"] = now
            absent = now - tr["absent_since"]
            if tr["confirmed"] and tr["seen_leaving"]:
                del self.tracks[tid]                       # confirmed exit -> fast clear
                continue
            if not tr["confirmed"]:
                if absent >= cfg["T_hold"]:
                    del self.tracks[tid]                   # unconfirmed + lost -> drop
                continue
            # T_degraded_max bounds the degraded hold UNCONDITIONALLY from first entry,
            # evaluated before the corroboration split -- so a flapping radar (gaps that
            # reset nothing, returns that renew) can never stretch the one state the
            # watchdog can't reach. degraded_since resets only on camera re-acquire.
            if (tr["degraded_since"] is not None
                    and (now - tr["degraded_since"]) >= cfg["T_degraded_max"]):
                del self.tracks[tid]                       # forced loud clear...
                self.escalation = "CRITICAL"               # ...+ max-severity escalation
                continue
            corr = (tr["radar_last"] is not None
                    and (now - tr["radar_last"]) <= cfg["T_corr_tolerance"])
            if tr["suppressed_last_seen"] and not (corr and tr["radar_last"] >= tr["absent_since"]):
                # Congestion carry-over (R14, doc 02 §4 / ADR-0008): a track confirmed only
                # while the shoulder warning was SUPPRESSED never earned an un-suppressed
                # assertion. Vanishing with no confirmed exit and no radar corroboration,
                # there is no shown warning to hold -- holding it would flash a WARN_HOLD the
                # instant suppression lifts (cry-wolf on the very geometry R14 distrusts). The
                # same distrust that suppressed the assert clears it quietly (SC-38). Radar-
                # corroborated occlusion is unaffected (below): real presence holds -- but only
                # a return heard SINCE the camera lost the track counts (radar_last >=
                # absent_since); a pre-vanish return remembered through T_corr_tolerance is
                # not presence evidence and must not re-flash the very hold R14 distrusts.
                del self.tracks[tid]                       # suppressed + lost, uncorroborated -> quiet clear
            elif corr:
                if absent >= cfg["T_occlusion"] and tr["degraded_since"] is None:
                    tr["degraded_since"] = now             # enter CAMERA_OCCLUDED_DEGRADED
                # else: within T_occlusion -> corroboration renews the hold (WARN_HOLD)
            elif (absent >= cfg["T_hold"]
                  and (tr["radar_last"] is None
                       or (now - tr["radar_last"]) >= cfg["T_hold"])):
                # Lost ALL corroboration: the T_hold hysteresis runs from the last evidence
                # on ANY channel (camera absence AND radar silence both >= T_hold), honoring
                # "no corroboration -> T_hold -> loud clear" even when the camera went
                # absent long before the radar fell silent (SC-39 sustained-loss phase).
                del self.tracks[tid]                       # lost all corroboration -> loud clear

        present = held = degraded = fresh = False
        for tid in self.tracks:
            tr = self.tracks[tid]
            if not tr["confirmed"]:
                continue
            if tid in radar_corr:
                fresh = True                   # radar corroboration is fresh evidence
            if tr["absent_since"] is None:
                present = True
                if not tr["stale_now"]:
                    fresh = True               # a live (non-frozen) camera detection is fresh
            elif tr["degraded_since"] is not None:
                degraded = True
            else:
                held = True

        # Watchdog (ADR-0008 §4): the stale-ON backstop. A warning ON with NO fresh confirm
        # or corroboration from any channel for T_watchdog is treated as a wedged loop ->
        # clear + raise a fault. Radar corroboration counts as fresh, so a corroborated
        # occlusion never trips it (that is T_degraded_max's job, ADR-0009 §C).
        asserting_pre = present or held or degraded
        if not asserting_pre:
            self.warn_evidence_since = None
        elif fresh or self.warn_evidence_since is None:
            self.warn_evidence_since = now
        watchdog_fired = (asserting_pre and not fresh
                          and (now - self.warn_evidence_since) >= cfg["T_watchdog"])
        if watchdog_fired:
            self.tracks = {}                   # drop the wedged set
            self.escalation = "CRITICAL"       # loud fault (logic may be wedged)
            present = held = degraded = False

        if watchdog_fired:
            self.state = SAFE_STATE            # clear + fault (doc 02 §4)
        elif present:
            self.state = WARN_ON
        elif degraded:
            self.state = CAMERA_OCCLUDED_DEGRADED
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

        # Congestion suppression (R14): in a jam, only fragile ROI geometry separates a
        # shoulder breakdown from queued through-traffic -> suppress the shoulder warning
        # (the machine keeps detecting/logging; state stays WARN_*). (b)-dependent: designed,
        # not field-sound (doc 07 SC-11). An operator force-on below still overrides it.
        if congestion:
            asserting = False

        # Operator override (IF-10) applied on top of the autonomous decision (ADR-0010):
        # bounded, fail-loud, heartbeat-honoring. Force-on asserts via the SAME refreshed
        # SHOW (non-latching -- the dead-man's switch still blanks it on box-kill/expiry);
        # force-off/mute suppress the sign while detection/logging continue underneath; every
        # override auto-expires (<= T_override_max) and is rejected/clamped if out of policy.
        applied, self.override_rejected = self._eval_override(now, override)
        if applied == "force_on":
            asserting = True
            self.override_active = "FORCE_ON"
        elif applied == "force_off":
            asserting = False
            self.override_active = "FORCE_OFF"
        elif applied == "mute":
            asserting = False
            self.override_active = "MUTE"

        # OTA / restart request (IF-9) is DEFERRED while a warning is asserted -- applying it
        # would drop the warning mid-incident (a silent miss). Never a silent drop (FR-21).
        if inputs.get("ota", False) and asserting:
            self.ota_deferred = True

        # Sign-stuck detection (ADR-0013 §C.3): the SM commanded OFF but the IF-3 status
        # read-back shows the sign still ON well past T_signhold -> the sign is physically
        # wedged (the one fault the dead-man's switch cannot fix). Leave to SAFE_STATE and
        # raise a sign-stuck maintenance escalation.
        if (not asserting) and inputs.get("sign_status", False):
            if self.clear_since is None:
                self.clear_since = now
            if (now - self.clear_since) >= cfg["T_signhold"] + cfg["T_sign_stuck_grace"]:
                self.escalation = "CRITICAL"
                self.state = SAFE_STATE
        else:
            self.clear_since = None

        return self._decision("SHOW" if asserting else "NONE")

    def _eval_override(self, now, override):
        """Apply the ADR-0010 bounds to an IF-10 override command; return
        (applied_action or None, rejected_reason or None): clamp an over-ceiling expiry to
        T_override_max, reject out-of-policy force-ons, enforce mandatory auto-expiry."""
        if override is None:
            return None, None
        if not isinstance(override, dict):
            return None, "malformed"       # the IF-10 payload must be a command object
        action = override.get("action")
        if action not in ("force_on", "force_off", "mute"):
            return None, "unknown_action"
        issued = override.get("issued", now)
        expiry = override.get("expiry", None)
        # Timing fields must be numbers, and never NaN: a NaN expiry compares False against
        # both the ceiling clamp AND `now >= expiry`, so it would neither clamp nor ever
        # expire -- a forever-mute from one malformed field (the FR-20 NaN lesson from the
        # config path, applied to IF-10; CMD-16). Rejected fail-loud, never applied.
        if isinstance(issued, bool) or not isinstance(issued, (int, float)) or issued != issued:
            return None, "malformed"
        if expiry is None:
            expiry = issued + self.cfg["T_override_max"]
        if isinstance(expiry, bool) or not isinstance(expiry, (int, float)) or expiry != expiry:
            return None, "malformed"
        if expiry > issued + self.cfg["T_override_max"]:
            expiry = issued + self.cfg["T_override_max"]   # clamp over-ceiling expiry (SC-18)
        if action == "force_on":
            if not override.get("reason"):
                return None, "no_reason"                   # force-on needs an operator reason
            if override.get("message_id", MESSAGE_STOPPED) != MESSAGE_STOPPED:
                return None, "unknown_message"
        if now >= expiry:
            return None, None                              # auto-expired -> normal logic resumes
        return action, None

    def _decision(self, assertion):
        # Operator-alert severity = max of: the sensing-mode alert (FULL none /
        # CAMERA-ONLY degraded / RADAR-ONLY|NEITHER critical), a "DEGRADED" for being in a
        # sustained camera-unverified hold (investigate), and any latched escalation
        # (T_degraded_max forced clear -> CRITICAL). ADR-0009 §B/§C, ADR-0011.
        if self.mode == FULL:
            alert = "NONE"
        elif self.mode == CAMERA_ONLY:
            alert = "DEGRADED"
        else:  # RADAR_ONLY or NEITHER
            alert = "CRITICAL"
        if self.state == CAMERA_OCCLUDED_DEGRADED or self.drift_degraded or self.time_degraded:
            alert = _max_alert(alert, "DEGRADED")
        alert = _max_alert(alert, self.escalation)

        # Alarm management (NFR-15, ADR-0011): a sustained CRITICAL raises ONE alarm (dedup) and,
        # until the operator acks it (inputs["ack"], handled in tick()), re-escalates once per
        # T_reescalate window so the count climbs slowly rather than storming every tick. An ack
        # freezes the climb for this epoch; when the epoch ends (alert drops then re-raises) it
        # re-arms, so a fresh critical after an ack alarms again.
        if alert == "CRITICAL":
            if self.alarm_since is None:
                self.alarm_count += 1
                self.alarm_since = self._now
                self.alarm_acked = False       # a freshly-raised alarm starts un-acked
            elif not self.alarm_acked and (self._now - self.alarm_since) >= self.cfg["T_reescalate"]:
                self.alarm_count += 1
                self.alarm_since = self._now
        else:
            self.alarm_since = None
            self.alarm_acked = False            # epoch ends -> a new critical re-alarms afresh

        # OVERRIDDEN posture takes precedence (ADR-0010 §2); a drift-degraded unit or a
        # degraded sensing mode -> DEGRADED; otherwise NORMAL.
        if self.override_active:
            posture = "OVERRIDDEN"
        elif self.mode != FULL or self.drift_degraded or self.time_degraded:
            posture = "DEGRADED"
        else:
            posture = "NORMAL"
        return {"assertion": assertion, "message_id": MESSAGE_STOPPED,
                "state": self.state, "mode": self.mode, "posture": posture,
                "alert": alert, "override": self.override_active,
                "override_rejected": self.override_rejected,
                "ota_deferred": self.ota_deferred, "alarm_count": self.alarm_count,
                "config_rejected": self.config_rejected,
                "cfg_ver": self.cfg_ver}
