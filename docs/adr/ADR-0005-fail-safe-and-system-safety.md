# ADR-0005: Fail-safe posture, safe state, and health escalation

**Status:** Accepted (software side) — 2026-06-27
**Date:** 2026-06-26
**Deciders:** PI, technical lead, road-safety advisor

> ## ⚠ PHASE NOTE — this build is CAMERA-ONLY
>
> [ADR-0001](ADR-0001-sensing-modality.md) (camera + radar fusion) was **Rejected on 2026-07-10**. The cấp trường bench
> prototype ships **camera-only**. Every radar-dependent behaviour described below — radar
> corroboration, the occlusion hold (`WARN_HOLD` / `CAMERA_OCCLUDED_DEGRADED`), `T_degraded_max`, and
> the `FULL` / `RADAR-ONLY` sensing modes — is **dormant: the code retains it, but it never executes**,
> because `corr` is never true without a radar channel.
>
> Accepted consequences: **R5** (night/rain/fog blindness) is **unmitigated** and night/adverse recall
> is **not claimed**; **R20** — an occluded vehicle is cleared at `T_hold` (~10 s), blanking the sign
> with the hazard present; **R21** — the unit sits permanently in `CAMERA_ONLY`, hence permanently
> `DEGRADED`. See [doc 04](../04-risk-and-safety.md).
>
> Radar content below is the **cấp sở** target design, not this phase's build.

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
2. On any **critical fault**, the system enters a defined **SAFE STATE**: the sign is driven to a
   **known, non-deceptive condition** (default: **CLEAR/blank** — never a *specific* "vehicle ahead"
   message it cannot substantiate), and the fault is **escalated to operators immediately**.
3. **Independent safe-state actuation (dead-man's switch).** The actuator **defaults to the safe
   (blank) state on loss of a fresh "assertion" heartbeat** from the state machine, and the health
   monitor holds a **direct path to force the actuator safe that does not route through the state
   machine**. A crashed or wedged SM therefore **cannot** leave a warning asserted — the sign falls
   blank on its own. This reconciles the [doc 02](../02-system-architecture.md) invariant ("only the
   state machine may *assert* a warning") with fail-safe: the SM is the only component that may
   *assert*, but it is **not required in order to clear**. Without this, the component that detects a
   wedged SM would have to command the safe state *through* the very SM that is wedged — a watchdog
   that depends on its subject. **The safe-state actuation must physically live in the _sign
   controller_, downstream of the local link — not in the edge box** — or a dead edge box, a wedged OS,
   or a cut/jammed link strands a latched sign in its last (possibly ON) state. The placement, the
   refreshed-assertion protocol, its `T_signhold` timing trade-off, and the latching-VMS caveat are
   specified in [ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.md), which also fixes the
   asymmetric **degraded-mode** semantics (a camera-dead unit is *blind to new hazards*, not "degraded
   but running").
4. A **watchdog** bounds every activation: no warning may remain ON without fresh confirmation or
   corroboration (`T_watchdog`, NFR-04), eliminating indefinite stale-ON. Its interaction with the
   occlusion hold is specified in [ADR-0008](ADR-0008-detection-persistence-and-multitrack.md) — the
   watchdog clears **and raises a fault**, so a clear under uncertainty is never silent. The one state the
   watchdog *deliberately* does not bound (camera occluded, radar still corroborating) is bounded instead
   by **`T_degraded_max`** ([ADR-0009 §C](ADR-0009-failsafe-placement-and-degraded-modes.md)), so no state
   holds the sign ON indefinitely.
5. The unit **never reports healthy when it is degraded**; "blind" is an alarm condition, not silence.
6. The fail-loud escalation assumes a **bounded operator response path** — alarm dedup/prioritization,
   severities, target response times, re-escalation — specified in
   [ADR-0011](ADR-0011-operator-concept-and-alarm-management.md); and the control / telemetry / override
   attack surface is enumerated in the threat model
   ([ADR-0012](ADR-0012-security-and-threat-model.md)). Both were left implicit in the first cut: "fail
   loud" is only a control if someone is listening, and "cannot be spoofed" needs a stated surface.

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
3. [ ] Implement the **dead-man's switch** in the **sign controller** (downstream of the link), plus an
       independent health-monitor → actuator force-safe path, per
       [ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.md) (verify by killing the SM process,
       **killing the edge box, and cutting the link** in fault-injection tests and confirming the sign
       blanks within `T_signhold` in every case).
4. [ ] Implement sign **status read-back** so "commanded ON" is verified against "actually ON."
5. [ ] Define TMC alert severities and acknowledgement flow.
6. [ ] Add **fault-injection tests** to the acceptance suite (target ≥95% fault-detection coverage).
