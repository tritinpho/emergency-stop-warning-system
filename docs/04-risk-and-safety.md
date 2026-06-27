# 04 — Risk, Safety & Compliance

**Project:** Emergency Stop-Lane Automatic Warning System (ESW)
**Status:** Proposed
**Last updated:** 2026-06-26
**Related:** [ADR-0005 fail-safe](adr/ADR-0005-fail-safe-and-system-safety.md) · [requirements §1](01-requirements.md#1-the-safety-reframe-read-first)

Because the system advises fast-moving drivers near a stationary obstacle, risk and safety are
treated as a first-class part of the architecture, not an annex. This document holds the **limits of
protection**, the **risk register**, a **failure-mode analysis (FMEA-lite)**, the **fail-safe
summary**, and **privacy / legal** obligations.

---

## 0. Limits of protection (residual hazards)

What the system covers is the measure of what it does **not** — stating the boundary is both honest
and the main control for over-reliance (R7). The ESW does **not**:

- warn about a vehicle still **decelerating onto** the shoulder — the most dynamic, highest-energy
  moment; only a *confirmed-stopped* vehicle (≥ dwell) raises a warning;
- protect **between** monitored zones — coverage is discrete high-value zones, not a whole corridor
  ([doc 02 §6](02-system-architecture.md#6-coverage-model));
- compel any driver to act — it is **advisory**; a driver who ignores the sign is unprotected;
- detect causes, dispatch help, or control any vehicle (explicit non-goals,
  [doc 00 §2](00-context-and-glossary.md#2-goal--non-goals));
- guarantee detection beyond the validated envelope (e.g. night/adverse before the
  [ADR-0001](adr/ADR-0001-sensing-modality.md) radar gate passes — designed, not yet proven).

Every item is a deliberate scope boundary, carried into the operating concept and the over-reliance
mitigation (R7), and revisited at the field pilot.

---

## 1. Risk register

**Safety hazards vs. project risks.** The exposure-scored register below intentionally holds both. For
a safety-related system the *safety hazards* — the ways the system can contribute to harm on the road —
deserve their own line of sight, so they are isolated here first and traced to the controlling
requirement/ADR. This is a **hazard-log skeleton**; a full hazard analysis is a cấp sở deliverable
([doc 05 §3](05-field-pilot-proposal.md#3-objectives)).

| Hazard (road harm) | Principal cause | Primary control | Residual after control | Traced to |
|--------------------|-----------------|-----------------|------------------------|-----------|
| **H-A** Rear-end / secondary collision with a stopped vehicle — following traffic not warned in time | Silent miss (blind sensor, occlusion, crash) **or** warning placed too close | Multi-sensor + health monitor + dead-man's safe-state; DSD placement | Benign-condition misses; gaps between zones; the dwell window before confirmation | R1, R4, R5, R12; ADR-[0001](adr/ADR-0001-sensing-modality.md)/[0005](adr/ADR-0005-fail-safe-and-system-safety.md)/[0008](adr/ADR-0008-detection-persistence-and-multitrack.md); [doc 01 §4](01-requirements.md#4-warning-placement--the-math-the-proposal-omits) |
| **H-B** Unnecessary hard braking / swerve from a false or stale warning | False activation or stale-ON ("cry wolf") | Dwell + hysteresis + ROI gating + radar cross-check; watchdog + status read-back | Residual false-alarm rate (operator-calibrated) | R2, R3; [ADR-0008](adr/ADR-0008-detection-persistence-and-multitrack.md); [doc 01 §5](01-requirements.md#5-evaluation-metrics--acceptance-criteria) |
| **H-C** Pedestrian on the shoulder struck | Person not detected (especially at night) | Person class in detector; warn on in/beside-ROI person | Night pedestrian detection is best-effort (doc 01 §5) | FR-08; [ADR-0003](adr/ADR-0003-detection-algorithm.md) |
| **H-D** Over-reliance — drivers stop scanning, trusting the system | Trust mis-calibrated to actual coverage | Frame as an aid; bounded-protection statement (§0); consistent behaviour | Behavioural; cannot be fully engineered out | R7; [doc 01 §1](01-requirements.md#1-the-safety-reframe-read-this-first) |

The exposure-scored register then covers **all** risks (safety + project + operational) for planning.

Likelihood (L) and Impact (I): 1 = low, 5 = high. Exposure = L × I.

| ID | Risk | L | I | Exp | Mitigation |
|----|------|--:|--:|----:|-----------|
| R1 | **Silent miss** — stopped vehicle not detected; no warning shown | 3 | 5 | 15 | Multi-sensor fusion ([ADR-0001](adr/ADR-0001-sensing-modality.md)); health monitor; measured recall targets (doc 01 §5). |
| R2 | **Cry wolf** — repeated false activations erode driver trust | 3 | 4 | 12 | Dwell + hysteresis + ROI gating + radar cross-check; false-alarm-rate target; trust-calibration review. |
| R3 | **Stale-ON** — warning stuck on after the vehicle left | 2 | 4 | 8 | Watchdog bounds activation (NFR-04); sign status read-back; hysteresis with bounded hold. |
| R4 | **Warning placed too close** — too late for drivers to act | 3 | 5 | 15 | **DSD-based placement requirement** (doc 01 §4); per-site siting study; repeater signs (PL-04). |
| R5 | **Adverse-condition blindness** — night/rain/fog defeats the camera | 4 | 4 | 16 | Radar (+ optional thermal); condition-specific acceptance tests; degraded-mode alerting. |
| R6 | **Power/connectivity loss** in the field | 3 | 3 | 9 | Solar+battery ≥72 h; edge autonomy ([ADR-0002](adr/ADR-0002-edge-vs-cloud-processing.md)); store-and-forward; heartbeat alarms. |
| R7 | **Driver over-reliance / complacency** — drivers stop scanning, trusting the system | 3 | 4 | 12 | Frame as an *aid*, not a guarantee; consistent, credible behaviour; do not promise full coverage. |
| R8 | **Spoofing / tampering** — sign forced to show false messages | 2 | 4 | 8 | Authenticated, encrypted control; signed firmware; physical security; status read-back (NFR-09). |
| R9 | **Privacy / legal** — PII capture (plates, faces) and retention | 3 | 3 | 9 | On-device inference; **no raw-video retention**; minimized event evidence; access control (§4). |
| R10 | **Liability of reliance** — a deployed-but-fallible safety system may *raise* operator exposure vs. having none (reliance is created), plus ambiguity over who is responsible if a warning fails | 2 | 4 | 8 | Clear operating concept; audit log proving spec-conformant behaviour; explicit "advisory, driver-responsible" framing; **operator agreement that explicitly addresses the reliance question**; bounded-protection statement (§0). |
| R11 | **Budget overrun / over-scope** — trying to field-deploy on a prototype grant | 4 | 3 | 12 | Scoped MVP and budget envelope ([doc 03](03-roadmap-and-phasing.md)); field pilot deferred to cấp sở. |
| R12 | **Occlusion** — passing trucks hide the stopped vehicle | 3 | 3 | 9 | Hysteresis hold absorbs brief occlusion; radar (different geometry); sensor placement/height. |
| R13 | **False object classes** — debris/shadows/animals trigger or confuse | 2 | 3 | 6 | Learned detector with classes; ROI gating; dwell; radar corroboration. |

**Top exposures to design against first:** R5 (adverse-condition blindness), R1 (silent miss), R4
(placement too close) — all three are addressed by load-bearing decisions already taken (ADR-0001,
ADR-0005, doc 01 §4).

## 2. FMEA-lite (failure mode → effect → detection → response)

| Failure mode | Effect | How detected | System response |
|--------------|--------|--------------|-----------------|
| Camera dead / frozen frames | Loss of visual detection | Frame-staleness watchdog; per-sensor health check | If radar still healthy → degraded run + alert; else SAFE STATE + alert |
| Radar dead | Loss of weather-robust confirmation | Sensor heartbeat | Camera-only degraded + alert (flag night/weather risk) |
| Perception process crash | No detections produced | Process supervisor / watchdog heartbeat | Auto-restart; if repeated → SAFE STATE + alert |
| **State-machine process dead / wedged** | Warning cannot be updated or cleared by the logic | Loss of the SM **assertion heartbeat** at the actuator; supervisor | **Dead-man's switch**: actuator auto-blanks; health monitor forces safe state **independently of the SM** (ADR-0005) |
| Decision logic wedged with sign ON | Stale-ON warning | `T_watchdog` re-confirm timer | Force re-evaluate → CLEAR if unconfirmed |
| Sign link down / sign unresponsive | Commanded warning not actually shown | Sign **status read-back** mismatch | Alert immediately; mark site degraded |
| Sign stuck ON physically | Cry wolf | Status read-back vs commanded | Alert; operator/maintenance dispatch |
| Power low (solar depletion) | Imminent shutdown | Battery telemetry threshold | Early low-power alert; graceful shutdown to SAFE STATE |
| WAN outage | No telemetry/oversight | Heartbeat gap at TMC | Safety loop continues (edge-autonomous); events queue; alert on gap |
| Clock skew between sensors | Bad fusion | Time-sync monitor | Flag; fall back to single-sensor; alert |
| Model regression after OTA | Accuracy drop | Canary metrics post-update | **Rollback** to previous signed version |

This FMEA list is also the **fault-injection test set** for acceptance (doc 01 §5 — target ≥95%
detection coverage). **Caveat:** that target verifies the detectors you *built* against the faults you
*enumerated*; it does not bound *unenumerated* faults. Treat 95% as coverage-of-known-modes and keep
adding modes as they surface — the faults you did not think of are the ones that matter most.

## 3. Fail-safe summary

The safe behaviour is specified in [ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.md). In short:

- **Fail-safe:** on critical fault the sign goes to a **known, non-deceptive state** (default blank —
  it never asserts a hazard it cannot substantiate).
- **Fail-loud:** the unit **escalates degradation to operators**; "blind" is an alarm, never silence.
- **No stale-ON:** a **watchdog** bounds every activation; **status read-back** verifies the sign
  truly reflects the command.
- **Independent safe-state:** an actuator **dead-man's switch** plus a health-monitor force-safe path
  blank the sign even if the state machine crashes — the safe state never depends on the component
  being supervised ([ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.md)).
- **Trust-preserving:** dwell + hysteresis prevent flapping and false triggers, keeping the warning
  credible (anti-cry-wolf).

## 4. Privacy, data & legal compliance

The proposal does not address these; for a public-road camera system they are mandatory.

| Area | Obligation | Design response |
|------|-----------|-----------------|
| **PII minimization** | Cameras capture plates/faces (personal data) | **Inference on-device**; do not upload or retain continuous raw video. |
| **Evidence retention** | Auditing a decision needs *some* evidence | Store only **minimal event snapshots/metadata**, bounded retention, access-controlled (FR-16, NFR-10). |
| **Miss auditability** | Auditing the *dominant* hazard — a silent **miss** — needs evidence of periods the system did **not** fire, yet raw retention is barred | A short, access-controlled, **auto-expiring rolling buffer** (seconds–minutes) released only on a flagged near-miss/incident, plus cross-checking against operator CCTV/incident logs; **never** long-term raw storage. Settle the exact window with the privacy policy (open question 4). |
| **Purpose limitation** | System is for **safety warning, not enforcement** | No ticketing/identification pipeline; framing and data scope reflect this (guiding principle 2). |
| **Signage conformance** | Road signs/messages are regulated | Warning content and the sign conform to **QCVN 41** (national technical regulation on road signs & signals); message set reviewed. |
| **Road/geometric standards** | Placement & installation are regulated | Follow expressway geometric standards (e.g., **TCVN 5729**) and operator requirements; DSD-based placement (doc 01 §4). |
| **Security** | Prevent spoofed/tampered warnings | Authenticated, encrypted channels; signed firmware; physical security (NFR-09, R8). |
| **Liability / operating concept** | Clarify responsibility | Document the system as **advisory** (drivers remain responsible); maintain an **audit log**; agree roles with the operator; **explicitly address whether deploying a fallible detector raises operator exposure vs. none** — the operator's counsel will ask, so surface it at the cấp sở stage (R10). |
| **Approvals** | Field deployment needs authority sign-off | Engage road authority/operator early; treat approvals as a field-pilot (cấp sô) prerequisite. |

> These obligations are light to honour at the university/bench stage (little public data captured) —
> but note the detector's training/evaluation **data plan** ([ADR-0007](adr/ADR-0007-validation-and-data-strategy.md))
> can itself involve roadside clips, so the same minimization rules apply **from day one**. The
> **design choices that make compliance easy later — on-device inference, no raw retention, audit log —
> must be made now**, which is why they are baked into the requirements and architecture rather than
> bolted on at field time.

## 5. Open safety questions for the team

1. What is the **acceptable false-alarm rate** with the operator before drivers begin to distrust the
   sign? (Calibrate R2's target with the operator.)
2. For sites where DSD placement is infeasible, is a **repeater sign** acceptable, or is the site
   simply excluded? (PL-04.)
3. Should a degraded unit ever show a **per-site standing caution** (ADR-0005 Option C), and under
   what governance?
4. What **retention period and access policy** for event evidence satisfies both audit needs and
   privacy duty?
