#!/usr/bin/env python3
# K230 timing spike -- the gate on ADR-0015 D3 (MicroPython for the safety loop).
#
# WHY THIS EXISTS
#   The safety loop refreshes the sign SHOW every T_assert_refresh = 0.5 s; the
#   sign controller blanks if no fresh refresh arrives within T_signhold = 2.0 s.
#   If a MicroPython GC pause ever stalls the tick loop long enough to miss
#   refreshes for ~2 s, a live warning would wrongly blank. ADR-0015 chose
#   MicroPython on the bet that GC pauses are 40x+ below these budgets. This spike
#   MEASURES the worst-case tick stall + GC pause on the target so we can confirm
#   (or refute) that bet with a number instead of an assumption.
#
# HOW TO RUN
#   The GATING run is on the physical K230 -- a host run does NOT count (CPython's
#   GC is nothing like MicroPython's mark-sweep).
#     On the K230 (CanMV/MicroPython):
#       1. Copy this file to the board.
#       2. START THE REAL PERCEPTION LOAD FIRST (run your YOLO demo, e.g.
#          demo_yolo.py) so the CPU + KPU + heap are under realistic contention.
#       3. In a second CanMV session (or from main.py): run this file.
#       4. Read the VERDICT line at the end and paste it into ADR-0015 AI#1.
#     Host smoke-test (proves the script runs; NOT a substitute):
#       python software/spikes/k230_timing_spike.py
#
# VERDICT (worst single-tick stall vs T_assert_refresh = 500 ms)
#   PASS      < 50 ms    -> GC is a non-issue; MicroPython confirmed (ADR-0015 D3)
#   MARGINAL  50-250 ms  -> OK, but re-run under heavier load before locking D3
#   FAIL      >= 250 ms  -> investigate; consider the C-core fallback (ADR-0015 D3)
#
# MicroPython-safe subset (no enum / dataclasses / typing / f-strings-only-tricks).

import gc
import sys

# ---- portable timing + sleep (MicroPython ticks_us vs CPython perf_counter) ----
try:
    from time import ticks_us, ticks_diff, sleep_ms  # MicroPython

    def now_us():
        return ticks_us()

    def diff_us(a, b):
        return ticks_diff(b, a)
except ImportError:                                    # CPython
    import time

    _T0 = time.perf_counter()

    def now_us():
        return int((time.perf_counter() - _T0) * 1000000)

    def diff_us(a, b):
        return b - a

    def sleep_ms(ms):
        time.sleep(ms / 1000.0)


TICK_MS = 100          # 10 Hz fixed-rate tick (ADR-0015 D2)
N_TICKS = 300          # ~30 s soak; raise for a longer run
T_ASSERT_REFRESH_MS = 500
T_SIGNHOLD_MS = 2000
WARN_MS = 50           # 10% of T_assert_refresh
FAIL_MS = 250          # half of T_assert_refresh


def _work(state):
    # Mimic one state-machine tick's allocation footprint: build a few IF-2
    # observation dicts, touch the track set, churn some transient garbage.
    obs = []
    for i in range(4):
        obs.append({"track_id": "T%d" % i, "cls": "car", "in_roi": 1.0,
                    "speed_kph": 0.0, "sensor_source": "fused", "ts": state["t"]})
    tracks = state["tracks"]
    for o in obs:
        tr = tracks.get(o["track_id"])
        if tr is None:
            tr = {"stationary_since": state["t"], "confirmed": False, "absent_since": None}
            tracks[o["track_id"]] = tr
        tr["absent_since"] = None
    tmp = [o["speed_kph"] for o in obs] * 8
    s = 0.0
    for v in tmp:
        s += v
    state["t"] += TICK_MS / 1000.0
    return s


def _pct(sorted_list, p):
    if not sorted_list:
        return 0.0
    k = int((len(sorted_list) - 1) * p)
    return sorted_list[k]


def run(n_ticks=N_TICKS):
    gc.enable()
    state = {"t": 0.0, "tracks": {}}
    for _ in range(20):          # warm up caches / first-GC
        _work(state)

    stalls = []
    gc_pauses = []
    next_due = now_us()
    for i in range(n_ticks):
        start = now_us()
        _work(state)
        if i % 30 == 0:
            state["tracks"] = {}     # churn the heap so GC actually fires
        stalls.append(diff_us(start, now_us()) / 1000.0)
        if i % 50 == 0:              # sample explicit collection cost
            g0 = now_us()
            gc.collect()
            gc_pauses.append(diff_us(g0, now_us()) / 1000.0)
        next_due += TICK_MS * 1000
        remain = diff_us(now_us(), next_due)
        if remain > 0:
            sleep_ms(int(remain / 1000))
    return stalls, gc_pauses


def main():
    impl = sys.implementation.name
    stalls, gc_pauses = run()
    ss = sorted(stalls)
    worst = ss[-1]
    gc_worst = max(gc_pauses) if gc_pauses else 0.0
    over_warn = 0
    for v in stalls:
        if v > WARN_MS:
            over_warn += 1

    if worst < WARN_MS:
        verdict = "PASS"
    elif worst < FAIL_MS:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    print("")
    print("K230 timing spike -- ADR-0015 D3 gate")
    print("-" * 60)
    print("runtime           : %s" % impl)
    if impl != "micropython":
        print("  ** HOST SMOKE-TEST ONLY -- CPython GC != K230 MicroPython GC.")
        print("  ** The gating numbers must come from a run on the K230.")
    print("ticks             : %d at %d ms (%.1f s)" % (len(stalls), TICK_MS, len(stalls) * TICK_MS / 1000.0))
    print("budget            : T_assert_refresh=%d ms, T_signhold=%d ms" % (T_ASSERT_REFRESH_MS, T_SIGNHOLD_MS))
    print("tick stall p50    : %.3f ms" % _pct(ss, 0.50))
    print("tick stall p95    : %.3f ms" % _pct(ss, 0.95))
    print("tick stall p99    : %.3f ms" % _pct(ss, 0.99))
    print("tick stall MAX    : %.3f ms" % worst)
    print("ticks over %d ms   : %d / %d" % (WARN_MS, over_warn, len(stalls)))
    print("gc.collect() MAX  : %.3f ms" % gc_worst)
    print("-" * 60)
    print("VERDICT: %s  (max stall %.1f ms vs T_assert_refresh %d ms)" % (verdict, worst, T_ASSERT_REFRESH_MS))
    if verdict == "PASS":
        print("-> MicroPython confirmed for the safety loop (ADR-0015 D3).")
    elif verdict == "MARGINAL":
        print("-> Acceptable; re-run under heavier YOLO load before locking D3.")
    else:
        print("-> Investigate; consider the C-core fallback (ADR-0015 D3).")
    return 0 if verdict != "FAIL" else 1


if __name__ == "__main__":
    sys.exit(main())
