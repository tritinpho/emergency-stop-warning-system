# 09 — Software → Hardware Requirements & Interface Handoff

**Project:** Emergency Stop-Lane Automatic Warning System (ESW)
**Status:** Proposed / Draft — handoff from the **software team** (ThS. Phó Trí Tín) to the **hardware/firmware** and **ops/business** teams
**Last updated:** 2026-06-27
**Related:** [08 ICD](08-interface-control-document.md) · [02 architecture](02-system-architecture.md) · [ADR-0001](adr/ADR-0001-sensing-modality.md) · [ADR-0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.md) · [ADR-0012](adr/ADR-0012-security-and-threat-model.md)

**Purpose.** The software design is frozen enough to build (docs [02](02-system-architecture.md)/[07](07-simulation-methodology.md)/[08](08-interface-control-document.md); the software-owned ADRs are accepted). This page is the **one-stop list of what software needs from the hardware/firmware team** — and the **cross-team decisions** that gate the still-*Proposed* ADRs. Each requirement below is a place where a component choice **silently makes or breaks a software safety guarantee**, so meet it or flag it back **before procurement**. The full message schemas live in the [ICD (doc 08)](08-interface-control-document.md).

---

## 1. Hardware/firmware requirements the software safety design depends on

| ID | What software needs | Source | If unmet → software consequence | How it's verified |
|----|---------------------|--------|---------------------------------|-------------------|
| **RQ-H1** | **Radar that detects a *stationary* vehicle in roadside clutter (a) _and_ resolves shoulder vs. adjacent through-lane at the monitored range (b)** — an imaging / HRR FMCW eval module, **not** a generic presence unit. | [ADR-0001](adr/ADR-0001-sensing-modality.md) | The occlusion-hold and `CAMERA_OCCLUDED_DEGRADED` logic **invert to stale-ON** (R12); night/adverse recall becomes unprovable → **field-deferred**. | Phase-1 radar spike; Phase-3 gate (a)+(b) |
| **RQ-H2** | **Sign controller = a *smart endpoint*:** it must **blank the sign** if no fresh, **authenticated** `SHOW` arrives within `T_signhold`, and honor the refreshed-`SHOW` heartbeat (IF-4). | [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.md), [ADR-0012](adr/ADR-0012-security-and-threat-model.md) | The **dead-man's switch cannot work** — a latching sign strands a stale-ON when the box/link dies. (A latching VMS forces the weaker watchdog+CLEAR fallback.) | Fault-inject: box-kill / link-cut → sign blanks ≤ `T_signhold` |
| **RQ-H3** | **Camera:** global-shutter / strong WDR + **IR illumination** for night. | [ADR-0001](adr/ADR-0001-sensing-modality.md), NFR-05 | Worse night recall; more false detections feeding the loop. | Bench day/night scenario set |
| **RQ-H4** | **Edge compute** with enough TOPS to run the detector **within the NFR-01 latency budget** *and* the solar power envelope. | ADR-0002/0003/[0006](adr/ADR-0006-connectivity-and-power.md) | Stop→warn latency or the solar budget breaks. | Bench latency on the target board |
| **RQ-H5** | **Time source:** GNSS/PPS-disciplined **absolute** time + **sub-frame relative** inter-sensor sync, holding over outages. | NFR-16 | Camera↔radar fusion degrades; **audit timestamps become inadmissible** (R10 liability). | Bench sync measurement; outage hold-over (field) |
| **RQ-H6** | **Edge↔sign link** characterized for **loss / latency / energy** at the ≥ DSD distance, and able to carry an **authenticated** channel. | [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.md), IF-4 | Can't safely tune `T_signhold`/`T_assert_refresh` → flap (cry-wolf) or stale-ON. | Over-distance link test (field-deferred) |
| **RQ-H7** | **Power budget must include the gate-grade radar draw** (higher than a generic presence unit). | [ADR-0006](adr/ADR-0006-connectivity-and-power.md), [ADR-0001](adr/ADR-0001-sensing-modality.md) | Solar ≥ 72 h autonomy (NFR-07) missed. | Energy budget recomputed after radar selection |

> The single highest-stakes pair is **RQ-H1** (radar capability) and **RQ-H2** (smart sign controller): both are the foundation of the system's core safety guarantees, and both are **hardware choices**, not software ones.

---

## 2. Interfaces frozen *jointly* (software proposes, hardware co-signs)

Software has unilaterally frozen the **internal** interfaces — **IF-2** (perception → state machine) and **IF-3** (state machine ↔ actuator abstraction). The following are **shared** and must be agreed with hardware before they're frozen; schemas are in the [ICD (doc 08)](08-interface-control-document.md):

- **IF-1** — sensor drivers (camera frames, radar returns) with timestamps.
- **IF-4** — edge → sign-controller **refreshed-`SHOW` + authentication** (the safety-critical link; RQ-H2/H6).
- **Time distribution** (RQ-H5).

---

## 3. What software provides ↔ what it needs back

- **Software provides:** the `SHOW / CLEAR / STATUS` and refreshed-`SHOW` contracts (IF-3/IF-4); config / OTA / override semantics with on-unit bounds enforcement; the heartbeat and event schemas.
- **Software needs back from hardware:** sign **status read-back** (commanded-vs-actual lamp state); **per-sensor health** signals (frame-staleness, radar liveness); **battery/power telemetry** thresholds; and the **measured loss/latency** of the edge↔sign link.

---

## 4. Cross-team decisions that gate the still-*Proposed* ADRs

These ADRs stay **Proposed** until the owning team signs off (software-side review is done):

| ADR | Decision the owning team must make | Owner |
|-----|------------------------------------|-------|
| [ADR-0001](adr/ADR-0001-sensing-modality.md) | Radar module selection **+ the budget reshape** (~6–8M gate-grade vs. generic) | **Hardware + business** |
| [ADR-0004](adr/ADR-0004-warning-actuator-integration.md) | Sign backend (own LED vs. operator VMS) **+ the QCVN-41 message set** | **Hardware + ops/regulator** |
| [ADR-0006](adr/ADR-0006-connectivity-and-power.md) | Power (solar/battery sizing), connectivity, IP65 enclosure | **Hardware** |
| [ADR-0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.md) | Sign-controller-as-smart-endpoint placement (**RQ-H2**) | **Hardware/firmware** |
| [ADR-0011](adr/ADR-0011-operator-concept-and-alarm-management.md) | Operator ConOps: staffing, response times, the operator agreement | **Ops/business** |
| [ADR-0012](adr/ADR-0012-security-and-threat-model.md) | Physical security + fleet key management (the **software auth** is already specified) | **Hardware/ops** |

> **Software-owned ADRs accepted 2026-06-27:** [0002](adr/ADR-0002-edge-vs-cloud-processing.md), [0003](adr/ADR-0003-detection-algorithm.md), [0005](adr/ADR-0005-fail-safe-and-system-safety.md), [0007](adr/ADR-0007-validation-and-data-strategy.md), [0008](adr/ADR-0008-detection-persistence-and-multitrack.md), [0010](adr/ADR-0010-operator-override-and-manual-control.md) (mechanism), [0013](adr/ADR-0013-degraded-hold-unification.md).

---

## 5. Two items for the business/ops team (not software, but software needs the answer)

- **SXTN scope (R19) — confirm with the funder first.** Is the cấp-trường deliverable a **principle prototype** (what all these docs assume) or a contractually-expected **trial-production unit**? It changes what everyone builds.
- **Procurement lead time.** The mmWave eval kit is **8–12 weeks** out; ordering it gates the RQ-H1 spike and the whole night/adverse claim — order at project start.
