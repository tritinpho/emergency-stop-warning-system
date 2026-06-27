# ADR-0009: Fail-safe actuation placement & degraded-mode semantics

**Status:** Proposed
**Date:** 2026-06-27
**Deciders:** PI (ThS. Phó Trí Tín), technical lead, road-safety advisor, field/installation engineer

## Context

[ADR-0005](ADR-0005-fail-safe-and-system-safety.md) established **fail-safe + fail-loud** and named a
**dead-man's switch** so a crashed state machine cannot leave a warning asserted.
[ADR-0008](ADR-0008-detection-persistence-and-multitrack.md) established **set-based persistence** with
a **radar-corroborated occlusion hold**. Three follow-on questions were left implicit — and each is
safety-decisive once you look at the *physical* topology and the *single-sensor-down* modes rather than
the logical block diagram.

1. **Where does the dead-man's switch physically live?** [Doc 02 §2](../02-system-architecture.md#2-logical-architecture-components--responsibilities)
   placed the "default-to-blank on loss of the SM assertion heartbeat" in the **actuator abstraction**,
   which runs on the **edge box**. But the sign is driven by a **separate sign controller** across a
   local link ([doc 02 §3](../02-system-architecture.md#3-physical--deployment-architecture)). A switch
   on the edge box protects against an SM crash *while the box is alive* — but a **dead edge box**, a
   **cut or jammed link**, or a wedged OS leaves a separate latching sign **holding its last state**.
   If that state was ON, this is exactly the **stale-ON** the design exists to prevent. A watchdog that
   lives upstream of the link cannot guarantee a downstream sign goes dark.

2. **What can the system actually do with one sensor down?** The FMEA
   ([doc 04 §2](../04-risk-and-safety.md#2-fmea-lite-failure-mode--effect--detection--response)) treated
   "camera dead → radar-only degraded run" and "radar dead → camera-only degraded run" as symmetric.
   They are **not**. Per [ADR-0001](ADR-0001-sensing-modality.md)/[ADR-0003](ADR-0003-detection-algorithm.md)/[ADR-0008](ADR-0008-detection-persistence-and-multitrack.md)
   the **camera owns classification, image-ROI geometry, and the track that dwell runs on**; radar
   *corroborates* an already-confirmed track. So **radar-only cannot _initiate_ a new in-ROI
   confirmation** — it is blind to new hazards, not merely degraded.

3. **What happens at the end of the occlusion hold while radar still sees the vehicle?** ADR-0008 holds
   a lost track "up to `T_occlusion` (60 s)" but never said what happens at 60 s **while radar still
   corroborates**. Clearing then would manufacture the silent miss ADR-0008 was written to prevent.

Forces: silent-miss avoidance (dominant), stale-ON avoidance, the physical edge↔sign topology,
third-party VMS latching behaviour, edge-compute simplicity, and testability (every claim here must be
provable by fault injection).

## Decision

### A. The dead-man's switch lives in the sign controller, downstream of the link

The warning is asserted by a **continuously refreshed SHOW heartbeat, not a latching command**:

- the edge box refreshes an **authenticated SHOW assertion** to the sign controller every
  `T_assert_refresh` (default **0.5 s**);
- the **sign controller blanks the sign if no fresh, valid SHOW arrives within `T_signhold`
  (default 2 s)** — independently of the edge box, the link, and the state machine. **This is the true
  backstop.**
- the edge-box actuator abstraction keeps an *inner* dead-man's switch on the SM assertion heartbeat
  (faster local reaction), and the health monitor keeps its independent force-safe path
  ([ADR-0005](ADR-0005-fail-safe-and-system-safety.md)). **Three layers, each strictly downstream of
  what it guards.**

Every hard-failure path now resolves to blank: **SM crash** → edge stops refreshing → inner abstraction
and sign controller both blank; **edge box dead** → controller blanks; **link cut/jammed** → controller
blanks; **sign controller dead** → an LED sign is simply dark (safe). The safe-state authority is never
upstream of, or dependent on, the thing it protects.

**`T_signhold` is a real trade-off, not a free guarantee.** It is *simultaneously* the **maximum
stale-ON window after a hard failure** and the **minimum heartbeat gap that will blank a live, correct
warning**. Too short → a normal edge-box stall (GC pause, inference spike) blanks a valid warning and
the sign flaps off/on (a brief silent miss + a cry-wolf flicker); too long → stale-ON lingers after a
true crash. The default **2 s ≈ 4× `T_assert_refresh`** is a starting point to tune in Phase 3; the
flap risk is bounded by keeping `T_assert_refresh` well below `T_signhold` and by smoothing transient
edge-box latency below the refresh period.

**The heartbeat's worst enemy is the _link_, not the edge box — and the bench cannot see it.** The sign
sits **≥ DSD upstream** (≈ 315 m at 100 km/h,
[doc 02 §3](../02-system-architecture.md#3-physical--deployment-architecture)), so the refreshed `SHOW`
runs over a **300 m+ cable or RF link**, not the 1 m bench cable. A lossy or congested field link is a
far more likely source of `T_signhold`-length gaps than an edge-box GC pause — and every such gap blanks
a valid warning (a brief silent miss + a cry-wolf flicker), while a *jammed* link is a deliberate
denial-of-warning ([doc 04 §5 Q5](../04-risk-and-safety.md#5-open-safety-questions-for-the-team)). So
`T_signhold` / `T_assert_refresh` must be tuned against the **field link's** loss and latency
distribution, the link needs its **own reliability / latency / energy / authentication budget** as a
first-class interface ([doc 02 §7](../02-system-architecture.md#7-interfaces--contracts-initial)), and —
because the bench runs this over a metre of cable — **the over-distance heartbeat is itself
field-deferred validation**, not something a bench pass can close.

**Backend caveat — a latching third-party VMS cannot give the hardware guarantee.** An operator VMS
reached over its own protocol ([ADR-0004](ADR-0004-warning-actuator-integration.md)) may *latch* a
message and may not honour a heartbeat-refresh contract. For that backend the strong guarantee above
does **not** hold; the system falls back to **watchdog + active CLEAR + status read-back**, and the
residual stale-ON window equals the operator-protocol command cycle. This must be stated per site, and
is one more reason the VMS backend's latency and behaviour are qualified separately (ADR-0004,
[NFR-01](../01-requirements.md#3-non-functional-requirements)). Where the operator allows it, prefer a
refreshed-assertion or hardware-interlock mode on the VMS.

### B. Degraded-mode semantics — *initiate* and *hold* are not symmetric

| Mode | Sensor state | INITIATE a new warning? | HOLD an existing one? | Posture |
|------|--------------|-------------------------|------------------------|---------|
| **FULL** | camera + radar healthy | Yes | Yes (incl. radar occlusion hold) | Normal |
| **CAMERA-ONLY** | radar dead | **Yes** (camera class + ROI + track-speed) | Yes, but **no radar occlusion hold** and no independent stationary cross-check | Degraded + alert; flag night/weather miss risk |
| **RADAR-ONLY** | camera dead | **No** — no class, no image-ROI gate; radar azimuth may not resolve shoulder vs. through-lane | Only briefly, for tracks **already** confirmed, while radar corroborates | **BLIND-TO-NEW: critical alert** — *not* a benign run |
| **NEITHER** | both down | No | No | **SAFE STATE** (blank) + critical alert |

The load-bearing correction is **RADAR-ONLY**: it is **blind to new hazards** and must escalate as a
**critical** degradation, while tracks already confirmed may persist for a **bounded** hold so an
in-progress warning is not dropped the instant the camera fails. A unit that cannot confirm a new stop
**must never present itself as monitoring**. (CAMERA-ONLY remains a genuine degraded-run, since the
camera alone can still initiate; it simply loses radar's weather robustness and occlusion hold.)

### C. Sustained occlusion with live corroboration never clears silently — and is time-bounded

Refine ADR-0008's hold: **`T_occlusion` bounds *un-renewed* corroboration.** While radar keeps
returning a corroborating detection, the hold **renews** and the warning persists. If camera occlusion
persists **beyond `T_occlusion` while radar still corroborates**, the unit enters a
**CAMERA-OCCLUDED-DEGRADED** state: the warning **stays ON** (the hazard is still corroborated) **and**
the operator is alerted to investigate — sustained occlusion is often a *compound* incident (a second
stopped vehicle) or a camera fault.

**This state must itself be time-bounded — it is the one place the watchdog cannot reach.** The watchdog
([ADR-0008](ADR-0008-detection-persistence-and-multitrack.md) §4) is *deliberately* suppressed while any
channel corroborates, so in CAMERA-OCCLUDED-DEGRADED — camera occluded, only radar holding the warning ON
— nothing autonomous bounds the hold. Two failure shapes make that dangerous: a **permanently occluded
but genuinely-present** vehicle (correct to keep warning, but a hours-long hold should be *owned by the
operator*, not sustained silently by the machine), and — worse — a **weak criterion (b)**
([ADR-0001](ADR-0001-sensing-modality.md)) where the "corroborating" return is the **occluding
through-lane truck**, not a departed shoulder car, making the warning a **stale-ON keyed to
through-traffic** that would never clear. A confirmed exit cannot rescue either case: a *camera-occluded*
unit cannot observe a footprint cross the exit boundary.

Therefore **`T_degraded_max` (default ~5 min, tunable) bounds time in CAMERA-OCCLUDED-DEGRADED.** On
expiry with no camera re-acquire, the unit forces an explicit, **loud** disposition — a **low-confidence
clear + max-severity operator escalation** ([ADR-0011](ADR-0011-operator-concept-and-alarm-management.md))
— handing the decision to a human with CCTV/patrol rather than trusting an unverifiable radar return
forever. It is the same trade ADR-0008 makes when evidence runs out (fail loud, hand off), applied to the
one state the watchdog can't see. The paths that clear a warning are now **four**: a **confirmed exit**
(fast), **loss of all corroboration with no exit** (→ `T_hold` → loud low-confidence clear), a
**wedged-logic watchdog expiry** (→ clear + fault), and **`T_degraded_max` expiry** (→ forced loud clear
+ escalation). **None is silent, and none is unbounded** (NFR-04, broadened to sensor-discrimination
stale-ON).

## Options Considered

### Option A: Dead-man's switch on the edge box only *(the first-cut placement)*
| Dimension | Assessment |
|-----------|------------|
| Protects against SM crash (box alive) | Yes |
| Protects against box death / link loss | **No** — latching sign holds last state |
| Complexity | Low |

**Pros:** simplest; no smart sign endpoint.
**Cons:** the safe-state authority is *upstream* of the link and the sign, so the two failures most
likely to strand a lit sign (box dead, link cut) are exactly the ones it cannot cover. Disqualifying.

### Option B: Switch in the sign controller + asymmetric degraded modes + renewable hold *(chosen)*
| Dimension | Assessment |
|-----------|------------|
| Fail-safe coverage | **Complete** — box, link, SM, sensor failures all resolve to blank |
| Honesty of degraded modes | **High** — radar-only is correctly "blind to new" |
| Complexity | Medium — smart sign endpoint + two degraded modes + one degraded state |

**Pros:** the safe state is strictly downstream of every component it guards; degraded modes match the
real sensing capability; no silent clear under corroboration.
**Cons:** the sign controller must be a smart endpoint (heartbeat + blank logic); a latching VMS cannot
give the hardware guarantee and must be documented as a weaker backend.

### Option C: Latching sign + pure software watchdog
| Dimension | Assessment |
|-----------|------------|
| Fail-safe coverage | **Weak** — depends on the guarded component being alive |
| Complexity | Low |

**Pros:** trivial; works with dumb/latching signs.
**Cons:** a watchdog that depends on its subject. Acceptable **only** as the unavoidable fallback for a
third-party latching VMS (caveat in A), never as the primary design.

## Trade-off Analysis

The single principle that decides A is that **the safe-state authority must be strictly downstream of —
and independent of — every component it protects.** A switch on the edge box violates this for the link
and the sign; moving it into the sign controller satisfies it for the whole chain at the cost of a smart
endpoint, which the bench LED stand-in and a field LED sign both have anyway. B's degraded-mode
asymmetry is not a refinement but a correctness fix: calling radar-only a "degraded run" would let a
camera-blind unit keep *advertising* coverage it no longer has — the silent-miss failure wearing a
"degraded but OK" label. C's renewable-hold rule closes the last silent-clear path in ADR-0008, and its **`T_degraded_max` bound
closes the last *indefinite-hold* path** — the one state the watchdog deliberately cannot reach. All
three buy out silent-miss (and indefinite stale-ON) modes for modest, testable engineering, consistent
with guiding principle 1 (fail safe, fail loud).

## Consequences

- **Easier:** genuine fail-safe against whole-box and link failure; honest, capability-matched degraded
  modes; no silent clear while a hazard is corroborated; every failure path is a concrete fault-injection
  test.
- **Harder:** the sign controller becomes a **smart endpoint** (heartbeat + blank logic) — fine for the
  bench LED (microcontroller) and a field LED sign, but a **latching third-party VMS cannot** give the
  hardware guarantee and must be documented as a weaker backend with a stated residual; two named
  degraded modes and one degraded state to implement and fault-inject; `T_signhold` / `T_assert_refresh`
  become safety-relevant timing parameters to tune.
- **Revisit when:** a VMS vendor exposes a hardware interlock or refreshed-assertion mode (collapse the
  latching caveat), or field data quantifies real edge-box stall **and field-link loss** distributions
  (tune `T_signhold`).

## Action Items

1. [ ] Specify the **refreshed-SHOW assertion protocol** (period `T_assert_refresh`, authentication,
       `T_signhold`) between edge and sign controller; implement **blank-on-loss in the sign controller**
       (and in the bench LED controller).
2. [ ] **Fault-inject all three hard failures** — kill the edge box, cut the link, kill the SM process —
       and confirm the sign **blanks within `T_signhold`** in every case (extends
       [ADR-0005](ADR-0005-fail-safe-and-system-safety.md) AI#3).
3. [ ] Implement the **degraded modes** (CAMERA-ONLY, RADAR-ONLY/BLIND-TO-NEW, NEITHER) with the correct
       *initiate/hold* capability and escalation severity; add each to the fault-injection acceptance set
       and reconcile the [doc 04 §2](../04-risk-and-safety.md#2-fmea-lite-failure-mode--effect--detection--response)
       FMEA rows.
4. [ ] Implement **CAMERA-OCCLUDED-DEGRADED** (warning persists + operator alert) at `T_occlusion`
       expiry under live corroboration, **bounded by `T_degraded_max`** → forced loud low-confidence
       clear + max-severity escalation ([ADR-0011](ADR-0011-operator-concept-and-alarm-management.md));
       add **sustained-occlusion-with-radar** *and the `T_degraded_max` forced clear* to the acceptance
       suite (ties [ADR-0008](ADR-0008-detection-persistence-and-multitrack.md) AI#5).
5. [ ] Document the **latching-VMS backend caveat** and its residual stale-ON window in the
       [ADR-0004](ADR-0004-warning-actuator-integration.md) VMS adapter spec.
6. [ ] Characterise the **edge↔sign link** (cable / RF) loss + latency budget at the ≥ DSD deployment
       distance; tune `T_signhold` / `T_assert_refresh` against it; tag the over-distance heartbeat as
       **field-deferred** validation (the bench exercises only a short cable) and give the link its own
       entry in the [doc 02 §7](../02-system-architecture.md#7-interfaces--contracts-initial) contracts.
