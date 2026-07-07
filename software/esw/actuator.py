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
    # Prototype QCVN-41 set has one element (ADR-0004); map its text id to the wire byte.
    if text == "STOPPED_VEHICLE_AHEAD":
        return if4.MSG_ID_STOPPED
    return if4.MSG_ID_STOPPED


class Actuator:
    def __init__(self, key, cfg_ver):
        self._key = key
        self._cfg_ver = cfg_ver
        self._seq = 0

    def step(self, now, decision, nonce=None):
        """Return the frame bytes to transmit this tick, or None to transmit nothing.
        None (silence) is how the sign is ALLOWED to blank -- see the module invariant."""
        if decision is None or decision.get("assertion") != "SHOW":
            return None
        self._seq += 1
        if nonce is None:
            nonce = self._seq          # deterministic in sim; a real edge uses os.urandom(4)
        mid = _msg_id(decision.get("message_id"))
        return if4.encode_show(self._key, mid, self._seq, nonce, self._cfg_ver, if4.to_ms(now))
