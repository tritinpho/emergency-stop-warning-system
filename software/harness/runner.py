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
from esw.health import HealthMonitor
from esw.telemetry import Telemetry
from esw import crypto, if4
from harness.sensors import (observations_at, health_at, override_at, ota_at, drift_at, ack_at,
                             gnss_at, selftest_at)
from harness.sign import Sign
from harness.commands import CommandFeed

TICK_DT = 0.1  # 10 Hz fixed-rate tick (ADR-0015)

# Audit fingerprint stubs for the sim (doc 02 §7). cfg_ver is computed per run from the real
# clamped config (sm.cfg_ver); fw/model/calib are placeholders until those artifacts exist.
_SITE_ID = "bench-01"
_FW_VER = "sim-fw"
_MODEL_VER = "sim-model"
_CALIB_VER = "sim-calib"

# Per-site, per-channel link keys, DERIVED from a master secret (esw.crypto.derive_key,
# ADR-0012 / doc 10 §5): the channel label ("IF4" vs "CMD") and the site id are bound into
# the key itself, so a frame MAC'd for another unit or channel can never verify here even
# if a fleet were (mis)provisioned from one master. These are test vectors; real
# deployments provision the master out-of-band per unit and rotate it. _WRONG_* stand in
# for an attacker who can transmit but holds no key material for this unit.
_MASTER = b"esw-master-secret-v1-0123456789abc"
_KEY = crypto.derive_key(_MASTER, "IF4", _SITE_ID)
_WRONG_KEY = crypto.derive_key(b"attacker-without-the-master-secret", "IF4", _SITE_ID)

# The IF-8/9/10 command channel gets its OWN derived key -- a separate hardened channel from
# the sign link (ADR-0012). _WRONG_CMD_KEY is an attacker who can transmit on the uplink but
# holds no command key; the replay window is how fresh a command's timestamp must be.
_CMD_KEY = crypto.derive_key(_MASTER, "CMD", _SITE_ID)
_WRONG_CMD_KEY = crypto.derive_key(b"attacker-without-the-master-secret", "CMD", _SITE_ID)
_CMD_REPLAY_WINDOW_MS = 5000


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


def run_scenario(scenario, outbox=None):
    """Run one scenario; return the per-tick timeline (sign state + disposition).

    If `outbox` (an esw.sink.Outbox) is passed, every emitted IF-6/IF-7 record is teed into it
    each tick -- durably stored, then forwarded when the uplink is up -- so a run can be scored
    off the durable evidence log instead of the in-memory timeline (Level-E). Default None leaves
    the loop byte-for-byte unchanged, so boards A-D are unaffected."""
    cfg = _merge(default_config(), scenario.get("config_push", {}))
    sm = StateMachine(cfg)                        # SUT gets the (possibly bad) pushed config
    cfg_ver = sm.cfg_ver                          # fingerprint of the config IN FORCE (post-clamp, R10)
    monitor = HealthMonitor(sm.cfg)               # derives health/time/force-safe (shares clamped cfg)
    telem = Telemetry(_SITE_ID, {"fw_ver": _FW_VER, "cfg_ver": cfg_ver,
                                 "model_ver": _MODEL_VER, "calib_ver": _CALIB_VER})  # IF-6/IF-7 audit
    actuator = Actuator(_KEY, cfg_ver)            # edge-side IF-4 driver (refresh-or-blank)
    sign = Sign(default_config(), _KEY,           # controller uses in-bounds safety constants
                latch=scenario.get("sign_latch", False),
                can_turn_off=not scenario.get("sign_stuck", False))

    # Opt-in authenticated command channel (IF-8/9/10): when a scenario sets `auth_commands`, the
    # override / OTA / ack the SM consumes come ONLY from verified command frames (forged/replayed
    # ones are rejected upstream). Default off -> the plain injectors run, so SC-01..38 are unchanged.
    feed = None
    if scenario.get("auth_commands", False):
        feed = CommandFeed(scenario, _CMD_KEY, _WRONG_CMD_KEY, _CMD_REPLAY_WINDOW_MS, TICK_DT)

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
                    monitor = HealthMonitor(sm.cfg)     # fresh box: health monitor restarts too
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

        force_safe = False
        hm_status = None
        if killed_sm or sm_down:
            decision = {"assertion": "NONE"}      # SM process dead / rebooting -> nothing asserted
        else:
            # Health monitor runs BEFORE the SM: it derives {camera, radar} (so the sensor mode is
            # DERIVED, not injected), judges time integrity, and owns the independent force-safe.
            hm = monitor.step(t, health_at(scenario, t), gnss_at(scenario, t),
                              selftest_at(scenario, t))
            force_safe = hm["force_safe"]          # IF-5 independent force-safe authority
            hm_status = hm["status"]
            health = {"camera": hm["camera"], "radar": hm["radar"], "time_valid": hm["time_valid"]}
            if feed is not None:
                ov, ota_flag, ack_val, cfg_push = feed.step(t)   # authenticated IF-8/9/10 (verified only)
            else:
                ov = override_at(scenario, t)
                ota_flag = ota_at(scenario, t)
                ack_val = ack_at(scenario, t)
                cfg_push = None
            inputs = {"sign_status": sign_status,
                      "ota": ota_flag,
                      "drift": drift_at(scenario, t),
                      "ack": ack_val,
                      "config_push": cfg_push}
            decision = sm.tick(t, observations_at(scenario, t), health, ov, inputs)

        # The edge emits an authenticated refresh iff it is alive and asserting SHOW. A dead
        # box (box_dead) sends nothing; a killed/rebooting SM asserts NONE, so the actuator
        # sends nothing -> the sign blanks in every hard-failure case (RQ-H2). Refreshing
        # every 0.1 s tick is well inside T_assert_refresh; a real edge uses that timer.
        frame = None
        if not box_dead and not force_safe:       # a health-monitor force-safe (IF-5) inhibits the refresh
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

        # IF-6/IF-7 telemetry: the edge logs audit events + heartbeats WHILE IT IS ALIVE. A dead
        # box emits nothing -- missing heartbeats are how the TMC detects the outage -- so telemetry
        # is gated on box-alive, not on force-safe (a force-safed but live edge still logs the clear).
        if not (box_dead or killed_sm or sm_down):
            events = telem.step(t, decision, hm_status, sign_status)
        else:
            events = []

        # Optional durable evidence sink (Level-E). Tee the SAME records the reducer consumes into
        # the store-and-forward outbox: durable-append first, then forward on the uplink. Gating is
        # already done above -- a dead box produced no events, so nothing is stored (the log gap is
        # the outage). The sim collapses the sign link and the oversight uplink into one `link_cut`.
        if outbox is not None:
            outbox.record(events)
            outbox.pump(not link_cut)

        timeline.append({
            "t": t,
            "on": sign_status,
            "events": events,
            "state": decision.get("state"),
            "posture": decision.get("posture"),
            "mode": decision.get("mode"),
            "alert": decision.get("alert"),
            "override": decision.get("override"),
            "override_rejected": decision.get("override_rejected"),
            "ota_deferred": decision.get("ota_deferred"),
            "config_rejected": decision.get("config_rejected"),
            "alarm_count": decision.get("alarm_count"),
            "rejects": sign.rejects,
            "cmd_rejects": feed.rejects if feed is not None else 0,
            "cmd_last_reject": feed.last_reject if feed is not None else None,
            "hm_status": hm_status,
            "force_safe": force_safe,
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
                     "ota_deferred", "config_rejected", "alarm_count", "hm_status",
                     "cmd_rejects", "cmd_last_reject")


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
