# ADR-0004: Pluggable warning actuator — reuse existing VMS, dedicated solar LED sign otherwise

**Status:** Proposed
**Date:** 2026-06-26
**Deciders:** PI, technical lead, expressway operator liaison

## Context

The warning to drivers is the system's only output, so *how* it is displayed and *whether we build or
reuse* the sign is architecturally significant. Figure 1 shows both a **gantry variable-message sign
(VMS)** and a **roadside LED board**. Modern expressways frequently already have operator-controlled
VMS gantries and an ITS backbone; other segments (and any bench rig) have nothing. Adding redundant
signage is costly, slow to permit, and clutters the roadway.

Forces: capital cost, installation/permitting effort, integration complexity with third-party ITS,
sign-placement geometry (must sit ≥ DSD upstream — [doc 01 §4](../01-requirements.md#4-warning-placement--the-math-the-proposal-omits)),
QCVN 41 conformance, and operator acceptance/control.

## Decision

Define a **single actuator abstraction** (`SHOW(message) / CLEAR / STATUS`) with **two
interchangeable backends**:

1. **Existing-VMS backend** — where the road already has an operator-controlled VMS within the
   required upstream window, drive it via the operator's protocol (NTCIP-style / vendor API), subject
   to operator authorisation and arbitration.
2. **Dedicated-sign backend** — a **solar-powered QCVN-41-compliant LED warning sign** for
   un-instrumented segments and for the bench rig.

The state machine is agnostic to which backend is connected.

## Options Considered

### Option A: Always install a dedicated sign
| Dimension | Assessment |
|-----------|------------|
| Cost | High (hardware + civil works per site) |
| Permitting | Slow (new roadside structure) |
| Control clarity | Simple (we own it) |
| Reuse | None |

**Pros:** full control; uniform behaviour; works where no ITS exists.
**Cons:** expensive and slow where a perfectly good VMS already exists; sign clutter; redundant.

### Option B: Always reuse existing VMS
| Dimension | Assessment |
|-----------|------------|
| Cost | Low (no new sign) |
| Coverage | Only where VMS already exists at the right place |
| Integration | Operator protocol + arbitration |
| Control | Shared with operator priorities |

**Pros:** cheapest; no clutter; leverages existing approved infrastructure.
**Cons:** unavailable on un-instrumented segments; VMS may not sit at the required upstream distance;
priority conflicts with other operator messages; can't run a standalone bench rig.

### Option C: Pluggable abstraction, choose backend per site *(chosen)*
| Dimension | Assessment |
|-----------|------------|
| Cost | Optimised per site |
| Coverage | Universal (reuse or install) |
| Integration | One stable internal interface, two adapters |
| Control | Clear; arbitration handled in the VMS adapter |

**Pros:** reuse where possible, install where necessary; the core logic never changes; testable on a
bench LED today, deployable against real VMS later.
**Cons:** must build and maintain two adapters; the VMS adapter needs per-operator integration work.

## Trade-off Analysis

Committing to a single physical sign strategy (A or B) is a false economy: A overspends where ITS
exists; B has coverage gaps and geometry mismatches. The cost that actually matters is **coupling the
decision logic to a sign type** — avoided entirely by Option C's abstraction. The variability (vendor
protocols, operator arbitration, QCVN 41 message formatting) is isolated in adapters, keeping the
safety-critical state machine stable and testable. This also lets the university prototype use a cheap
LED panel while preserving a clean path to real VMS in the field pilot.

## Consequences

- **Easier:** per-site cost optimisation; bench testing today; field VMS reuse later; stable core.
- **Harder:** two adapters to maintain; the VMS adapter requires operator-specific integration and an
  **arbitration policy** (what wins if the operator is already showing a message); message content
  must be QCVN-41-conformant in both backends.
- **Revisit when:** a standard ITS message protocol is mandated by the operator (collapse toward one
  adapter), or a V2X/in-vehicle warning channel is added (a *third* backend behind the same interface).

## Action Items

1. [ ] Specify the `SHOW/CLEAR/STATUS` actuator interface and status read-back semantics.
2. [ ] Engage an expressway operator to learn their VMS protocol and message-arbitration rules.
3. [ ] Select a QCVN-41-compliant solar LED sign for the dedicated backend / bench rig.
4. [ ] Define the approved warning message set and its conformance review.
