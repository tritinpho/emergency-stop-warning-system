# 04 — Risk, Safety & Compliance

**Project:** Emergency Stop-Lane Automatic Warning System (ESW)
**Status:** Proposed
**Last updated:** 2026-06-26
**Related:** [ADR-0005 fail-safe](adr/ADR-0005-fail-safe-and-system-safety.md) · [requirements §1](01-requirements.md#1-the-safety-reframe-read-first)

Because the system advises fast-moving drivers near a stationary obstacle, risk and safety are
treated as a first-class part of the architecture, not an annex. This document holds the **risk
register**, a **failure-mode analysis (FMEA-lite)**, the **fail-safe summary**, and **privacy /
legal** obligations.

---

## 1. Risk register

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
| R10 | **Liability ambiguity** — who is responsible if a warning fails | 2 | 4 | 8 | Clear operating concept; audit log; explicit "advisory, driver-responsible" framing; operator agreement. |
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
| Decision logic wedged with sign ON | Stale-ON warning | `T_watchdog` re-confirm timer | Force re-evaluate → CLEAR if unconfirmed |
| Sign link down / sign unresponsive | Commanded warning not actually shown | Sign **status read-back** mismatch | Alert immediately; mark site degraded |
| Sign stuck ON physically | Cry wolf | Status read-back vs commanded | Alert; operator/maintenance dispatch |
| Power low (solar depletion) | Imminent shutdown | Battery telemetry threshold | Early low-power alert; graceful shutdown to SAFE STATE |
| WAN outage | No telemetry/oversight | Heartbeat gap at TMC | Safety loop continues (edge-autonomous); events queue; alert on gap |
| Clock skew between sensors | Bad fusion | Time-sync monitor | Flag; fall back to single-sensor; alert |
| Model regression after OTA | Accuracy drop | Canary metrics post-update | **Rollback** to previous signed version |

This FMEA list is also the **fault-injection test set** for acceptance (doc 01 §5 — target ≥95%
detection coverage).

## 3. Fail-safe summary

The safe behaviour is specified in [ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.md). In short:

- **Fail-safe:** on critical fault the sign goes to a **known, non-deceptive state** (default blank —
  it never asserts a hazard it cannot substantiate).
- **Fail-loud:** the unit **escalates degradation to operators**; "blind" is an alarm, never silence.
- **No stale-ON:** a **watchdog** bounds every activation; **status read-back** verifies the sign
  truly reflects the command.
- **Trust-preserving:** dwell + hysteresis prevent flapping and false triggers, keeping the warning
  credible (anti-cry-wolf).

## 4. Privacy, data & legal compliance

The proposal does not address these; for a public-road camera system they are mandatory.

| Area | Obligation | Design response |
|------|-----------|-----------------|
| **PII minimization** | Cameras capture plates/faces (personal data) | **Inference on-device**; do not upload or retain continuous raw video. |
| **Evidence retention** | Auditing a decision needs *some* evidence | Store only **minimal event snapshots/metadata**, bounded retention, access-controlled (FR-16, NFR-10). |
| **Purpose limitation** | System is for **safety warning, not enforcement** | No ticketing/identification pipeline; framing and data scope reflect this (guiding principle 2). |
| **Signage conformance** | Road signs/messages are regulated | Warning content and the sign conform to **QCVN 41** (national technical regulation on road signs & signals); message set reviewed. |
| **Road/geometric standards** | Placement & installation are regulated | Follow expressway geometric standards (e.g., **TCVN 5729**) and operator requirements; DSD-based placement (doc 01 §4). |
| **Security** | Prevent spoofed/tampered warnings | Authenticated, encrypted channels; signed firmware; physical security (NFR-09, R8). |
| **Liability / operating concept** | Clarify responsibility | Document the system as **advisory** (drivers remain responsible); maintain an **audit log**; agree roles with the operator (R10). |
| **Approvals** | Field deployment needs authority sign-off | Engage road authority/operator early; treat approvals as a field-pilot (cấp sô) prerequisite. |

> These obligations are light to honour at the university/bench stage (no public data captured), but
> the **design choices that make them easy later — on-device inference, no raw retention, audit log —
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
