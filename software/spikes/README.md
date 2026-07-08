# spikes/ — throwaway measurements that gate a decision

Small, self-contained scripts that answer one open question with a number. They
are **not** part of the SUT and do not ship.

> 🇻🇳 Phiên bản tiếng Việt: [README.vi.md](README.vi.md).

---

# K230 Timing-Spike Runbook — the ADR-0015 D3 gate

**Who runs it:** Nhóm ACLAB ELMS (hardware/firmware), on the physical K230.
**Who owns the decision:** software (Tin) — the result **confirms or refutes** ADR-0015 D3.
**Status:** blocked on board access. The tooling ([`k230_timing_spike.py`](k230_timing_spike.py)) is
ready and passes a host smoke-test; the **gating numbers must come from the K230** — CPython's GC is
nothing like MicroPython's, so a host PASS is **not** evidence.

## 1. Why this run exists (the decision at stake)

[ADR-0015 **D3**](../../docs/adr/ADR-0015-state-machine-implementation-strategy.md) bet that **one
byte-identical MicroPython codebase** runs the safety loop on both the host and the K230 — **no
separate C core**. That bet rests on one unproven assumption: that MicroPython's **stop-the-world GC
pause** never stalls the tick loop long enough to matter. It has never been measured on the board
under real load. This run replaces the assumption with a number.

- **PASS** → ship the single MicroPython codebase; close ADR-0015 AI#1 / ADR-0002 AI#3 / RQ-H4.
- **FAIL** → trigger the fallback: move the safety loop (state machine + SHOW refresh) to a **C core**
  (or the ESP32 at the sign end), keeping perception in MicroPython. The data shows *which* stage broke.

## 2. The budgets (why the thresholds are what they are)

The edge re-asserts the sign by **refreshing an authenticated SHOW frame**; the controller **blanks if
no fresh SHOW arrives in time** (the IF-4 dead-man's switch). From [`esw/params.py`](../esw/params.py)
(doc 02 §7a):

| Constant | Value | Meaning |
|---|---|---|
| tick period | **0.1 s** (10 Hz) | one fixed-rate safety-loop cycle (ADR-0015 D2) |
| `T_assert_refresh` | **0.5 s** | the edge emits a fresh SHOW at least this often |
| `T_signhold` | **2.0 s** | the sign blanks if no valid SHOW within this window |
| `T_watchdog` | **30 s** | independent stale-ON backstop |

**The safety factor is 4×:** refreshing every 0.5 s against a 2.0 s hold means the edge can miss
**three refreshes in a row** (~1.5 s) and the sign still stays correctly lit. For a GC pause to cause
a *wrong* outcome it must stall the loop **~1.5–2.0 s** — roughly **40–100× larger** than a typical
MicroPython GC pause (single- to low-tens of ms). The failure direction is **fail-safe**: a late
refresh causes a spurious **blank** (cry-wolf / availability loss), never a silent miss. The spike
measures how close we actually get.

## 3. What to measure

Under **real, sustained load**:
1. **Tick stall** — wall-clock to run one tick's work, including any GC pause mid-tick *(the script's number)*.
2. **GC pause** — a `gc.collect()` stop-the-world pause under heap pressure.
3. **Refresh gap** *(definitive, Tier 2)* — the actual time between consecutive SHOW frames leaving the edge; this is what the dead-man's switch sees.

## 4. Procedure

**Prerequisites:** a physical **K230** (CanMV/MicroPython) with the shipped `esw/` flashed; the
production **`kmodel`** (YOLO) + a camera feed (or looped representative video) so the KPU/CPU/heap are
under **real contention**, not idle. Record: K230 clock, RAM/PSRAM, CanMV/mpy version, `kmodel` size, FPS.

### Tier 1 — the spike script (quick)
Measures the safety-loop tick's own GC stalls under separate YOLO contention.
1. Copy [`k230_timing_spike.py`](k230_timing_spike.py) to the board.
2. **Start the YOLO demo first** (realistic KPU/CPU/heap contention).
3. Run the spike in a second CanMV session (or from `main.py`).
4. For a fuller picture raise `N_TICKS` (top of the script) from 300 (~30 s) to **~18000 (~30 min)** and re-run — slow GC / fragmentation only shows over a soak.
5. Record the printed table + **VERDICT** line.

### Tier 2 — integrated-loop instrumentation (definitive)
The gold-standard gate: measure the **real deployed loop**, not a proxy.
1. In the integrated firmware (YOLO → perception → state machine → actuator), timestamp **every emitted SHOW frame**.
2. Over a **≥ 2 h soak** with a live scene (include a **multi-vehicle burst** to stress allocation), log: **max inter-SHOW gap**, tick-interval jitter (max / p99 / p999), max `gc.collect()` pause.
3. If possible, instrument the **ESP32 sign controller** to log any actual **blank event** (refresh gap > `T_signhold`) — the ground-truth safety check.

## 5. Acceptance thresholds

The script's verdict keys on the **worst tick stall vs `T_assert_refresh` (500 ms)** — deliberately
conservative (a stall under one refresh interval can never approach the 2 s hold):

| Metric | PASS (confirm D3) | MARGINAL (investigate / re-soak) | FAIL (fallback) |
|---|---|---|---|
| **Max tick stall** *(script VERDICT)* | < **50 ms** | 50 – 250 ms | ≥ **250 ms** |
| **Max `gc.collect()` pause** | < 50 ms | 50 – 200 ms | > 200 ms |
| **Max inter-SHOW gap** *(Tier 2)* | < **1.0 s** (≥ 2× margin) | 1.0 – 1.8 s | ≥ 1.8 s |
| **Tick-interval jitter (max)** | < 0.2 s (never miss 2 ticks) | 0.2 – 0.5 s | > 0.5 s sustained |
| **Spurious blank** *(Tier 2)* | **none** | — | **any** |

**Hard gate:** any observed spurious blank, or a max inter-SHOW gap ≥ `T_signhold` (2.0 s), is an
automatic **FAIL** regardless of the other numbers. A **MARGINAL** result → re-run under heavier load
and a longer soak before locking D3.

## 6. Interpreting the result → the decision

- **PASS** → MicroPython confirmed for the safety loop. Ship the single byte-identical codebase; mark ADR-0015 D3 **validated**; close ADR-0002 AI#3 / RQ-H4.
- **MARGINAL** → acceptable but not locked. Re-soak (§4, ≥ 30 min / ≥ 2 h) under heavier scene load; if still marginal, plan the fallback.
- **FAIL** → **C-core fallback**: keep perception (YOLO + tracker) in MicroPython, move the **state machine + actuator refresh** to a C module or a dedicated MCU (the ESP32 already holds the dead-man's switch). The spike breakdown (tick stall vs GC pause vs stage) shows exactly what to move.

Either way, the outcome is **a number in the ADR**, not an assumption.

## 7. Report back (paste this filled in)

```
K230 timing spike — result
  board          : K230 @ ____ MHz, ____ MB RAM, CanMV/mpy ____
  kmodel / FPS   : ________________  @ ____ FPS
  run duration   : Tier 1 ticks = ____ ; Tier 2 soak = ____ h
  YOLO running   : yes / no   scene: ____ (n tracks, bursts?)

  tick stall  p50 / p95 / p99 / MAX : ____ / ____ / ____ / ____ ms
  ticks over 50 ms                  : ____ / ____
  gc.collect() MAX                  : ____ ms
  Tier 2 — max inter-SHOW gap       : ____ ms   (budget T_signhold = 2000 ms)
  Tier 2 — spurious blank observed  : none / ____
  VERDICT (script)                  : PASS / MARGINAL / FAIL
```

Attach the raw spike log (and the Tier-2 SHOW-gap log) to the ADR-0015 AI#1 tracking item.

## 8. Thuật ngữ (VI glossary)

| EN | VI |
|---|---|
| timing spike | phép đo thời gian thực thi (spike) |
| safety loop / tick | vòng lặp an toàn / nhịp (10 Hz) |
| GC pause (stop-the-world) | khoảng dừng thu gom bộ nhớ (dừng toàn bộ) |
| refresh (SHOW frame) | làm mới (khung SHOW) |
| sign-hold window / blank | cửa sổ giữ biển / làm trống |
| dead-man's switch | cơ chế tự ngắt an toàn |
| soak (test) | chạy bền (dài giờ) |
| C-core fallback | phương án dự phòng lõi C |

## References
- [ADR-0015 — state-machine implementation strategy](../../docs/adr/ADR-0015-state-machine-implementation-strategy.md) (D2 tick, **D3** MicroPython)
- [doc 09 — Software→Hardware handoff](../../docs/09-software-hardware-handoff.md) (RQ-H4 latency/power bench)
- [`k230_timing_spike.py`](k230_timing_spike.py) — the runnable spike
