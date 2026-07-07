# Telemetry emitter -- IF-6 heartbeat + IF-7 audit events (doc 08 §4, doc 02 §7).
#
# Non-safety, store-and-forward OVERSIGHT: the safety loop never depends on it (NFR-06,
# ADR-0002). But it runs on the edge, so it is part of the byte-identical SUT: it turns the
# per-tick decision stream into the structured, fingerprinted audit records the acceptance-
# evidence pipeline reduces (ADR-0007, doc 01 §5). Transport (MQTT / store-and-forward outbox)
# is a drop-in backend, not built here -- this produces the RECORDS.
#
# Every record carries the version fingerprint (fw/cfg/model/calib) so a liability-grade audit
# can bind each event to exactly the code+config that produced it (R10, doc 02 §7).
#
# MicroPython-safe subset (byte-identical sim + K230).

_HEARTBEAT_EVERY = 1.0   # IF-6 cadence (s) -- a fixed reporting cadence, not safety-relevant

# IF-7 event types that close a warning interval (the sign went dark). Kept in sync with the
# reducer (harness/metrics.py) -- these are what warn_intervals() treats as a clear.
_CLEAR_TYPES = ("clear", "low_confidence_clear", "forced_clear")


class Telemetry:
    def __init__(self, site_id, versions, heartbeat_every=_HEARTBEAT_EVERY):
        # versions = {fw_ver, cfg_ver, model_ver, calib_ver}. In sim, cfg_ver is real
        # (if4.cfg_fingerprint); fw/model/calib are stubs until the real artifacts exist.
        self.site_id = site_id
        self.versions = versions
        self.heartbeat_every = heartbeat_every
        self._prev_on = False
        self._prev_state = None
        self._prev_override = None
        self._prev_alarm = 0
        self._last_beat = None

    def step(self, now, decision, hm_status, sign_on):
        """Return the records emitted this tick: 0+ IF-7 events, plus an IF-6 heartbeat on cadence."""
        out = []
        state = decision.get("state")
        alert = decision.get("alert")
        override = decision.get("override")
        alarm = decision.get("alarm_count", 0)

        # IF-7 activation / clear -- keyed on the PUBLIC-VISIBLE sign (IF-3 read-back), because the
        # audit records what a driver actually saw, not merely what the SM intended (a force-safe or
        # a dead link can blank the sign while the SM still asserts SHOW).
        if sign_on and not self._prev_on:
            out.append(self._event(now, "activation", alert))
        elif self._prev_on and not sign_on:
            out.append(self._event(now, self._clear_type(decision), alert))

        # IF-7 fault / safe-state (entry) -- an audit marker; does NOT close a warn interval (the
        # sign may be wedged ON, SC-24). sign_stuck is a SAFE_STATE reached with the sign still lit.
        if state == "SAFE_STATE" and self._prev_state != "SAFE_STATE":
            out.append(self._event(now, "sign_stuck" if sign_on else "fault", "CRITICAL"))

        # IF-7 override lifecycle (a new override asserted).
        if override != self._prev_override and override:
            out.append(self._event(now, "override", alert))

        # IF-7 alarm -- a fresh deduped CRITICAL alarm was raised (ADR-0011, NFR-15).
        if alarm > self._prev_alarm:
            out.append(self._event(now, "alarm", "CRITICAL"))

        # IF-6 heartbeat at a fixed cadence, carrying health + posture so a degraded unit can
        # never look healthy on the oversight plane.
        if self._last_beat is None or (now - self._last_beat) >= self.heartbeat_every:
            out.append(self._heartbeat(now, decision, hm_status))
            self._last_beat = now

        self._prev_on = sign_on
        self._prev_state = state
        self._prev_override = override
        self._prev_alarm = alarm
        return out

    def _clear_type(self, decision):
        # Best-effort IF-7 clear subtype from what the decision exposes. A forced clear
        # (T_degraded_max / watchdog) latches a CRITICAL escalation; a plain confirmed-exit clear
        # does not. Finer subtyping (low_confidence vs normal) can be refined when the SM emits an
        # explicit reason -- an honest limit, noted here rather than faked.
        if decision.get("alert") == "CRITICAL":
            return "forced_clear"
        return "clear"

    def _event(self, now, etype, severity):
        rec = {"if": 7, "site_id": self.site_id, "type": etype, "severity": severity, "ts": now}
        self._stamp(rec)
        return rec

    def _heartbeat(self, now, decision, hm_status):
        rec = {"if": 6, "site_id": self.site_id, "sensor_mode": decision.get("mode"),
               "posture": decision.get("posture"), "state": decision.get("state"),
               "hm_status": hm_status, "alert": decision.get("alert"), "ts": now}
        self._stamp(rec)
        return rec

    def _stamp(self, rec):
        v = self.versions
        rec["fw_ver"] = v.get("fw_ver")
        rec["cfg_ver"] = v.get("cfg_ver")
        rec["model_ver"] = v.get("model_ver")
        rec["calib_ver"] = v.get("calib_ver")
