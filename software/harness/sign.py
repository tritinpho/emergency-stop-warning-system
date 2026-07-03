# Synthetic sign controller (doc 07 §3.4) -- models IF-4 and the dead-man's switch.
#
# The controller shows SHOW(message_id) ONLY while a fresh refresh arrived within
# T_signhold; otherwise it blanks. That is the whole fail-safe: SM crash, dead
# edge box, or cut link all stop the refresh -> the sign blanks (ADR-0009 §A).
#
# Configurable failure modes for the fault scenarios:
#   latch=True        -> non-compliant third-party VMS that will not blank (ICD §3 caveat)
#   can_turn_off=False -> stuck-ON hardware fault (SC-24)


class Sign:
    def __init__(self, cfg, latch=False, can_turn_off=True):
        self.cfg = cfg
        self.latch = latch
        self.can_turn_off = can_turn_off
        self.link_up = True          # a cut link stops refreshes reaching the controller
        self.last_show_ts = None
        self.message_id = None
        self.on = False

    def refresh(self, now, message_id):
        """Actuator delivers a refreshed SHOW. Ignored if the field link is down."""
        if self.link_up:
            self.last_show_ts = now
            self.message_id = message_id

    def update(self, now):
        """Dead-man's switch: blank unless a fresh refresh is within T_signhold."""
        fresh = (self.last_show_ts is not None and
                 (now - self.last_show_ts) <= self.cfg["T_signhold"])
        if fresh:
            self.on = True
        elif self.latch or not self.can_turn_off:
            pass  # fault injection: refuse to blank (tests SAFE_STATE / VMS fallback paths)
        else:
            self.on = False
            self.message_id = None
        return self.on
