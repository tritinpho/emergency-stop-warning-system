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

## 1. Functional requirements

| ID | Requirement (short) | Pri | Governing ADR(s) | Tier | Verification scenario / test | Pass criterion |
|----|---------------------|-----|------------------|------|------------------------------|----------------|
| FR-01 | Monitor configurable ROI | M | [0003](adr/ADR-0003-detection-algorithm.md) | B·S | All scenarios; ROI-gating unit test (footprint overlap ≥ 50 %) | Detections outside ROI rejected; straddling pose deterministic |
| FR-02 | Detect vehicle in ROI | M | [0001](adr/ADR-0001-sensing-modality.md)/[0003](adr/ADR-0003-detection-algorithm.md) | B·S (day) · **F** (night/adverse) | Day/night/rain set; recall metric (§5) | Recall ≥ 95 % day; night/adverse **gated** on radar gate, else field-deferred |
| FR-03 | Stopped vs. passing | M | [0003](adr/ADR-0003-detection-algorithm.md)/[0008](adr/ADR-0008-detection-persistence-and-multitrack.md) | B·S | Transient pass-through; creep-along-shoulder | Pass-through does **not** trigger (false-activation §5) |
| FR-04 | Dwell confirmation | M | [0008](adr/ADR-0008-detection-persistence-and-multitrack.md) | B·S | Stop-and-hold; dwell sweep 3–10 s | Confirm only after `T_dwell`; sized vs. unwarned-exposure budget |
| FR-05 | Activate sign on confirm | M | [0004](adr/ADR-0004-warning-actuator-integration.md) | B·S | Closed-loop happy path | Sign ON ≤ dwell + 2 s (NFR-01) |
| FR-06 | Track while active | M | [0008](adr/ADR-0008-detection-persistence-and-multitrack.md) | B·S | Sustained presence; multi-vehicle | Warning held while set non-empty |
| FR-07 | Clear + hysteresis | M | [0008](adr/ADR-0008-detection-persistence-and-multitrack.md) | B·S | Departure; brief occlusion | Clear ≤ hold + 2 s on confirmed exit; brief dropout does not flap |
| FR-08 | Pedestrian warrant (**presence-onset**) | S | [0003](adr/ADR-0003-detection-algorithm.md)/[0008](adr/ADR-0008-detection-persistence-and-multitrack.md) | S(approx)·**F** | **Moving stranded occupant** (walks, never stationary); person in/beside ROI | Presence-debounced trigger fires; recall tracked **separately** (§5), night best-effort |
| FR-09 | Day/night/rain/fog | M | [0001](adr/ADR-0001-sensing-modality.md) | S(approx)·**F** | Simulated adverse; real-condition field | Degraded-but-functional; real recall **field-deferred** |
| FR-10 | Self-monitor + heartbeat | M | [0005](adr/ADR-0005-fail-safe-and-system-safety.md) | B·S | Per-subsystem health; heartbeat cadence | Heartbeat carries health + version fingerprint; faults detected |
| FR-11 | Safe state + alert on fault | M | [0005](adr/ADR-0005-fail-safe-and-system-safety.md)/[0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.md) | B·S | **Fault injection** (kill SM, kill box, cut link) | Sign blanks within `T_signhold` in **every** case; operator alerted |
| FR-12 | Events to TMC + audit log | S | [0002](adr/ADR-0002-edge-vs-cloud-processing.md) | B·S | Activation/clear/fault events; link-down queueing | Events with version fingerprint reach audit; store-and-forward survives outage |
| FR-13 | Operator override (bounded) | S | [0010](adr/ADR-0010-operator-override-and-manual-control.md) | B·S | **Override expiry**; out-of-policy override **rejection**; force-on under box-kill | Mute auto-expires; force-on blanks on box-kill/link-cut; unauth rejected |
| FR-14 | Remote config | S | [0010](adr/ADR-0010-operator-override-and-manual-control.md)/[0012](adr/ADR-0012-security-and-threat-model.md) | B·S | Signed config push; bad-config (→ FR-20) | Valid signed config applied; invalid rejected |
| FR-15 | OTA + rollback | C | [0007](adr/ADR-0007-validation-and-data-strategy.md)/[0012](adr/ADR-0012-security-and-threat-model.md) | B·S | Model regression → **canary** → rollback | Regressed model rolled back to last signed version |
| FR-16 | Evidence logging (no raw video) | S | [0007](adr/ADR-0007-validation-and-data-strategy.md) | B·S·D | Event-snapshot capture; retention/expiry | Minimal metadata/snapshot only; bounded auto-expiry; privacy review (NFR-10) |
| FR-17 | Reuse existing VMS | S | [0004](adr/ADR-0004-warning-actuator-integration.md) | **F** | Real operator VMS (bench uses LED stand-in) | NFR-01 **qualified**; arbitration + latching caveat documented |
| FR-18 | Generic obstacles / wrong-way | W | [0003](adr/ADR-0003-detection-algorithm.md) | — | *Future* — not verified this phase | n/a (extensibility argument, NFR-14) |
| FR-19 | Notify emergency services | W | — | — | *Future* — not verified this phase | n/a |
| FR-20 | Config bounds enforcement | M | [0010](adr/ADR-0010-operator-override-and-manual-control.md)/[0012](adr/ADR-0012-security-and-threat-model.md) | B·S | **Out-of-bounds config** (ROI/`T_dwell=900 s`/etc.) rejected/clamped | Out-of-range parameter rejected or clamped; last-good kept; alerted |
| FR-21 | Defer OTA while warning active | S | [0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.md) | B·S | **OTA requested with track-set non-empty** | Update deferred, or blank *loud to operators* — never a silent drop |

## 2. Non-functional requirements

| ID | Requirement (short) | Governing ADR(s) | Tier | Verification scenario / test | Pass criterion |
|----|---------------------|------------------|------|------------------------------|----------------|
| NFR-01 | Stop→warn ≤ 2 s | [0004](adr/ADR-0004-warning-actuator-integration.md)/[0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.md) | B·S (LED) · **F** (VMS) | Latency measurement, LED backend | ≤ dwell + 2 s on LED; VMS backend **qualified** with its own budget |
| NFR-02 | Vehicle-gone→off ≤ hold + 2 s | [0008](adr/ADR-0008-detection-persistence-and-multitrack.md) | B·S | Clear-latency on confirmed exit | ≤ hold + 2 s; held occlusion is **not** a clear-latency failure |
| NFR-03 | Functional availability ≥ 99 % | [0005](adr/ADR-0005-fail-safe-and-system-safety.md) | **F** | Field measurement; bench = software-loop MTBF under fault injection | **Provisional** ≥ 99 %, **pending MTBF/MTTR budget** ([doc 04 Q6](04-risk-and-safety.md#5-open-safety-questions-for-the-team)) |
| NFR-04 | No stale-ON (any fault) | [0005](adr/ADR-0005-fail-safe-and-system-safety.md)/[0008](adr/ADR-0008-detection-persistence-and-multitrack.md)/[0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.md) | B·S | Watchdog expiry; **`T_degraded_max` forced clear**; wedged-logic | No state holds sign ON without lane-attributed confirmation; bounded clear in every case |
| NFR-05 | Rain/night robustness | [0001](adr/ADR-0001-sensing-modality.md) | **F** | Radar gate (a) bench, (b) test-track/field | **Contingent on radar gate**; not claimable from synthetic radar |
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
- **Everything tagged F carries to field-pilot acceptance** ([doc 05 §11](05-field-pilot-proposal.md#11-acceptance-kpis-field));
  nothing tagged F is a measured prototype result.
