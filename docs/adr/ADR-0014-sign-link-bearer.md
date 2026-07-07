# ADR-0014: Sign-link bearer for IF-4 — LoRa point-to-point, and its duty-cycle constraint on the dead-man's switch

**Status:** Proposed — hardware/firmware (RF + regulatory) + software (IF-4 timing/auth). Software-side analysis done; **blocked** on a bench airtime test, a regulatory duty-class confirmation, and an over-distance range test before it can be Accepted.
**Date:** 2026-07-03
**Deciders:** PI / software lead, hardware/firmware lead, regulatory/compliance check

## Context

IF-4 (edge box → sign controller, [ICD §3](../08-interface-control-document.md)) is the one **fail-safe-bearing** interface: the controller displays `SHOW` **only** while a fresh, authenticated assertion arrives within `T_signhold`, else it **blanks** — the dead-man's switch lives in the sign controller ([ADR-0009 §A](ADR-0009-failsafe-placement-and-degraded-modes.md)). That requires the bearer to sustain a **refreshed assertion at `T_assert_refresh` ≤ ¼·`T_signhold`**. The sign sits **≥ DSD (~315 m) upstream** of the edge box (TCVN 5729 placement), so a long link is unavoidable and co-locating the sign with the edge box is precluded.

Two developments forced this decision now:

1. The **hardware team's Week-1 prototype** (2026-06-29) put the edge→sign link on **LoRa 433 MHz (ESP32 + SX1276)**. The demo actually latched an LED on a one-shot frame, but the intended bearer is LoRa — a de-facto choice of the IF-4 physical layer, which [ICD §7](../08-interface-control-document.md) had explicitly **deferred to integration**.
2. [ADR-0006](ADR-0006-connectivity-and-power.md) named LoRaWAN only as a **non-safety** telemetry side-channel to the TMC ("the safety loop never depends on any of these"). Putting LoRa on **IF-4** moves it onto the safety path — a different set of requirements (authentication, anti-replay, refresh timing) that this ADR records.

Forces: reach (≥315 m, near-LOS along the shoulder, rain/foliage margin), power (solar, both clusters), the **airtime/duty-cycle budget vs. the required refresh rate**, authentication overhead (HMAC + seq/nonce → frame size → airtime), the applicable **Vietnamese 433 MHz regulatory limits**, and prototype cost.

## Decision

Adopt **raw LoRa (SX1276-class) point-to-point** — *not* LoRaWAN (no gateway or duty-managed MAC in the safety path; we control the timing directly) — as the IF-4 bearer **for the prototype, conditioned on** a bench-proven airtime/duty-cycle budget that sustains `T_assert_refresh` ≤ ¼·`T_signhold` at a spreading factor that **also** closes the ≥315 m link within the license-exempt power cap. If that budget cannot close, the resolution is an **explicit, recorded** relaxation of `T_signhold` (a worse max-stale-ON bound) **or** a different bearer (Option C) — either being an ADR-grade change, not a silent tuning.

This **supersedes the implicit assumption** in [ICD §7](../08-interface-control-document.md) that the IF-4 bearer was undecided, and **disambiguates** [ADR-0006](ADR-0006-connectivity-and-power.md): LoRa-as-TMC-telemetry (non-safety) and LoRa-as-IF-4-bearer (safety-critical) are different channels with different requirements.

## Options Considered

### Option A: LoRa 433 MHz point-to-point *(chosen, conditioned)*
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low–Medium (Week-1 demo already runs SX1276 on ESP32) |
| Cost | Low — fits the 20M envelope |
| Reach | Good at ~315 m near-LOS, even at low SF |
| Power | Low — solar-friendly |
| Duty-cycle headroom | **Tight / regulatorily bounded** |

**Pros:** cheapest, lowest-power, already prototyped, controllable PHY for a deterministic heartbeat.
**Cons:** a **refresh-rate ↔ airtime ↔ duty-cycle ↔ range** coupling that Vietnamese regulation makes binding (see Trade-off Analysis). Auth overhead (HMAC + seq/nonce) *adds* airtime, so security trades directly against staleness.

### Option B: Wired (buried / ducted cable) edge↔sign
| Dimension | Assessment |
|-----------|------------|
| Determinism | **High** — no duty limit, trivial auth |
| Feasibility | **Low** for the prototype |

**Pros:** deterministic, no regulatory duty cap, simple authenticated channel.
**Cons:** trenching ~315 m of shoulder is infeasible for a 20M bench prototype (civil works, road-opening permits) and often for field. Rejected for the prototype; retained as an option for some permanent field sites.

### Option C: Higher-rate RF without a strict duty cap
2.4 GHz directional link; a sub-GHz FHSS module in a band that permits high duty / LBT; or LTE-M / private cellular.

**Pros:** removes the duty ceiling → can sustain a fast heartbeat.
**Cons:** 2.4 GHz has worse range/rain/foliage margin and needs antenna alignment; cellular re-introduces a recurring cost and a WAN element we deliberately kept off the safety path; higher power/cost. **Held as the fallback if Option A's duty-cycle budget fails**, with the **920–923 MHz** VN LPWAN band as the front-runner to evaluate.

### Option D: Redesign IF-4 off continuous refresh
Event `SHOW` + slow keepalive + controller blanks after N missed keepalives.

**Pros:** cuts airtime.
**Cons:** a slow keepalive means a **large `T_signhold`** → longer max-stale-ON — the weaker "latching-VMS" posture [ICD §3](../08-interface-control-document.md) already flags. Acceptable only as a documented degradation, not a default.

## Trade-off Analysis

The crux is a coupling the naive demo hides: **`T_signhold` ↔ refresh-rate ↔ airtime ↔ range**, now made *binding* by Vietnamese regulation. Under **Circular 08/2021/TT-BTTTT**, 433 MHz LoRa is license-exempt only as an **LPWAN** device (Appendix 19) with **≤ 25 mW ERP** and a duty cycle of **≤ 10 % for a data-transmission / gateway** end and **≤ 1 % for a terminal** end. The edge box continuously refreshing the assertion is the data source — plausibly the "gateway" 10 % class, but a conservative reading of a point-to-point node is the 1 % terminal class. **This classification is load-bearing and must be confirmed.**

Illustratively: a ~40-byte authenticated frame is ~70 ms on air at SF7/BW125 (and ~250 ms by SF9, which the low 25 mW cap may force to hold range in rain). At a 2 Hz refresh (`T_signhold` = 2 s → `T_assert_refresh` ≤ 0.5 s) that is **~14 % duty at SF7 — already over the 10 % ceiling**, and hopeless at SF9 or under the 1 % class. Staying under 10 % at SF7 pushes the refresh to ≈1.4 Hz → a **`T_signhold` floor of ≈3 s**; under the 1 % terminal class it collapses to ~30 s, which **effectively defeats the dead-man's switch**. The **25 mW ERP cap** and the **duty cap compound**: low power pushes toward a higher SF for range margin, and higher SF multiplies airtime, worsening duty.

So everything good about LoRa (reach, power, cost) is real, and Option A is the right *prototype* bearer **if** the budget closes at the gateway-10 % class with SF7 and adequate 25 mW margin — a narrow corner. The honest risk is that it may not, forcing a looser `T_signhold` (Option D flavour, worse safety) or Option C. This is a **measure-don't-assume** decision: a bench airtime test + a regulatory-class confirmation + a ≥315 m range test resolve it in days. Until then, **LoRa-on-the-safety-path is proposed, not proven**, and 920–923 MHz should be evaluated in parallel.

## Consequences

- **Easier:** a cheap, low-power, solar-friendly sign link already in hand, with a PHY we control end-to-end.
- **Harder:** `T_signhold` is **no longer a free software knob** — it is co-determined by the RF layer and must be set from *measured* airtime + link margin + the regulatory duty class, then frozen as a §7a bounded constant ([doc 02 §7a](../02-system-architecture.md)). The auth frame size now has a timing cost that must be co-designed with security ([ADR-0012](ADR-0012-security-and-threat-model.md)).
- **Corrects the record:** LoRa is now on the **safety path** and inherits IF-4's authentication + anti-replay + refresh requirements — no longer the [ADR-0006](ADR-0006-connectivity-and-power.md) non-safety telemetry side-channel. ADR-0006 is amended to keep the two roles distinct.
- **New field-deferred item:** the over-distance duty-cycle / loss / latency budget that sets `T_signhold` joins the [ADR-0009 §A](ADR-0009-failsafe-placement-and-degraded-modes.md) field-deferred link validation and the [doc 06](../06-traceability-matrix.md) coverage notes.
- **Revisit when:** the bench/regulatory tests land (accept, or move to Option C), or field range/robustness data arrives.

## Action Items

1. [ ] **Bench airtime test** (sw + fw): measure SX1276 time-on-air for the real authenticated frame at candidate SF/BW/CR; compute the achievable refresh rate; verify `T_assert_refresh` ≤ ¼·`T_signhold` holds at a legal duty cycle. **Software has now computed this for the frozen 29-byte frame** ([doc 10 §6](../10-if4-sign-controller-firmware-spec.md)): at SF7 / 10 % class the `T_signhold` floor is **~2.7 s** (fits the 3 s clamp, tight); SF8+ (which the 25 mW ERP range margin may force) or the 1 % terminal class give **4.9–27 s**, which defeats the dead-man's switch. The bench test now has a concrete prediction to confirm or refute.
2. [ ] **Regulatory-class confirmation** (hw/ops): confirm under Circular 08/2021/TT-BTTTT whether the edge→sign transmitter is the **10 % (gateway)** or **1 % (terminal)** class, and the **25 mW ERP** cap; record the binding duty limit.
3. [ ] **Range/margin test** at ≥315 m near-LOS incl. wet conditions at the chosen SF; confirm the link budget with fade margin at ≤ 25 mW ERP.
4. [ ] **Evaluate 920–923 MHz** VN LPWAN as the Option-C front-runner (duty / LBT rules, module availability, power).
5. [ ] If (1)–(3) fail → escalate to Option C or a recorded `T_signhold` relaxation (ADR-grade).
6. [ ] Fold the SX1276 + ESP32 sign-controller draw into the [ADR-0006](ADR-0006-connectivity-and-power.md) power budget.
7. [ ] Fix the [ICD §7](../08-interface-control-document.md) field-link line (bearer = LoRa P2P, budget pending) and the [doc 06](../06-traceability-matrix.md) coverage note.
