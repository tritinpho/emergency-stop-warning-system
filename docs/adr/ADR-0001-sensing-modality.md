# ADR-0001: Sensing modality — camera + radar fusion

**Status:** Proposed
**Date:** 2026-06-26
**Deciders:** PI (ThS. Phó Trí Tín), technical lead, road-safety advisor

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
> [doc 03 §5](../03-roadmap-and-phasing.md#5-per-phase-risk-gates)). Because the whole night/rain/fog
> robustness argument rests on this, it is also the system's **top risk exposure**
> ([doc 04 R5](../04-risk-and-safety.md#1-risk-register)).

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

### Option B: Camera + radar fusion *(chosen)*
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
- **Conditional:** the entire adverse-condition benefit is **contingent on the radar gate**. Until it
  passes on real hardware, treat night/rain/fog robustness as a *designed hypothesis*, not a measured
  result ([ADR-0007](ADR-0007-validation-and-data-strategy.md)).
- **Revisit when:** field data shows the camera alone meets targets at a given benign site (then a
  camera-only variant could be a documented cost-down), or thermal proves necessary at hard sites
  (promote Option C elements per-site).

## Action Items

1. [ ] Select a specific **stopped-vehicle-capable** radar (imaging / HRR FMCW, 24/77 GHz, with clutter mapping) and camera (good WDR + IR) — not a generic presence module.
2. [ ] **Validation gate (Phase 3):** demonstrate reliable detection of a *stationary* vehicle in roadside clutter at the shoulder grazing geometry, day and night, before claiming adverse-condition robustness.
3. [ ] Define the fusion contract and the time-sync method (shared clock / PTP / timestamp align).
4. [ ] Build the synthetic radar channel for the simulation harness — with a **documented, conservative** sensor model ([ADR-0007](ADR-0007-validation-and-data-strategy.md)).
5. [ ] Add per-sensor health checks to the health monitor (feeds [ADR-0005](ADR-0005-fail-safe-and-system-safety.md)).
