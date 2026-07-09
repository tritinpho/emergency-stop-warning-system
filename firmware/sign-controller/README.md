# firmware/sign-controller — the IF-4 dead-man's-switch scaffold (doc 10)

The ESP32 (YoloUno) sign-controller firmware implementing
[doc 10](../../docs/10-if4-sign-controller-firmware-spec.md): the sign shows
`SHOW(message_id)` **only** while a fresh, valid, **authenticated** 29-byte IF-4
frame has arrived within `T_signhold` (2.0 s); otherwise it **blanks**. There is
**no "off" command** — a dead edge box, a crashed state machine, or a cut link all
blank the sign *by construction*, because what they share is that nothing arrives.

This replaces the Week-1 fail-danger prototype behaviour (one-shot latching
trigger + checksum) with the doc 10 contract: recompute-from-freshness, HMAC
authentication, and two-guard anti-replay.

## One source of truth

The wire contract lives in [`software/esw/if4.py`](../../software/esw/if4.py); this
firmware's [`src/if4_verify.cpp`](src/if4_verify.cpp) is its C mirror (same check
order, same reject reasons). The link is proven, not assumed:

- [`tools/gen_vectors.py`](tools/gen_vectors.py) runs the **real Python encoder**
  to generate [`src/test_vectors.h`](src/test_vectors.h) (16 frames + expected
  verdicts, including wrong-site and wrong-channel keys from
  `crypto.derive_key`). The firmware runs them through `if4_verify()` **on every
  boot** and prints `VECTORS PASS 16/16`. Regenerate after any `esw/if4.py` /
  `esw/crypto.py` change.
- [`tools/bench_send.py`](tools/bench_send.py) drives the flashed board with
  frames from the same Python codec and scores the doc 10 §7 conformance rows
  C1, C2/C4, C5, C6, C7 automatically (C3 and C8 stay physical).

## Layout

```
platformio.ini        # envs: yolouno (OhStem ESP32-S3), esp32s3-devkit
boards/
  esp32s3-n16r8.json  # YoloUno board def (mirrors OhStem's own PlatformIO config)
src/
  main.cpp            # dead-man's update() + bench serial protocol + NVS key
  if4_verify.h/.cpp   # the verify core (platform-free C, mbedtls-backed HMAC)
  config.h            # T_signhold / replay window / pins (§7a bounded constants)
  dev_key.h           # GENERATED bench key (never a deployment key)
  test_vectors.h      # GENERATED conformance vectors from the Python codec
tools/
  gen_vectors.py      # regenerate the two headers from esw/if4.py
  bench_send.py       # host bench: refresh / forge / replay / low-seq re-assert
```

## Build · flash · bench

```
cd firmware/sign-controller
python -m platformio run                       # build (env: yolouno)
python -m platformio run -t upload             # flash over USB-C
python -m platformio device monitor -b 115200  # watch BOOT/VECTORS/STAT/SIGN lines

python tools/bench_send.py --port COM5         # run the C1..C7 bench sequence
python tools/bench_send.py --port COM5 --soak  # continuous refresh (demo / Tier-2 soak)
```

**The board (OhStem Yolo:UNO):** ESP32-S3 **N16R8** (16 MB QIO flash, 8 MB OPI
PSRAM), **native USB-C** (`0x303A:0x1001` — no UART-bridge driver needed), BOOT
button on GPIO0. There is no registry entry for it, so
[`boards/esp32s3-n16r8.json`](boards/esp32s3-n16r8.json) mirrors OhStem's own
PlatformIO board definition (from `ohstem-public/coreiot-client-sdk`).

The sign output is `ESW_SIGN_GPIO` (HIGH = SHOW) plus the onboard RGB pixel
(red = SHOW, dark = blank). On the YoloUno the defaults are **zero-wiring**:
sign = GPIO48 (the onboard D13 LED — shares SPI SCK, so move it to a Grove pin
like D2 = GPIO5 when the LoRa SX1276 takes the SPI bus) and pixel = GPIO45
(the onboard WS2812). Pins are `build_flags` in `platformio.ini`.

## Bench serial protocol (115200, one line per message)

| Line | Meaning |
|---|---|
| `<58 hex chars>` | one 29-byte IF-4 frame (other lengths hit the `len` reject on purpose) |
| `T<ms>` | edge clock sync — the doc 10 "Time" edge-synced option; GNSS/PPS replaces it in the rig |
| `K<64 hex>` | provision a 32-byte link key into NVS (bench provisioning) |
| `KDEV` | revert to the built-in dev key |
| `V` / `S` | re-run the boot vectors / print an immediate `STAT` line |

Without a clock sync the freshness guard rejects genuine frames as `stale` —
the fail-safe direction (doc 10 §6 "Time"): the sign stays dark, loudly.

## What is scaffold vs. what is real

**Real and final in shape:** the verify core, the two anti-replay guards, the
recompute-from-freshness blank rule, the reject counters (observability), NVS
key storage, the conformance vectors.

**Bench stand-ins, by design:**
- **Transport** — hex lines over USB serial. The production bearer (LoRa SX1276
  at 433/920 MHz) is the open [ADR-0014](../../docs/adr/ADR-0014-sign-link-bearer.md)
  bench decision; when it lands, radio receive replaces `poll_serial()`'s line
  reader and **nothing else may change**.
- **Clock** — `T<ms>` host sync stands in for GNSS/PPS or an edge-synced clock
  (doc 10 §8.4 open handoff). The no-clock fallback (persistent seq, drop
  freshness) is deliberately **not** implemented — it trades away the reconnect
  guard and needs the flash-wear design doc 10 defers.
- **Key provisioning** — `K<64hex>` over the bench link. The real mechanism
  (out-of-band, rotatable, flash-encrypted NVS) is the doc 10 §8.3 open handoff.
- **Sign panel** — a GPIO + pixel. The LED-matrix drive and the IF-3 read-back
  needed for conformance C8 (wedged-panel detection) arrive with the panel
  hardware.

## Conformance status (doc 10 §7)

| Row | Where it's proven |
|---|---|
| C1 valid refresh → lit steady | `bench_send.py` |
| C2 edge dead → blank ≤ `T_signhold` | `bench_send.py` (stop-sending stimulus) |
| C3 edge power-off → blank | **physical rig** (same code path as C2) |
| C4 link cut → blank | `bench_send.py` (same stimulus as C2 on this bench) |
| C5 wrong-key frames → never lights | `bench_send.py` + boot vectors |
| C6 replayed frame → never re-lights | `bench_send.py` + boot vectors |
| C7 rebooted edge (low seq) → re-asserts | `bench_send.py` + boot vectors |
| C8 wedged panel → IF-3 read-back reports | **blocked on panel hardware** |
