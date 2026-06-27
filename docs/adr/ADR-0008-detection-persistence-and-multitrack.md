# ADR-0008: Detection persistence — occlusion, departure, and multi-track policy

**Status:** Proposed
**Date:** 2026-06-27
**Deciders:** PI (ThS. Phó Trí Tín), technical lead, CV engineer, road-safety advisor

## Context

The decision state machine ([doc 02 §4](../02-system-architecture.md#4-the-detectionwarning-state-machine))
must hold a warning ON for as long as a real hazard is present and clear it promptly when the hazard
truly leaves — under three field realities the first cut of the loop did not separate:

1. **Occlusion vs. departure.** A through-lane truck can hide a shoulder-stopped vehicle for many
   seconds. The first design collapsed "vehicle departed" and "detection dropped out" into one
   condition (*object absent ≥ T_hold → clear*). With a 10 s hold, a sustained occlusion in heavy
   traffic — a **named** high-risk condition — clears a warning while the hazard is still physically
   present: a silent miss manufactured by the safety logic itself. Lengthening the hold to cover
   occlusion instead risks stale-ON after a genuine departure. The two cases need **different
   evidence, not a longer single timer**.
2. **Multiple simultaneous stopped vehicles.** An emergency lane can hold two or more stopped
   vehicles, or a small queue. A single-object enter/leave cycle is ambiguous about when the warning
   may clear.
3. **Departure is observable.** A vehicle that genuinely leaves crosses the ROI boundary as a
   *moving* track (speed rising above the stationary gate, footprint exiting the polygon). A vehicle
   that is merely occluded produces **no exit** — its track simply stops updating in place. The first
   design discarded this distinction.

Forces: silent-miss avoidance (dominant), stale-ON avoidance (cry-wolf), occlusion frequency in dense
traffic, the independent radar presence channel ([ADR-0001](ADR-0001-sensing-modality.md)), and
edge-compute simplicity.

## Decision

The state machine operates over the **set of confirmed-stopped tracks inside the ROI**, and treats
*loss of detection* and *observed departure* as distinct events corroborated across sensors:

1. **Set semantics.** The warning is ON iff the set of confirmed-stopped in-ROI tracks is non-empty.
   Entry to the set requires the per-track dwell (`T_dwell`). The warning clears only when the set
   becomes empty under the rules below — **not** when any single track disappears.
2. **Confirmed exit (fast clear).** A track observed leaving — speed crossing above the stationary
   gate **and** its footprint exiting the ROI polygon across the downstream boundary — is removed
   from the set immediately (subject to a short debounce). A genuine departure clears quickly.
3. **Lost track (hold, don't clear).** A confirmed-stopped track whose detections stop *without an
   observed exit* is retained as **presumed-present (occluded)**:
   - while the **radar presence channel still substantiates a return** at that range/position, the
     track is retained and the warning persists — an occluded-but-present vehicle keeps warning.
     `T_occlusion` (default 60 s) bounds only **un-renewed** corroboration: a live corroborating return
     **renews** the hold, and if occlusion persists past `T_occlusion` *while radar still corroborates*,
     the unit enters **CAMERA-OCCLUDED-DEGRADED** (warning stays ON **+ operator alert**) rather than
     clearing — a long camera outage is never silently turned into a clear
     ([ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.md) §C);
   - with **no corroboration from any sensor**, the track is retained only for the brief `T_hold`
     hysteresis (default 10 s) and then moved to clearing — but clearing a *possibly-still-present*
     hazard is logged and escalated as a **low-confidence clear** event, never a silent one.
4. **Watchdog fails toward clear, loudly.** `T_watchdog` bounds any activation that has had *no* fresh
   confirmation or corroboration from *any* channel; on expiry the warning clears **and raises a
   fault** (the logic may be wedged — [ADR-0005](ADR-0005-fail-safe-and-system-safety.md)). Radar
   presence counts as corroboration, so a genuinely-present, camera-occluded vehicle does **not** trip
   the watchdog.

**Scope: the persistence guarantees are vehicle-grade, not pedestrian-grade.** The occlusion hold and
the radar-corroborated set semantics above all lean on the **radar presence channel**. A pedestrian has
a negligible radar cross-section ([doc 04 H-C](../04-risk-and-safety.md#1-risk-register)), so a
**pedestrian-only warrant** (a person in/beside the ROI with no associated vehicle) gets **no radar
corroboration and therefore no occlusion hold** — it runs effectively camera-only and falls back to the
brief `T_hold` hysteresis. This is a real, narrower guarantee for FR-08 and must be **stated, not assumed
equal to the vehicle case** ([doc 01 FR-08](../01-requirements.md#2-functional-requirements)).

The concrete timers and the enriched state diagram live in
[doc 02 §4](../02-system-architecture.md#4-the-detectionwarning-state-machine); this ADR fixes the
**policy** those timers implement.

## Options Considered

### Option A: Single-object, single absence-timeout (the first-cut implicit design)
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low |
| Occlusion handling | **Poor** — long occlusion clears a live warning |
| Multi-vehicle | **Unsupported** |
| Stale-ON risk | Traded directly against occlusion (one timer cannot serve both) |

**Pros:** trivial.
**Cons:** conflates departure with occlusion; single-track; forces an unsafe timer compromise.

### Option B: Set-based, exit-vs-lost distinction, radar-corroborated hold *(chosen)*
| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium (track-set bookkeeping + exit boundary) |
| Occlusion handling | **Good** — hold while corroborated, fast-clear on real exit |
| Multi-vehicle | Native |
| Stale-ON risk | Bounded by watchdog + loud low-confidence clear |

**Pros:** removes the occlusion/departure conflation; supports multiple vehicles; reuses the radar
channel already bought in ADR-0001; never clears a possibly-present hazard silently.
**Cons:** more track state; needs a defined ROI exit boundary; depends on radar corroboration being
real (validate per [ADR-0001](ADR-0001-sensing-modality.md) / [ADR-0007](ADR-0007-validation-and-data-strategy.md)).

### Option C: Presence-only ("warn while any motion/return in the ROI", no tracks)
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low–medium |
| False triggers | **Poor** — cannot separate a transient pass-through from a stop without per-track dwell |

**Pros:** simple; robust to occlusion (presence is presence).
**Cons:** loses per-object dwell, so a vehicle merely passing along the shoulder can trigger; no class
info for the pedestrian case.

## Trade-off Analysis

The core insight is that **departure carries evidence (an exit) and occlusion does not** — so the safe
design conditions on *which* it is rather than on a single timeout. Radar corroboration is what makes
a long occlusion hold safe: it lets the system keep warning about a vehicle it cannot currently see
**without** opening an unbounded stale-ON window, because the moment radar too loses the return and no
exit was seen, the watchdog clears loudly. Option B spends modest bookkeeping to buy out the single
most dangerous state-machine failure (occlusion-induced silent miss) and the multi-vehicle gap in one
move. It also makes the radar channel load-bearing for **persistence**, not just initial detection —
strengthening the ADR-0001 case and giving ADR-0007 a concrete thing to validate.

## Consequences

- **Easier:** correct behaviour under occlusion and multiple vehicles; fast clear on genuine
  departure; no silent clears.
- **Harder:** a track-set lifecycle and a defined ROI exit boundary to implement and test; a hard
  dependency on real radar corroboration — including radar **azimuth/lane discrimination** good enough
  to attribute a return to the *shoulder* ROI rather than the adjacent through lane at the monitored
  range, not merely detect presence (folded into the [ADR-0001](ADR-0001-sensing-modality.md) gate). If
  radar is cut to a synthetic channel, the occlusion-hold guarantee is only as good as the synthetic
  model ([ADR-0007](ADR-0007-validation-and-data-strategy.md)); more scenarios in the acceptance suite
  (sustained occlusion with/without radar, multi-vehicle enter/leave interleavings).
- **Revisit when:** field data shows occlusion is rarer/shorter than assumed (simplify `T_occlusion`),
  or a richer tracker makes exit detection reliable enough to shorten `T_hold`.

## Action Items

1. [ ] Define the ROI **exit boundary** and the confirmed-exit test (speed gate + polygon crossing + debounce).
2. [ ] Implement the **track set** with per-track state (tracking / confirmed / presumed-occluded / exited).
3. [ ] Wire **radar presence corroboration** into the lost-track hold; define what counts as a corroborating return.
4. [ ] Specify the `T_occlusion` / `T_hold` / `T_watchdog` interplay in [doc 02 §4](../02-system-architecture.md#4-the-detectionwarning-state-machine) and add the **low-confidence clear** event to telemetry/audit.
5. [ ] Add sustained-occlusion (with and without radar) and multi-vehicle interleaving scenarios to the acceptance suite ([doc 01 §5](../01-requirements.md#5-evaluation-metrics--acceptance-criteria)).
