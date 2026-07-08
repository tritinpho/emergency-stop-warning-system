# Authenticated IF-8/9/10 command feed for the Level-F board (host-only harness -- NOT shipped).
#
# Turns a scenario's genuine command script into real esw.command frames (the SAME bytes the TMC
# sends and the edge CommandReceiver verifies), and injects attacker frames (forged / replay /
# stale) so a scenario can prove the auth gate end-to-end: a genuine command drives the real state
# machine; a forged, replayed, or stale one is inert. The inbound twin of harness/sign.py's
# forged/replay injection for the IF-4 sign-link.
#
# Scenario schema (opt-in via `auth_commands: True`):
#   "commands":        [{"t", "ctype": config|ota|override|ack, "payload": {...}}, ...]  (genuine)
#   "inject_commands": [{"t", "kind": forged|replay|stale, "ctype"?, "payload"?, "ts"?}, ...]

from esw import command
from esw.command import CommandReceiver, encode_command
from esw.if4 import to_ms

_CTYPE = {"config": command.CMD_CONFIG, "ota": command.CMD_OTA,
          "override": command.CMD_OVERRIDE, "ack": command.CMD_ACK}


class CommandFeed:
    """Per-run authenticated command source. `step(now)` delivers the frames due this tick to the
    CommandReceiver and folds the VERIFIED ones into the (override, ota, ack) the SM consumes -- so
    a rejected frame never reaches the state machine."""

    def __init__(self, scenario, key, wrong_key, replay_window_ms, tick_dt):
        self._key = key
        self._wrong = wrong_key
        self._dt = tick_dt
        self._rx = CommandReceiver(key, replay_window_ms)

        # Pre-build the genuine frames with monotonic seq in issue-time order (what a real TMC does).
        cmds = sorted(scenario.get("commands", []), key=lambda c: c["t"])
        self._genuine = []
        seq = 1
        for c in cmds:
            frame = encode_command(key, _CTYPE[c["ctype"]], seq, seq, to_ms(c["t"]), c.get("payload", {}))
            self._genuine.append({"t": c["t"], "frame": frame})
            seq += 1
        self._inject = scenario.get("inject_commands", [])

        # Operative state fed to the SM -- updated from VERIFIED commands only.
        self._override = None
        self._ota = False
        self._ack = None
        self._last_genuine_frame = None
        # Attacker frames carry a high seq so they clear the anti-replay seq guard and actually
        # exercise auth / freshness (a rejected frame never advances the receiver watermark anyway).
        self._atk_seq = 900000

    def step(self, now):
        # Genuine frames first, so a same-tick replay lands after the watermark it must fail against.
        for g in self._genuine:
            if g["t"] <= now < g["t"] + self._dt:
                self._last_genuine_frame = g["frame"]
                self._apply(self._rx.submit(g["frame"], to_ms(now)))
        for inj in self._inject:
            if inj["t"] <= now < inj["t"] + self._dt:
                self._apply(self._rx.submit(self._attacker_frame(inj, now), to_ms(now)))
        return self._override, self._ota, self._ack

    def _attacker_frame(self, inj, now):
        kind = inj.get("kind")
        if kind == "replay":
            return self._last_genuine_frame                 # re-send a captured genuine frame verbatim
        self._atk_seq += 1
        ct = _CTYPE[inj.get("ctype", "override")]
        payload = inj.get("payload", {})
        if kind == "forged":
            return encode_command(self._wrong, ct, self._atk_seq, 7, to_ms(now), payload)
        if kind == "stale":                                 # genuine key, but an OLD ts -> freshness fails
            return encode_command(self._key, ct, self._atk_seq, 8, to_ms(inj.get("ts", 0.0)), payload)
        return None

    def _apply(self, res):
        if not res["ok"]:
            return
        ct = res["ctype"]
        payload = res["payload"]
        if ct == command.CMD_OVERRIDE:
            self._override = payload        # SM-shaped override dict; the SM enforces ADR-0010 bounds
        elif ct == command.CMD_ACK:
            self._ack = payload.get("count")
        elif ct == command.CMD_OTA:
            self._ota = True                # latched, matching sensors.ota_at

    @property
    def rejects(self):
        return self._rx.rejects

    @property
    def last_reject(self):
        return self._rx.last_reject
