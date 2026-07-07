# Scenario runner + oracle comparator (doc 07 §2, §4).
#
# Drives the real esw StateMachine at a fixed tick, runs the real IF-4 actuator
# (esw.actuator) to emit authenticated refresh frames, and feeds them to the sign
# dead-man's switch (harness.sign, which decodes + verifies the SAME esw.if4 bytes the
# ESP32 firmware will). It injects faults + forged/replayed frames, then scores the
# recorded sign-state timeline against the scenario's oracle checkpoints.

from esw.params import default_config
from esw.state_machine import StateMachine
from esw.actuator import Actuator
from esw import if4
from harness.sensors import observations_at, health_at, override_at, ota_at, drift_at, ack_at
from harness.sign import Sign

TICK_DT = 0.1  # 10 Hz fixed-rate tick (ADR-0015)

# Per-unit shared secret for IF-4 auth (ADR-0012). Real deployments provision this
# out-of-band per unit and rotate it; these are test vectors. _WRONG_KEY stands in for an
# attacker who can transmit on the link but does not hold the key.
_KEY = b"esw-if4-shared-secret-v1-0123456789"
_WRONG_KEY = b"attacker-without-the-shared-secret!"


def _merge(base, over):
    out = dict(base)
    for k in over:
        out[k] = over[k]
    return out


def _attacker_frame(kind, t, cfg_ver, last_frame):
    """Build an injected hostile frame for the security scenarios (SC-33/34)."""
    if kind == "forged":
        # Well-formed SHOW but signed with the wrong key -> auth_tag fails verify().
        return if4.encode_show(_WRONG_KEY, if4.MSG_ID_STOPPED, 1, 1, cfg_ver, if4.to_ms(t))
    if kind == "replay":
        # Re-inject a genuine frame captured earlier -> stale ts / low seq -> rejected.
        return last_frame
    return None


def run_scenario(scenario):
    """Run one scenario; return the per-tick timeline (sign state + disposition)."""
    cfg = _merge(default_config(), scenario.get("config_push", {}))
    cfg_ver = if4.cfg_fingerprint(cfg)
    sm = StateMachine(cfg)                        # SUT gets the (possibly bad) pushed config
    actuator = Actuator(_KEY, cfg_ver)            # edge-side IF-4 driver (refresh-or-blank)
    sign = Sign(default_config(), _KEY,           # controller uses in-bounds safety constants
                latch=scenario.get("sign_latch", False),
                can_turn_off=not scenario.get("sign_stuck", False))

    killed_sm = box_dead = link_cut = rebooted = False
    sign_status = False                           # IF-3 status read-back (one tick delayed)
    last_frame = None                             # last genuine frame emitted (for replay tests)
    timeline = []
    steps = int(scenario["duration"] / TICK_DT) + 1
    for i in range(steps):
        t = round(i * TICK_DT, 3)
        sm_down = False
        for f in scenario.get("faults", []):
            kind = f["kind"]
            if kind == "reboot":                  # warm reboot: SM dead in downtime, then fresh
                down = f.get("downtime", 2.0)
                if f["t"] <= t < f["t"] + down:
                    sm_down = True
                elif t >= f["t"] + down and not rebooted:
                    sm = StateMachine(cfg)         # restart comes up IDLE -> full re-confirm
                    actuator = Actuator(_KEY, cfg_ver)  # fresh edge: seq resets (anti-replay reconnect)
                    rebooted = True
            elif t >= f["t"]:
                if kind == "kill_sm":
                    killed_sm = True
                elif kind == "kill_box":
                    box_dead = True
                elif kind == "cut_link":
                    link_cut = True
        sign.link_up = not link_cut

        if killed_sm or sm_down:
            decision = {"assertion": "NONE"}      # SM process dead / rebooting -> nothing asserted
        else:
            inputs = {"sign_status": sign_status,
                      "ota": ota_at(scenario, t),
                      "drift": drift_at(scenario, t),
                      "ack": ack_at(scenario, t)}
            decision = sm.tick(t, observations_at(scenario, t), health_at(scenario, t),
                               override_at(scenario, t), inputs)

        # The edge emits an authenticated refresh iff it is alive and asserting SHOW. A dead
        # box (box_dead) sends nothing; a killed/rebooting SM asserts NONE, so the actuator
        # sends nothing -> the sign blanks in every hard-failure case (RQ-H2). Refreshing
        # every 0.1 s tick is well inside T_assert_refresh; a real edge uses that timer.
        frame = None
        if not box_dead:
            frame = actuator.step(t, decision)
        if frame is not None:
            last_frame = frame

        # Injected hostile frames (SC-33/34): the attacker transmits directly at the sign.
        for inj in scenario.get("inject_frames", []):
            if "from" in inj:
                fire = inj["from"] <= t < inj["to"]
            else:
                fire = inj["t"] <= t < inj["t"] + TICK_DT
            if fire:
                sign.receive(t, _attacker_frame(inj.get("kind"), t, cfg_ver, last_frame))

        if frame is not None:
            sign.receive(t, frame)                # genuine refresh delivered last -> it wins the tick

        sign_status = sign.update(t)              # read-back fed to the next tick (IF-3)
        timeline.append({
            "t": t,
            "on": sign_status,
            "state": decision.get("state"),
            "posture": decision.get("posture"),
            "mode": decision.get("mode"),
            "alert": decision.get("alert"),
            "override": decision.get("override"),
            "override_rejected": decision.get("override_rejected"),
            "ota_deferred": decision.get("ota_deferred"),
            "alarm_count": decision.get("alarm_count"),
            "rejects": sign.rejects,
        })
    return timeline


def _sample_at(timeline, t):
    """The most recent recorded sample at or before t (None if none yet)."""
    rec = None
    for r in timeline:
        if r["t"] <= t + 1e-9:
            rec = r
        else:
            break
    return rec


def sign_on_at(timeline, t):
    """Sign state at time t = the most recent sample at or before t."""
    rec = _sample_at(timeline, t)
    return rec["on"] if rec else False


# Disposition fields a checkpoint may assert in addition to the sign state.
# doc 07 §4 scores disposition correctness (degraded/clear/safe-state), not just
# the sign -- e.g. SC-25/26/27 must prove mode/alert, not merely that ON matches.
_DISPOSITION_KEYS = ("state", "posture", "mode", "alert", "override", "override_rejected",
                     "ota_deferred", "alarm_count")


def evaluate(scenario, timeline):
    """Return a list of (t, expected, got) for every failed oracle checkpoint.

    Each checkpoint may assert the sign state ("on") and/or any disposition field
    in _DISPOSITION_KEYS; only the keys a checkpoint names are checked."""
    fails = []
    for c in scenario.get("checks", []):
        rec = _sample_at(timeline, c["t"])
        if "on" in c:
            got = rec["on"] if rec else False
            if got != c["on"]:
                fails.append((c["t"], c["on"], got))
        for key in _DISPOSITION_KEYS:
            if key in c:
                got = rec.get(key) if rec else None
                if got != c[key]:
                    fails.append((c["t"], (key, c[key]), (key, got)))
    return fails
