# Synthetic sign controller (doc 07 s3.4) -- models IF-4 + the dead-man's switch over
# the REAL frame bytes (esw.if4), so the harness verifies exactly what the ESP32 firmware
# (doc 10) will. It SHOWs only while a fresh, valid, AUTHENTICATED SHOW arrived within
# T_signhold; otherwise it blanks. A forged or replayed frame fails verify() -> ignored
# -> the sign blanks (ICD s3, ADR-0012, RQ-H2).
#
# Two anti-replay guards, matching the firmware spec (doc 10):
#   - within a session (sign lit): seq must strictly increase -> blocks in-session replay.
#   - across sessions (after a blank): last_seq resets, so a legitimately reconnecting edge
#     (e.g. a rebooted box whose RAM counter reset) can re-assert; an OLD captured frame is
#     still blocked by the timestamp freshness window.
#
# Failure-mode knobs for the fault scenarios:
#   latch=True         -> non-compliant third-party VMS that will not blank (ICD s3 caveat)
#   can_turn_off=False -> stuck-ON hardware fault (SC-24)

from esw import if4


class Sign:
    def __init__(self, cfg, key, latch=False, can_turn_off=True):
        self.cfg = cfg
        self.key = key
        self.latch = latch
        self.can_turn_off = can_turn_off
        self.link_up = True              # a cut link stops frames reaching the controller
        self.last_show_ts = None
        self.last_seq = None             # anti-replay high-water mark for THIS session
        self.message_id = None
        self.on = False
        self.rejects = 0                 # frames that failed verify (auth/replay/stale): observability

    def receive(self, now, frame):
        """Decode + verify one IF-4 frame. A cut link delivers nothing. A frame that fails
        auth / anti-replay / freshness is ignored -> the sign blanks on staleness (RQ-H2)."""
        if not self.link_up or frame is None:
            return
        window = self.cfg["T_signhold"]
        r = if4.verify(self.key, frame, self.last_seq, if4.to_ms(now), if4.to_ms(window))
        if r["ok"]:
            self.last_show_ts = now
            self.last_seq = r["seq"]
            self.message_id = if4.message_id_to_text(r["message_id"])
        else:
            self.rejects += 1

    def update(self, now):
        """Dead-man's switch: blank unless a fresh valid refresh is within T_signhold."""
        fresh = (self.last_show_ts is not None and
                 (now - self.last_show_ts) <= self.cfg["T_signhold"])
        if fresh:
            self.on = True
        elif self.latch or not self.can_turn_off:
            pass                         # fault injection: refuse to blank (SAFE_STATE / VMS paths)
        else:
            self.on = False
            self.message_id = None
            self.last_seq = None         # session ended -> a legit reconnect may re-assert;
            #                              an OLD replayed frame is still blocked by freshness.
        return self.on
