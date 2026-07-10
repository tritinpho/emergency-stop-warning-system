# ADR-0001: Sensing modality — camera + radar fusion

**Status:** **Rejected (2026-07-10)** — for the cấp trường bench-prototype phase. The build is
**camera-only**. Reopen at the cấp sở field project.
**Date:** 2026-06-26 · **Closed:** 2026-07-10
**Deciders:** PI (ThS. Phó Trí Tín), technical lead, road-safety advisor
**Closed by:** **ThS. Phó Trí Tín** — chủ nhiệm đề tài (principal investigator), 2026-07-10, on the
project lead's direction. ADR-0001 is owned by the hardware + business teams; the PI records and
accepts the decision and its consequences (R5, R20, R21).

> ## Decision record — radar is NOT used in this phase
>
> This ADR was **never Accepted**. It is now **Rejected for the bench-prototype phase**. Everything
> below the Context heading is **retained unchanged**: it is the specification for the follow-on
> cấp sở project, **not** a live requirement for this one. Read it as an archive, not a plan.
>
> ### Why
>
> 1. The phase deliverable is **buildability and logic, not safety efficacy**
>    ([doc 01 §5](../01-requirements.md)). Radar contributes ≈ 0 to that.
> 2. Gate criterion **(b)** — resolving the shoulder from the adjacent through lane at the monitored
>    range — is **not bench-testable** (see the Caveat below), and **the monitored range is nowhere
>    specified in this repo**. Angular resolution scales as λ/aperture: a module that resolves a
>    3.5 m lane gap at 100 m (≈ 2°) may cost more than the entire 20M VND project. Radar bought for
>    *this* phase would discharge **(a) only**, leaving every radar-dependent guarantee exactly where
>    it already stands — *designed, not validated*.
> 3. Cost is **6–8M VND of a 20M VND budget**, plus an 8–12 week procurement lead.
> 4. The competing use of those funds — **≥ 200 real captures including night**, for the
>    recall-with-Wilson-bound headline ([ADR-0007](ADR-0007-validation-and-data-strategy.md)) — *is*
>    bench-achievable, and was unfunded.
>
> ### Accepted consequences
>
> Recorded here so they are **decided, not discovered later**. This ADR always demanded it:
> *"if hardware budget forces it out, down-scope the night/adverse claim, do not quietly rest it on
> synthetic data."*
>
> - **The occlusion hold is unreachable.** `esw/state_machine.py` gates entry to `WARN_HOLD` /
>   `CAMERA_OCCLUDED_DEGRADED` on radar corroboration (`corr`), which is never true without a radar
>   channel. A confirmed vehicle lost to occlusion is **cleared at `T_hold` (default 10 s)** on the
>   loud-clear path — a truck occluding the shoulder for >10 s blanks the sign with the hazard still
>   present. Tracked as **[R20](../04-risk-and-safety.md)**.
> - **The unit runs permanently in `CAMERA_ONLY`**, so the operator alert is permanently `DEGRADED`.
>   A posture that is always on carries no information. Tracked as **[R21](../04-risk-and-safety.md)**.
> - **[R5](../04-risk-and-safety.md) (adverse-condition blindness) has no mitigation.** Night, rain
>   and fog recall is **not claimed** — neither from a bench radar nor from synthetic data.
>
> ### No code change
>
> `esw/health.py` already derives `CAMERA_ONLY` from sensor liveness, and the state machine degrades
> on its own. Radar support stays in the codebase as the cấp sở asset. Nothing is deleted.
>
> ### Reopen when
>
> The cấp sở project funds a **test track or field venue** — the only place criterion (b) can be
> exercised. **Specify the monitored range first**; it decides whether any affordable radar can pass.

## Context

The system must detect a vehicle stopped in the emergency lane and do so **specifically in the
conditions the proposal flags as most dangerous: night, rain, fog, glare, and high traffic density**.
A camera alone is cheapest and gives rich classification, but it is weakest in exactly those
conditions — low light, headlight glare, water on the lens, and occlusion by passing trucks. Basing a
*safety* warning on the sensor that fails when it is needed most is the central risk of the original
"AI camera" framing.

Forces: detection robustness in adverse conditions (dominant), cost and power (solar budget), edge
compute load, night/weather performance, classification ability (car vs person vs debris), and
maintainability.

## Decision

> **SUPERSEDED — see the decision record above.** This section states the *cấp sở* target design.
> It was **Rejected for this phase on 2026-07-10**; the build is camera-only. Read the following in
> the past conditional: this is what the system *would* do once radar is funded and its gate passes.

Use a **camera + radar sensor pair with fusion** as the core sensing modality. The camera provides
classification and ROI geometry; the radar provides **range, presence, and speed that survive
darkness, rain, and fog**, and confirms "present and stationary" independently of pixels. Thermal
imaging is held as an optional add-on for sites with severe night/fog where budget allows.

> **Caveat — this is the load-bearing assumption, so it is a validation gate, not a given.** Detecting
> a **stationary** vehicle in roadside clutter is the *hard* case for radar: a parked car has near-zero
> Doppler and competes with static returns from guardrails, signs, and the road surface, and a
> roadside radar looking along the shoulder is itself partially occluded by through-lane trucks. This
> needs a **stopped-vehicle-capable radar** (e.g. an imaging / high-range-resolution FMCW unit with a
> clutter map), **not** a generic "presence" module, and it must be **validated at the shoulder
> grazing geometry** before the adverse-condition claim is evidence-backed (Phase-3 go/no-go,
> [doc 03 §5](../03-roadmap-and-phasing.md#5-per-phase-risk-gates)). The gate has **two** success
> criteria, not one: (a) reliably pick a *stationary* vehicle out of roadside clutter, and (b)
> **resolve the shoulder lane from the adjacent through lane** at the monitored range
> (azimuth/lane discrimination) — without (b), a corroborating return cannot be attributed to the ROI,
> which is what [ADR-0008](ADR-0008-detection-persistence-and-multitrack.md)'s occlusion hold relies on.
>
> **The two criteria do not validate in the same venue — and saying so is part of claim honesty.**
> Criterion (a) is *bench-testable at short range*. Criterion (b) is an **angular** problem and is
> **not**: at 100 m a lane width (~3.5 m) subtends ≈ 2°, but at a few-metre bench the same gap subtends
> tens of degrees and is trivially resolvable. A literal bench therefore **cannot exercise (b)** — it
> needs lane separation **at the monitored range** (a test track or a field setting, not a desk). Treat
> (a) as bench/Phase-3 and **(b) as field-deferred** (or test-track), and never let a clean short-range
> demo of (a) be read as having passed the whole gate ([ADR-0007](ADR-0007-validation-and-data-strategy.md)).
>
> **If (b) is weak, the failure _inverts_ — from silent miss to stale-ON.** The occlusion hold and the
> `CAMERA_OCCLUDED_DEGRADED` state ([ADR-0008](ADR-0008-detection-persistence-and-multitrack.md),
> [ADR-0009 §C](ADR-0009-failsafe-placement-and-degraded-modes.md)) keep a warning ON because *radar
> still corroborates a return in the ROI*. If radar cannot tell shoulder from through-lane, the
> "corroborating return" during a truck occlusion may be the **occluding truck in the through lane**, not
> the shoulder car — so the rule written to prevent a silent miss instead **manufactures a stale-ON
> (cry-wolf)**. Until (b) is validated, those persistence guarantees are *designed, not proven*, and the
> inverted-failure residual is tracked at [doc 04 R12/R14](../04-risk-and-safety.md#1-risk-register).
>
> Because the whole night/rain/fog robustness argument rests on this, it is also the system's **top risk
> exposure** ([doc 04 R5](../04-risk-and-safety.md#1-risk-register)).
>
> **Budget reality (reconciled in [doc 03 §1](../03-roadmap-and-phasing.md#1-scope--budget-reality-check-read-first)).**
> An ADR-grade radar — an imaging/HRR FMCW *evaluation* module — costs well above the first-cut
> 1.5–2.5M VND line; a module at that price is exactly the generic presence unit this ADR rules out.
> Either fund a real mmWave eval module (recommended — it is the *only* on-bench mitigation of R5, the
> top risk) and trim elsewhere, or accept a generic module and mark **this gate itself field-deferred**.
> What is not acceptable is budgeting a generic module while *claiming* the gate is run on the bench.

## Options Considered

### Option A: Camera only
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low |
| Cost | Low |
| Robustness (night/rain/fog/glare) | **Poor** — the failure conditions coincide with the danger conditions |
| Classification | Good |
| Power | Low–moderate |

**Pros:** cheapest; simplest; rich semantics; matches the proposal's "AI camera" image.
**Cons:** weakest precisely when most needed; glare/occlusion false-negatives; a safety system that
degrades silently at night.

### Option B: Camera + radar fusion *(chosen for cấp sở — **rejected for this phase**, 2026-07-10)*
| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium (fusion + time sync) |
| Cost | Medium (+ one radar/site) |
| Robustness | **Good** — radar covers the camera's blind conditions |
| Classification | Good (camera) + reliable presence/speed (radar) |
| Power | Moderate (radar is low-power) |

**Pros:** robust day/night/weather; independent confirmation reduces both misses and false alarms;
radar gives speed directly (clean "stationary" signal); graceful degradation (one sensor down → still
partial coverage + a health alert).
**Cons:** more cost and integration; fusion and inter-sensor time sync add engineering.

### Option C: Full multi-sensor (camera + radar + thermal + lidar)
| Dimension | Assessment |
|-----------|------------|
| Complexity | High |
| Cost | High |
| Robustness | Excellent |
| Power | High |

**Pros:** best possible robustness.
**Cons:** over budget and over-scoped for a university prototype; high power undermines solar siting;
diminishing returns over B for this use case.

## Trade-off Analysis

The decisive factor is **conditional robustness**: the value of the system is highest at night and in
bad weather, so the sensing must not collapse there. Option A optimises cost at the expense of the
core safety promise. Option C buys robustness the budget and power envelope cannot sustain. Option B
covers the camera's specific failure modes with a cheap, low-power, weather-tolerant complement and
yields an independent "stationary" signal that also **cuts false alarms** — serving both error-rate
requirements at once.

For the simulation/bench scope, radar can be represented by a synthetic presence/speed channel, so
choosing B now costs little and keeps the field path open. **But a synthetic radar that assumes
perfect stationary detection cannot be used to _evidence_ the adverse-condition recall target** — that
claim is field-deferred unless a real stopped-vehicle-capable radar is on the bench and passes the
validation gate above ([ADR-0007](ADR-0007-validation-and-data-strategy.md),
[doc 01 §5](../01-requirements.md#5-evaluation-metrics--acceptance-criteria)). Keep the radar a budget
priority for exactly this reason; if hardware budget forces it out, **down-scope the night/adverse
claim, do not quietly rest it on synthetic data**.

## Consequences

- **Easier (if the gate passes):** dependable night/weather detection; cleaner stationary detection;
  graceful degradation; lower false-alarm rate.
- **Harder:** camera-radar **time synchronisation and extrinsic calibration**; a fusion module to
  design and test; slightly higher per-site cost and power; **and the stationary-in-clutter radar
  capability must be validated, not assumed** (the gate above).
- **Forward (power):** the gate-grade module the budget reconciliation selected (imaging/HRR FMCW eval
  kit, [doc 03 §1](../03-roadmap-and-phasing.md#1-scope--budget-reality-check-read-first)) draws **more
  than the "radar is low-power" generic-presence assumption** this ADR leaned on. Its **cost** was
  reconciled into the budget; its **power** is still an open input to the solar / ≥72 h sizing
  ([ADR-0006](ADR-0006-connectivity-and-power.md)/NFR-07). Moot at bench (mains); reconcile before the
  field unit.
- **Conditional:** the entire adverse-condition benefit is **contingent on the radar gate**. Until it
  passes on real hardware, treat night/rain/fog robustness as a *designed hypothesis*, not a measured
  result ([ADR-0007](ADR-0007-validation-and-data-strategy.md)).
- **Venue-bound:** even "real hardware" is not enough for criterion (b) — lane discrimination needs the
  *monitored range*, so it is **test-track/field-deferred**, and with it the
  [ADR-0008](ADR-0008-detection-persistence-and-multitrack.md) /
  [ADR-0009 §C](ADR-0009-failsafe-placement-and-degraded-modes.md) occlusion-hold guarantees. A weak (b)
  inverts silent-miss into stale-ON ([doc 04 R12/R14](../04-risk-and-safety.md#1-risk-register)), so the
  bench may not claim the persistence behaviour as *validated*, only as *designed*.
- **Revisit when:** field data shows the camera alone meets targets at a given benign site (then a
  camera-only variant could be a documented cost-down), or thermal proves necessary at hard sites
  (promote Option C elements per-site).

## Action Items

> **Items 1–4 are DEFERRED to the cấp sở project — do not action them in this phase.** ADR-0001 is
> Rejected (2026-07-10); no radar is procured, no fusion contract is defined, no radar gate is run.
> **Item 5 remains live** — it is not radar-specific, and per-sensor health is exactly what derives
> the permanent `CAMERA_ONLY` mode (R21).

1. [ ] *(deferred — cấp sở)* Select a specific **stopped-vehicle-capable** radar (imaging / HRR FMCW, 24/77 GHz, with clutter mapping) and camera (good WDR + IR) — not a generic presence module; **record its power draw** as an input to the [ADR-0006](ADR-0006-connectivity-and-power.md) solar budget (it exceeds the generic-presence assumption).
2. [ ] *(deferred — cấp sở; **specify the monitored range first**, it decides whether any affordable radar can pass (b))* **Validation gate:** demonstrate (a) reliable detection of a *stationary* vehicle in roadside clutter at the shoulder grazing geometry, day and night, **and** (b) azimuth/lane discrimination sufficient to attribute the return to the shoulder ROI vs. the adjacent through lane at the monitored range — before claiming adverse-condition robustness. Run an early, cheap feasibility spike in Phase 1 ([doc 03 §5](../03-roadmap-and-phasing.md#5-per-phase-risk-gates)) so a gate failure is found before the design leans its full weight on radar. **Venue split:** (a) is bench/Phase-3 at short range; **(b) needs lane separation at the monitored range** (test track or field) and is **field-deferred** — a bench pass of (a) alone does not discharge the gate. Record which criterion each result actually evidences.
3. [ ] *(deferred — cấp sở)* Define the fusion contract and the time-sync method (shared clock / PTP / timestamp align).
4. [x] *(done, and retained)* Build the synthetic radar channel for the simulation harness — with a **documented, conservative** sensor model ([ADR-0007](ADR-0007-validation-and-data-strategy.md)). It lives in `harness/sensors.py` (`radar_visible`, `radar_ghosts`) and still exercises the state machine's dormant radar paths in simulation. It **cannot** evidence recall ([doc 07](../07-simulation-methodology.md)).
5. [x] **(live — done)** Add per-sensor health checks to the health monitor (feeds [ADR-0005](ADR-0005-fail-safe-and-system-safety.md)). Implemented in `esw/health.py`; this is what derives the permanent `CAMERA_ONLY` mode.
