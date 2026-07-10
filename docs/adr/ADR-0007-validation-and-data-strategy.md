# ADR-0007: Validation & data strategy — what simulation proves, and where the data comes from

**Status:** Accepted (software side) — 2026-06-27
**Date:** 2026-06-27
**Deciders:** PI (ThS. Phó Trí Tín), technical lead, CV engineer

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

The funded (cấp trường) deliverable is a **bench rig + simulation**, not a field deployment
([doc 03](../03-roadmap-and-phasing.md)). That makes *"how do we validate a safety claim without a
road?"* a load-bearing decision in its own right — yet the first cut of the docs assumed simulation
results were self-evidently meaningful and left the detector's **training/evaluation data**
unaddressed. Both gaps decide whether the final report can defend its claims.

Two coupled questions:

1. **What can the bench/sim actually prove, and what must be deferred to the field pilot?** A
   simulator and a lab rig can exercise logic and timing exhaustively but cannot reproduce real rain,
   glare, fog, or radar clutter.
2. **Where does representative data come from?** The perception choice
   ([ADR-0003](ADR-0003-detection-algorithm.md)) needs day/night/rain clips of Vietnamese expressway
   shoulders to tune and evaluate — and acquiring roadside video triggers the same privacy duties
   ([doc 04 §4](../04-risk-and-safety.md#4-privacy-data--legal-compliance)) at the **prototype**
   stage, not just in the field.

Forces: claim honesty (the project's stated value), simulation fidelity vs. effort, data availability
and privacy, and a clean hand-off to the cấp sở pilot.

## Decision

Adopt a **two-tier validation split with explicit provability boundaries**, plus a **tiered data
plan**:

**Validation tiers.**
- **Simulation** validates the *logic*: the state machine, dwell/hysteresis/occlusion/multi-track
  policy ([ADR-0008](ADR-0008-detection-persistence-and-multitrack.md)), and **fault-injection
  coverage** against the scenario catalogue.
- **Bench rig** validates *perception + actuation*: a real camera (**camera-only — radar was not funded**,
  [ADR-0001](ADR-0001-sensing-modality.md) Rejected 2026-07-10) driving the real loop to a stand-in sign on
  staged physical scenarios.

**Provability boundary (state it in the report).** Bench/sim may claim: logic correctness,
timing/latency, fault handling, and false-trigger resistance to *modelled* nuisances. They may **not**
claim: real-world recall in rain/glare/fog, the real false-alarm rate, real radar clutter performance,
or the **real-world soundness of the radar-corroborated occlusion hold** — these are **field-deferred**
to the cấp sở pilot ([doc 05](../05-field-pilot-proposal.md)).

**The occlusion-hold caveat is sharper than "deferred recall."** Simulation validates the *policy* of
[ADR-0008](ADR-0008-detection-persistence-and-multitrack.md) /
[ADR-0009 §C](ADR-0009-failsafe-placement-and-degraded-modes.md) **given the correct sensor semantics it
is fed** — but the policy's *safety* depends on real radar resolving the shoulder from the through lane
at the monitored range (criterion (b) of the [ADR-0001](ADR-0001-sensing-modality.md) gate), which a
few-metre bench **cannot reproduce** (it is an angular problem — see ADR-0001) and which is
test-track/field-deferred. So the report may say the occlusion / `CAMERA_OCCLUDED_DEGRADED` logic is
*correct as specified*, **not** that it is *sound in the field*; if (b) is weak the same logic inverts a
silent miss into a **stale-ON** ([doc 04 R12/R14](../04-risk-and-safety.md#1-risk-register)).

**Synthetic sensor channels** are permitted but must use a **documented, conservative sensor model**
with stated assumptions; a synthetic radar that *assumes* perfect stationary-vehicle detection cannot
be used to evidence adverse-condition recall (see [ADR-0001](ADR-0001-sensing-modality.md) and the
[doc 01 §5](../01-requirements.md#5-evaluation-metrics--acceptance-criteria) acceptance split).

**Data plan**, in order of preference: (1) public ITS/traffic datasets; (2) operator-provided
historical CCTV under a data agreement; (3) a small, purpose-limited, **consented** local capture only
if (1)–(2) are insufficient — under the data-minimization rules from day one (on-device handling,
bounded retention, access control). Data acquisition is an explicit Phase-1/Phase-3 task with
permission and privacy steps, **not** a free input.

**Pass criteria (simulation).** The closed loop meets the doc-01 §5 *prototype-column* targets across
the full scenario catalogue, fault-injection catches ≥ 95 % of the FMEA list
([doc 04 §2](../04-risk-and-safety.md#2-fmea-lite-failure-mode--effect--detection--response)), and
**no injected fault yields a deceptive or stuck output**.

## Options Considered

### Option A: "Validate in simulation" left undefined *(the first-cut gap)*
**Pros:** least planning now.
**Cons:** no pass criteria, no provability boundary, no data source — invites a final report that
claims more than it tested. Unacceptable for a safety-related system.

### Option B: Two-tier split with explicit provability boundary + tiered data plan *(chosen)*
**Pros:** honest, defensible claims; sets up the field pilot cleanly; forces the data/privacy work to
surface early, where it is cheap and no public data is yet at stake.
**Cons:** more upfront methodology; must build a credible synthetic sensor model and document its
caveats; data acquisition becomes a tracked dependency.

### Option C: Attempt field-representative validation now
**Pros:** stronger claims if it worked.
**Cons:** impossible inside the 20M VND / bench scope; would over-promise and under-deliver. This
**is** the cấp sở project, not this one.

## Trade-off Analysis

The project's credibility rests on claiming exactly what it proved — no more. Option A's silence is how
good prototypes end up with indefensible final reports. Option B costs some methodology writing and a
documented sensor model, and in return every claim in the final report carries a clear *"validated by
sim / bench / deferred to field"* label, and the data-privacy work lands at the prototype stage where
it is cheap. It also gives [ADR-0001](ADR-0001-sensing-modality.md)'s radar-robustness claim and
[ADR-0008](ADR-0008-detection-persistence-and-multitrack.md)'s occlusion-hold a concrete validation
target rather than an assumption.

## Consequences

- **Easier:** an honest, reviewer-proof acceptance story; a clean cấp sở hand-off; early, cheap
  privacy compliance.
- **Harder:** must author the simulation methodology and a documented synthetic sensor model; data
  acquisition (with permissions) becomes a real task; some headline claims are explicitly deferred,
  which must be communicated as a **strength** (scope honesty), not a shortfall.
- **Revisit when:** the field pilot supplies real data and real performance, at which point the
  deferred claims get measured for real.

## Action Items

1. [ ] Write the **simulation methodology** — scenario catalogue, synthetic sensor model + assumptions (noise / dropout / occlusion behaviour), ground-truth labeling rule, and pass criteria — and **freeze it as a Phase-2 artifact**, not a Phase-3 by-product: it is the basis every Phase-3 logic claim rests on, so it must be settled *before* the loop is built ([doc 03 §3](../03-roadmap-and-phasing.md#3-phase-plan-aligned-to-the-proposals-6-phases)). **Drafted as [doc 07 — Simulation & Validation Methodology](../07-simulation-methodology.md).**
2. [ ] Tag every doc-01 requirement and §5 metric as **bench / sim / field-deferred** (feeds the requirement-verifiability pass).
3. [ ] Stand up the **data plan**: identify public datasets; open an operator-CCTV data-agreement conversation; define a consented local-capture protocol with retention/access limits as a fallback.
3a. [ ] **Size the acceptance-evidence generation** as a Phase-1 deliverable: the [§5](../01-requirements.md#5-evaluation-metrics--acceptance-criteria) recall N must be **real captures** (synthetic N does not count toward recall) and the false-activation per-hour rate needs **continuous bench-hours** — so set the target positive-event count (e.g. ≥ 200, incl. night) and a staging-and-capture protocol that can reach the Wilson bound. **It is now funded by the ~6–8M released when the radar was rejected** ([doc 03 §1](../03-roadmap-and-phasing.md#1-scope--budget-reality-check-read-first)) — this is the deliverable that money buys instead. Public datasets are sparse in shoulder-stop positives, so most real positives will be **staged**; plan the logistics now, not at Phase 5.
4. [ ] Ensure the synthetic radar model's assumptions are **conservative** and that adverse-condition claims are gated on real-radar evidence ([ADR-0001](ADR-0001-sensing-modality.md)).
5. [ ] Record the radar gate's **venue split** — (a) stationary-in-clutter is bench/Phase-3; (b) lane/azimuth discrimination at the monitored range is test-track/field — and label the occlusion-hold / `CAMERA_OCCLUDED_DEGRADED` guarantees **designed (logic-validated), not field-sound**, until (b) passes.
