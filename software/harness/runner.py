# Scenario runner + oracle comparator (doc 07 §2, §4).
#
# Drives the real esw StateMachine at a fixed tick, models the actuator refresh
# and the sign dead-man's switch, injects faults, then scores the recorded
# sign-state timeline against the scenario's oracle checkpoints.

from esw.params import default_config
from esw.state_machine import StateMachine, MESSAGE_STOPPED
from harness.sensors import observations_at, health_at
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

    killed_sm = box_dead = link_cut = False
    timeline = []
    steps = int(scenario["duration"] / TICK_DT) + 1
    for i in range(steps):
        t = round(i * TICK_DT, 3)
        for f in scenario.get("faults", []):
            if t >= f["t"]:
                kind = f["kind"]
                if kind == "kill_sm":
                    killed_sm = True
                elif kind == "kill_box":
                    box_dead = True
                elif kind == "cut_link":
                    link_cut = True
        sign.link_up = not link_cut

        if killed_sm:
            decision = {"assertion": "NONE"}     # SM process dead -> nothing asserted
        else:
            decision = sm.tick(t, observations_at(scenario, t), health_at(scenario, t))

        if (not box_dead) and decision.get("assertion") == "SHOW":
            # Actuator refreshes at >= T_assert_refresh; ticking (0.1s) is well inside it.
            sign.refresh(t, decision.get("message_id", MESSAGE_STOPPED))

        timeline.append((t, sign.update(t)))
    return timeline


def sign_on_at(timeline, t):
    """Sign state at time t = the most recent sample at or before t."""
    on = False
    for (tt, val) in timeline:
        if tt <= t + 1e-9:
            on = val
        else:
            break
    return on


def evaluate(scenario, timeline):
    """Return a list of (t, expected, got) for every failed oracle checkpoint."""
    fails = []
    for c in scenario.get("checks", []):
        got = sign_on_at(timeline, c["t"])
        if got != c["on"]:
            fails.append((c["t"], c["on"], got))
    return fails
