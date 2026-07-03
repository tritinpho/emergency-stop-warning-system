# 08 — Interface Control Document (ICD v1)

**Project:** Emergency Stop-Lane Automatic Warning System (ESW)
**Status:** Proposed / Draft — **Phase-2 artifact** (freeze the boundaries + schemas before parallel build)
**Last updated:** 2026-06-27
**Related:** [02 architecture §7](02-system-architecture.md#7-interfaces--contracts-initial) · [02 §7a parameter surface](02-system-architecture.md#7-interfaces--contracts-initial) · [ADR-0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.md) · [ADR-0010](adr/ADR-0010-operator-override-and-manual-control.md) · [ADR-0012](adr/ADR-0012-security-and-threat-model.md) · [ADR-0013](adr/ADR-0013-degraded-hold-unification.md)

This document concretises the contracts [doc 02 §7](02-system-architecture.md#7-interfaces--contracts-initial)
left "indicative." It is **ICD v1**: the **interface boundaries, message shapes, fields, units, and
delivery/auth semantics are frozen** so perception, the state machine, the actuator adapter, the sign
controller, and the TMC can be built in parallel without integration drift. The **wire encoding**
(protobuf vs JSON), exact MQTT topics, and the specific VMS protocol profile are deliberately **deferred
to first integration** (Phase 4) — see [§7](#7-frozen-in-v1-vs-deferred-to-integration).

> **Versioning.** The ICD is SemVer'd; every message schema carries a `schema_ver`. A breaking change to a
> frozen field is a major bump and an ADR-grade decision. Additive optional fields are minor bumps.

---

## 1. Interface inventory

```
        IF-1            IF-2              IF-3                 IF-4 (auth, ≥DSD link)
 sensors ───▶ perception ───▶ state machine ───▶ actuator abstraction ═══▶ sign controller ──▶ sign
                                  ▲  │                  ▲                         ▲
                          health  │  │ IF-3            IF-5 force-safe ───────────┘
                          monitor ┘  │ (status read-back)
                                     │
        ┌────────────────────────────┴───── edge box ─────────────────────────────┐
        │  IF-6 heartbeat · IF-7 events (store-and-forward) ──▶ TMC                 │
        │  TMC ──▶ IF-8 config (signed) · IF-9 OTA (signed) · IF-10 override (auth) │
        └──────────────────────────────────────────────────────────────────────────┘
```

| IF | Between | Direction | Safety-critical? | Transport (indicative) | Delivery |
|----|---------|-----------|------------------|------------------------|----------|
| **IF-1** | Sensors → Perception | in | yes (loop) | in-process / driver SDK | streaming |
| **IF-2** | Perception → State machine | in | yes (loop) | in-process / IPC | streaming |
| **IF-3** | State machine ↔ Actuator abstraction | in/out | yes (loop) | in-process / IPC | request + status read-back |
| **IF-4** | Edge box → **Sign controller** | out | **yes — fail-safe-bearing** | field link (cable / RF), **authenticated** | **refreshed assertion** every `T_assert_refresh`; blank on loss within `T_signhold` |
| **IF-5** | Health monitor → Sign controller / actuator | out | **yes** | independent force-safe path | command (force-safe) |
| **IF-6** | Edge → TMC | out | no | MQTT/TLS | periodic, store-and-forward |
| **IF-7** | Edge → TMC / audit | out | no | MQTT/TLS | **store-and-forward, ordered, durable** |
| **IF-8** | TMC → Edge (config) | in | yes (content) | HTTPS / MQTT, **signed** | request + ack; **unit enforces §7a bounds** |
| **IF-9** | TMC → Edge (OTA) | in | yes (content) | HTTPS, **signed** | staged; **deferred while warning active** |
| **IF-10** | TMC → Edge (override) | in | **yes** | **same hardened channel as IF-8/9**, authenticated | edge-mediated, **refreshed (non-latching)**, auto-expiry |

The **safety loop is IF-1→IF-2→IF-3→IF-4** and runs edge-local; IF-6..IF-10 are oversight and **never in
the safety path** (NFR-06, [ADR-0002](adr/ADR-0002-edge-vs-cloud-processing.md)). A TMC outage cannot make
the loop unsafe.

---

## 2. Internal loop interfaces (IF-1 … IF-3, IF-5)

### IF-2 — Detection / track event (Perception → State machine)
The contract the **event-level simulation** ([doc 07 §2](07-simulation-methodology.md#2-harness-architecture--simulate-the-sensors-and-the-sign-never-the-logic)) feeds. One message per tracked object per cycle:

| Field | Type | Units / notes |
|-------|------|---------------|
| `track_id` | string/uint | stable per tracker lifetime |
| `class` | enum | `car·truck·bus·motorcycle·person` |
| `footprint` | polygon / bbox | ground footprint (preferred) or image bbox |
| `in_roi` | float | **fractional overlap** of footprint with ROI polygon (gate ≥ 0.5, [doc 02 §4](02-system-architecture.md#4-the-detectionwarning-state-machine)) |
| `range_m` | float | metres (radar) |
| `speed_kph` | float | km/h; signed toward/away |
| `sensor_source` | enum/flags | `camera·radar·fused` — lets the SM know corroboration source |
| `ts` | timestamp | **absolute**, GNSS/PPS-disciplined (NFR-16) |

### IF-3 — Sign command + status read-back (State machine ↔ Actuator abstraction)
- Command: `SHOW(message_id)` | `CLEAR` | `STATUS?`
- `STATUS?` returns `{ state: ON|OFF|FAULT, lamp_ok: bool, message_id?, ts }`
- The actuator abstraction is the **only** asserter of a warning; **absence** of a live assertion is fail-safe by construction. It translates IF-3 into the IF-4 refreshed assertion and reads back status. Backend-swappable (own LED / VMS, [ADR-0004](adr/ADR-0004-warning-actuator-integration.md)).

### IF-5 — Independent force-safe (Health monitor → controller/actuator)
A path that drives the sign to **blank** **without routing through the state machine** ([ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.md)) — used when the SM is wedged. Strictly downstream of the SM.

---

## 3. IF-4 — the sign-link refreshed-`SHOW` protocol (the fail-safe-bearing interface)

This is the most safety-load-bearing interface: the sign sits **≥ DSD upstream** over a 300 m+ link, and
the **dead-man's switch lives in the sign controller** ([ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)).

**Assertion message** (edge box → sign controller, every `T_assert_refresh`):

| Field | Type | Notes |
|-------|------|-------|
| `assertion` | enum | `SHOW(message_id)` \| `NONE` |
| `seq` | uint | monotonic — **anti-replay** |
| `nonce` | bytes | **anti-replay** |
| `cfg_ver` | hash | active-config fingerprint |
| `ts` | timestamp | absolute |
| `auth_tag` | bytes | **HMAC/signature over the message** ([ADR-0012](adr/ADR-0012-security-and-threat-model.md)) |

**Controller rule (the dead-man's switch):** display `SHOW(message_id)` **only** while a *fresh, valid,
authenticated* assertion arrives within `T_signhold`; otherwise **blank**. "Valid" = good `auth_tag` **and**
`seq`/`nonce`/`ts` within the replay window. Therefore: SM crash → edge stops refreshing → blank; edge box
dead → blank; link cut/jammed → blank; forged/replayed `SHOW` → rejected (auth/replay) → blank.

**Timing** is governed by [doc 02 §7a](02-system-architecture.md#7-interfaces--contracts-initial): `T_assert_refresh`
≤ ¼·`T_signhold`; `T_signhold` is simultaneously the max stale-ON after a hard failure and the min gap that
blanks a valid warning, so it is tuned against the **field link's** loss/latency (over-distance validation is
**field-deferred**, [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)).

**Latching-VMS caveat.** A third-party VMS that cannot honour the refresh contract falls back to *watchdog +
active CLEAR + status read-back*, with a residual stale-ON = the operator command cycle; NFR-01 is
**qualified** for that backend ([ADR-0004](adr/ADR-0004-warning-actuator-integration.md), [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)).

---

## 4. Edge → TMC interfaces (IF-6, IF-7) — non-critical, store-and-forward

### IF-6 — Heartbeat
Fixed cadence; carries health **and posture** so a degraded unit can never look healthy:

| Field | Type | Notes |
|-------|------|-------|
| `site_id` | string | |
| `fw_ver` `cfg_ver` `model_ver` `calib_ver` | hashes | **version fingerprint** (R10 audit, [doc 02 §7](02-system-architecture.md#7-interfaces--contracts-initial)) |
| `subsystem_health[]` | list | per camera/radar/compute/link/sign |
| `sensor_mode` | enum | `FULL·CAMERA-ONLY·RADAR-ONLY·NEITHER` ([ADR-0009 §B](adr/ADR-0009-failsafe-placement-and-degraded-modes.md), [ADR-0013](adr/ADR-0013-degraded-hold-unification.md) matrix) |
| `posture` | enum | `NORMAL·OVERRIDDEN·BLIND-TO-NEW·CAMERA_OCCLUDED_DEGRADED·SAFE_STATE` |
| `drift_status` | enum | drift-monitor verdict (FR-10, R15) |
| `state` | enum | current warning state |
| `ts` | timestamp | absolute |

### IF-7 — Activation / clear / fault event (audit)
Store-and-forward, **ordered and durable** (survives outage, syncs opportunistically):

| Field | Type | Notes |
|-------|------|-------|
| `site_id` | string | |
| `type` | enum | `activation·clear·low_confidence_clear·forced_clear(T_degraded_max)·fault·override·sign_stuck` |
| `severity` | enum | drives the ConOps response ([ADR-0011](adr/ADR-0011-operator-concept-and-alarm-management.md)) |
| `evidence_ref?` | id | pointer to a minimised event snapshot (no raw video, NFR-10) |
| `cfg_ver` `model_ver` `calib_ver` | hashes | fingerprint bound to the event |
| `ts` | timestamp | absolute |

---

## 5. TMC → Edge interfaces (IF-8 config, IF-9 OTA, IF-10 override)

### IF-8 — Config (signed)
Payload = the **site-tunable subset**; the unit **enforces the full §7a bounds** on every field (FR-20):

```
{ schema_ver, roi_polygon, T_dwell, T_hold, T_occlusion, T_person_debounce,
  speed_gate, message_set, T_override_max, sig }
```
- **Signed**; the unit verifies signature, then **range-checks every parameter against [doc 02 §7a](02-system-architecture.md#7-interfaces--contracts-initial)** — out-of-bounds → **reject/clamp, keep last-good, alert** (FR-20, R16). Signing stops tampering; the bounds check stops operator error.
- Staged/validated like an update; the safety **backstops** (`T_watchdog`/`T_signhold`/`T_assert_refresh`/`T_degraded_max`/`T_activate`) are bounded constants with hard ceilings per §7a and are **not** freely pushable to values that disable their invariant.

### IF-9 — OTA (signed + rollback)
```
{ image, version, rollback_token, sig }
```
- **Deferred while a warning is active** (track-set non-empty) or the sign is taken to a known blank state **loud to operators** — never a silent drop (FR-21). **Canary** metrics post-update → **rollback** to the last signed version on regression.

### IF-10 — Operator override (authenticated, non-latching)
Rides the **same hardened channel** as IF-8/9 ([ADR-0010](adr/ADR-0010-operator-override-and-manual-control.md), [ADR-0012](adr/ADR-0012-security-and-threat-model.md)):

```
{ command: force_on|force_off|mute, message_id?, reason_code, operator_id,
  expiry (≤ T_override_max), auth }
```
- **Force-on** is asserted by the **same refreshed-`SHOW` heartbeat**, refreshed **by the edge box locally** — never latched over the WAN; the dead-man's switch still blanks it on box-kill / link-cut / expiry.
- **Force-off / mute** carries a **mandatory auto-expiry**; while active the heartbeat posture is **OVERRIDDEN** (not "healthy"), and it **re-escalates** if it outlives its window.
- Out-of-policy overrides (expiry > ceiling, unknown `message_id`, no `reason_code`) are **rejected/clamped** at the unit (FR-20 mechanism).
- Override acts **only on the sign output** — perception, fusion, the state machine, and the audit log keep running, so an override is always reconstructable.

---

## 6. Cross-cutting contracts

- **Authentication & integrity** ([ADR-0012](adr/ADR-0012-security-and-threat-model.md)): the **sign link (IF-4)** is authenticated (anti-forge, anti-replay) — a control plane that lights a roadside sign cannot be weaker than telemetry; IF-8/9/10 are signed/authenticated on one hardened channel. NFR-09's scoped claim: *authenticated against forge/replay on the enumerated surfaces; denial (jam/blind) mitigated to **fail-safe-blank-and-alarm**, not prevented.*
- **Time** (NFR-16): all `ts` are **absolute**, from a GNSS/PPS-disciplined source, holding over outages; relative inter-sensor sync (sub-frame) for fusion. No timestamp is inherited from a free-running OS clock.
- **Version fingerprint**: every safety-relevant message (IF-4/6/7) carries `cfg_ver`/`model_ver`/`calib_ver` so an audit can reconstruct *what the unit was running* at event time ([doc 02 §7](02-system-architecture.md#7-interfaces--contracts-initial), R10).
- **Failure semantics**: IF-4 loss → controller blanks (dead-man's switch); IF-6/7 loss → queue locally, loop unaffected; IF-8 bad/out-of-bounds → reject, keep last-good; IF-9 regression → rollback.

---

## 7. Frozen in v1 vs deferred to integration

**Frozen now** (so parallel build can proceed): the interface **inventory and boundaries**, message **field
sets, types, units, and required/optional status**, the **IF-4 refreshed-assertion + auth semantics**, the
**§7a bounds enforcement** on IF-8, the **non-latching/auto-expiry** override semantics, and the **time +
fingerprint** cross-cutting rules.

**Deferred to first integration (Phase 4), tracked as open items:**
- Concrete **wire encoding** — protobuf vs JSON for IF-2/3/6/7; exact MQTT topic tree.
- The specific **VMS protocol profile** (NTCIP-style / vendor API) for the existing-VMS backend, and its arbitration-priority rules ([ADR-0004](adr/ADR-0004-warning-actuator-integration.md) AI#2/#5).
- The **physical field-link** for IF-4: the **bearer is now chosen — LoRa point-to-point** ([ADR-0014](adr/ADR-0014-sign-link-bearer.md)); its loss/latency/energy/auth **and duty-cycle** budget at ≥ DSD distance — which co-determines `T_signhold` — remains **field-deferred** ([ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)).
- Exact **key-management** for IF-4/8/9/10 auth (prototype: keys provisioned at commissioning; fleet-scale key management is field/productisation, [ADR-0012](adr/ADR-0012-security-and-threat-model.md)).
- The approved **`message_set`** contents — pending the QCVN-41 conformance gate ([ADR-0004](adr/ADR-0004-warning-actuator-integration.md) AI#4); if only one legal element exists, congestion **re-messaging** is unavailable and the design is suppression-only.
