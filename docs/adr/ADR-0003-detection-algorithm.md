# ADR-0003: Detection approach — lightweight detector + ROI gating + dwell logic

**Status:** Proposed
**Date:** 2026-06-26
**Deciders:** PI, technical lead, CV engineer

## Context

We must decide *how* the perception layer decides "a vehicle is stopped in the emergency lane." The
problem is narrow and favourable: a **fixed camera**, a **fixed region of interest** (the emergency
lane polygon), and a question that is mostly **presence + stationarity**, not fine-grained scene
understanding. The choice trades accuracy, robustness, edge cost, and engineering effort.

Forces: edge compute/power budget (solar), robustness to lighting/shadow/occlusion, false-alarm vs
miss balance, available skills and data, and the need to gate on a geometric ROI.

## Decision

Use a **compact object detector** (YOLO-nano / SSD-MobileNet class) producing vehicle/person
detections, **gated by the ROI polygon**, followed by a **lightweight tracker** (SORT/ByteTrack) and
**temporal dwell logic** in the state machine. Combine with the radar presence/speed channel
([ADR-0001](ADR-0001-sensing-modality.md)) for stationarity confirmation. This hybrid — learned
appearance + geometric gating + temporal confirmation + radar cross-check — is more robust than any
single technique.

**Two distinct onset triggers, by class.** A **vehicle** warrant uses *stationarity* — track speed below
the gate (`< 3 km/h`) for `T_dwell`. A **person** warrant uses *presence* — a `person`-class detection in
or immediately beside the ROI, debounced (`T_person_debounce`), **not** the stationarity gate: a stranded
occupant typically *walks* (3–6 km/h) and would never satisfy `< 3 km/h`, so reusing the vehicle path
would systematically miss exactly the pedestrian hazard
([doc 04 H-C](../04-risk-and-safety.md#1-risk-register)) the person class exists to cover. Persistence for
a pedestrian-only warrant is correspondingly narrower (no radar occlusion hold —
[ADR-0008](ADR-0008-detection-persistence-and-multitrack.md)). A stopped **motorcycle** sits between the
two: a vehicle class (stationarity onset), but its small radar cross-section makes its occlusion-hold
corroboration weaker than a car's — treat its persistence as vehicle-grade only while radar actually
returns it, else camera-only.

## Options Considered

### Option A: Classical background subtraction / frame differencing only
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low |
| Edge cost | Very low |
| Robustness | **Poor** — sensitive to lighting changes, shadows, headlights, slow/gradual stops, camera shake |
| Class info | None (blob only) — can't tell car from debris/person |

**Pros:** trivial, cheap, no training data.
**Cons:** brittle outdoors; a vehicle stopped for a while fades into the learned background;
shadows/headlight sweep cause false positives. Unsafe as the sole method.

### Option B: Lightweight detector + ROI gating + dwell + radar *(chosen)*
| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium |
| Edge cost | Moderate (fits Jetson/accelerator) |
| Robustness | **Good** — appearance + geometry + time + radar |
| Class info | Yes (car/truck/bus/motorcycle/person) |

**Pros:** robust and explainable; classes enable the pedestrian case (FR-08); ROI gating kills most
out-of-lane false alarms; dwell + radar give a clean "stopped" signal; modest compute.
**Cons:** needs a model + some local data for tuning; detector + tracker + fusion to integrate.

### Option C: Heavy end-to-end deep model (large detector / video-based incident model)
| Dimension | Assessment |
|-----------|------------|
| Complexity | High |
| Edge cost | **High** (power/thermal hostile to solar) |
| Robustness | High, but data-hungry |
| Explainability | Lower |

**Pros:** potentially highest raw accuracy; could absorb richer incident types later.
**Cons:** over budget/power for the edge; large data and training burden; harder to validate and
explain for a safety function; overkill for presence+stationarity.

## Trade-off Analysis

The task is **constrained and geometric**, which is precisely where heavy end-to-end learning is
unnecessary and classical-only is too brittle. Option B exploits the structure: the detector handles
*what*, the ROI handles *where*, dwell handles *for how long*, and radar independently handles
*is it really stationary*. That layering is also **easier to validate and explain** — important for a
safety system — than a single opaque model (Option C), and far more robust than pixel differencing
(Option A). It fits the edge/solar envelope from [ADR-0002](ADR-0002-edge-vs-cloud-processing.md).

## Consequences

- **Easier:** robust detection within budget; explainable decisions; pedestrian handling; tunable
  false-alarm/miss balance via ROI + dwell + fusion thresholds.
- **Harder:** assemble/tune detector + tracker + fusion; gather representative local clips
  (day/night/rain) for threshold tuning and evaluation; manage model versions via OTA.
- **Revisit when:** field accuracy demands a stronger model at hard sites (swap the detector behind
  the same interface), or new event classes (debris, wrong-way) justify a richer model (FR-18).

## Action Items

1. [ ] Choose the detector + tracker and benchmark latency/accuracy on the target edge device.
2. [ ] Define the ROI polygon configuration format and a per-site calibration procedure.
3. [ ] Specify the stationarity decision: detector track speed + radar speed + dwell, with thresholds.
4. [ ] Assemble an evaluation clip set covering the doc-01 §5 scenarios (incl. night/rain/occlusion).
5. [ ] Specify the **person-warrant onset** as *presence* in/beside the ROI with a debounce (`T_person_debounce`) and a defined "beside-ROI" margin — distinct from the vehicle stationarity gate; include a **moving stranded occupant** in the evaluation set.
