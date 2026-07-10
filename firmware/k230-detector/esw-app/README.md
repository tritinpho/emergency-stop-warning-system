# `esw-app` — the K230 device entrypoint

The first thing that runs the shipped [`software/esw/`](../../../software/esw/) subset on real
hardware. It constructs the same [`esw.app.EdgeApp`](../../../software/esw/app.py) the Level-H
board constructs, hands it device backends instead of host fakes, and ticks it at 10 Hz.

```
detector.py   the K230 YOLO detector as an IF-1 backend (mirrors the vendored k230/main.py core)
backends.py   radio (IF-4 over UART), clock, durable store (SD), capture log
main.py       wiring + the 10 Hz loop + tick-overrun accounting
```

**Status: written, never run.** No K230 is in hand ([doc 11 §5](../../../docs/11-dev-environment-setup.md)).
`EdgeApp` itself runs under the real MicroPython unix port in CI, so the loop, the state machine,
the perception stage and the IF-4 codec are runtime-proven; `detector.py` and `backends.py` import
CanMV modules (`libs.PipeLine`, `machine.UART`, `nncase_runtime`) that only exist on the board and
are therefore **unexercised**. Expect to debug them on first bring-up.

## Before it will boot

Two files are **required** and neither has a default — the unit refuses to start without them.

| File | Contents | Why no default |
|---|---|---|
| `/sdcard/esw/calib.json` | `{"H": [[…3×3…]], "roi": [[x,y],…]}` | An identity `H` is meaningful only for a synthetic top-down scene. Falling back to it on a real camera gates the ROI in **pixels** while the footprint model works in **metres**: every decision wrong, nothing visibly broken. |
| `/sdcard/esw/secrets.json` | `{"master": "<64 hex>", "site_id": "…"}` | The IF-4 link key is derived from this per site and per channel. The vendored ESP32 code shipped a Wi-Fi password and a CoreIoT token in git; both are public now (ADR-0016 backlog #6). |

Copy `software/esw/` to `/sdcard/esw/` and this directory to `/sdcard/esw-app/`.

## What it prints at boot

The capability report, before the first tick. A capability that reads `False` is a safety claim
this unit **cannot make** — and on today's hardware three of them do:

- `sign_readback` → only if the ESP32's `SIGN on/off` lines are wired back on the UART. Without it
  a physically wedged lamp (SC-24) is undetectable.
- `absolute_time` → **False on this build.** There is no GNSS/PPS receiver (RQ-H3 unmet), so IF-4
  frames are stamped with the tick clock and the controller is put on that same clock via the
  doc 10 `T<ms>` edge-sync line. The unit runs permanently time-degraded, loudly.
- `sees_person` / `per_class_footprint` → `False` if a single-class model is loaded, which would
  leave the sign working for cars while the unit is blind to pedestrians.

## The IF-4 bearer

Today: hex-encoded frames over the bench UART to
[`firmware/sign-controller`](../../sign-controller/README.md). LoRa (SX1276, ADR-0014) is a
drop-in — the same 29 bytes, sent by radio — and is deliberately unwritten until the ADR-0014
gating tests resolve (bench airtime, regulatory duty class, range at 25 mW ERP).

Frames are transmitted at `T_assert_refresh` (0.5 s), **not** at the 10 Hz tick: the dead-man's
window (`T_signhold` 2.0 s) only ever needed a 4× margin, and a per-tick transmit would exceed the
433 MHz duty budget five-fold while the lamp looked identical. Pinned by AP-11.

## Tick accounting is the ADR-0015 D3 evidence

`main.py` counts loop overruns and prints `[TICK] n=… overruns=… worst=…ms` once a minute. A
MicroPython GC pause that pushes the loop past `T_assert_refresh` eats the margin before
`T_signhold` blanks the sign. An overrun is fail-safe, never a silent miss — but a soak reporting
a worst overrun anywhere near 2000 ms is the FAIL condition in
[`software/spikes/README.md`](../../../software/spikes/README.md), which is the runbook to follow
once a board is in hand.
