# 04 — Risk, Safety & Compliance

**Project:** Emergency Stop-Lane Automatic Warning System (ESW)
**Status:** Proposed
**Last updated:** 2026-06-26
**Related:** [ADR-0005 fail-safe](adr/ADR-0005-fail-safe-and-system-safety.md) · [ADR-0009 fail-safe placement & degraded modes](adr/ADR-0009-failsafe-placement-and-degraded-modes.md) · [requirements §1](01-requirements.md#1-the-safety-reframe-read-this-first)

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
- **assert the shoulder warning during heavy congestion / stop-and-go** — when the through lane beside
  the ROI is itself stationary, the warning is deliberately **suppressed or re-messaged** to avoid
  false-triggering into a jam ([doc 02 §4](02-system-architecture.md#4-the-detectionwarning-state-machine),
  R14). Note the sharpness: *high traffic density* is a **named** top-danger condition
  ([doc 00 §1](00-context-and-glossary.md#1-problem-statement)), so the cry-wolf mitigation opens a
  coverage gap **in exactly a high-risk condition** — carried to the operator concept and revisited with
  real congestion data at the field pilot;
- compel any driver to act — it is **advisory**; a driver who ignores the sign is unprotected;
- warn during the **confirmation window** — for ~`T_dwell + T_activate` (≈ 7 s) after a vehicle first
  stops, no warning is shown yet (the *unwarned-exposure budget*,
  [doc 01 §4](01-requirements.md#4-warning-placement--the-math-the-proposal-omits));
- reliably detect a **pedestrian at night** — a small radar cross-section with the camera at its
  weakest, so FR-08 sets only a *best-effort* night target
  ([doc 01 §5](01-requirements.md#5-evaluation-metrics--acceptance-criteria)); a person stranded on the
  shoulder in the dark is a **stated residual** (hazard H-C), not a covered case;
- detect causes, dispatch help, or control any vehicle (explicit non-goals,
  [doc 00 §2](00-context-and-glossary.md#2-goal--non-goals));
- guarantee detection beyond the validated envelope (e.g. night/adverse before the
  [ADR-0001](adr/ADR-0001-sensing-modality.md) radar gate passes — designed, not yet proven).

Every item is a deliberate scope boundary, carried into the operating concept and the over-reliance
mitigation (R7), and revisited at the field pilot.

One interaction is sharper than the rest, so state it plainly: **fail-safe-blank × over-reliance.**
When the unit fails it goes **blank** (no warning) — the right call against cry-wolf
([ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.md)) — but a driver who has *learned to rely* on
the sign is then **worse off than with no system at all** (they have stopped scanning *and* there is no
warning). The control is to **fail loud to operators** (dispatch patrols / CCTV) and to never let trust
outrun coverage (R7); the residual is behavioural and cannot be fully engineered out.

**The cumulative envelope of actual protection (state it once, plainly).** Each limit above is disclosed
separately, but their *product* is narrower than "detects stopped vehicles." The system actively protects
against a vehicle **fully stopped for ≳ `T_dwell` + `T_activate` (~7 s)**, **in free-flow (non-congested)
traffic**, **inside a monitored zone**, **in validated conditions** (day now; night/adverse only once the
[ADR-0001](adr/ADR-0001-sensing-modality.md) radar gate passes), seen by a **healthy or camera-up** unit.
Outside that envelope the system is **silent by design** — acceptable only because it is *stated* and the
operator concept (patrols / CCTV) covers the rest. This consolidated sentence is the honest headline the
per-item bullets add up to.

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
| **H-E** Braking shockwave — even a *true* warning makes dense following traffic brake/slow, risking rear-end collisions *within* the through-traffic | A correct activation in high density triggers an abrupt deceleration wave | **DSD** placement gives smooth reaction time (not an emergency stop); concise, unambiguous QCVN-41 message; (field) align with the operator's VMS practice | Residual deceleration risk in heavy flow | R2-adjacent; [doc 01 §4](01-requirements.md#4-warning-placement--the-math-the-proposal-omits) |

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
| R8 | **Spoofing / tampering** — sign forced to show false messages | 2 | 4 | 8 | Authenticated, encrypted control; signed firmware; physical security; status read-back (NFR-09); attack surface enumerated and the NFR-09 claim scoped in the consolidated threat model ([ADR-0012](adr/ADR-0012-security-and-threat-model.md)). |
| R9 | **Privacy / legal** — PII capture (plates, faces) and retention | 3 | 3 | 9 | On-device inference; **no raw-video retention**; minimized event evidence; access control (§4). |
| R10 | **Liability of reliance** — a deployed-but-fallible safety system may *raise* operator exposure vs. having none (reliance is created), plus ambiguity over who is responsible if a warning fails | 2 | 4 | 8 | Clear operating concept; audit log proving spec-conformant behaviour; explicit "advisory, driver-responsible" framing; **operator agreement that explicitly addresses the reliance question**; bounded-protection statement (§0). |
| R11 | **Budget overrun / over-scope** — trying to field-deploy on a prototype grant | 4 | 3 | 12 | Scoped MVP and budget envelope ([doc 03](03-roadmap-and-phasing.md)); field pilot deferred to cấp sở. |
| R12 | **Occlusion** — passing trucks hide the stopped vehicle | 3 | 3 | 9 | Hysteresis hold absorbs brief occlusion; radar (different geometry); sensor placement/height. **Depends on radar lane-discrimination ([ADR-0001](adr/ADR-0001-sensing-modality.md) gate b); if weak, the occlusion hold can _invert_ to a false-hold (stale-ON) on the occluding truck — field-validated, not bench-closable.** Bounded by **`T_degraded_max`**: the inverted stale-ON cannot persist indefinitely — past the bound the sign is forced to a loud clear + operator disposition ([ADR-0009 §C](adr/ADR-0009-failsafe-placement-and-degraded-modes.md), [ADR-0011](adr/ADR-0011-operator-concept-and-alarm-management.md)). |
| R13 | **False object classes** — debris/shadows/animals trigger or confuse | 2 | 3 | 6 | Learned detector with classes; ROI gating; dwell; radar corroboration. |
| R14 | **Congestion false-trigger** — stopped through-traffic beside the ROI reads as a shoulder stop; the "high density" condition is worst-case for ROI discrimination | 3 | 3 | 9 | Congestion detection (stationary tracks spanning through lanes) → suppress/re-message; ROI geometry + radar lane discrimination; explicit acceptance scenario ([doc 02 §4](02-system-architecture.md#4-the-detectionwarning-state-machine)). |
| R15 | **Calibration error / drift** — bad homography or camera↔radar extrinsics, or drift from pole sway / vibration / thermal, silently shifts the ROI → systematic miss or false alarm | 3 | 4 | 12 | Per-site calibration procedure; periodic re-check; **drift monitor** — now a **named FR-10 self-monitoring function** with a defined reference-residual-vs-tolerance spec ([doc 01 FR-10](01-requirements.md#2-functional-requirements), [doc 02 §4](02-system-architecture.md#4-the-detectionwarning-state-machine)); alert on out-of-tolerance. **Tier:** the detection *logic* is bench-verifiable (inject a synthetic homography shift); **real** drift is field-deferred, so at bench scope this control is logic-verified, not field-proven ([doc 01 §3a](01-requirements.md#3a-verification-scope--what-the-funded-benchsim-phase-can-actually-show)). |
| R16 | **Unsafe config / OTA push** — a wrong ROI/timer or a regressed model breaks the safety function remotely; signing stops *tampering*, not operator *error* | 2 | 4 | 8 | Unit-side **parameter-bounds enforcement** (FR-20); staged/validated rollout + canary metrics; **defer OTA while a warning is active** (FR-21); signed rollback (§2); config/OTA channel in the threat model ([ADR-0012](adr/ADR-0012-security-and-threat-model.md)). |
| R17 | **Operator non-response / alarm fatigue** — "fail loud" routes silent-miss, degraded-mode, override-expiry and congestion-suppression residuals to the operator, but a flooded or unstaffed TMC may not act, so the compensating control (patrol / CCTV dispatch) never fires | 3 | 4 | 12 | **Operator concept of operations + alarm management** (NFR-15, [ADR-0011](adr/ADR-0011-operator-concept-and-alarm-management.md)): dedup/prioritize alarms, severity + target response time, re-escalation on non-ack; **`T_degraded_max`** forces a machine disposition rather than waiting on the operator forever. Residual: response-time is field-tuned and staffing is the operator's commitment, surfaced in the operator agreement (R10). |
| R18 | **Stale-ON in a degraded state outliving every autonomous bound** — `CAMERA_OCCLUDED_DEGRADED` keeps the sign ON on radar alone while the watchdog is suppressed; the camera may be **occluded _or_ faulted** | 2 | 4 | 8 | **`T_degraded_max`** terminal bound → forced loud low-confidence clear + max-severity escalation; **the bound is cause-agnostic — occlusion *or* camera fault** ([ADR-0013](adr/ADR-0013-degraded-hold-unification.md)), closing the previously-unbounded RADAR-ONLY "brief hold"; NFR-04 broadened to cover sensor-discrimination stale-ON ([doc 02 §4](02-system-architecture.md#4-the-detectionwarning-state-machine), [ADR-0009 §C](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)). |
| R19 | **SXTN scope/expectation mismatch** — the declared grant type (*sản xuất thử nghiệm* / experimental-pilot-**production**) may contractually imply a *trial-production unit*, while the 20M VND envelope funds only a bench prototype; distinct from R11 (this is the **funder expecting more**, not the team over-scoping) | 2 | 4 | 8 | Resolve project-type vs. deliverable **explicitly with the funder now** ([doc 03 §1](03-roadmap-and-phasing.md#1-scope--budget-reality-check-read-first), [doc 00 glossary](00-context-and-glossary.md#7-bilingual-glossary-en--vi)): confirm the cấp-trường deliverable is a principle prototype, or raise the scope/budget mismatch **before** contract milestones bind — not at the final review. |

**Top exposures to design against first:** R5 (adverse-condition blindness), R1 (silent miss), R4
(placement too close) — all three are addressed by load-bearing decisions already taken (ADR-0001,
ADR-0005, doc 01 §4).

## 2. FMEA-lite (failure mode → effect → detection → response)

| Failure mode | Effect | How detected | System response |
|--------------|--------|--------------|-----------------|
| Camera dead / frozen frames | Loss of class + image-ROI geometry → **cannot confirm a _new_ stop**; an active warning is now camera-unverified | Frame-staleness watchdog; per-sensor health check | **RADAR-ONLY = BLIND-TO-NEW** ([ADR-0009 §B](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)): may *hold* an already-confirmed warning **only as the bounded camera-unverified hold** — `T_degraded_max` → forced loud clear, **no** re-acquire ([ADR-0013](adr/ADR-0013-degraded-hold-unification.md)) — but **cannot initiate** → **critical alert**, *not* a benign "degraded run"; both sensors down → SAFE STATE |
| Radar dead | Loss of weather-robust confirmation + occlusion hold | Sensor heartbeat | **CAMERA-ONLY**: can still *initiate* (camera class + ROI + track-speed) but loses the radar occlusion hold → degraded + alert, flag night/weather miss risk |
| Perception process crash | No detections produced | Process supervisor / watchdog heartbeat | Auto-restart; if repeated → SAFE STATE + alert |
| **State-machine process dead / wedged** | Warning cannot be updated or cleared by the logic | Loss of the SM **assertion heartbeat**; supervisor | **Dead-man's switch in the sign controller** blanks the sign on heartbeat loss; health monitor forces safe state **independently of the SM** ([ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.md), [ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.md)) |
| **Edge box dead / OS wedged / unit power loss while a warning is ON** | The edge box cannot command anything; a latched sign would stay stale-ON | Sign controller sees the **refreshed-SHOW heartbeat stop** | Sign controller **auto-blanks within `T_signhold`** (this is *why* the dead-man's switch must live downstream of the link — [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)); TMC heartbeat gap raises the alarm |
| Decision logic wedged with sign ON | Stale-ON warning | `T_watchdog` re-confirm timer | Force re-evaluate → CLEAR if unconfirmed |
| Sign link down / sign unresponsive | A new command can't reach the sign; **a warning already ON must not be left stale** | Sign **status read-back** mismatch; heartbeat loss at the sign controller | If a warning was ON, the **sign-controller dead-man's switch blanks it** on heartbeat loss (own-LED backend, [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)); a **latching VMS** can't honour this → residual stale-ON = operator command cycle (stated caveat). Alert immediately; mark degraded |
| Sign stuck ON physically | Cry wolf | Status read-back vs commanded | Alert; operator/maintenance dispatch |
| Power low (solar depletion) | Imminent shutdown | Battery telemetry threshold | Early low-power alert; graceful shutdown to SAFE STATE |
| WAN outage | No telemetry/oversight | Heartbeat gap at TMC | Safety loop continues (edge-autonomous); events queue; alert on gap |
| Clock skew between sensors | Bad fusion | Time-sync monitor | Flag; fall back to single-sensor; alert |
| Model regression after OTA | Accuracy drop | Canary metrics post-update | **Rollback** to previous signed version |
| **Bad config push** (wrong ROI / out-of-range timer) | Safety function silently broken — misses or false alarms | **Unit-side bounds check**; staged rollout; post-change canary | Reject/clamp out-of-bounds config (FR-20); alert; keep last-good; signed rollback (R16) |
| **OTA / restart while a warning is active** | A live warning dropped for the update window | Track-set non-empty at update time | **Defer** the update, or blank *loud to operators* for the window (FR-21) — never a silent drop |
| **Calibration error / drift** (homography or cam↔radar extrinsics) | ROI shifts → systematic miss or false alarm, no obvious symptom | **Drift monitor** vs. reference landmarks; periodic re-check | Alert on out-of-tolerance; re-calibrate; treat as degraded until corrected (R15) |
| **Operator force-off / mute during a real hazard** | Operator-induced silent miss | Override logged + **OVERRIDDEN** heartbeat posture; mandatory auto-expiry; TMC escalation | Bounded, fail-loud, time-limited; auto-resume on expiry ([ADR-0010](adr/ADR-0010-operator-override-and-manual-control.md)) |
| **Operator force-on left latched / spoofed override** | Stale-ON or cry-wolf; unauthorized suppression-or-assertion | Edge-mediated **refreshed (non-latching)** force-on; authenticated override channel; status read-back | Dead-man's switch still blanks on box-kill / link-cut / expiry; reject unauthenticated / out-of-policy override (ADR-0010, NFR-09) |
| **`CAMERA_OCCLUDED_DEGRADED` outlives `T_degraded_max`** (camera never re-acquires; radar may be corroborating the *occluding* through-lane vehicle, not the shoulder car) | Indefinite stale-ON the watchdog can't catch (radar corroboration suppresses it) | `T_degraded_max` timer | **Forced loud low-confidence clear + max-severity escalation**; operator owns the disposition via CCTV / patrol ([ADR-0009 §C](adr/ADR-0009-failsafe-placement-and-degraded-modes.md), [ADR-0011](adr/ADR-0011-operator-concept-and-alarm-management.md)) |
| **Operator alarm unacknowledged / alarm flood** | "Fail-loud" control ineffective — no patrol/CCTV compensation for a silent-miss or degraded state | Acknowledge-timeout; alarm-rate monitor | **Re-escalation** by severity; dedup/prioritize to bound load (NFR-15, [ADR-0011](adr/ADR-0011-operator-concept-and-alarm-management.md)) |

This FMEA list is also the **fault-injection test set** for acceptance (doc 01 §5 — target ≥95%
detection coverage). **Caveat:** that target verifies the detectors you *built* against the faults you
*enumerated*; it does not bound *unenumerated* faults. Treat 95% as coverage-of-known-modes and keep
adding modes as they surface — the faults you did not think of are the ones that matter most. **Tier the
list, too:** several modes here are **field-only** — calibration **drift** (R15, needs pole sway /
thermal), **edge-box / link death at the ≥ DSD distance** (the over-distance link,
[ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)), and **solar depletion** — so the
bench cannot inject them. Report fault-coverage as a fraction of **bench-injectable** modes and carry the
field-only ones to the pilot, or the 95% silently excludes exactly the modes that need the field to
appear.

## 3. Fail-safe summary

The safe behaviour is specified in [ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.md) and
[ADR-0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.md). In short:

- **Fail-safe:** on critical fault the sign goes to a **known, non-deceptive state** (default blank —
  it never asserts a hazard it cannot substantiate).
- **Fail-loud:** the unit **escalates degradation to operators**; "blind" is an alarm, never silence.
- **No stale-ON:** a **watchdog** bounds every activation; **status read-back** verifies the sign
  truly reflects the command.
- **Independent safe-state, downstream of the link:** the **dead-man's switch lives in the sign
  controller**, so a crashed SM, a **dead edge box**, or a **cut link** all blank the sign; a
  health-monitor force-safe path is the inner layer. The safe state is never upstream of — nor
  dependent on — the component it supervises ([ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)).
- **Honest degraded modes:** a camera-dead unit is **blind to new hazards** (radar alone cannot
  initiate a new in-ROI confirmation) and escalates as **critical** — it never advertises coverage it
  has lost ([ADR-0009 §B](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)).
- **No indefinite degraded hold:** the watchdog is deliberately suppressed by radar corroboration, so
  **`T_degraded_max`** separately bounds `CAMERA_OCCLUDED_DEGRADED` — past it the sign is forced to a
  **loud** disposition (low-confidence clear + escalation), never held ON forever on an unverifiable
  radar return ([ADR-0009 §C](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)). The bound is
  **cause-agnostic — camera occluded _or_ faulted** — so the camera-dead (RADAR-ONLY) hold, previously an
  unbounded "brief hold," is the same bounded state ([ADR-0013](adr/ADR-0013-degraded-hold-unification.md)).
- **A listener for the loud failures:** "fail loud" is only a control if someone acts on it. The
  operator response path — alarm dedup/prioritization, severities, target response times, re-escalation
  on non-ack — is a **specified requirement** (NFR-15, [ADR-0011](adr/ADR-0011-operator-concept-and-alarm-management.md)),
  not an assumption.
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
| **Security** | Prevent spoofed/tampered warnings | Authenticated, encrypted channels; signed firmware; physical security (NFR-09, R8). The "cannot be spoofed" claim is **scoped to the consolidated threat model** ([ADR-0012](adr/ADR-0012-security-and-threat-model.md)) — covering the local edge↔sign refreshed-SHOW link, the override channel (ADR-0010), config/OTA, and sensor denial (radar jam, camera blind/IR-flood); deep hardening is field-staged (§5 Q5). |
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
5. What is the **threat model** for the edge↔sign link and the sensors? **Now consolidated in
   [ADR-0012](adr/ADR-0012-security-and-threat-model.md)** — retained here as the open *completion* item.
   The "cannot be spoofed" claim (NFR-09) needs its attack surfaces enumerated — forged/replayed
   `SHOW`/`CLEAR` or a **jammed heartbeat** on the local link (note: jamming the heartbeat forces a
   *blank*, which is fail-safe but a denial-of-warning), **radar jamming**, **camera blinding /
   IR-flood**, the **override channel** (ADR-0010), and config/OTA — and the **sign-link refreshed-SHOW
   heartbeat must be authenticated**, not just the telemetry. Deep hardening is a field-stage task; scope
   the NFR-09 claim to the analysis actually done.
6. What **MTBF/MTTR reliability budget** backs the ≥ 99% functional-availability target (NFR-03)? For a
   remote single unit, one multi-day field repair (~0.5% of a year *each*) nearly exhausts the budget,
   so 99% needs an explicit MTBF given the achievable field MTTR — or it should be relaxed. State the
   budget at the field-pilot stage rather than asserting 99% unbacked.
7. **Warm-reboot re-exposure.** Should a persisted *warning-active-at-shutdown* flag shorten
   re-confirmation for a vehicle still at the same ROI position after an **unplanned reboot**
   ([doc 02 §4](02-system-architecture.md#4-the-detectionwarning-state-machine))? It trades a fresh
   unwarned-exposure window against a possible **stale-ON on a vehicle that actually departed during the
   outage** — a detailed-design decision to settle explicitly, not by default.
