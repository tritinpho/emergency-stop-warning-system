# 06 — Verification Traceability Matrix

**Project:** Emergency Stop-Lane Automatic Warning System (ESW)
**Status:** Proposed
**Last updated:** 2026-06-27
**Related:** [01 requirements](01-requirements.md) · [02 architecture](02-system-architecture.md) · [04 risk & safety](04-risk-and-safety.md) · [ADRs](adr/README.md)

This matrix is the **pre-build gate**: one auditable row per requirement, tying each to the decision
that governs it, the verification **tier** that can prove it, the **named scenario/test** that does, and
the **pass criterion**. It assembles what was previously scattered across the [doc 01 §2/§3](01-requirements.md#2-functional-requirements)
requirement tables, the [§3a](01-requirements.md#3a-verification-scope--what-the-funded-benchsim-phase-can-actually-show)
B/S/F/D tags, the [§5](01-requirements.md#5-evaluation-metrics--acceptance-criteria) metrics & scenario
set, and the [doc 04 §2](04-risk-and-safety.md#2-fmea-lite-failure-mode--effect--detection--response)
FMEA-as-fault-injection-set — so **no "Must" is orphaned** and no claim outruns its evidence tier.

**Tiers** (from [ADR-0007](adr/ADR-0007-validation-and-data-strategy.md)): **B** = bench rig · **S** =
simulation · **F** = field-deferred (cấp sở) · **D** = design/review only. A row with **F** in its tier
**may not be reported as a measured prototype result** — it carries to field-pilot acceptance
([doc 05 §11](05-field-pilot-proposal.md#11-acceptance-kpis-field)).

---

> ## ⚠ PHASE NOTE — this build is CAMERA-ONLY
>
> [ADR-0001](adr/ADR-0001-sensing-modality.md) (camera + radar fusion) was **Rejected on 2026-07-10**. The cấp trường bench
> prototype ships **camera-only**. Every radar-dependent behaviour described below — radar
> corroboration, the occlusion hold (`WARN_HOLD` / `CAMERA_OCCLUDED_DEGRADED`), `T_degraded_max`, and
> the `FULL` / `RADAR-ONLY` sensing modes — is **dormant: the code retains it, but it never executes**,
> because `corr` is never true without a radar channel.
>
> Accepted consequences: **R5** (night/rain/fog blindness) is **unmitigated** and night/adverse recall
> is **not claimed**; **R20** — an occluded vehicle is cleared at `T_hold` (~10 s), blanking the sign
> with the hazard present; **R21** — the unit sits permanently in `CAMERA_ONLY`, hence permanently
> `DEGRADED`. See [doc 04](04-risk-and-safety.md).
>
> Radar content below is the **cấp sở** target design, not this phase's build.

## 1. Functional requirements

| ID | Requirement (short) | Pri | Governing ADR(s) | Tier | Verification scenario / test | Pass criterion |
|----|---------------------|-----|------------------|------|------------------------------|----------------|
| FR-01 | Monitor configurable ROI | M | [0003](adr/ADR-0003-detection-algorithm.md) | B·S | All scenarios; ROI-gating unit test (footprint overlap ≥ 50 %) | Detections outside ROI rejected; straddling pose deterministic |
| FR-02 | Detect vehicle in ROI | M | [0001](adr/ADR-0001-sensing-modality.md) *(Rejected)* /[0003](adr/ADR-0003-detection-algorithm.md) | B·S (day) · **—** (night/adverse) | Day set; recall metric (§5) over **real** captures | Recall ≥ 95 % day. Night/adverse **withdrawn** — no radar, no gate, no claim (R5 unmitigated) |
| FR-03 | Stopped vs. passing | M | [0003](adr/ADR-0003-detection-algorithm.md)/[0008](adr/ADR-0008-detection-persistence-and-multitrack.md) | B·S | Transient pass-through; creep-along-shoulder | Pass-through does **not** trigger (false-activation §5) |
| FR-04 | Dwell confirmation | M | [0008](adr/ADR-0008-detection-persistence-and-multitrack.md) | B·S | Stop-and-hold; dwell sweep 3–10 s | Confirm only after `T_dwell`; sized vs. unwarned-exposure budget |
| FR-05 | Activate sign on confirm | M | [0004](adr/ADR-0004-warning-actuator-integration.md) | B·S | Closed-loop happy path | Sign ON ≤ dwell + 2 s (NFR-01) |
| FR-06 | Track while active | M | [0008](adr/ADR-0008-detection-persistence-and-multitrack.md) | B·S | Sustained presence; multi-vehicle | Warning held while set non-empty |
| FR-07 | Clear + hysteresis | M | [0008](adr/ADR-0008-detection-persistence-and-multitrack.md) | B·S | Departure; brief occlusion | Clear ≤ hold + 2 s on confirmed exit; brief dropout does not flap |
| FR-08 | Pedestrian warrant (**presence-onset**) | S | [0003](adr/ADR-0003-detection-algorithm.md)/[0008](adr/ADR-0008-detection-persistence-and-multitrack.md) | S(approx)·**F** | **Moving stranded occupant** (walks, never stationary); person in/beside ROI | Presence-debounced trigger fires; recall tracked **separately** (§5), night best-effort |
| ~~FR-09~~ | Day/night/rain/fog | ~~M~~ **descoped** | [0001](adr/ADR-0001-sensing-modality.md) *(Rejected 2026-07-10)* | **—** | *(none — no adverse-condition acceptance in this phase)* | **Withdrawn.** Day only. Night/rain/fog needs the second sensor that was not funded; R5 unmitigated, reinstate at cấp sở |
| FR-10 | Self-monitor + heartbeat (**incl. calibration-drift monitor**) | M | [0005](adr/ADR-0005-fail-safe-and-system-safety.md) | B·S · **F** (real drift) | Per-subsystem health; heartbeat cadence; **drift monitor** — inject a synthetic homography shift | Heartbeat carries health + version fingerprint; faults detected; drift shift → degraded + alert (real drift field-deferred, R15) |
| FR-11 | Safe state + alert on fault | M | [0005](adr/ADR-0005-fail-safe-and-system-safety.md)/[0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)/[0013](adr/ADR-0013-degraded-hold-unification.md) | B·S | **Fault injection** (kill SM, kill box, cut link; **kill camera under active warning**; **CLEAR vs. wedged-ON sign**) | Sign blanks within `T_signhold` (SM/box/link); camera-kill → bounded hold → `T_degraded_max` loud clear; stuck-ON → SAFE STATE + sign-stuck escalation; operator alerted in every case |
| FR-12 | Events to TMC + audit log | S | [0002](adr/ADR-0002-edge-vs-cloud-processing.md) | B·S | Activation/clear/fault events; link-down queueing | Events with version fingerprint reach audit; store-and-forward survives outage |
| FR-13 | Operator override (bounded) | S | [0010](adr/ADR-0010-operator-override-and-manual-control.md) | B·S | **Override expiry**; out-of-policy override **rejection**; force-on under box-kill | Mute auto-expires; force-on blanks on box-kill/link-cut; unauth rejected |
| FR-14 | Remote config | S | [0010](adr/ADR-0010-operator-override-and-manual-control.md)/[0012](adr/ADR-0012-security-and-threat-model.md) | B·S | Signed config push; bad-config (→ FR-20) | Valid signed config applied; invalid rejected |
| FR-15 | OTA + rollback | C | [0007](adr/ADR-0007-validation-and-data-strategy.md)/[0012](adr/ADR-0012-security-and-threat-model.md) | B·S | Model regression → **canary** → rollback | Regressed model rolled back to last signed version |
| FR-16 | Evidence logging (no raw video) | S | [0007](adr/ADR-0007-validation-and-data-strategy.md) | B·S·D | Event-snapshot capture; retention/expiry | Minimal metadata/snapshot only; bounded auto-expiry; privacy review (NFR-10) |
| FR-17 | Reuse existing VMS | S | [0004](adr/ADR-0004-warning-actuator-integration.md) | **F** | Real operator VMS (bench uses LED stand-in) | NFR-01 **qualified**; arbitration + latching caveat documented |
| FR-18 | Generic obstacles / wrong-way | W | [0003](adr/ADR-0003-detection-algorithm.md) | — | *Future* — not verified this phase | n/a (extensibility argument, NFR-14) |
| FR-19 | Notify emergency services | W | — | — | *Future* — not verified this phase | n/a |
| FR-20 | Config bounds enforcement (**full safety-parameter surface**, [doc 02 §7a](02-system-architecture.md#7-interfaces--contracts-initial)) | M | [0010](adr/ADR-0010-operator-override-and-manual-control.md)/[0012](adr/ADR-0012-security-and-threat-model.md)/[0013](adr/ADR-0013-degraded-hold-unification.md) | B·S | **Out-of-bounds value** for any surface parameter — ROI / `T_dwell=900 s` / **`T_signhold` large enough to defeat the dead-man's switch** / **`T_degraded_max`→"never"** — rejected/clamped | Out-of-range parameter (incl. the safety backstops) rejected or clamped; last-good kept; alerted |
| FR-21 | Defer OTA while warning active | S | [0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.md) | B·S | **OTA requested with track-set non-empty** | Update deferred, or blank *loud to operators* — never a silent drop |

## 2. Non-functional requirements

| ID | Requirement (short) | Governing ADR(s) | Tier | Verification scenario / test | Pass criterion |
|----|---------------------|------------------|------|------------------------------|----------------|
| NFR-01 | Stop→warn ≤ 2 s | [0004](adr/ADR-0004-warning-actuator-integration.md)/[0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.md) | B·S (LED) · **F** (VMS) | Latency measurement, LED backend | ≤ dwell + 2 s on LED; VMS backend **qualified** with its own budget |
| NFR-02 | Vehicle-gone→off ≤ hold + 2 s | [0008](adr/ADR-0008-detection-persistence-and-multitrack.md) | B·S | Clear-latency on confirmed exit | ≤ hold + 2 s; held occlusion is **not** a clear-latency failure |
| NFR-03 | Functional availability ≥ 99 % | [0005](adr/ADR-0005-fail-safe-and-system-safety.md) | **F** | Field measurement; bench = software-loop MTBF under fault injection | **Provisional** ≥ 99 %, **pending MTBF/MTTR budget** ([doc 04 Q6](04-risk-and-safety.md#5-open-safety-questions-for-the-team)) |
| NFR-04 | No stale-ON (any fault) | [0005](adr/ADR-0005-fail-safe-and-system-safety.md)/[0008](adr/ADR-0008-detection-persistence-and-multitrack.md)/[0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)/[0013](adr/ADR-0013-degraded-hold-unification.md) | B·S | Watchdog expiry; **`T_degraded_max` forced clear (occlusion _and_ camera-fault cause)**; wedged-logic | No state — and no sensor-degraded mode — holds the sign ON without camera-verified, lane-attributed confirmation; bounded clear in every case |
| ~~NFR-05~~ | Rain/night robustness | [0001](adr/ADR-0001-sensing-modality.md) *(Rejected 2026-07-10)* | **—** | *(gate removed — deferred to cấp sở)* | **Descoped, not deferred.** No radar → no gate → **no claim**; never rested on synthetic radar (R5 unmitigated) |
| NFR-06 | Edge autonomy (WAN offline) | [0002](adr/ADR-0002-edge-vs-cloud-processing.md) | B·S | WAN-outage injection | Detect→warn loop unaffected; events queue |
| NFR-07 | Solar ≥ 72 h autonomy | [0006](adr/ADR-0006-connectivity-and-power.md) | **F** (D at bench) | Energy budget incl. gate-grade radar draw | Design-only at bench; field-measured at pilot |
| NFR-08 | Maintainability (remote health/config/OTA) | [0002](adr/ADR-0002-edge-vs-cloud-processing.md) | B·D | Remote health/config/OTA exercised | Modular; remotely serviceable |
| NFR-09 | Security (scoped) | [0012](adr/ADR-0012-security-and-threat-model.md) | D · **F** | Threat-model review; sign-link/override auth; replay test | Authenticated against forge/replay on enumerated surfaces; denial → fail-safe-blank-and-alarm; deep hardening **field** |
| NFR-10 | Privacy (on-device, no raw retention) | [0007](adr/ADR-0007-validation-and-data-strategy.md) | B·D | Data-handling review; retention/expiry test | On-device inference; no continuous raw video; bounded evidence |
| NFR-11 | Standards (QCVN 41 / TCVN 5729) | [0004](adr/ADR-0004-warning-actuator-integration.md) | D | Conformance review; message-set review | Message set conformant **or** regulated exception sought (ADR-0004 AI#4) |
| NFR-12 | Cost (20M envelope / field BoM) | — ([doc 03](03-roadmap-and-phasing.md)) | D | Budget tracking | University build inside 20M; field BoM tracked |
| NFR-13 | Environment IP65+ | [0006](adr/ADR-0006-connectivity-and-power.md) | **F** | Field-grade enclosure | No field enclosure at bench; field-deferred |
| NFR-14 | Extensibility | [0003](adr/ADR-0003-detection-algorithm.md)/[0004](adr/ADR-0004-warning-actuator-integration.md) | D | Architectural argument | New sensor/event class / backend without redesign |
| NFR-15 | Operator response / alarm mgmt | [0011](adr/ADR-0011-operator-concept-and-alarm-management.md) | D · **F** | Alarm dedup/priority demo; **alarm-unack re-escalation**; ConOps review | Dedup/priority/re-escalation demonstrated; response-time bounds **field-tuned** |
| NFR-16 | Time integrity (rel. + abs.) | [0001](adr/ADR-0001-sensing-modality.md) | B · **F** | Inter-sensor sync measurement; outage hold-over | Sub-frame relative sync on bench; absolute hold-over **field** (GNSS-denied tunnel) |

## 3. Placement requirements

| ID | Requirement (short) | Governing | Tier | Verification | Pass criterion |
|----|---------------------|-----------|------|--------------|----------------|
| PL-01 | Sign ≥ DSD upstream of ROI near edge | [doc 01 §4](01-requirements.md#4-warning-placement--the-math-the-proposal-omits) | D · **F** | Siting study (grade + 85th-%ile speed corrected); on-site survey | ≥ DSD-C for governing speed, from upstream ROI edge; TCVN 5729 reconciled |
| PL-02 | Legibility distance | [doc 01 §4](01-requirements.md#4-warning-placement--the-math-the-proposal-omits) | D · **F** | Character-height calc; on-site legibility | Readable by the time driver is DSD away |
| PL-03 | Activation-latency accounting | [doc 01 §4](01-requirements.md#4-warning-placement--the-math-the-proposal-omits) | B·S | Unwarned-exposure model | `N_unwarned` within operator-agreed ceiling at site headway |
| PL-04 | Repeater / unsuitable-site rule | [doc 01 §4](01-requirements.md#4-warning-placement--the-math-the-proposal-omits) | D | Per-site geometry review | Repeater where sight blocked; else site recorded unsuitable (A4) |

---

## 4. Coverage notes — what this matrix makes explicit

- **No orphaned "Must".** Every **M** requirement now has a named scenario and pass criterion. The
  previously-implicit functional requirements — **FR-12** (events/audit), **FR-13** (override),
  **FR-14** (config), **FR-16** (evidence), **FR-20** (config bounds), **FR-21** (OTA-defer) — are now
  **explicit acceptance scenarios** ([doc 01 §5](01-requirements.md#5-evaluation-metrics--acceptance-criteria)),
  not absorbed silently into "injected faults".
- **Two scenarios are *designed*, not *field-sound*.** Congestion no-false-trigger and sustained-occlusion
  hold rest on the field-deferred radar criterion (b) — report them **logic-validated as specified**, not
  field-proven ([ADR-0001](adr/ADR-0001-sensing-modality.md)/[ADR-0007](adr/ADR-0007-validation-and-data-strategy.md)).
- **Fault coverage is a fraction of *bench-injectable* modes.** Calibration drift, edge-box/link death at
  the ≥ DSD distance, and solar depletion are **field-only**; the ≥ 95 % fault-detection target is
  reported over what the bench can inject ([doc 04 §2](04-risk-and-safety.md#2-fmea-lite-failure-mode--effect--detection--response)).
- **The IF-4 sign-link bearer is now decided** — LoRa point-to-point ([ADR-0014](adr/ADR-0014-sign-link-bearer.md))
  — and adds a **field-deferred** item: the over-distance **duty-cycle / loss / latency budget that sets
  `T_signhold`** (the 433 MHz duty limit can bind the dead-man's-switch refresh rate). It governs
  FR-11 / NFR-01 / NFR-04 at the link layer and joins the ≥ DSD link validation already field-deferred by
  [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.md).
- **Everything tagged F carries to field-pilot acceptance** ([doc 05 §11](05-field-pilot-proposal.md#11-acceptance-kpis-field));
  nothing tagged F is a measured prototype result.
