# 10 — IF-4 Sign-Controller Firmware Specification (RQ-H2 realization)

**Project:** Emergency Stop-Lane Automatic Warning System (ESW / ELMS)
**Status:** Proposed — software-authored handoff to the hardware/firmware team (Nhóm ACLAB ELMS).
**Last updated:** 2026-07-07
**Owns:** the ESP32 sign-controller firmware behaviour. **Consumes:** [ICD §3](08-interface-control-document.md#3-if-4--the-sign-link-refreshed-show-protocol-the-fail-safe-bearing-interface), [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.md), [ADR-0012](adr/ADR-0012-security-and-threat-model.md), [ADR-0014](adr/ADR-0014-sign-link-bearer.md), [RQ-H2](09-software-hardware-handoff.md).

This document is the firmware-level realization of **RQ-H2** (the sign controller as a *smart endpoint*). It exists because the Week-1 prototype link is **fail-danger**: a one-shot `$NODE01|ALERT|STOP|A3#` + checksum that **latches** the LED. That is the exact inverse of the safety thesis — a latching sign strands a stale-ON warning when the edge box or link dies. The fix is a **firmware-behaviour change, not a redesign**: the ESP32 already sits where the dead-man's switch must live ([ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.md)). The **reference implementation is executable and tested** in this repo — [`software/esw/if4.py`](../software/esw/if4.py) (the wire codec + `verify()`) and [`software/harness/sign.py`](../software/harness/sign.py) (the controller model), exercised by scenarios **SC-21/22/23** (hard-failure blanking) and **SC-33/34** (forged / replay rejection) on the Level-A board.

---

## 1. The one rule (the dead-man's switch)

> The sign displays `SHOW(message_id)` **only** while a **fresh, valid, authenticated** assertion has arrived within `T_signhold`. Otherwise it **blanks**.

Consequences that must hold **by construction**, not by any command being sent:

- SM crash, edge-box death, cut or jammed link → the refresh stops arriving → the sign blanks within `T_signhold`.
- A forged or replayed `SHOW` → fails verification → ignored → the sign blanks.

**There is no "off"/"blank" message, and the firmware must never add one.** OFF is the *absence* of a valid refresh. Any design in which a message is required to turn the sign off is fail-danger, because the failure that most needs to blank the sign (a dead edge box) is exactly the one that cannot send that message.

## 2. Frame format (authoritative — 29 bytes, big-endian)

One message type only: an authenticated **SHOW assertion**. Byte layout (see `esw/if4.py`):

| Offset | Field | Size | Meaning |
|-------:|-------|-----:|---------|
| 0 | `version` | 1 | protocol version = `1` |
| 1 | `msg_type` | 1 | `MSG_SHOW` = `1` (the only type) |
| 2 | `message_id` | 1 | QCVN-41 message index ([ADR-0004](adr/ADR-0004-warning-actuator-integration.md)); `1` = `STOPPED_VEHICLE_AHEAD` |
| 3–6 | `seq` | 4 | monotonic counter — **anti-replay (in-session)** |
| 7–10 | `nonce` | 4 | random per frame (edge uses `os.urandom`) |
| 11–14 | `cfg_ver` | 4 | active-config fingerprint (audit, [R10](04-risk-and-safety.md#1-risk-register)); authenticated but **opaque** to the controller |
| 15–20 | `ts_ms` | 6 | transmit timestamp, ms since the agreed epoch — **anti-replay (cross-session)** |
| 21–28 | `auth_tag` | 8 | truncated **HMAC-SHA256** over bytes 0–20 |

The frame is deliberately compact: LoRa time-on-air scales with payload bytes and IF-4 airtime is duty-cycle-bound (§6). **The size is frozen here because it is the airtime input** — changing a field changes `T_signhold` (§6), so it is an ADR-grade change, not a firmware tweak.

## 3. Controller verify algorithm

On each received frame, in order (mirror of `esw/if4.verify` + `harness/sign.py`):

```
receive(frame, now):
    if link_down or frame is None:            return            # nothing arrived
    if len(frame) != 29:                      reject("len")
    if frame[0] != 1 or frame[1] != 1:        reject("proto")   # version / type
    tag  = HMAC_SHA256(key, frame[0:21])[0:8]
    if not constant_time_equal(tag, frame[21:29]): reject("auth")
    seq  = u32(frame[3:7]);  ts = u48(frame[15:21])
    if session_open and seq <= last_seq:      reject("replay")  # in-session monotonicity
    if abs(now_ms - ts) > REPLAY_WINDOW_MS:   reject("stale")   # cross-session freshness
    # accept:
    last_show_ts = now;  last_seq = seq;  message_id = frame[2]

update(now):                                   # runs continuously (the dead-man's switch)
    if last_show_ts is not None and (now - last_show_ts) <= T_signhold:
        sign_on()                              # a fresh valid SHOW is holding it
    else:
        sign_off();  last_seq = None           # session ends -> a legit reconnect may re-assert
```

- **Constant-time tag compare** — do not early-exit on the first mismatched byte (no timing oracle).
- **Fail-closed on any parse/verify error** — a malformed or unverifiable frame is a *no-op*, never a partial accept.

## 4. Anti-replay — two guards, one for each threat

1. **In-session (`seq` strictly increasing).** While the sign is lit, a captured frame re-sent (replay) or an out-of-order/duplicated frame has `seq ≤ last_seq` → rejected. Blocks an attacker (or a buggy repeater) from *extending* a live warning with stale bytes.
2. **Cross-session (`ts` freshness window).** When the sign has been blank (the dead-man's window elapsed), `last_seq` resets, so a **legitimately reconnecting edge** — e.g. a rebooted box whose RAM `seq` counter restarted low ([SC-15](../software/scenarios/catalogue.py)) — can re-assert. A **replayed old frame is still blocked** because its `ts` is outside `REPLAY_WINDOW`. Without this reset, naïve monotonic anti-replay would lock out a rebooted edge forever; without the freshness check, the reset would open a resurrection hole. Both are required.

`REPLAY_WINDOW` defaults to `T_signhold` (a frame older than the hold window is useless and suspicious). Real LoRa latency (~100 ms) ≪ `T_signhold`, so legitimate frames never fail freshness.

## 5. Authentication & keys ([ADR-0012](adr/ADR-0012-security-and-threat-model.md))

- **HMAC-SHA256**, tag **truncated to 8 bytes (64-bit)** — the airtime-vs-security trade (a full 32-byte tag would nearly triple the payload). 64-bit forgery resistance is adequate for a short-lived roadside heartbeat; revisit if the threat model hardens.
- **Key** = a **per-unit shared secret**, provisioned **out-of-band** (not over the air), stored in ESP32 secure storage (NVS with flash-encryption), and **rotatable**. The edge box and its paired controller share one key. *(Key-provisioning mechanism is an open handoff item — §8.)*
- `cfg_ver` is inside the authenticated span but **opaque** to the controller (echoed for audit, never interpreted), so config-representation differences across runtimes cannot change a safety decision.

## 6. Time & the LoRa airtime budget — how `T_signhold` is *determined*

**Time.** The cross-session freshness check needs the controller clock within `REPLAY_WINDOW` of the edge clock (NFR-16). Provision a time source: GNSS/PPS at the sign, or a periodically edge-synced clock. **If no adequate clock exists**, the controller must fall back to a *persistent* monotonic `seq` in secure storage (no reset on reboot) and drop the freshness check — a documented degradation, since it re-introduces the reconnect-lockout the freshness guard was solving.

**Airtime.** Under **Circular 08/2021/TT-BTTTT**, 433 MHz LoRa is license-exempt at **≤ 25 mW ERP** with a duty cycle of **≤ 10 %** (data/gateway class) or **≤ 1 %** (terminal class) — the class is load-bearing and unconfirmed ([ADR-0014](adr/ADR-0014-sign-link-bearer.md)). Because `T_assert_refresh ≤ ¼·T_signhold`, the refresh rate sets a **floor** on `T_signhold`:

> computed time-on-air of the **real 29-byte frame** (BW 125 kHz, CR 4/5, explicit header, CRC on):

| SF | ToA (ms) | max refresh @10% | `T_signhold` floor @10% | `T_signhold` floor @1% |
|---:|---------:|:----------------:|:-----------------------:|:----------------------:|
| 7 | 66.8 | 1.50 Hz | **2.7 s** | 26.7 s |
| 8 | 123.4 | 0.81 Hz | 4.9 s | 49.4 s |
| 9 | 226.3 | 0.44 Hz | 9.1 s | 90.5 s |
| 10 | 411.6 | 0.24 Hz | 16.5 s | 164.7 s |

**Reading:** only **SF7 at the 10 % class** yields a `T_signhold` floor (~2.7 s) that fits the frozen clamp (`T_signhold` ≤ **3.0 s**, [doc 02 §7a](02-system-architecture.md#7-interfaces--contracts-initial) / `esw/params.py`). Any higher SF — which the 25 mW ERP cap may **force** to close the ≥315 m link in rain — or the 1 % terminal class pushes the floor to seconds-to-tens-of-seconds, which **defeats the dead-man's switch**. This is a *computed prediction*; the [ADR-0014](adr/ADR-0014-sign-link-bearer.md) bench airtime test must confirm it on the real SX1276, and **920–923 MHz must be evaluated in parallel** as the Option-C fallback. `T_signhold` is therefore **not a free firmware constant** — it is set from measured airtime + link margin + the confirmed duty class, then frozen as the §7a bounded constant.

## 7. Firmware conformance tests (acceptance)

The firmware is RQ-H2-conformant when, on the bench rig:

| # | Stimulus | Required sign behaviour | Mirrors |
|--:|----------|-------------------------|---------|
| C1 | Valid refresh at `T_assert_refresh` | lit, steady, no flicker | SC-01 |
| C2 | Kill the edge-box process (SM) | blanks ≤ `T_signhold` | SC-21 |
| C3 | Power off the edge box | blanks ≤ `T_signhold` | SC-22 |
| C4 | Cut / jam the RF link | blanks ≤ `T_signhold` | SC-23 |
| C5 | Inject `SHOW` frames with a wrong key | **never lights**; reject-count climbs | SC-33 |
| C6 | Replay a captured valid frame after blank | **never re-lights** | SC-34 |
| C7 | Reboot the edge box (fresh low `seq`) | re-lights after a valid refresh returns | SC-15 |
| C8 | Commanded CLEAR vs a wedged-ON panel | reports still-ON via IF-3 read-back | SC-24 |

C2–C4 and C5–C6 are the two halves of RQ-H2: **hard-failure blanking** and **spoof/replay rejection**. Both must pass before the fail-safe design is acceptance-ready ([doc 03 §5 “After P4”](03-roadmap-and-phasing.md#5-per-phase-risk-gates)).

## 8. What the Week-1 firmware must stop doing, and open handoffs

**Stop (the fail-danger divergences):** (a) **no latching** — the LED state must be recomputed every `update()` from refresh freshness, never set-and-hold; (b) **no one-shot trigger** — a single frame must not produce a persistent ON; (c) **checksum ≠ authentication** — a CRC/XOR checksum stops corruption, not forgery; use the HMAC; (d) **no "off" command** — see §1.

**Open handoffs (not software's to decide):**
1. [ADR-0014](adr/ADR-0014-sign-link-bearer.md) bench tests — SX1276 airtime for this frame, the **duty class** (10 % vs 1 %), and ≥315 m range at ≤25 mW ERP — resolve whether 433 MHz can host the switch at `T_signhold` ≤ 3 s (§6 predicts *only just*, at SF7/10 %).
2. **920–923 MHz** evaluation as the Option-C fallback if (1) fails.
3. **Key-provisioning mechanism** — how the per-unit shared secret is loaded and rotated (§5).
4. **Controller time source** — GNSS/PPS vs edge-synced vs persistent-`seq` fallback (§6).
