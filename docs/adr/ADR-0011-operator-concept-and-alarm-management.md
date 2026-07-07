# ADR-0011: Operator concept of operations & alarm management

**Status:** Proposed
**Date:** 2026-06-27
**Deciders:** PI (ThS. Phó Trí Tín), technical lead, road-safety advisor, expressway operator liaison

## Context

The whole safety design is **fail-safe + fail-loud** ([ADR-0005](ADR-0005-fail-safe-and-system-safety.md)):
on any failure the sign goes **blank** and the unit **escalates to the operator**. That makes the
**operator the terminal of almost every residual-risk path** in the system:

- a **silent miss** / blind unit fails to blank-and-alarm → the operator is meant to dispatch patrols / CCTV;
- a **BLIND-TO-NEW** (camera-dead) or **CAMERA-OCCLUDED-DEGRADED** unit escalates as critical → the
  operator is meant to investigate and, via CCTV, dispose of it ([ADR-0009 §B/§C](ADR-0009-failsafe-placement-and-degraded-modes.md));
- the **`T_degraded_max`** forced clear hands a sustained-occlusion decision explicitly to the operator;
- **congestion suppression** opens a deliberate coverage gap in a named high-risk condition, "carried to
  the operator concept" ([doc 04 §0](../04-risk-and-safety.md#0-limits-of-protection-residual-hazards));
- an **operator override** must be watched so a mute does not silently outlive its window
  ([ADR-0010](ADR-0010-operator-override-and-manual-control.md));
- the **fail-safe-blank × over-reliance** interaction is controlled by failing *loud to operators*
  ([doc 04 §0](../04-risk-and-safety.md#0-limits-of-protection-residual-hazards)).

Yet the first cut named "escalate to the TMC" as a verb and never specified the path. **"Fail loud" is
only a control if someone is listening and acts within a bounded time** — otherwise every escalation
above resolves to nothing. A flooded console (alarm fatigue), an unstaffed night shift, or an
unacknowledged critical alert silently defeats the compensating control the safety case leans on. This is
the missing **human half** of fail-loud, and it decides whether the autonomous design's residuals are
actually covered.

Forces: the safety case's dependence on operator compensation (dominant), alarm-fatigue / console
overload, operator staffing reality (the operator owns the TMC, not the project), liability (R10), and
the need to keep numbers field-tunable without leaving them unspecified now.

## Decision

Specify an **operator concept of operations (ConOps) + alarm-management discipline** as a first-class
part of the safety design (requirement **NFR-15**), not an afterthought left to the TMC integrator.

1. **Every escalation has a named operator response.** For each escalating condition —
   `BLIND-TO-NEW`, `CAMERA-OCCLUDED-DEGRADED`, `T_degraded_max` forced clear, low-confidence clear,
   `OVERRIDDEN`-past-window, sign-stuck / status-mismatch, power-low, link-down — the ConOps states
   **what the operator is expected to do** (acknowledge, verify via CCTV, dispatch a patrol, force-off /
   force-on within policy, schedule maintenance) and the **target time** to do it.
2. **Severity + target response time + re-escalation.** Each condition carries a **severity** and a
   **target acknowledge/respond time**; an **unacknowledged** escalation **re-escalates** (louder, or to
   a higher tier / supervisor), so a missed alarm is itself an alarmed condition. No safety-relevant
   escalation can sit unseen.
3. **Alarm load is bounded by design.** Alarms are **deduplicated** (one incident ≠ a storm of rows),
   **prioritized** (safety escalations rank above informational telemetry), and **rate-limited /
   grouped**, so a single failure or a noisy site cannot bury a critical alarm. Flapping conditions are
   debounced before they alarm.
4. **The machine never waits on the operator forever.** Where an autonomous bound exists it fires
   regardless of operator action — most sharply, **`T_degraded_max`** disposes of a sustained
   camera-occlusion ([ADR-0009 §C](ADR-0009-failsafe-placement-and-degraded-modes.md)) rather than
   holding the sign ON until a human happens to look. The ConOps **compensates** for residuals; it is
   **not** a link in the real-time safety loop ([ADR-0002](ADR-0002-edge-vs-cloud-processing.md) keeps
   that loop edge-local).
5. **Staffing & coverage are an explicit operator commitment.** Because the project does not own the
   TMC, the response path's **staffing, hours, and escalation tiers** are agreed in the **operator
   agreement** (sibling to the liability/roles clause, R10). The design states the *requirement*; the
   operator commits the *resourcing*. A site whose operator cannot staff the response path is a **siting
   constraint**, surfaced, not assumed away.
6. **Provisional numbers, field-tuned.** Concrete target response times and alarm-rate ceilings are set
   provisionally now and **calibrated at the field pilot** ([doc 05](../05-field-pilot-proposal.md)) with
   real alarm volumes and the operator's console — alongside the false-alarm trust-calibration (R2) and
   the MTBF/MTTR budget (NFR-03, [doc 04 §5 Q6](../04-risk-and-safety.md#5-open-safety-questions-for-the-team)).

## Options Considered

### Option A: Leave the operator path implicit ("escalate to TMC") *(the first-cut gap)*
| Dimension | Assessment |
|-----------|------------|
| Effort now | **None** |
| Safety-case integrity | **Broken** — every residual routes to an unspecified, possibly-absent responder |
| Alarm fatigue | Unmanaged — a noisy site can bury the one alarm that matters |

**Pros:** nothing to write now.
**Cons:** the compensating control the fail-safe posture depends on is undefined, so the residual-risk
claims (silent-miss, degraded-mode, congestion gap, override) are unbacked. Unacceptable for a
safety-related system.

### Option B: ConOps + alarm management as a specified requirement *(chosen)*
| Dimension | Assessment |
|-----------|------------|
| Effort now | Medium (ConOps table, severities, dedup/priority rules; numbers provisional) |
| Safety-case integrity | **Closed** — each escalation has a named, bounded, re-escalating response |
| Alarm fatigue | **Bounded** — dedup + priority + rate-limit by design |

**Pros:** makes "fail loud" a real control; bounds operator load before it becomes fatigue; gives the
operator agreement a concrete resourcing ask; field-tunable without being unspecified.
**Cons:** more design + an operator dependency to negotiate; one more requirement (NFR-15) and timer
class (`T_override_max`, ack-timeouts) to tune and fault-inject.

### Option C: Fully automate — remove the human from the loop
| Dimension | Assessment |
|-----------|------------|
| Operability | **Poor** — no one to dispatch a patrol, verify a degraded unit, or suppress a known false alarm |
| Feasibility | Out of scope — automated incident response / dispatch is an explicit non-goal ([doc 00 §2](../00-context-and-glossary.md#2-goal--non-goals)) |

**Pros:** no staffing dependency.
**Cons:** the residuals fail-safe-blank creates (a blind unit on a live road) *require* a human
compensator at this maturity; automating dispatch is a different, larger system. Rejected.

## Trade-off Analysis

The real choice is **A vs B — is the operator a specified system or a hopeful verb?** The autonomous
design spent its rigor eliminating silent and stuck outputs; all of that routes, on failure, to a human
who must notice and act. Leaving that human unspecified (A) quietly reintroduces the silent failure at
the *socio-technical* layer: a critical escalation no one acknowledges is, in effect, a silent miss with
extra steps. B costs a ConOps table and an operator-agreement clause, and in return every "escalate to
operator" in the other ADRs gains a defined, bounded, re-escalating response — and the machine still
never *waits* on the human, because the autonomous bounds (watchdog, `T_degraded_max`, override expiry)
fire on their own. The cost is modest and **testable** (inject a critical fault; confirm the alarm
raises, dedups, and re-escalates on non-ack).

## Consequences

- **Easier:** the residual-risk claims in [doc 04](../04-risk-and-safety.md) are actually backed; alarm
  load is bounded before fatigue sets in; the operator agreement has a concrete resourcing ask; a clean
  field-pilot calibration target.
- **Harder:** a ConOps table and severity model to author; alarm dedup/priority/rate-limit to build and
  fault-inject (NFR-15); a real **operator staffing dependency** to negotiate (R17), which can become a
  **siting constraint**; response-time numbers are provisional until the field pilot.
- **Revisit when:** field alarm volumes show the dedup/priority rules or response-time targets need
  retuning, or an operator's existing TMC alarm system mandates a specific integration (map this ConOps
  onto it rather than duplicating it).

## Action Items

1. [ ] Author the **ConOps table**: per escalating condition (`BLIND-TO-NEW`, `CAMERA-OCCLUDED-DEGRADED`,
       `T_degraded_max` clear, low-confidence clear, `OVERRIDDEN`-past-window, sign-stuck, power-low,
       link-down) → expected operator action + severity + target acknowledge/respond time.
2. [ ] Specify **alarm dedup, prioritization, rate-limiting, and re-escalation-on-non-ack**; add the
       OVERRIDDEN/degraded postures to the heartbeat surfacing
       ([doc 02 §7](../02-system-architecture.md#7-interfaces--contracts-initial)).
3. [x] Add **alarm-unacknowledged / alarm-flood** to the FMEA + fault-injection set
       ([doc 04 §2](../04-risk-and-safety.md#2-fmea-lite-failure-mode--effect--detection--response), R17)
       and verify a critical escalation re-escalates if unacknowledged. **Wired:** dedup +
       re-escalate-on-non-ack **and** the operator **ack** (IF-10 `command: ack`, keyed by
       `alarm_seq`) that clears a latched escalation and freezes re-escalation, epoch-scoped so a
       persistent fault re-raises and a fresh critical re-arms. Verified by **SC-30** (dedup +
       re-escalate) and **SC-32** (ack freeze → epoch re-arm) on the Level-A board.
4. [ ] Put **response-path staffing, hours, and escalation tiers** into the **operator agreement**
       (with the R10 roles/liability clause); flag sites that cannot staff it as a siting constraint.
5. [ ] Set **provisional** response-time and alarm-rate numbers; schedule their **field calibration**
       ([doc 05](../05-field-pilot-proposal.md)) alongside the R2 trust-calibration and the NFR-03
       MTBF/MTTR budget.
