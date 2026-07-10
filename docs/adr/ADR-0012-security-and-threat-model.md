# ADR-0012: Security posture & consolidated threat model

**Status:** Proposed
**Date:** 2026-06-27
**Deciders:** PI (ThS. Phó Trí Tín), technical lead, road-safety advisor, expressway operator liaison

> ## ⚠ PHASE NOTE — this build is CAMERA-ONLY
>
> [ADR-0001](ADR-0001-sensing-modality.md) (camera + radar fusion) was **Rejected on 2026-07-10**. The cấp trường bench
> prototype ships **camera-only**. Every radar-dependent behaviour described below — radar
> corroboration, the occlusion hold (`WARN_HOLD` / `CAMERA_OCCLUDED_DEGRADED`), `T_degraded_max`, and
> the `FULL` / `RADAR-ONLY` sensing modes — is **dormant: the code retains it, but it never executes**,
> because `corr` is never true without a radar channel.
>
> Accepted consequences: **R5** (night/rain/fog blindness) is **unmitigated** and night/adverse recall
> is **not claimed**; **R20** — an occluded vehicle is cleared at `T_hold` (~10 s), blanking the sign
> with the hazard present; **R21** — the unit sits permanently in `CAMERA_ONLY`, hence permanently
> `DEGRADED`. See [doc 04](../04-risk-and-safety.md).
>
> Radar content below is the **cấp sở** target design, not this phase's build.

## Context

NFR-09 makes a **hard claim** — *"sign activation cannot be spoofed by an outside party"* — and several
later decisions quietly **widened the attack surface** without a single place to reason about it:

- the **sign-link refreshed-`SHOW` heartbeat** is now safety-load-bearing
  ([ADR-0009 §A](ADR-0009-failsafe-placement-and-degraded-modes.md)) — a forged/replayed `SHOW` is a
  spoofed warning, a **jammed** heartbeat forces a *blank* (fail-safe, but a **denial-of-warning**);
- **operator override** is an authenticated remote command that can suppress or assert the sign
  ([ADR-0010](ADR-0010-operator-override-and-manual-control.md)) — a spoofed force-off is a
  denial-of-warning, a spoofed force-on is cry-wolf;
- **config (FR-20) and OTA (FR-21)** can break the safety function remotely; signing stops *tampering*,
  not operator *error*;
- **sensor denial** is unique to this system class — **radar jamming**, **camera blinding / IR-flood** —
  produces a silent miss with no packet ever forged.

Security was parked in an **open question** ([doc 04 §5 Q5](../04-risk-and-safety.md#5-open-safety-questions-for-the-team))
while every *other* load-bearing concern earned an ADR. That is the wrong shape: NFR-09's claim has no
stated scope, so it is either over-broad (indefensible) or undefined. This ADR gives security a home,
**scopes the NFR-09 claim to an enumerated surface**, and stages the depth of hardening against the
project's phases — full hardening is a field/productisation task, but the *analysis* and the
**cheap-now, expensive-later** controls (auth on the sign link, signed config/OTA, audit) belong at the
prototype stage.

Forces: claim honesty (NFR-09 must mean something specific), the safety cost of each surface (a spoofed
or jammed warning is a road hazard, not just a data breach), the edge-autonomous topology
([ADR-0002](ADR-0002-edge-vs-cloud-processing.md)), cost/effort at a 20M VND prototype, and a clean
hand-off to the cấp sở pilot.

## Decision

Adopt a **consolidated, phase-staged threat model** as the home for NFR-09 and the security-relevant
rows of [doc 04](../04-risk-and-safety.md).

1. **Enumerate assets, actors, and surfaces.** Assets: the **sign output** (the thing that must not be
   falsely asserted or suppressed), the **detection integrity** (sensors), **config/model/calibration**,
   and the **audit log**. Actors: outside attacker, malicious/compromised insider, and a
   **non-malicious operator error** (treated as a threat to the safety function, per FR-20). Surfaces:
   the **edge↔sign refreshed-`SHOW` link**, **telemetry**, **config/OTA**, the **override channel**, and
   the **sensors** (RF + optical denial).
2. **Authenticate the safety-relevant local channel, not just telemetry.** The **sign-link
   refreshed-`SHOW` heartbeat must be authenticated** (anti-forge, anti-replay) — a control plane that
   can light a roadside sign cannot be weaker than the telemetry plane. Override rides the **same
   hardened, non-repudiable channel** as config/OTA (ADR-0010); config/OTA are **signed** with rollback.
3. **Map each surface to a control and a residual.** e.g. forged/replayed `SHOW` → authenticated,
   nonce'd assertion; **jammed heartbeat** → fail-safe blank **but** a stated denial-of-warning residual
   (detected as a heartbeat gap → operator alarm, ADR-0011); **radar jam / camera blind** → per-sensor
   health + the degraded-mode escalation ([ADR-0009 §B](ADR-0009-failsafe-placement-and-degraded-modes.md))
   make denial **loud**, never silent; **bad config** → unit-side bounds (FR-20) + canary + signed
   rollback.
4. **Scope the NFR-09 claim to the analysis actually done.** "Cannot be spoofed" is rewritten as
   *"sign assertion is authenticated against forge/replay on the enumerated surfaces; sensor- and
   link-**denial** are mitigated to fail-safe-blank-and-alarm, not prevented"* — an honest claim with a
   boundary, not a slogan.
5. **Stage the depth.** Prototype stage: the threat-model **document**, sign-link + override + telemetry
   **authentication**, signed config/OTA, and the audit log — the controls that are **cheap now and
   expensive to retrofit**. Field/productisation stage: penetration testing, key-management at fleet
   scale, anti-jam/anti-blind hardening, physical security — explicitly **field-deferred**, with the
   prototype scoping its claim accordingly ([ADR-0007](ADR-0007-validation-and-data-strategy.md)).

## Options Considered

### Option A: Leave it as open-question Q5 *(the first-cut state)*
| Dimension | Assessment |
|-----------|------------|
| Effort now | **None** |
| NFR-09 integrity | **Undefined** — a hard claim with no scope |
| Surface coverage | Scattered across R8 / R16 / ADR-0009 / ADR-0010 with no single view |

**Pros:** nothing to write now.
**Cons:** the safety-relevant *spoof/jam* surfaces (sign link, override, sensors) have no consolidated
analysis, and NFR-09 is unfalsifiable. Unacceptable for a system whose output is a roadside safety
signal.

### Option B: Consolidated, phase-staged threat-model ADR *(chosen)*
| Dimension | Assessment |
|-----------|------------|
| Effort now | Medium (enumerate surfaces + controls; authenticate the sign link; document) |
| NFR-09 integrity | **Scoped** — claim bounded to an enumerated surface |
| Surface coverage | **Single view** — sign link, override, config/OTA, sensor denial, audit |

**Pros:** NFR-09 means something specific; the cheap-now controls land at the prototype stage where they
are cheap; a clean hand-off of the deferred hardening to the pilot.
**Cons:** more upfront analysis; some controls (key management, anti-jam) are explicitly deferred and
must be communicated as **scoped**, not done.

### Option C: Full security hardening / certification now
| Dimension | Assessment |
|-----------|------------|
| Effort | **High** — pen-testing, fleet key management, anti-jam RF work |
| Fit to scope | Out of budget/scope for a 20M VND bench prototype |

**Pros:** strongest possible posture.
**Cons:** this **is** the cấp sở / productisation security workstream, not the prototype's; attempting it
now over-promises. Rejected for this phase, retained as the field target.

## Trade-off Analysis

The decisive point is that for this system a security failure is a **road-safety failure**: a spoofed
`SHOW` is a phantom hazard, a jammed heartbeat or blinded sensor is a denial-of-warning. So the surfaces
that matter are the **safety-relevant** ones (sign link, override, sensors), and the right move is not
maximal hardening (C, over budget) nor silence (A, indefensible) but a **scoped model (B)** that
authenticates the channel that lights the sign, makes sensor/link denial **loud** via the degraded-mode
and heartbeat machinery already built, and **states the boundary** of the claim. The cheap-now controls
(sign-link auth, signed config/OTA, audit) are exactly the ones expensive to retrofit, so they belong at
the prototype stage; the rest is honestly deferred.

## Consequences

- **Easier:** NFR-09 becomes a scoped, defensible claim; the spoof/jam surfaces have one analysis;
  the audit log (R10) and signed config/OTA (R16) gain a security rationale; clean cấp sở hand-off.
- **Harder:** authentication on the **local sign link** (not just telemetry) to design and key-manage at
  bench scale; a threat-model document to maintain as surfaces change; deferred items (pen-test,
  anti-jam, fleet keys) must be tracked, not forgotten.
- **Revisit when:** the field pilot adds real keys/fleet scale, an operator mandates a specific security
  profile, or a new surface appears (e.g. a V2X backend — [ADR-0004](ADR-0004-warning-actuator-integration.md)).

## Action Items

1. [ ] Write the **threat-model document**: assets, actors (incl. operator error), surfaces, per-surface
       control + residual; supersede open-question [doc 04 §5 Q5](../04-risk-and-safety.md#5-open-safety-questions-for-the-team).
2. [ ] Specify and implement **authentication for the sign-link refreshed-`SHOW` heartbeat**
       (anti-forge, anti-replay) — extends [ADR-0009 §A](ADR-0009-failsafe-placement-and-degraded-modes.md) AI#1.
3. [ ] Put **override on the same hardened channel** as config/OTA; sign config/OTA with rollback
       (folds [ADR-0010](ADR-0010-operator-override-and-manual-control.md) AI#5, R16).
4. [ ] **Rewrite NFR-09** to its scoped form (authenticated against forge/replay on the enumerated
       surfaces; denial mitigated to fail-safe-blank-and-alarm) in
       [doc 01 §3](../01-requirements.md#3-non-functional-requirements).
5. [ ] Add **radar-jam / camera-blind / IR-flood** and **forged/replayed/​jammed sign-link** to the FMEA +
       fault-injection set where bench-injectable; tag RF/optical-denial hardening **field-deferred**.
