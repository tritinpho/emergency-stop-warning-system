#!/usr/bin/env python3
# Level-D metrics board: (1) unit-test the acceptance-evidence reducer (harness/metrics.py), then
# (2) run the evidence scenario set through the REAL loop, collect the IF-7 event log, and print a
# sample acceptance-evidence report -- honestly tagged tier S (synthetic: it substantiates the
# MACHINERY and modelled false-trigger resistance, NOT a recall claim; the recall N must be real
# captures, doc 01 §5 / ADR-0007).
#
#   python software/run_metrics.py     (from the repo root)
#
# Exit 0 when the reducer unit tests pass; 1 otherwise. The report itself is informational --
# proving the pipeline is ready to ingest real staged/field captures.

import sys

# Put software/ on the import path on both CPython and MicroPython. mpy's `os` has no
# `os.path`, so derive this script's directory from __file__ by hand -- uniform across
# runtimes, no host-only branch, so `micropython <board>.py` runs too (ADR-0015 D3).
_here = __file__
_cut = _here.rfind("/")
_bs = _here.rfind("\\")
if _bs > _cut:
    _cut = _bs
sys.path.insert(0, _here[:_cut] if _cut >= 0 else ".")

from harness import metrics
from harness.runner import run_scenario
from scenarios.evidence_cases import EVIDENCE


def _approx(a, b, tol=1e-6):
    return abs(a - b) <= tol


def _unit_tests():
    """Pin the reducer math: exact for the discrete logic, property + loose anchors for Wilson."""
    fails = []

    # Wilson lower bound (95%) -- properties + loose anchors to doc 01 §5's reference points.
    if metrics.wilson_lower(0, 10) != 0.0:
        fails.append(("wilson 0/10 == 0", 0.0, metrics.wilson_lower(0, 10)))
    if metrics.wilson_lower(0, 0) != 0.0:
        fails.append(("wilson 0/0 == 0", 0.0, metrics.wilson_lower(0, 0)))
    if not (0.75 <= metrics.wilson_lower(19, 20) <= 0.78):        # doc's ~75% at 19/20
        fails.append(("wilson 19/20 in [.75,.78]", "~0.76", metrics.wilson_lower(19, 20)))
    if not (0.90 <= metrics.wilson_lower(190, 200) <= 0.92):      # ~200-event bar
        fails.append(("wilson 190/200 in [.90,.92]", "~0.91", metrics.wilson_lower(190, 200)))
    if not (metrics.wilson_lower(18, 20) < metrics.wilson_lower(19, 20) < 0.95):  # monotone, < point est
        fails.append(("wilson monotone/below-point", True, False))
    if not (0.0 < metrics.wilson_lower(4, 4) < 0.55):            # small-N -> weak bound (the honest point)
        fails.append(("wilson 4/4 weak", "0<x<0.55", metrics.wilson_lower(4, 4)))

    # warn_intervals from a synthetic IF-7 stream (activation -> clear/forced_clear).
    ev = [{"if": 7, "type": "activation", "ts": 2.0}, {"if": 7, "type": "clear", "ts": 9.0},
          {"if": 7, "type": "activation", "ts": 12.0}, {"if": 7, "type": "forced_clear", "ts": 15.0}]
    if metrics.warn_intervals(ev, 20.0) != [[2.0, 9.0], [12.0, 15.0]]:
        fails.append(("warn_intervals", [[2.0, 9.0], [12.0, 15.0]], metrics.warn_intervals(ev, 20.0)))
    if metrics.warn_intervals([{"if": 7, "type": "activation", "ts": 3.0}], 10.0) != [[3.0, 10.0]]:
        fails.append(("warn_intervals-open (stuck-ON closes at duration)", [[3.0, 10.0]], None))

    # score_scenario: one hazard detected (TP), one missed (FN), one spurious warn (FP).
    sc = metrics.score_scenario([[1.0, 5.0], [10.0, 14.0]], [[2.0, 6.0], [18.0, 19.0]])
    if (sc["tp"], sc["fn"], sc["fp"]) != (1, 1, 1):
        fails.append(("score_scenario tp/fn/fp", (1, 1, 1), (sc["tp"], sc["fn"], sc["fp"])))

    # aggregate: false-activation per-100-scenarios and per-hour.
    agg = metrics.aggregate([{"tp": 4, "fn": 0, "fp": 1, "latencies": [5.0]}],
                            n_scenarios=5, total_hours=0.5)
    if not (_approx(agg["fa_per_100_scenarios"], 20.0) and _approx(agg["fa_per_hour"], 2.0)):
        fails.append(("aggregate rates (per-100, per-hour)", (20.0, 2.0),
                      (agg["fa_per_100_scenarios"], agg["fa_per_hour"])))
    return fails


def _events_of(timeline):
    out = []
    for r in timeline:
        for e in r.get("events", []):
            out.append(e)
    return out


def _report():
    per = []
    total_hours = 0.0
    for ev in EVIDENCE:
        tl = run_scenario(ev)
        wi = metrics.warn_intervals(_events_of(tl), ev["duration"])
        per.append(metrics.score_scenario(ev["oracle"], wi))
        total_hours += ev["duration"] / 3600.0
    agg = metrics.aggregate(per, n_scenarios=len(EVIDENCE), total_hours=total_hours)
    return metrics.format_report(agg, tier="S (synthetic -- machinery + modelled false-trigger only)")


def main():
    print("")
    print("ESW Level-D metrics board -- acceptance-evidence reducer (ADR-0007 / doc 01 §5)")
    print("-" * 64)
    fails = _unit_tests()
    if fails:
        print("REDUCER UNIT TESTS: FAIL")
        for f in fails:
            print("  {}: expected {!r} got {!r}".format(f[0], f[1], f[2]))
        return 1
    print("reducer unit tests: PASS")
    print("")
    print(_report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
