# ADR-0010: Operator override & manual-control policy

**Status:** Proposed
**Date:** 2026-06-27
**Deciders:** PI (ThS. Phó Trí Tín), technical lead, road-safety advisor, expressway operator liaison

## Context

[FR-13](../01-requirements.md#2-functional-requirements) grants operators a manual override —
**force-on, force-off, mute** — and the TMC dashboard exposes it
([doc 02 §2](../02-system-architecture.md#2-logical-architecture-components--responsibilities)). The
first cut named the capability in one line and never analysed it, yet override is a **safety-critical
control path that bypasses the very invariants the rest of the safety design is built on**:

- **Force-off / mute while a real hazard is present is an operator-induced _silent miss_** — the
  dominant hazard ([doc 01 §1](../01-requirements.md#1-the-safety-reframe-read-this-first)), now
  created deliberately and remotely. A mute that persists silently is indistinguishable from the very
  failure the whole design exists to prevent.
- **Force-on collides with the no-latch dead-man's switch**
  ([ADR-0009 §A](ADR-0009-failsafe-placement-and-degraded-modes.md)). The warning is asserted only by a
  *continuously refreshed* `SHOW` heartbeat, precisely so that a dead box or cut link blanks the sign.
  A forced-on warning must answer: *who refreshes the heartbeat, and over which link?* If the TMC
  **latches** a message over the WAN, it reintroduces exactly the stale-ON the architecture removed —
  and couples a safety output to the network the safety loop is meant to be independent of
  ([ADR-0002](ADR-0002-edge-vs-cloud-processing.md)).
- Override is an **authenticated remote command**, so it is part of the NFR-09 attack surface — a
  spoofed force-off is a *denial-of-warning*, a spoofed force-on is *cry-wolf* — and is owed the same
  treatment as config/OTA ([doc 04 §5 Q5](../04-risk-and-safety.md#5-open-safety-questions-for-the-team)).

The override semantics must therefore be decided **explicitly**, not left to implementation, because
each naïve choice silently re-opens a failure mode the other ADRs spent their effort closing.

## Decision

Adopt a **bounded, fail-loud, heartbeat-honoring** override model. Every override is **authenticated,
reason-coded, written to the immutable audit trail, and time-bounded with mandatory auto-expiry**
(`T_override_max`); **none may silently persist.**

1. **Detection and logging never stop.** Override acts only on the *sign output* — never on
   perception, fusion, the state machine's evaluation, or the audit log. The unit keeps detecting and
   recording throughout, so an override is always reconstructable after the fact, and a real hazard
   present during a mute is logged as a **known, operator-accepted exposure** (feeds the R10 liability
   audit).
2. **Force-off / mute is time-bounded and loud.** It carries a mandatory expiry (default **30 min**,
   ceiling `T_override_max` e.g. **8 h**) — both bounded and staged/validated like a config change
   (sibling to [FR-20](../01-requirements.md#2-functional-requirements)). While active, the unit
   reports an **OVERRIDDEN** posture in its heartbeat (it is **not** "healthy"), the TMC shows it
   prominently, and the condition **escalates** if the override outlives its window. On expiry, normal
   logic resumes automatically and re-evaluates from the current sensor state.
3. **Force-on honors the refreshed-`SHOW` contract — it never latches.** An operator-forced warning is
   asserted by the **same refreshed `SHOW` heartbeat** the state machine uses, refreshed **by the edge
   box (locally)**, under an authenticated, time-bounded command. The dead-man's switch therefore
   still protects it: a dead edge box, a cut/jammed link, or expiry all blank the sign. A force-on
   issued from the TMC is **mediated and refreshed by the edge box, not latched over the WAN**; if the
   box or link is down, force-on simply *cannot assert* (fail-safe-blank preserved) and the operator is
   told so.
4. **Override authority is scoped and authenticated.** Define the operator roles permitted to
   override; require authenticated, non-repudiable commands on the same hardened channel as config/OTA
   (NFR-09). An unauthenticated party can neither suppress nor assert a warning.
5. **Override is bounded like config.** Out-of-policy overrides (an expiry beyond the ceiling, an
   unknown message id, a force-on with no operator-supplied reason) are **rejected or clamped at the
   unit** (the FR-20 mechanism), not honored blindly.

## Options Considered

### Option A: No override (autonomous-only)
| Dimension | Assessment |
|-----------|------------|
| Attack surface | **None added** |
| Operability | **Poor** — cannot suppress a known false alarm, mute a sign under maintenance, or assert a warning for an incident the detector missed |
| Complexity | Low |

**Pros:** nothing to secure; no bypass path.
**Cons:** operationally untenable — operators *will* need to suppress and to assert; denying it pushes
them toward worse out-of-band workarounds (pulling the sign's power, etc.). Rejected.

### Option B: Unbounded latching override (set state until manually unset)
| Dimension | Assessment |
|-----------|------------|
| Complexity | **Low** |
| Silent-miss risk | **High** — a forgotten mute is a permanent silent miss |
| Stale-ON risk | **High** — a latched force-on reintroduces stale-ON, coupled to the WAN |
| Fail-safe | **Bypassed** — the dead-man's switch no longer governs the sign |

**Pros:** trivial.
**Cons:** pays for convenience in exactly the two failure modes the architecture exists to remove.
Disqualifying for a safety function.

### Option C: Bounded, fail-loud, heartbeat-honoring override *(chosen)*
| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium (expiry timers, OVERRIDDEN posture, edge-mediated force-on, channel auth) |
| Silent-miss risk | **Bounded** — mute auto-expires and is loud while active |
| Stale-ON risk | **Bounded** — force-on is refreshed, not latched; dead-man's switch still blanks |
| Fail-safe | **Preserved** — override lives inside the same fail-safe frame as the autonomous logic |

**Pros:** real operator control without ever creating a silent or stuck output; every override
authenticated, bounded, and audited.
**Cons:** more to build and to fault-inject; one more safety-relevant timer (`T_override_max`).

## Trade-off Analysis

The real choice is **B vs C — what does an override cost when the operator walks away?** B's
convenience is paid for in precisely the two failure modes the rest of the architecture spends its
effort eliminating: a forgotten mute is a *silent miss*, a latched force-on is *stale-ON* coupled to
the network. C keeps override inside the same fail-safe frame as the autonomous logic — **bounded,
loud, downstream-blankable, audited** — so a manual action can never quietly defeat the safety
function. The cost is modest and **entirely testable by fault injection** (let a mute expire; kill the
box under a force-on; replay a captured override command).

## Consequences

- **Easier:** operators can suppress false alarms and assert known incidents without ever creating a
  silent or stuck output; every manual action is auditable for the liability case (R10).
- **Harder:** expiry timers, the OVERRIDDEN heartbeat posture and its TMC surfacing, edge-mediated
  (non-latching) force-on, and authentication on the override channel must be built and fault-injected;
  `T_override_max` becomes a safety-relevant parameter to tune.
- **Revisit when:** an operator integration mandates a specific override/arbitration protocol on a
  third-party VMS — the VMS adapter must map this policy onto the operator's controls, and a **latching
  VMS inherits the [ADR-0009 §A](ADR-0009-failsafe-placement-and-degraded-modes.md) residual for
  force-on too** (it cannot give the refreshed-assertion guarantee).

## Action Items

1. [ ] Specify the override commands (force-on / force-off / mute) with authentication, reason code,
       expiry, and the **OVERRIDDEN** heartbeat posture; add them to the
       [doc 02 §7](../02-system-architecture.md#7-interfaces--contracts-initial) interface contracts and
       the audit schema.
2. [ ] Implement **edge-mediated, refreshed (non-latching) force-on**; verify the dead-man's switch
       still blanks it on box-kill / link-cut / expiry (extends
       [ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.md) AI#2).
3. [ ] Implement **mandatory auto-expiry + TMC escalation** for mute/force-off; verify a mute cannot
       silently outlive its window.
4. [ ] **Enforce override bounds at the unit** (FR-20 mechanism); reject/clamp out-of-policy overrides.
5. [ ] Fold override into the **NFR-09 threat model**
       ([doc 04 §5 Q5](../04-risk-and-safety.md#5-open-safety-questions-for-the-team)) and the override
       **FMEA rows** ([doc 04 §2](../04-risk-and-safety.md#2-fmea-lite-failure-mode--effect--detection--response)).
