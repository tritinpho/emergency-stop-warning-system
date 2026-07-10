# 07 — Simulation & Validation Methodology

**Project:** Emergency Stop-Lane Automatic Warning System (ESW)
**Status:** Proposed / Draft — **Phase-2 frozen artifact** (freeze before Phase-3 build begins)
**Last updated:** 2026-06-27
**Related:** [01 requirements §5](01-requirements.md#5-evaluation-metrics--acceptance-criteria) · [02 architecture §4](02-system-architecture.md#4-the-detectionwarning-state-machine) · [04 risk & safety](04-risk-and-safety.md) · [06 traceability](06-traceability-matrix.md) · [ADR-0007](adr/ADR-0007-validation-and-data-strategy.md) · [ADR-0001](adr/ADR-0001-sensing-modality.md) · [ADR-0013](adr/ADR-0013-degraded-hold-unification.md)

This document realises [ADR-0007](adr/ADR-0007-validation-and-data-strategy.md) AI#1. It is the spine of
Phase 3: it fixes **what the simulation harness is, what it injects, what counts as a pass, and what it
may and may not claim** — *before* the loop is built, so Phase-3 results are **evidence**, not a demo.
The pass criteria and sample sizes here are **pre-registered**: they are settled in this document and not
adjusted after seeing results.

> **Why freeze it now.** A pass criterion defined *after* looking at the output is not a criterion. The
> credibility of the whole funded phase rests on claiming exactly what was tested — so the scenario set,
> the synthetic-sensor assumptions, and the thresholds are frozen as a Phase-2 artifact and version-controlled.

---

## 1. Provability boundary (what simulation may and may not claim)

Restating the [ADR-0007](adr/ADR-0007-validation-and-data-strategy.md) boundary, because every result in
this document inherits it:

| Simulation **may** claim | Simulation **may not** claim (field-deferred) |
|--------------------------|-----------------------------------------------|
| State-machine logic correctness (dwell, hysteresis, set semantics, occlusion/degraded holds, watchdog, `T_degraded_max`) | Real-world recall in rain / glare / fog |
| Timing/latency (stop→warn, clear, `T_signhold`, watchdog) | The real false-alarm rate |
| Fault handling and fail-safe behaviour under injected faults | Real radar clutter performance / criterion (b) soundness |
| False-trigger resistance to **modelled** nuisances (pass-through, congestion, shadows) | The over-distance edge↔sign link, calibration drift, solar, IP65 |

**The hard rule: synthetic events do not count toward recall.** A Wilson bound on *recall* computed from
synthetic events the loop itself consumes measures the simulator's determinism, not detection
([doc 01 §5](01-requirements.md#5-evaluation-metrics--acceptance-criteria)). Simulation substantiates
**logic / timing / fault-handling / modelled-false-trigger**; the **recall N is real captures** (bench,
then field) and is governed by the acceptance-evidence plan, not this harness.

Every result produced under this methodology is reported with its **tier** ([doc 06](06-traceability-matrix.md):
**S** simulation, and where a scenario only approximates reality, **S-approx**). Nothing tagged **F**
(field) is claimable here.

---

## 2. Harness architecture — simulate the sensors and the sign, never the logic

The **system under test (SUT) is the real code**: the same perception-output contract, fusion, decision
state machine, actuator abstraction, and health monitor that run on the bench and the field unit. The
harness replaces **only** the physical ends — the sensors and the sign — with models. This is what makes
a sim pass meaningful for the field: the logic exercised is the logic that ships.

```
 scenario script ──▶ synthetic sensor model ──▶ [ REAL: perception · fusion · state machine ·
                                                   actuator abstraction · health monitor ]
                                                          │
                                                          ▼
                                              synthetic sign + status read-back
                                                          │
 ground-truth oracle ──────────────────────────────▶ comparator ──▶ metrics (tagged S / S-approx)
```

Two injection levels, with **different claim power**:

| Level | What is synthetic | What is real (SUT) | Substantiates |
|-------|-------------------|--------------------|---------------|
| **A — event-level** (primary) | The Perception→SM detection/track events ([IF-2](08-interface-control-document.md), [doc 02 §7](02-system-architecture.md#7-interfaces--contracts-initial)) | State machine, persistence/timers, fault logic, actuator abstraction, health monitor | The bulk of [doc 01 §5](01-requirements.md#5-evaluation-metrics--acceptance-criteria) — logic, timing, fault handling, set/occlusion/degraded policy |
| **B — frame-level** (optional, if budget allows) | Synthetic camera frames + radar returns | Also the **real perception** (detector + ROI gating + tracker) | Perception *plumbing* (ROI gating, footprint overlap) — **not** real-condition recall |

**Start with Level A** (a custom 2-D scenario player is the cheapest path and exercises the state machine,
which is where the safety logic and most of §5 live). Add Level B only if it earns its cost. Whatever the
level, the SUT must be byte-identical to the bench/field build — no "sim-only" branches in the decision
logic.

---

## 3. Synthetic sensor model & assumptions (documented and conservative)

The model is only as honest as its assumptions, so each is **stated and recorded with the result**. An
optimistic assumption that flatters the SUT invalidates the claim it supports.

### 3.1 Camera channel
Models a detection stream as a function of the scripted scene, with these **nuisances injected** (not a
clean oracle feed):
- **Detection dropout** — probabilistic and event-driven (occlusion by a scripted through-lane vehicle); drives the occlusion/lost-track path.
- **False detections** — shadows, headlight sweep, debris, at a configurable rate; tests ROI gating + dwell + radar cross-check.
- **Footprint/box noise** — jitter on the ground-footprint estimate; tests the ≥ 50 % ROI-overlap rule and straddling poses.
- **Latency & cadence** — frame interval and processing latency; tests `T_activate` / NFR-01 budgets.
- **Class confusion** — car/truck/bus/motorcycle/person mislabels at a configurable rate.
- **Day vs night/adverse** — *approximated* by raising dropout/noise; explicitly **S-approx**, never a real-recall claim (FR-09 real recall is **F**).

### 3.2 Radar channel — model the uncertainty, do not assume it away

> **This channel is simulation-only, and now exclusively so.** [ADR-0001](adr/ADR-0001-sensing-modality.md)
> was **Rejected on 2026-07-10** — the shipped unit is camera-only, so no radar return ever reaches the real
> state machine, and the radar-dependent scenarios below (SC-06/08/09/25/26, SC-39) exercise code paths that
> are **dormant on the device** ([doc 04](04-risk-and-safety.md) R20, R21). The model is retained
> deliberately: it keeps the cấp sở design under test. The hard rule is unchanged — **synthetic events never
> count toward recall.**
Models presence/range/speed returns. The **methodologically critical** parameter:
- **Lane-attribution error (criterion (b))** — a *configurable* probability that a return is attributed to the wrong lane (shoulder vs adjacent through-lane). The harness **must** run scenarios under **both** a *good-(b)* and a *weak-(b)* setting, because the [ADR-0001](adr/ADR-0001-sensing-modality.md) gate (b) is field-deferred and **uncertain**. The whole point of the occlusion-hold / `CAMERA_OCCLUDED_DEGRADED` / `T_degraded_max` design is its behaviour when (b) is weak — so the sim feeds it a radar that *can* mis-attribute, and verifies the failure is bounded (no indefinite stale-ON), never a radar that is perfect by assumption.
- Presence dropout, range/speed noise, and (radar) false returns are also configurable.

### 3.3 Time channel
Injects **clock skew/jitter** between the camera and radar streams to exercise fusion sync and the NFR-16
time-integrity handling; the SUT must degrade gracefully (flag, fall back to single-sensor) rather than
fuse on bad timestamps.

### 3.4 Sign channel
A modelled sign controller that honours (or, by configuration, **fails to honour**) the refreshed-`SHOW`
contract ([IF-4](08-interface-control-document.md), [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)):
blanks within `T_signhold` on lost heartbeat; can be told to **latch** (to model a third-party VMS), to
**not turn off** (stuck-ON, ADR-0013), or to drop status read-back.

> **Conservatism register.** Every parameter above (dropout rates, noise σ, lane-error probability,
> latencies) is recorded per scenario run, with a flag on any setting chosen *optimistically*. A claim
> resting on an optimistic setting is downgraded or withheld.

---

## 4. Ground-truth oracle & metric computation

Every scenario carries a machine-readable **oracle** derived from the script, **independent of the SUT**:
for each timestep it states the *true* set of in-ROI confirmed-stopped vehicles/persons and therefore
whether the warning **should** be ON, plus the true exit / occlusion / fault events. Metrics are computed
by the comparator from (SUT sign-state-over-time) vs (oracle):

- **Correct-ON / correct-OFF** intervals; **false-activation** (ON when oracle says OFF); **missed-warning** (OFF when oracle says ON).
- **Latencies**: stop→warn, confirmed-exit→clear, fault→blank (`T_signhold`).
- **Disposition correctness**: did `T_degraded_max` force a loud clear? did a stuck-ON go to SAFE_STATE? did override auto-expire?

The oracle distinguishes a **held occlusion** (warning correctly retained) from a **stale-ON** (oracle
says the hazard left) — so a correct occlusion hold is never scored as a clear-latency failure
([NFR-02](01-requirements.md#3-non-functional-requirements), [ADR-0008](adr/ADR-0008-detection-persistence-and-multitrack.md)).

---

## 5. Scenario catalogue (shared, ID'd — the acceptance backbone)

This is the canonical catalogue; the test/acceptance plan and [doc 06](06-traceability-matrix.md) reference
these IDs. Each scenario fixes: preconditions, injected timeline, the **oracle**, the requirement/risk
exercised, and the **tier**. *Logic-validated as specified* ≠ *field-sound*: scenarios marked **(b)-dep**
rest on the field-deferred radar criterion (b) and are reported as designed-not-field-proven
([ADR-0007](adr/ADR-0007-validation-and-data-strategy.md)).

| ID | Scenario | Oracle (expected) | Exercises | Tier |
|----|----------|-------------------|-----------|------|
| SC-01 | Stop → dwell → warn → depart → clear (happy path) | ON after `T_dwell`+`T_activate`; OFF after confirmed exit + ≤2 s | FR-01..07, NFR-01/02 | S |
| SC-02 | Transient pass-through along shoulder | never ON | FR-03 | S |
| SC-03 | Creep-along-shoulder (< speed gate, not stopping) | per dwell rule | FR-03/04 | S |
| SC-04 | Dwell sweep 3–10 s | confirm only after `T_dwell` | FR-04 | S |
| SC-05 | Brief occlusion (< `T_hold`) | stays ON, no flap | FR-07, NFR-02 | S |
| SC-06 | Sustained occlusion, radar corroborates | ON → `CAMERA_OCCLUDED_DEGRADED` past `T_occlusion`, + alert | ADR-0008/0009 | S **(b)-dep** |
| SC-07 | Sustained occlusion → `T_degraded_max` reached | forced **loud low-confidence clear** + max-severity escalation | NFR-04, ADR-0009 §C | S |
| SC-08 | **Camera fault while warning active**, radar corroborates | enters bounded camera-unverified hold → `T_degraded_max` forced loud clear; **no** re-acquire | **ADR-0013**, NFR-04 | S |
| SC-09 | **Weak-(b)**: radar corroborates the *occluding through-lane truck*, shoulder car departed | warning does **not** persist indefinitely — `T_degraded_max` forces a loud clear | R12 inversion, ADR-0001/0013 | S **(b)-dep** |
| SC-10 | Multi-vehicle arrive/leave interleavings | ON while set non-empty; no early clear | FR-06, ADR-0008 | S |
| SC-11 | Congestion / stop-and-go beside ROI | **no** false-trigger; suppress or re-message | R14, [doc 02 §4](02-system-architecture.md#4-the-detectionwarning-state-machine) | S **(b)-dep** |
| SC-12 | Pedestrian presence-onset incl. **moving stranded occupant** (never < speed gate) | presence-debounced warrant fires (not the stationarity path) | FR-08, ADR-0003 | S-approx |
| SC-13 | Stopped motorcycle (small RCS) | vehicle-grade persistence only while radar returns, else camera-only | ADR-0003/0008 | S |
| SC-14 | Vehicle present at boot (cold start) | treated as new track; full dwell | [doc 02 §4](02-system-architecture.md#4-the-detectionwarning-state-machine) | S |
| SC-15 | **Warm reboot during active warning** | sign blanks during downtime; re-confirm on restart (re-exposure noted, Q7) | [doc 04 Q7](04-risk-and-safety.md#5-open-safety-questions-for-the-team) | S |
| SC-16 | Operator force-on, then kill edge box / expiry | force-on refreshed (non-latching) → blanks on box-kill / expiry | FR-13, ADR-0010 | S |
| SC-17 | Operator force-off / mute → auto-expiry | mute expires; OVERRIDDEN posture while active; re-evaluates | FR-13, ADR-0010 | S |
| SC-18 | Out-of-policy override (expiry > ceiling / unknown msg / no reason) | rejected/clamped at unit | FR-13/20, ADR-0010 | S |
| SC-19 | Out-of-bounds config push (bad ROI; `T_dwell=900 s`; **`T_signhold` huge**; **`T_degraded_max`→"never"**) | rejected/clamped per §7a; last-good kept; alert | FR-20, [doc 02 §7a](02-system-architecture.md#7-interfaces--contracts-initial) | S |
| SC-20 | OTA / restart requested while warning active | deferred, or blank **loud to ops** — never silent drop | FR-21, ADR-0009 | S |
| SC-21 | Fault-inject: kill SM process | sign blanks within `T_signhold`; safe state + alert | FR-11, ADR-0005/0009 | S |
| SC-22 | Fault-inject: kill edge box | sign-controller blanks within `T_signhold` | FR-11, ADR-0009 §A | S |
| SC-23 | Fault-inject: cut sign link | sign-controller blanks within `T_signhold` | FR-11, ADR-0009 §A | S |
| SC-24 | **CLEAR vs wedged-ON sign** (status never off) | → SAFE_STATE + sign-stuck maintenance escalation | **ADR-0013** | S |
| SC-25 | Radar dead (CAMERA-ONLY) | can still initiate; no occlusion hold; degraded + alert | ADR-0009 §B matrix | S |
| SC-26 | Camera dead idle (RADAR-ONLY) | **BLIND-TO-NEW** — cannot initiate; critical alert | ADR-0009 §B matrix | S |
| SC-27 | Both sensors dead | SAFE_STATE (blank) + critical alert | ADR-0009 §B | S |
| SC-28 | Watchdog: wedged logic, no corroboration | clear + raise fault (`T_watchdog`) | NFR-04, ADR-0005/0008 | S |
| SC-29 | Calibration-drift: inject synthetic homography shift | drift monitor → degraded + alert | FR-10, R15 | S (real drift **F**) |
| SC-30 | Alarm dedup / priority / re-escalate-on-non-ack | one incident ≠ storm; critical re-escalates if unacked | NFR-15, ADR-0011 | S (response-time **F**) |

> Two scenarios are *designed, not field-sound*: **SC-11** (congestion) and **SC-06** (sustained-occlusion
> hold) both rest on criterion (b) and are reported **logic-validated as specified**, with **SC-09** as the
> explicit weak-(b) guard that the failure stays bounded.

---

## 6. Pass criteria & statistical method (pre-registered)

A run passes the **university-prototype acceptance** when, across the full catalogue:

1. **Logic/disposition** — every scenario's SUT output matches its oracle disposition (correct ON/OFF, correct degraded/clear/safe-state transition). This is **pass/fail per scenario**, not a rate.
2. **Timing** — measured latencies within budget: stop→warn ≤ `T_dwell`+2 s; confirmed-exit→clear ≤ `T_hold`+2 s; fault→blank ≤ `T_signhold`; no warning ON past `T_watchdog`/`T_degraded_max` without the specified loud disposition.
3. **Modelled false-activation** — ≤ the [doc 01 §5](01-requirements.md#5-evaluation-metrics--acceptance-criteria) target across the staged nuisance scenarios, reported **per-100-scenarios and per-sim-hour** with its exposure denominator.
4. **Fault-detection coverage** — ≥ 95 % of the **bench-injectable** FMEA list ([doc 04 §2](04-risk-and-safety.md#2-fmea-lite-failure-mode--effect--detection--response)); field-only modes (drift, over-distance link, solar) are excluded and reported as such, not silently counted.
5. **No deceptive/stuck output** — under **no** injected fault does the SUT leave a stale-ON or a silent clear.

**Statistical method.** Rate metrics carry a **minimum N and a confidence statement** fixed *here* before runs
(e.g. modelled-false-activation reported with its exposure and a confidence interval). **Recall is excluded
from simulation** (§1) — its N is real captures, governed by the acceptance-evidence plan. Simulation *may*
cheaply generate volume for the logic/timing/false-trigger-on-modelled-nuisance metrics; it must **not**
report a recall number.

**Pre-registration.** The thresholds, the catalogue, the synthetic-sensor parameter ranges, and the N per
rate metric are frozen in this document (and its version history) before Phase-3 runs begin. Changes after
runs are recorded as amendments with rationale, never silent edits.

---

## 7. What simulation cannot close (carry to bench / field)

Per [doc 06](06-traceability-matrix.md) **F**-tier and [ADR-0007](adr/ADR-0007-validation-and-data-strategy.md):
real recall in rain/glare/fog, the real false-alarm rate, **real radar clutter / criterion (b)**, the
over-distance edge↔sign link, **real calibration drift**, solar ≥ 72 h autonomy, and IP65 environment.
SC-06/09/11's *(b)-dependence* is the sharpest of these: the logic is validated, the field-soundness is not.

---

## 8. Reproducibility, tooling & artefacts

- **Determinism** — the harness uses a **seeded** RNG; the seed is recorded so any run reproduces exactly. (This determinism is *why* synthetic N cannot evidence recall — §1.)
- **Versioning** — scenario files, synthetic-sensor parameters, and the SUT build are version-controlled together; every result record carries the **`cfg_ver` / `model_ver` / `calib_ver` fingerprint** ([doc 02 §7](02-system-architecture.md#7-interfaces--contracts-initial)) and its **tier**.
- **Tooling** — start with a **custom event-level (Level A) scenario player** (cheapest, directly validates the state machine and persistence/fault logic that hold most of §5). CARLA/SUMO or a frame-level player ([doc 02 §8](02-system-architecture.md#8-recommended-technology-stack-indicative-not-binding)) is optional, added only if Level B earns its cost. The SUT stays identical across sim, bench, and field.
- **Output** — a per-run report: scenario IDs, pass/fail, measured latencies/rates with CIs, the synthetic-sensor settings (with optimism flags), and the tier of every claim — the raw material for the Phase-5 feasibility report, where each result is stated *with its tier* so no claim outruns its evidence.
