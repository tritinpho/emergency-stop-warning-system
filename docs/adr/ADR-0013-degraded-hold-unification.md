# ADR-0013: Degraded-hold unification — a camera-unverified warning is bounded regardless of cause, and the warning × sensor-mode matrix

**Status:** Accepted (software side) — 2026-06-27
**Date:** 2026-06-27
**Deciders:** PI (ThS. Phó Trí Tín), technical lead, road-safety advisor, CV engineer

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
>
> **Unaffected and shipped:** §A (the dead-man's switch in the sign controller) and the
> `CLEARING → SAFE_STATE` sign-stuck rule are **not** radar-dependent. They remain live.

## Context

[ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.md) did two things that, read together,
leave one path under-specified:

- **§C** bounded the `CAMERA_OCCLUDED_DEGRADED` state with **`T_degraded_max`** — because the watchdog
  is *deliberately suppressed while radar corroborates*
  ([ADR-0008](ADR-0008-detection-persistence-and-multitrack.md) §4), a warning held ON on radar alone
  (camera **occluded**, view blocked by a through-lane truck) had no terminal bound, so under a weak
  [ADR-0001](ADR-0001-sensing-modality.md) criterion (b) the "corroborating" return could be the
  occluding truck and the sign would stay ON forever. `T_degraded_max` forces a **loud low-confidence
  clear + max-severity escalation** on expiry.
- **§B** gave the **RADAR-ONLY** sensing mode (camera **dead / frozen**) the rule: *cannot initiate a
  new warning (BLIND-TO-NEW), but may **hold an already-confirmed warning briefly** while radar
  corroborates.* That "brief bounded hold" was never given a **named timer or a terminal disposition**.

These are the **same hazard wearing two labels.** In both, *the warning is held ON while the camera
cannot verify the in-ROI track and only radar corroborates* — so both inherit the exact failure §C was
written to close: if criterion (b) is weak, the corroborating return may be a **through-lane vehicle**,
not the shoulder car, and the warning becomes a **stale-ON keyed to through-traffic that never clears**.
Yet only the occlusion label got the bound. The camera-**fault** label — which is *worse*, because a
dead camera has **no prospect of re-acquiring** the track in software, so there is not even a
self-healing exit — was left with an unbounded "briefly."

A second, related gap sits underneath it. The decision state machine
([doc 02 §4](../02-system-architecture.md#4-the-detectionwarning-state-machine)) is modelled as a single
region over the **warning** lifecycle (IDLE → … → WARN_ON/WARN_HOLD/CAMERA_OCCLUDED_DEGRADED → CLEARING →
SAFE_STATE). But **sensing health** (FULL / CAMERA-ONLY / RADAR-ONLY / NEITHER,
[ADR-0009 §B](ADR-0009-failsafe-placement-and-degraded-modes.md)) is an **orthogonal** dimension: a unit
can be in WARN_ON *and* lose its camera. The behaviour lives in the **product** of the two regions, and
that product was specified only in prose scattered across [ADR-0009 §B](ADR-0009-failsafe-placement-and-degraded-modes.md),
the [doc 02 §4](../02-system-architecture.md#4-the-detectionwarning-state-machine) degraded-mode table,
and the [doc 04 §2](../04-risk-and-safety.md#2-fmea-lite-failure-mode--effect--detection--response) FMEA
— never enumerated. The most consequential cell (camera dies *while a warning is active*) is exactly the
unbounded path above. A builder implementing the state machine cannot derive the right behaviour from the
single-region diagram; they will guess, and the guess is a safety parameter.

Forces: silent-miss avoidance and stale-ON avoidance (both dominant), the deliberate watchdog
suppression under corroboration, implementability (the model must be buildable without inference), and
testability (every cell must be reachable by fault injection).

## Decision

### A. One bound for "camera cannot verify, radar corroborates" — whatever the cause

**Any state in which the warning is held ON while (i) the camera cannot verify the in-ROI track and
(ii) only radar corroborates is bounded by `T_degraded_max`** and resolves, on expiry without camera
re-verification, to the **same forced loud low-confidence clear + max-severity operator escalation**
([ADR-0009 §C](ADR-0009-failsafe-placement-and-degraded-modes.md),
[ADR-0011](ADR-0011-operator-concept-and-alarm-management.md)). The cause of the camera being unable to
verify — sustained **occlusion** (camera alive, view blocked) **or** camera **fault** (frozen / dead /
RADAR-ONLY) — does **not** change the bound. This generalises §C's rule to the camera-fault case that
§B left unbounded, and is the principled closure of the *last* under-specified hold (NFR-04, broadened in
pass 4 to sensor-discrimination stale-ON, now reads on cause-agnostic camera-unverified stale-ON).

The two causes differ in **exactly one** respect — the **re-acquire prospect** — and the state machine
encodes only that difference:

| Cause | Self-healing exit | Leaves the bounded hold via |
|-------|-------------------|------------------------------|
| **Occlusion** (camera alive, blocked) | **Yes** — `→ WARN_ON` when the camera re-acquires the track | camera re-acquire · confirmed exit (if it can observe one) · loss of all corroboration → `T_hold` → loud clear · **`T_degraded_max`** forced clear |
| **Camera fault** (dead / frozen) | **No** — a dead camera cannot re-acquire in software | loss of all corroboration → loud clear · **`T_degraded_max`** forced clear · → SAFE_STATE if radar also drops (NEITHER) |

Because the camera-fault variant has **no self-healing exit and no observable confirmed exit** (a dead
camera cannot watch a footprint cross the exit boundary), `T_degraded_max` is in practice its **only**
autonomous terminal — which is precisely why leaving it unbounded was the sharper hole. Operators **may**
configure a **shorter** ceiling for the fault variant than for occlusion (there is no point holding a
warning on radar-only for the full occlusion budget when the camera will not return without a truck
roll), but the default is the single `T_degraded_max`; both are within the FR-20 bounds surface
([doc 01 FR-20](../01-requirements.md#2-functional-requirements),
[doc 02 §7a](../02-system-architecture.md#7-interfaces--contracts-initial)).

The state name `CAMERA_OCCLUDED_DEGRADED` is **retained for continuity** but is now defined as
*"camera cannot verify the in-ROI track (by occlusion **or** fault) while radar corroborates"* — the name
reads "occluded," the semantics are "camera-unverified." Where the distinction matters (re-acquire
prospect, escalation severity) the docs name the cause explicitly.

### B. The warning × sensor-mode interaction matrix (the two regions, made explicit)

The warning lifecycle and the sensing-health mode are **concurrent regions**. Their interaction is
**enumerated**, not left to prose:

| Sensing mode → | **FULL** (cam+radar) | **CAMERA-ONLY** (radar dead) | **RADAR-ONLY** (camera dead) | **NEITHER** |
|---|---|---|---|---|
| **IDLE / TRACKING** | normal | initiate OK; no radar cross-check; degraded + alert | **BLIND-TO-NEW** — cannot initiate (no class, no image-ROI gate); **critical alert** | **SAFE STATE** + critical alert |
| **CONFIRMED → WARN_ON** | normal | normal initiate; no occlusion hold available | warning **was** asserted, camera now dead → enters the **bounded camera-unverified hold** (§A): held while radar corroborates, **`T_degraded_max`**, **critical alert** | **SAFE STATE** (blank) + critical alert |
| **WARN_HOLD** (track lost, no exit) | hold while corroborated; → `CAMERA_OCCLUDED_DEGRADED` past `T_occlusion` | brief `T_hold` hysteresis only (no radar to corroborate) → loud low-confidence clear | **bounded camera-unverified hold** (§A), `T_degraded_max`, **critical alert** | **SAFE STATE** + critical alert |
| **CAMERA_OCCLUDED_DEGRADED** | (occlusion cause) bounded by `T_degraded_max`; `→ WARN_ON` on re-acquire | same, with no radar cross-check note | (fault cause) bounded by `T_degraded_max`; **no** re-acquire exit | **SAFE STATE** + critical alert |
| **CLEARING** | clear; confirm sign off | clear; confirm sign off | clear; confirm sign off | **SAFE STATE** + critical alert |

Reading: **RADAR-ONLY is BLIND-TO-NEW when idle and a bounded camera-unverified hold when a warning is
already up** — never an unbounded or silent state in any cell. **NEITHER is always SAFE STATE.**
CAMERA-ONLY keeps the ability to *initiate* (the camera alone can class + gate + track) but loses the
radar occlusion hold and the independent stationary cross-check, so a lost track with no corroboration
falls to the brief `T_hold` and then a loud low-confidence clear — never a silent one.

### C. State-machine deltas (authoritative Mermaid in doc 02 §4)

1. Add transitions **`WARN_ON → CAMERA_OCCLUDED_DEGRADED`** and **`CONFIRMED → CAMERA_OCCLUDED_DEGRADED`**
   on *camera fault while radar corroborates* (today only `WARN_HOLD → CAMERA_OCCLUDED_DEGRADED` via the
   occlusion timeout exists). The destination state and its `T_degraded_max` bound are unchanged — this
   only adds the camera-fault **entry** so the unbounded §B "brief hold" routes into the bounded state.
2. The `CAMERA_OCCLUDED_DEGRADED → WARN_ON` (camera re-acquires) edge applies to the **occlusion** cause
   only; the fault cause has no such edge (per §A).
3. Independently of §A/§B, add **`CLEARING → SAFE_STATE`** on *sign status ≠ off after CLEAR* (a
   physically stuck-ON sign — the one fault the dead-man's switch cannot fix, since the sign will not
   blank): the machine leaves CLEARING to SAFE STATE and raises a **sign-stuck maintenance escalation**
   ([ADR-0011](ADR-0011-operator-concept-and-alarm-management.md)) rather than looping in CLEARING. This
   closes the only state with no modelled exit on its failure branch.

## Options Considered

### Option A: Leave §B's "brief hold" as prose, tune a magic number in code
| Dimension | Assessment |
|-----------|------------|
| Effort now | **None** |
| Safety-case integrity | **Broken** — the one path the watchdog can't bound is unbounded for the camera-fault cause |
| Implementability | **Poor** — "briefly" is a safety timer with no value or disposition |

**Pros:** nothing to write.
**Cons:** re-opens, under the "camera-dead" label, exactly the indefinite stale-ON `T_degraded_max` was
created to close; hands the builder an undefined safety parameter. Unacceptable for a safety function.

### Option B: Unify the bound (cause-agnostic) + enumerate the warning × sensor-mode matrix *(chosen)*
| Dimension | Assessment |
|-----------|------------|
| Effort now | Low–medium (one generalisation + one matrix + two Mermaid edges) |
| Safety-case integrity | **Closed** — no camera-unverified hold is unbounded, whatever the cause |
| Implementability | **High** — the product of the two regions is a table, not an inference |

**Pros:** one rule for one hazard; the orthogonal regions are explicit so the build is deterministic;
every cell is a fault-injection target; reuses `T_degraded_max` (no new core parameter, just an optional
shorter ceiling for the fault variant).
**Cons:** the state name `CAMERA_OCCLUDED_DEGRADED` slightly under-describes its (now broader) meaning —
mitigated by stating the definition wherever it first appears.

### Option C: Rename the state and split into two distinct degraded states
| Dimension | Assessment |
|-----------|------------|
| Naming clarity | **High** |
| Churn / regression risk | **High** — the name threads through ~10 EN docs + VI siblings + the diagram |
| Behavioural benefit over B | **None** — the bound and disposition are identical |

**Pros:** the name would match the meaning exactly.
**Cons:** large cross-document rename for zero behavioural gain, and two states where one suffices invites
the divergent-handling bug this ADR exists to remove. Rejected in favour of B's single bounded state with
a stated definition.

## Trade-off Analysis

The decisive observation is that **"camera occluded, radar corroborating" and "camera dead, radar
corroborating" are the same warning-held-without-verification hazard**, so they must share one bound; the
only real difference — whether the camera can come back — is a single transition, not a different safety
rule. Option A's prose "briefly" is how a reviewed design still ships an unbounded stale-ON: the hole is
invisible because it is described in words, not a timer. Option C buys naming at the price of churn and a
second code path. Option B closes the hole with the parameter already defined, makes the two-region
product a table the builder can implement directly, and folds the orphan stuck-ON CLEARING branch into the
model — all testable by fault injection (kill the camera under an active warning; confirm `T_degraded_max`
forces a loud clear; command CLEAR against a wedged-ON sign; confirm escalation to SAFE STATE). It is the
same fail-safe/fail-loud move ([ADR-0005](ADR-0005-fail-safe-and-system-safety.md)) applied to the last
two unmodelled branches.

## Consequences

- **Easier:** no camera-unverified warning can stick ON indefinitely, whether the camera is blocked or
  dead; the state machine is implementable without inferring cross-region behaviour; the stuck-ON CLEARING
  branch has a defined exit; one bound to tune and fault-inject, not two.
- **Harder:** the `CAMERA_OCCLUDED_DEGRADED` name now needs its broadened definition stated where it
  appears; one more entry transition and the CLEARING→SAFE_STATE edge to implement and test; an optional
  second (shorter) ceiling for the fault variant to expose through config (within FR-20 bounds).
- **Residual:** after a `T_degraded_max` forced clear on a *genuinely-present but camera-dead* vehicle,
  the hazard is real, unwarned, and **cannot re-warn until the camera is repaired** (RADAR-ONLY cannot
  initiate). This is a **stated, operator-owned residual** — the forced clear hands a known live hazard to
  the operator (CCTV/patrol) with max-severity escalation; it is the honest disposition, not a silent one,
  and its response time is the NFR-15 / [ADR-0011](ADR-0011-operator-concept-and-alarm-management.md)
  concern. Tracked at [doc 04 R18](../04-risk-and-safety.md#1-risk-register) (extended to the camera-fault
  cause).
- **Revisit when:** field data quantifies how often camera faults occur mid-warning and how long
  genuinely-present occlusions last (tune the occlusion vs fault ceilings separately), or a richer health
  monitor can distinguish a corroborating shoulder return from a through-lane one at range (relaxes the
  whole §A concern — it is the [ADR-0001](ADR-0001-sensing-modality.md) criterion (b) dependency).

## Action Items

1. [ ] Generalise `CAMERA_OCCLUDED_DEGRADED` to *camera-unverified (occlusion **or** fault)* and route
       **camera-fault-while-warning** into it, bounded by `T_degraded_max`; update the
       [doc 02 §4](../02-system-architecture.md#4-the-detectionwarning-state-machine) Mermaid (two entry
       transitions + the re-acquire edge scoped to the occlusion cause) and the degraded-mode table.
2. [ ] Add the **warning × sensor-mode interaction matrix** (§B) to
       [doc 02 §4](../02-system-architecture.md#4-the-detectionwarning-state-machine) as the authoritative
       enumeration of the two concurrent regions; reconcile the
       [doc 04 §2](../04-risk-and-safety.md#2-fmea-lite-failure-mode--effect--detection--response) FMEA
       rows and the [ADR-0009 §B](ADR-0009-failsafe-placement-and-degraded-modes.md) table to it.
3. [ ] Implement **`CLEARING → SAFE_STATE` on sign-stuck-ON** (status ≠ off after CLEAR) with a
       sign-stuck maintenance escalation ([ADR-0011](ADR-0011-operator-concept-and-alarm-management.md)).
4. [ ] Expose the (optional, shorter) **camera-fault degraded ceiling** as a bounded config parameter
       (FR-20 surface, [doc 02 §7a](../02-system-architecture.md#7-interfaces--contracts-initial)); default
       to the single `T_degraded_max`.
5. [ ] **Fault-inject the new cells:** kill the camera while a warning is active (→ bounded hold →
       `T_degraded_max` loud clear); kill the camera in WARN_HOLD; command CLEAR against a wedged-ON sign
       (→ SAFE STATE + sign-stuck escalation). Add to the acceptance suite
       ([doc 01 §5](../01-requirements.md#5-evaluation-metrics--acceptance-criteria)).
