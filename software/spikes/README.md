# spikes/ — throwaway measurements that gate a decision

Small, self-contained scripts that answer one open question with a number. They
are **not** part of the SUT and do not ship.

## `k230_timing_spike.py` — gates ADR-0015 D3 (MicroPython for the safety loop)

**Question:** do MicroPython GC pauses on the K230 stay far below the safety
timers (`T_assert_refresh` = 0.5 s, `T_signhold` = 2 s), so the tick loop never
stalls long enough to wrongly blank a live warning?

**Run it on the K230 (this is the gating run):**
1. Copy `k230_timing_spike.py` to the board.
2. **Start the real perception load first** (your YOLO demo, e.g. `demo_yolo.py`)
   so the CPU/KPU/heap are under realistic contention.
3. Run the spike in a second CanMV session (or from `main.py`).
4. Paste the `VERDICT:` line into **[ADR-0015](../../docs/adr/ADR-0015-state-machine-implementation-strategy.md) AI#1**.

**Verdict thresholds** (worst single-tick stall vs `T_assert_refresh` = 500 ms):

| Result | Max stall | Meaning |
|--------|-----------|---------|
| **PASS** | < 50 ms | GC is a non-issue → MicroPython confirmed (D3) |
| **MARGINAL** | 50–250 ms | OK; re-run under heavier load before locking D3 |
| **FAIL** | ≥ 250 ms | Investigate; consider the C-core fallback (D3) |

**Host smoke-test** (`python software/spikes/k230_timing_spike.py`) only proves
the script runs — CPython's GC is nothing like MicroPython's, so a host PASS is
**not** evidence for D3. Only a K230 run counts.
