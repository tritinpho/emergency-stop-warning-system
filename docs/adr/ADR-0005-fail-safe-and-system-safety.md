# ADR-0005: Fail-safe posture, safe state, and health escalation

**Status:** Proposed
**Date:** 2026-06-26
**Deciders:** PI, technical lead, road-safety advisor

## Context

This is the most important non-functional decision. The system influences fast-moving traffic near a
stationary obstacle, so its **behaviour when something breaks** matters as much as its behaviour when
healthy. Two failure modes pull in opposite directions ([doc 01 §1](../01-requirements.md#1-the-safety-reframe-read-this-first)):

- a **silent miss** (blind sensor, crashed process) — the warning that should appear never does, yet
  the unit looks "fine";
- a **stale / false ON** — a warning shown with no hazard, which trains drivers to ignore it
  ("cry wolf").

A naïve system has neither self-awareness nor a defined behaviour for either case. We must decide the
fail-safe posture explicitly.

## Decision

Adopt **fail-safe + fail-loud**:

1. A **health monitor independent of the perception path** continuously self-tests sensors, compute,
   the decision process, the link to the sign, and the sign's own status read-back; it emits a
   **heartbeat** to the TMC.
2. On any **critical fault**, the state machine enters a defined **SAFE STATE**: the sign is commanded
   to a **known, non-deceptive condition** (default: **CLEAR/blank** — never a *specific* "vehicle
   ahead" message it cannot substantiate), and the fault is **escalated to operators immediately**.
3. A **watchdog** bounds every activation: no warning may remain ON without fresh confirmation or a
   watchdog refresh (`T_watchdog`, NFR-04), eliminating indefinite stale-ON.
4. The unit **never reports healthy when it is degraded**; "blind" is an alarm condition, not silence.

> Why blank-on-fault rather than a persistent generic caution? A sign that is *always* cautioning
> becomes wallpaper and erodes trust in the real, specific warning (the cry-wolf failure). The honest
> degraded behaviour is: stop asserting a hazard you can no longer detect, and **make the outage
> loud to the people who can fix or compensate for it** (TMC, patrols) — not to drivers via a vague
> standing sign. Sites that genuinely warrant a standing "incident detection here" treatment can
> configure it per-site, but it is not the default.

## Options Considered

### Option A: No explicit fail-safe (best-effort)
**Pros:** least effort.
**Cons:** silent misses; possible stuck-ON; no operator visibility. Unacceptable for a safety
function.

### Option B: Fail-safe to **blank** + health escalation + watchdog *(chosen)*
**Pros:** no deceptive output; no stale-ON; outages are visible and actionable; protects trust.
**Cons:** requires an independent health monitor, watchdog, sign status read-back, and TMC alerting —
real engineering, but the core of a dependable system.

### Option C: Fail-safe to a **persistent generic caution** sign
**Pros:** "something is always warning" feels conservative.
**Cons:** classic cry-wolf — standing vague warnings get ignored, devaluing the specific warning; can
itself cause unnecessary braking. Rejected as default; allowed only as a per-site option.

## Trade-off Analysis

Option A optimises effort at the cost of the system's reason to exist. The real decision is between B
and C — *what does a failed sign show?* C trades a feeling of safety for trust erosion that
ultimately makes the **working** warning less effective. B keeps the channel **credible**: the sign
only ever asserts a hazard it can substantiate, and failures are routed to those who can act. Trust
is the product (guiding principle 3), so B wins.

## Consequences

- **Easier:** honest degradation; no stuck-ON; operators see outages and can dispatch patrols; the
  warning channel stays credible.
- **Harder:** must build the independent health monitor, watchdog, sign status read-back, fault
  taxonomy, and TMC alerting; must define and test the SAFE-STATE transition (fault injection is part
  of acceptance, [doc 01 §5](../01-requirements.md#5-evaluation-metrics--acceptance-criteria)).
- **Revisit when:** a productised field system pursues formal functional-safety treatment (e.g., a
  hazard analysis / SIL target) — this ADR is the foundation that effort would build on.

## Action Items

1. [ ] Enumerate the **fault taxonomy** (sensor dead, frame freeze, model crash, link down, sign
       unresponsive, power low, clock skew) and the response for each.
2. [ ] Implement the watchdog and the SAFE-STATE transition in the state machine.
3. [ ] Implement sign **status read-back** so "commanded ON" is verified against "actually ON."
4. [ ] Define TMC alert severities and acknowledgement flow.
5. [ ] Add **fault-injection tests** to the acceptance suite (target ≥95% fault-detection coverage).
