# 01 — Requirements & Acceptance Criteria

**Project:** Emergency Stop-Lane Automatic Warning System (ESW)
**Status:** Proposed
**Last updated:** 2026-06-26

This document turns the proposal's prose objectives into testable requirements. It also adds three
things the proposal needs before it can be built: a **safety framing**, the **warning-placement
math**, and **measurable acceptance criteria**.

---

## 1. The safety reframe (read this first)

The proposal treats the work as "detect a stopped car and show a sign." Functionally true, but the
system is **safety-related**: its output influences how fast-moving drivers behave near a stationary
obstacle. That changes how we must reason about failure.

Two failure modes dominate, and they pull in opposite directions:

| Failure | What happens | Consequence | Worse because… |
|---------|--------------|-------------|----------------|
| **Miss (false negative)** | Vehicle is stopped; warning never shows | No early warning — the exact situation we set out to fix | The system was *trusted* to cover this and silently didn't. |
| **False alarm (false positive)** | Warning shows with no real hazard | Drivers slow/swerve needlessly; repeated → they stop believing it | "Cry wolf" — erodes the trust that makes the *real* warning work. |

Design consequences (carried through every other document):

- **Fail-safe + fail-loud.** The system must detect its own degradation and tell operators. A unit
  that is blind must not appear healthy. See [ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.md).
- **Both error rates are first-class requirements** with numeric targets (§5), not an afterthought.
- **Trust calibration.** Warning content and behaviour must stay credible; no flapping, no stale
  warnings. Hysteresis and dwell logic exist for this reason ([doc 02](02-system-architecture.md)).
- **The system advises; it never controls** other vehicles. Final responsibility stays with drivers.
- **Bounded protection (stated, not implied).** The system warns about a *confirmed-stopped* vehicle in
  a *monitored zone*; it does **not** warn about a vehicle still *decelerating onto* the shoulder (the
  most dynamic moment), one stopped *between* monitored zones, or a driver who ignores the sign. These
  residual hazards are enumerated in [doc 04 §0](04-risk-and-safety.md#0-limits-of-protection-residual-hazards)
  and bound what the system can promise — which is also how R7 (over-reliance) is managed.

This is not "do ISO 26262 / SIL certification now" — that is for a productized field system. It is:
*adopt the fail-safe mindset from day one so the prototype is honest about what it can and cannot do.*

---

## 2. Functional requirements

Priority uses MoSCoW: **M**ust / **S**hould / **C**ould / **W**on't-now.

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-01 | Continuously monitor a configurable detection zone (ROI) covering the emergency lane within the sensor field of view. | M |
| FR-02 | Detect the presence of a vehicle (car, truck, bus, motorcycle) inside the ROI. | M |
| FR-03 | Distinguish a **stopped** vehicle (stationary ≥ dwell time) from one merely passing along/through the shoulder. | M |
| FR-04 | Confirm a detection over a configurable **dwell time** before declaring "stopped" (default 5 s, range 3–10 s). | M |
| FR-05 | On confirmation, automatically activate the upstream warning sign(s) showing "STOPPED VEHICLE AHEAD" (*PHÍA TRƯỚC CÓ XE DỪNG KHẨN CẤP*). | M |
| FR-06 | Continue to track the stopped vehicle while the warning is active. | M |
| FR-07 | Automatically clear the warning after the vehicle has left the ROI, applying a **hold/hysteresis** delay (default 10 s) so brief occlusion does not drop a live warning. | M |
| FR-08 | Detect a **pedestrian** in or immediately beside the ROI (stranded occupant) and treat as a warrant for warning. **Triggered by *presence* (debounced), not the stationarity gate** — a stranded occupant typically *walks* (3–6 km/h) and would fail the `< 3 km/h` speed gate, so the vehicle stop-detection path would systematically miss them ([doc 02 §4](02-system-architecture.md#4-the-detectionwarning-state-machine), [ADR-0003](adr/ADR-0003-detection-algorithm.md)). *(Harder sensing profile than vehicles — small radar cross-section + camera weakest at night; §5 sets a separate, realistic pedestrian target rather than folding it into vehicle recall. Persistence guarantees are **vehicle-grade**: a pedestrian-only warrant gets no radar occlusion hold — [ADR-0008](adr/ADR-0008-detection-persistence-and-multitrack.md).)* | S |
| FR-09 | Operate across day, night, rain, and fog (degraded but functional). | M |
| FR-10 | Continuously self-monitor sensor, compute, link, and sign health — **including a calibration-drift monitor** (reference-point residual vs. the stored homography; out-of-tolerance → degraded + alert, R15) — and emit a heartbeat. | M |
| FR-11 | Enter a defined **safe state** and alert operators on any critical fault (see ADR-0005). | M |
| FR-12 | Send activation/clear/fault events with timestamps to the TMC and an audit log. | S |
| FR-13 | Allow an operator to manually override (force-on, force-off, mute) a sign — **bounded, fail-loud, heartbeat-honoring; never latching or silently persistent** ([ADR-0010](adr/ADR-0010-operator-override-and-manual-control.md)). | S |
| FR-14 | Support remote configuration of ROI, thresholds, and dwell/hold timings. | S |
| FR-15 | Support over-the-air (OTA) software/model updates with rollback. | C |
| FR-16 | Log enough detection evidence (event snapshots/metadata, not continuous raw video) to audit a decision. | S |
| FR-17 | Integrate with an existing operator-controlled VMS where one is present, instead of adding a sign. | S |
| FR-18 | Detect generic obstacles (debris, animals) / wrong-way vehicles. | W (future) |
| FR-19 | Notify emergency services / incident management automatically. | W (future) |
| FR-20 | Enforce **safety-parameter bounds at the unit**: reject or clamp any pushed parameter that falls outside its declared safe range, keep the last-good, and alert — staging/validating a config change like an update. The bounded set is the **full safety-parameter surface** (ROI, dwell, hold, occlusion, person-debounce, speed gate, override ceiling, message set **and** the safety backstops `T_watchdog` / `T_signhold` / `T_assert_refresh` / `T_degraded_max` / `T_activate`), enumerated with its hard bounds in **[doc 02 §7a](02-system-architecture.md#7-interfaces--contracts-initial)** — not just the site-tunable subset. Signing prevents *tampering*, not operator *error* — a bad ROI, `T_dwell=900 s`, or a `T_signhold` large enough to defeat the dead-man's switch silently breaks the safety function and won't trip a model canary. | M |
| FR-21 | Defer **OTA updates and non-critical restarts while a warning is active** (the track set is non-empty), or take the sign to a known blank state *loud to operators* for the update window — never silently drop a live warning for a software update (see boot-present handling, [doc 02 §4](02-system-architecture.md#4-the-detectionwarning-state-machine)). | S |

### Detection-to-warning behaviour (canonical loop)

```
idle → (vehicle enters ROI) → tracking
tracking → (stationary ≥ dwell) → CONFIRMED → WARN ON
WARN ON → (vehicle still present) → hold
WARN ON → (vehicle absent ≥ hold) → WARN OFF → idle
any state → (critical fault) → SAFE STATE + operator alert
```

The full state machine, with timers and edge cases, is specified in
[doc 02 §4](02-system-architecture.md#4-the-detectionwarning-state-machine).

---

## 3. Non-functional requirements

| ID | Category | Requirement |
|----|----------|-------------|
| NFR-01 | **Latency** | Stop-confirmed → warning ON ≤ 2 s after dwell elapses (so total stop→warn ≈ dwell + ≤2 s). **Backend-qualified:** met directly by the dedicated LED sign; for an existing operator **VMS** the operator's command/refresh and message-arbitration cycle may exceed 2 s, so NFR-01 carries the VMS adapter's own latency budget ([ADR-0004](adr/ADR-0004-warning-actuator-integration.md), [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)). |
| NFR-02 | **Latency** | Vehicle-gone → warning OFF within hold + ≤ 2 s. |
| NFR-03 | **Availability** | **Functional** availability ≥ 99% per monitored site over the pilot period — the fraction of time the unit can actually *detect-and-warn to spec*, not merely "powered and reporting"; time spent in a degraded/safe state counts as **unavailable**. Excludes scheduled maintenance. Field-measured (see §3a); the **≥ 99% figure is provisional pending an MTBF/MTTR reliability budget** — a single multi-day remote repair can exhaust it ([doc 04 §5 Q6](04-risk-and-safety.md#5-open-safety-questions-for-the-team)). |
| NFR-04 | **Reliability** | No fault — **software *or* sensor-discrimination** — may leave a **stale ON** warning indefinitely. A watchdog time-bounds any activation with no corroboration; because radar corroboration deliberately suppresses the watchdog, **`T_degraded_max`** separately bounds the `CAMERA_OCCLUDED_DEGRADED` hold — the warning held ON while the **camera cannot verify the track (occluded _or_ faulted)** and radar would otherwise sustain it forever — forcing a loud disposition ([doc 02 §4](02-system-architecture.md#4-the-detectionwarning-state-machine), [ADR-0009 §C](adr/ADR-0009-failsafe-placement-and-degraded-modes.md), [ADR-0013](adr/ADR-0013-degraded-hold-unification.md) makes the bound cause-agnostic). No state — and no sensor-degraded mode — holds the sign ON without **camera-verified, lane-attributed** confirmation. |
| NFR-05 | **Robustness** | Maintain target detection in rain and at night via multi-sensor sensing ([ADR-0001](adr/ADR-0001-sensing-modality.md)) — **contingent on the radar stationary-detection validation gate**; field-validated, not claimable from a synthetic-radar bench (§3a, §5). |
| NFR-06 | **Edge autonomy** | The detect→warn loop must function with the WAN/cloud fully offline ([ADR-0002](adr/ADR-0002-edge-vs-cloud-processing.md)). |
| NFR-07 | **Power** | Run on mains, or solar+battery with ≥ 72 h autonomy without sun ([ADR-0006](adr/ADR-0006-connectivity-and-power.md)). |
| NFR-08 | **Maintainability** | Remote health, remote config, OTA update; modular sensor/compute/sign units. |
| NFR-09 | **Security** | Authenticated, encrypted control + telemetry channels; signed firmware; sign activation cannot be spoofed by an outside party. |
| NFR-10 | **Privacy** | On-device inference; **no retention of continuous raw video**; event evidence minimized and access-controlled (see [doc 04](04-risk-and-safety.md)). |
| NFR-11 | **Standards** | Warning signage conforms to **QCVN 41** (national technical regulation on road signs & signals) and expressway geometric standards (e.g., TCVN 5729 for expressway design). |
| NFR-12 | **Cost** | Per-site bill of materials targeted for a credible field-pilot unit (tracked in [doc 03](03-roadmap-and-phasing.md)); the university build stays inside the 20M VND envelope (prototype/sim). |
| NFR-13 | **Environment** | Field units rated for outdoor temperature, humidity, dust, vibration (IP65+ enclosures). |
| NFR-14 | **Extensibility** | Architecture must allow adding sensor types and new event classes (FR-18/19) without redesign. |
| NFR-15 | **Operability / safety** | The fail-loud controls are only effective with a **staffed, bounded operator response path**. Alarms are **deduplicated and prioritized** to bound operator load; each safety-relevant escalation (BLIND-TO-NEW, CAMERA_OCCLUDED_DEGRADED, low-confidence clear, OVERRIDDEN-past-window, sign-stuck) carries a **severity and a target acknowledge/respond time** and **re-escalates if unacknowledged**. The operating concept and these bounds are specified in [ADR-0011](adr/ADR-0011-operator-concept-and-alarm-management.md); the numbers are provisional pending field tuning. |
| NFR-16 | **Time integrity** | **Relative** inter-sensor sync sufficient for camera↔radar fusion (sub-frame) **and** trustworthy **absolute** timestamps for the audit log (liability evidence, [doc 04 R10](04-risk-and-safety.md#1-risk-register)), both **holding over connectivity outages**. The time source is chosen explicitly (e.g. **GNSS/PPS + PTP**), never inherited from a free-running OS clock ([doc 02 §7](02-system-architecture.md#7-interfaces--contracts-initial), [ADR-0001](adr/ADR-0001-sensing-modality.md) AI#3). |

---

## 3a. Verification scope — what the funded (bench/sim) phase can actually show

Not every requirement above can be *validated* on a lab bench inside the 20M VND scope; several are
**designed now but proven only in the field** (cấp sở). Stating this up front keeps the final report
honest — a "Must" with no funded acceptance evidence is flagged *here*, not discovered at review. Tags:
**B** = bench rig · **S** = simulation · **F** = field-deferred · **D** = design/review only. The
methodology behind this split is [ADR-0007](adr/ADR-0007-validation-and-data-strategy.md).

| Requirement | Funded-scope verification | Why |
|-------------|---------------------------|-----|
| FR-09 (day/night/rain/fog) | **S (approx) + F** | A bench cannot make real rain/glare/fog; simulation only approximates. Real-condition recall is field-deferred. |
| FR-17 (reuse existing VMS) | **F** | Needs a real operator VMS; the bench uses an LED stand-in. |
| NFR-03 (functional availability) | **F** | An operational metric; the bench can only characterise software-loop MTBF under fault injection. |
| NFR-05 (rain/night robustness) | **F** | Contingent on the [ADR-0001](adr/ADR-0001-sensing-modality.md) radar gate; not claimable from a synthetic-radar bench. |
| NFR-07 (solar ≥ 72 h autonomy) | **F** | Design-only at bench scope (lab mains). |
| NFR-11 / NFR-14 (standards, extensibility) | **D** | Conformance review and architectural argument, not a runtime test. |
| NFR-13 (IP65 environment) | **F** | No field-grade enclosure is built at bench scope. |
| NFR-15 (operator response / alarm mgmt) | **D + F** | Alarm dedup/prioritization and the OVERRIDDEN/degraded surfacing are bench-demonstrable; the **operator response-time** and alarm-load bounds are an operational metric, field-deferred ([ADR-0011](adr/ADR-0011-operator-concept-and-alarm-management.md)). |
| NFR-16 (time integrity) | **B + F** | Relative inter-sensor sync is bench-measurable; **absolute-time hold-over** across a real multi-hour outage (and a GNSS-denied tunnel site) is field-deferred. |
| FR-10 calibration-drift monitor | **B (logic) + F (real drift)** | The bench can inject a synthetic homography shift to prove the monitor *detects and alarms*; **real** drift (pole sway, vibration, thermal cycling) needs the field mast/enclosure, so R15's control is logic-verified, not field-proven, at bench scope. |
| All other FR/NFR | **B + S** | Logic, latency, fault handling, privacy, edge autonomy, override, config, and events are exercisable on the rig/sim. |

Everything tagged **F** carries forward to field-pilot acceptance
([doc 05 §11](05-field-pilot-proposal.md#11-acceptance-kpis-field)); **nothing tagged F may be reported
as a measured prototype result.**

---

## 4. Warning placement — the math the proposal omits

The proposal says the sign goes "at the start of the emergency-lane section / before the danger
zone." That is under-specified and is the single most safety-critical geometric decision. If the
warning is too close to the stopped vehicle, drivers cannot act in time; the system would be
**theatre**.

A following driver must **detect → recognise → decide → manoeuvre** (slow and/or change lane). The
governing standard is therefore not just Stopping Sight Distance (SSD) but **Decision Sight
Distance (DSD)** for a speed/path-change manoeuvre on a high-speed road.

**Stopping Sight Distance** (AASHTO metric form, level grade, perception-reaction t = 2.5 s,
deceleration a = 3.4 m/s²):

```
SSD = 0.278 · V · t  +  0.039 · V² / a       (V in km/h, SSD in m)
```

| Design speed V | SSD (must stop) | DSD — manoeuvre C* (perceive + change lane/slow) |
|---------------:|----------------:|--------------------------------------------------:|
| 80 km/h | ≈ 130 m | ≈ 230 m |
| 100 km/h | ≈ 185 m | ≈ 315 m |
| 120 km/h | ≈ 250 m | ≈ 360 m |

\* DSD manoeuvre C = "speed/path/direction change on a rural/high-speed road" (AASHTO). It is the
appropriate basis because the safe response here is a **lane change**, not an emergency stop. The
DSD-C column is read from AASHTO's published table — a constant-speed manoeuvre distance of the form
`d = 0.278 · V · t_C` — and is **not** computed from the SSD formula above (it has no braking term), so
don't expect that expression to reproduce 315 m at 100 km/h.

**Why DSD-C and not just "SSD + a lane change"?** SSD assumes the driver *stops*; the safe response to
a shoulder obstacle is usually to *hold speed and change lane* — a decision-and-manoeuvre task — so DSD
(manoeuvre C) is the defensible basis. It is deliberately **conservative**: DSD-C exceeds SSD by
~130 m at 100 km/h, which buys margin but also **raises the bar a site must clear** (PL-04). An
over-long required distance can mark otherwise-viable sites "unsuitable", so treat the table as a
**design floor** and, per site, also compute "SSD + a comfortable lane-change distance" as a lower
bound; use engineering judgement (and operator agreement) where the two diverge.

**Two corrections the table does _not_ include — both push the distance up at the worst sites.** (1) The
table is **level-grade**; on a **downgrade** (common at the tunnel/bridge approaches and long descents
that are exactly the high-value sites, [doc 02 §6](02-system-architecture.md#6-coverage-model)) braking
distance grows, so SSD/DSD must carry a grade correction. (2) The table keys off **design speed**, but
Vietnamese expressway **operating speeds often exceed design speed**, so placement should key off the
**85th-percentile operating speed (or posted speed + margin)** — otherwise it is non-conservative exactly
where vehicles are fastest. Both are **Phase-1 siting-study inputs**, not per-site afterthoughts.

**Reconcile with the Vietnamese standard.** The numbers above are AASHTO. For approvals, the
sight-distance basis must be expressed against the **governing Vietnamese standard — TCVN 5729
(expressway geometric design), alongside QCVN 41 for the signage itself**. Map the DSD-C argument onto
TCVN 5729's sight-distance provisions, or justify AASHTO DSD as a supplementary safety basis where
TCVN is silent. This is a **methodology task for the siting study** (Phase 1), not a per-site
afterthought.

**Requirement PL (placement):**

- **PL-01 (M):** The warning sign must be displayed **at least DSD (manoeuvre C) upstream of the
  upstream (near) edge of the detection zone** for the corridor's design speed (the table above is the
  design floor; confirm against the governing Vietnamese standard for each site).
- **PL-02 (M):** Add a **legibility distance** so the sign is *readable* by the time the driver is
  DSD away — for a LED text VMS, legibility is on the order of 1 m per 4–8 mm of character height;
  size the sign accordingly, or place it correspondingly farther upstream.
- **PL-03 (M):** Account for **activation latency**: during stop→warn time (≈ dwell + ≤2 s) traffic
  keeps approaching. The sign is fixed upstream, so once lit every following driver gets the full
  DSD; latency only bounds the brief window before it lights. Keep total stop→warn small (NFR-01) so
  that window is short relative to vehicle headways.
- **PL-04 (S):** Where geometry (curve, crest, tunnel mouth) blocks sight of a single sign at the
  required distance, use a **second repeater sign** or relocate; if neither fits, the site is
  unsuitable for a single-unit deployment — record this as a siting constraint (assumption A4).

**Unwarned-exposure budget (what `T_dwell` costs).** Confirmation is not free. For the window
`τ = T_dwell + T_activate` (nominal 5 + ≤2 ≈ **7 s**) after a vehicle first stops, no warning is yet
shown. Because the sign is fixed upstream, this does **not** shorten the lead of drivers who pass the
sign *after* it lights — they still get the full DSD; the exposure is the **following vehicles that
pass the sign's location during `τ`**, who get a reduced or zero lead. Approximate it as:

```
N_unwarned ≈ τ / h        (h = mean following headway, s/veh, per lane)
L_unwarned ≈ τ · V        (distance a follower covers during τ; 7 s @ 100 km/h ≈ 194 m)
```

At a 2 s headway, `τ ≈ 7 s` exposes ~3–4 following vehicles per lane before the warning appears. This
is the quantitative form of the residual hazard in
[doc 04 §0](04-risk-and-safety.md#0-limits-of-protection-residual-hazards), and it bounds `T_dwell`
**from above**: a longer dwell buys fewer false alarms (good) but enlarges `N_unwarned` and leaves the
just-stopped vehicle unprotected longer (bad). Size `T_dwell` so `N_unwarned` stays within an
operator-agreed ceiling at the site's headway, and keep `T_activate` small (NFR-01). **This is the
budget** [doc 02 §4](02-system-architecture.md#4-the-detectionwarning-state-machine) refers to when it
says to tune the dwell against unwarned exposure.

> This makes warning placement a **derived, defensible number per site**, not a guess. It is one of
> the most valuable additions over the original proposal.

---

## 5. Evaluation metrics & acceptance criteria

The proposal says to "evaluate detection capability and auto on/off." This section says **against
what**. Targets are split into *university-prototype* (bench/sim) and *field-pilot* (follow-on)
because they are validated very differently.

| Metric | Definition | Prototype target (bench/sim) | Field-pilot target |
|--------|-----------|------------------------------|--------------------|
| **Recall — vehicles** | genuine stopped-vehicle events detected ÷ all such events | ≥ 95% day (bench/sim). **Night/adverse is gated** — claimable only if the [ADR-0001](adr/ADR-0001-sensing-modality.md) radar gate passes on real hardware; otherwise **field-deferred**, never asserted from synthetic radar | ≥ 98% day · ≥ 95% night/adverse |
| **Recall — pedestrians** | stranded-occupant events detected ÷ all such (FR-08) | tracked **separately**, best-effort (small RCS + camera weakest at night); target set after Phase-3 data, **not** assumed equal to vehicles | ≥ 90% day · best-effort night |
| **False activation rate** | false warnings ÷ **exposure** — report **both** per-100-staged-scenarios *and* per-operating-hour (raw counts across different scenario mixes are not comparable) | ≤ 1 per 100 staged scenarios *and* a reported per-hour rate | **provisional** ≤ 1 / site / week, **pending operator trust-calibration** ([doc 04 §5](04-risk-and-safety.md#5-open-safety-questions-for-the-team)) |
| **Detection latency** | vehicle becomes stationary → warning ON | ≤ dwell + 2 s | same |
| **Clear latency** | vehicle leaves ROI → warning OFF | ≤ hold + 2 s **on a confirmed exit** (a held occlusion is not a clear-latency failure — [ADR-0008](adr/ADR-0008-detection-persistence-and-multitrack.md)) | same |
| **Effective warning lead distance** | upstream distance at which the active warning is visible/legible | ≥ DSD for the modelled speed | ≥ DSD on-site, surveyed |
| **Functional availability** | time able to *detect-and-warn to spec* ÷ total time (degraded/safe-state time counts as down — NFR-03) | software-loop MTBF under fault injection (availability itself is **field-deferred**) | ≥ 99% |
| **Fault-detection coverage** | injected faults the self-monitor catches & escalates | ≥ 95% of the FMEA fault list ([doc 04 §2](04-risk-and-safety.md#2-fmea-lite-failure-mode--effect--detection--response)) — **caveat:** this measures detection of *enumerated* faults, not unknown ones, **and not faults the bench cannot inject** (calibration drift, box/link death at field distance, solar depletion are field-deferred; report coverage as a fraction of **bench-injectable** modes — §3a) | ≥ 95% |
| **MTBF / MTTR** | mean time between failures / to repair | characterise on rig | MTBF target set at pilot |

**Statistical sufficiency (so a target is actually testable).** A bare "≥ 95%" is not a pass/fail bar
without a sample size and a confidence level: 19/20 events is 95%, but its lower 95% confidence bound is
~75%. Each **rate** metric therefore carries a **minimum event count and a confidence statement** —
e.g. *recall ≥ 95% with a lower 95% (Wilson) bound ≥ 90% over ≥ 200 staged events*, and false-activation
reported with its exposure denominator and a confidence interval. **Be precise about what the N counts.**
Simulation can cheaply generate volume for the *logic / timing / false-trigger-on-modelled-nuisance*
metrics — but a Wilson bound on **recall** computed from synthetic events the loop itself consumes
measures the **simulator's determinism, not real detection**, so **synthetic N does _not_ count toward
the recall claim**. The recall N+Wilson bound is a statistic on **real captures** (bench, then field);
the bench rig reports the N it actually achieved. Fix the exact N and bound per metric in the simulation
methodology ([ADR-0007](adr/ADR-0007-validation-and-data-strategy.md) AI#1); a "≥ 95%" claimed off a
handful of runs — **or off synthetic recall** — is not a measured result.

> **Generating the evidence is itself a planned deliverable, not a by-product.** The recall N must come
> from **real captures**, and the per-hour false-activation denominator from **continuous bench-hours** —
> neither is produced by running the loop a few times. Public datasets are sparse in "stopped vehicle on a
> Vietnamese expressway shoulder, day *and* night" positives, so hitting *(e.g.)* ≥ 200 real positive
> events with a Wilson lower bound is a **staging-and-capture task that must be scoped, scheduled, and
> resourced in Phase 1** — at the same altitude as the radar spike — or Phase 5 arrives with a working
> loop and too few events to *report* recall to this bar (the 19/20 trap, sprung on ourselves). The
> acceptance-evidence-generation plan is an explicit Phase-1 deliverable
> ([doc 03 §3](03-roadmap-and-phasing.md#3-phase-plan-aligned-to-the-proposals-6-phases),
> [ADR-0007](adr/ADR-0007-validation-and-data-strategy.md)).

**Acceptance for the university task** = demonstrate, on the bench rig and/or simulation, the full
closed loop (detect → confirm → warn → track → clear) meeting the prototype-column targets (at the
sample sizes above) across a defined scenario set (day, night, rain, transient pass-through,
**through-lane congestion / stop-and-go stationary beside the ROI — must _not_ false-trigger**,
**brief and sustained occlusion with and without radar corroboration**, **the `T_degraded_max` forced
clear of a sustained camera-occlusion**, **multiple simultaneous vehicles arriving and leaving**,
pedestrian **(including a *moving* stranded occupant who never satisfies the speed gate)**, **a vehicle
already present at boot**, **operator override expiry and out-of-policy override rejection (FR-13,
[ADR-0010](adr/ADR-0010-operator-override-and-manual-control.md))**, **out-of-bounds config rejection
(FR-20) and OTA-deferral while a warning is active (FR-21)**, and **injected sensor/compute/sign faults —
including killing the state-machine process, killing the edge box, and cutting the sign link to prove the
sign-controller dead-man's switch blanks the sign in every case**
([ADR-0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.md))), plus the feasibility report and
the field-pilot development proposal the grant calls for.

> **Two of those scenarios are *designed*, not *field-sound*, at bench scope.** The congestion
> no-false-trigger and the sustained-occlusion hold both rest on radar **resolving the shoulder from the
> adjacent through lane** at the monitored range — criterion (b) of the
> [ADR-0001](adr/ADR-0001-sensing-modality.md) gate, which a few-metre bench **cannot reproduce** (an
> angular problem) and which is test-track/field-deferred. Report both as *logic-validated as specified*,
> not *proven sound in the field* ([ADR-0007](adr/ADR-0007-validation-and-data-strategy.md)); a weak (b)
> inverts each — congestion → false-trigger, occlusion → stale-ON
> ([doc 04 R12/R14](04-risk-and-safety.md#1-risk-register)).

**Provability boundary (state it in the report).** Bench/sim results substantiate *logic, timing,
fault handling, and false-trigger resistance to modelled nuisances*; they do **not** substantiate
real-world recall in rain/glare/fog, the real false-alarm rate, or real radar clutter performance —
those are field-deferred ([ADR-0007](adr/ADR-0007-validation-and-data-strategy.md)). Report every
result with its tier (§3a) so no claim outruns its evidence.

> **One honest headline for the report: this prototype proves _buildability and logic_, not _safety
> efficacy_.** The three mechanisms that make this a *safety* system rather than an engineering demo —
> the radar-corroborated occlusion/degraded hold, congestion suppression, and night/adverse robustness —
> **all** rest on the field-deferred radar criterion (b) that the bench cannot reproduce
> ([ADR-0001](adr/ADR-0001-sensing-modality.md)). So the funded phase establishes that the system can be
> *built* and that its decision logic is *correct as specified*; whether it is *effective and sound on a
> real road* is the cấp sở question. Stating this in aggregate — not only per-metric — pre-empts the
> reviewer who notices the pattern, and is the scope-honesty the whole [ADR-0007](adr/ADR-0007-validation-and-data-strategy.md)
> strategy is built on.

---

## Appendix A — Changes and corrections vs. the proposal

| # | In the proposal | Change / addition here | Why |
|---|-----------------|------------------------|-----|
| 1 | "Detect a stopped car, show a sign." | Reframed as a **safety-related** system with fail-safe + trust requirements. | Silent failure and cry-wolf are the real risks. |
| 2 | Sign "at the start of the lane." | **DSD-based placement requirement** with per-speed numbers (§4). | Otherwise the warning may be too late to be useful. |
| 3 | Multi-sensor listed as optional "can develop toward." | **Camera+radar elevated to core** for night/rain/fog. | Those are the named high-risk conditions and camera-only is weakest there. |
| 4 | "Closed loop: detect–confirm–warn–track–cancel." | Made a **concrete state machine** with dwell + hysteresis + watchdog. | Prevents false triggers, flapping, and stale-ON. |
| 5 | "Central processor." | Specified as **edge-local**; cloud non-critical. | A safety warning must not wait on a network round-trip. |
| 6 | "Evaluate detection." | **Numeric acceptance criteria** (§5). | "Evaluate" needs a pass/fail bar. |
| 7 | New signs implied everywhere. | **Reuse existing VMS** where present; solar LED sign as fallback. | Cheaper, avoids sign clutter, faster approval. |
| 8 | Privacy not addressed. | **Data minimization, no raw-video retention, QCVN 41 conformance.** | Public-road cameras carry PII and legal duties. |
| 9 | Budget 20M VND, field ambitions. | **Scope reality check**: prototype/sim now, field pilot = cấp sở follow-on. | Honest scoping; the proposal itself anticipates the follow-on. |
| 10 | Section numbering (5→2.x, 6→3.x) is template residue. | Cosmetic — renumber in the final proposal. | Document hygiene only. |
