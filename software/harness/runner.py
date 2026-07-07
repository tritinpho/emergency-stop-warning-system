# Scenario runner + oracle comparator (doc 07 §2, §4).
#
# Drives the real esw StateMachine at a fixed tick, models the actuator refresh
# and the sign dead-man's switch, injects faults, then scores the recorded
# sign-state timeline against the scenario's oracle checkpoints.

from esw.params import default_config
from esw.state_machine import StateMachine, MESSAGE_STOPPED
from harness.sensors import observations_at, health_at, override_at, ota_at, drift_at, ack_at
from harness.sign import Sign

TICK_DT = 0.1  # 10 Hz fixed-rate tick (ADR-0015)


def _merge(base, over):
    out = dict(base)
    for k in over:
        out[k] = over[k]
    return out


def run_scenario(scenario):
    """Run one scenario; return the sign-on timeline as a list of (t, on)."""
    cfg = _merge(default_config(), scenario.get("config_push", {}))
    sm = StateMachine(cfg)                       # SUT gets the (possibly bad) pushed config
    sign = Sign(default_config(),                # the sign uses in-bounds safety constants
                latch=scenario.get("sign_latch", False),
                can_turn_off=not scenario.get("sign_stuck", False))

    killed_sm = box_dead = link_cut = rebooted = False
    sign_status = False                          # IF-3 status read-back (one tick delayed)
    timeline = []
    steps = int(scenario["duration"] / TICK_DT) + 1
    for i in range(steps):
        t = round(i * TICK_DT, 3)
        sm_down = False
        for f in scenario.get("faults", []):
            kind = f["kind"]
            if kind == "reboot":                 # warm reboot: SM dead in downtime, then fresh
                down = f.get("downtime", 2.0)
                if f["t"] <= t < f["t"] + down:
                    sm_down = True
                elif t >= f["t"] + down and not rebooted:
                    sm = StateMachine(cfg)        # restart comes up IDLE -> full re-confirm
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
            decision = {"assertion": "NONE"}     # SM process dead / rebooting -> nothing asserted
        else:
            inputs = {"sign_status": sign_status,
                      "ota": ota_at(scenario, t),
                      "drift": drift_at(scenario, t),
                      "ack": ack_at(scenario, t)}
            decision = sm.tick(t, observations_at(scenario, t), health_at(scenario, t),
                               override_at(scenario, t), inputs)

        if (not box_dead) and decision.get("assertion") == "SHOW":
            # Actuator refreshes at >= T_assert_refresh; ticking (0.1s) is well inside it.
            sign.refresh(t, decision.get("message_id", MESSAGE_STOPPED))

        sign_status = sign.update(t)             # read-back fed to the next tick (IF-3)
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
