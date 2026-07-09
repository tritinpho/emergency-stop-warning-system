# IF-4 edge-side actuator: the refresh-or-blank driver (ICD s3, ADR-0009 s A).
#
# Policy, stated as an invariant: emit a fresh authenticated SHOW frame on EVERY tick
# the state machine asserts SHOW, and emit NOTHING otherwise. There is deliberately no
# "turn the sign off" command -- OFF is the ABSENCE of refresh. So every hard failure
# that stops this code running (SM crash, dead edge box) or stops bytes arriving (cut or
# jammed link) blanks the sign, without any message needing to be sent or received.
#
# The sim refreshes each 0.1 s tick, which is well inside T_assert_refresh; a real edge
# may instead refresh on a T_assert_refresh timer to conserve LoRa airtime (ADR-0014).
# Either way the controller only cares that a valid SHOW landed within T_signhold.
#
# MicroPython-safe subset (byte-identical sim + K230).

from esw import if4


def _msg_id(text):
    """Map a message text id to its wire byte. Returns (byte, known). The prototype
    QCVN-41 set has one element (ADR-0004); an UNKNOWN text still emits the generic
    stopped-vehicle warning (blanking on a live hazard would be a silent miss) but is
    reported not-known so the caller counts it loud (FR-21) instead of masking it."""
    if text == "STOPPED_VEHICLE_AHEAD":
        return if4.MSG_ID_STOPPED, True
    return if4.MSG_ID_STOPPED, False


class Actuator:
    def __init__(self, key, cfg_ver):
        self._key = key
        self._cfg_ver = cfg_ver        # boot fallback; a decision carrying cfg_ver overrides
        self._seq = 0
        self.unknown_msgs = 0          # observability: SHOWs asserted with an unmapped
        self.last_unknown = None       # message_id (mirrors sign.rejects; FR-21 fail-loud)

    def step(self, now, decision, nonce=None, wall_ms=None):
        """Return the frame bytes to transmit this tick, or None to transmit nothing.
        None (silence) is how the sign is ALLOWED to blank -- see the module invariant.

        CLOCKS: `now` is the loop's TICK time (monotonic -- whatever clock tick() runs on).
        The wire timestamp feeds the controller's anti-replay FRESHNESS check, which needs
        the clock the edge and the sign controller AGREE on (GNSS epoch ms, doc 10 "Time")
        -- on a real edge pass that as `wall_ms`; do NOT feed seconds-since-boot to the
        wire. The sim's tick time IS its epoch, so the default wall_ms = to_ms(now) is
        exact there and every existing caller is unchanged."""
        if decision is None or decision.get("assertion") != "SHOW":
            return None
        self._seq += 1
        if nonce is None:
            nonce = self._seq          # deterministic in sim; a real edge uses os.urandom(4)
        if wall_ms is None:
            wall_ms = if4.to_ms(now)
        mid, known = _msg_id(decision.get("message_id"))
        if not known:
            self.unknown_msgs += 1
            self.last_unknown = decision.get("message_id")
        # cfg_ver comes from the DECISION (the SM re-fingerprints on every runtime IF-8
        # push), so frames bind to the config in force, not the boot config (R10).
        cfg_ver = decision.get("cfg_ver", self._cfg_ver)
        return if4.encode_show(self._key, mid, self._seq, nonce, cfg_ver, wall_ms)
