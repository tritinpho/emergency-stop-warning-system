# Health monitor -- the independent self-test / liveness / time-integrity stage (FR-10,
# NFR-16, ADR-0009, doc 02 §2). It is the "sensor of health": it turns raw per-subsystem
# liveness into the {camera, radar} health the state machine acts on (so the FULL /
# CAMERA-ONLY / RADAR-ONLY / NEITHER mode is DERIVED, not injected), judges whether absolute
# time is trustworthy (GNSS/PPS, NFR-16), and -- crucially -- keeps an INDEPENDENT force-safe
# authority (IF-5): it can blank the sign directly, without routing through a possibly-wedged
# state machine (ADR-0009 §A, the third dead-man's-switch layer).
#
# It runs BEFORE the state machine each tick and is deliberately simple + side-effect-free so
# it cannot itself wedge. MicroPython-safe subset (byte-identical sim + K230).

_SENSORS = ("camera", "radar")


class HealthMonitor:
    def __init__(self, cfg):
        self.cfg = cfg
        self._last_live = {}          # sensor -> last tick it delivered fresh valid data
        self._last_lock = None        # last tick GNSS/PPS was locked
        self._beat = 0                # heartbeat counter (FR-10)

    def step(self, now, sensor_live=None, gnss_lock=True, selftest_ok=True):
        """Return this tick's health status:
        {camera, radar, time_valid, force_safe, status, beat}.

        sensor_live: {sensor: bool} did each sensor deliver fresh valid data this tick.
        gnss_lock:   is the GNSS/PPS time source currently locked.
        selftest_ok: did the critical self-test pass (compute / memory / link / sign checks)."""
        if sensor_live is None:
            sensor_live = {}
        self._beat += 1
        t_out = self.cfg["T_sensor_timeout"]

        # Per-sensor liveness with a debounce: HEALTHY while it delivered fresh data within
        # T_sensor_timeout, so a one-frame dropout does not flap the mode while a sustained loss
        # is reported DOWN. Default T_sensor_timeout = 0 -> react immediately (conservative).
        healthy = {}
        i = 0
        while i < len(_SENSORS):
            s = _SENSORS[i]
            if sensor_live.get(s, False):
                self._last_live[s] = now
            last = self._last_live.get(s, None)
            healthy[s] = last is not None and (now - last) <= t_out
            i += 1

        # Time integrity (NFR-16): absolute time is valid while GNSS/PPS is locked, or within
        # T_time_holdover of the last lock (oscillator coast). Bench models the DETECTION + the
        # degraded response; multi-hour hold-over and GNSS-denied siting are field-deferred.
        if gnss_lock:
            self._last_lock = now
        time_valid = (self._last_lock is not None and
                      (now - self._last_lock) <= self.cfg["T_time_holdover"])

        # Independent force-safe (IF-5): a failed critical self-test blanks the sign directly,
        # regardless of what the state machine asserts -- the one safe-state authority strictly
        # independent of the (possibly wedged) decision path.
        force_safe = not selftest_ok

        if force_safe:
            status = "FORCE_SAFE"
        elif (not healthy["camera"]) or (not healthy["radar"]) or (not time_valid):
            status = "DEGRADED"
        else:
            status = "OK"

        return {"camera": healthy["camera"], "radar": healthy["radar"],
                "time_valid": time_valid, "force_safe": force_safe,
                "status": status, "beat": self._beat}
