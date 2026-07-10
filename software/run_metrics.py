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

import json
import os
import shutil
import sys
import tempfile

# Put software/ on the import path on both CPython and MicroPython. mpy's `os` has no
# `os.path`, so derive this script's directory from __file__ by hand -- uniform across
# runtimes, no host-only branch, so `micropython <board>.py` runs too (ADR-0015 D3).
_here = __file__
_cut = _here.rfind("/")
_bs = _here.rfind("\\")
if _bs > _cut:
    _cut = _bs
sys.path.insert(0, _here[:_cut] if _cut >= 0 else ".")

from harness import evidence, metrics
from harness.devices import FileCapture
from harness.rig import drive
from harness.runner import run_scenario
from harness.store import FileStore
from scenarios.app_cases import EVIDENCE_CASE
from scenarios.evidence_cases import EVIDENCE

_SHA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


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

    # A warning that flaps within ONE hazard (occlusion blip / forced clear + re-confirm) is a
    # continuity story, not a false activation: both intervals overlap the hazard -> fp == 0.
    # (Regression: the matched-first-only scoring counted the re-activation as an FP and
    # inflated the doc 01 §5 FA-per-hour rate.)
    sc2 = metrics.score_scenario([[0.0, 20.0]], [[2.0, 8.0], [10.0, 18.0]])
    if (sc2["tp"], sc2["fn"], sc2["fp"]) != (1, 0, 0):
        fails.append(("score_scenario re-activation within a hazard is not FP", (1, 0, 0),
                      (sc2["tp"], sc2["fn"], sc2["fp"])))

    # One warning interval spanning TWO hazards: the second hazard's onset finds the warning
    # already ON -> its detection latency is 0, never negative (a negative latency would
    # deflate the mean and could mask a real max). (Regression: warn_start - onset went -11.)
    sc3 = metrics.score_scenario([[0.0, 10.0], [12.0, 20.0]], [[1.0, 15.0]])
    if (sc3["tp"], sc3["fn"], sc3["fp"]) != (2, 0, 0) or sc3["latencies"] != [1.0, 0.0]:
        fails.append(("score_scenario spanning-warn latency clamps to 0",
                      ((2, 0, 0), [1.0, 0.0]),
                      ((sc3["tp"], sc3["fn"], sc3["fp"]), sc3["latencies"])))

    # aggregate: false-activation per-100-scenarios and per-hour.
    agg = metrics.aggregate([{"tp": 4, "fn": 0, "fp": 1, "latencies": [5.0]}],
                            n_scenarios=5, total_hours=0.5)
    if not (_approx(agg["fa_per_100_scenarios"], 20.0) and _approx(agg["fa_per_hour"], 2.0)):
        fails.append(("aggregate rates (per-100, per-hour)", (20.0, 2.0),
                      (agg["fa_per_100_scenarios"], agg["fa_per_hour"])))
    return fails


def _write_gt(d, tier, sha, hazards, t_offset=0.0):
    gt = {"tier": tier, "hazards": hazards, "t_offset": t_offset, "notes": "generated by Level-D"}
    if sha:
        gt["model_sha256"] = sha
    with open(os.path.join(d, "ground_truth.json"), "w", encoding="utf-8") as f:
        json.dump(gt, f)


def _make_session(tmp, name, case, tier, sha, hazards):
    """Produce a session directory by RUNNING the real EdgeApp -- FileStore writes evidence.log and
    FileCapture writes capture.jsonl in exactly the format the K230 writes. The scorer is therefore
    tested against logs the device produces, not against a fixture written to satisfy the reader."""
    d = os.path.join(tmp, name)
    os.makedirs(d)
    drive(case, store=FileStore(os.path.join(d, "evidence")),
          capture=FileCapture(os.path.join(d, "capture.jsonl")))
    _write_gt(d, tier, sha, hazards)
    return evidence.Session(d)


def _has(blockers, needle):
    return any(needle in b for b in blockers)


def _device_log_tests():
    """The offline scorer (harness/evidence.py): can it read what a unit writes, and does it refuse
    to turn a degraded capture into an acceptance claim?"""
    fails = []
    tmp = tempfile.mkdtemp()
    try:
        # -- a clean, acceptance-grade session: real tier, pinned model, all capabilities present.
        clean = _make_session(tmp, "bench-clean", EVIDENCE_CASE, "real-staged", _SHA, [[1.0, 12.0]])
        if clean.boot is None or not clean.records or not clean.ticks:
            fails.append(("session reads both device logs + boot record", True, False))
        blk = evidence.blockers(clean)
        if blk:
            fails.append(("clean session has no blockers", [], blk))
        sc = metrics.score_scenario(clean.oracle(), clean.warn_intervals())
        if (sc["tp"], sc["fn"], sc["fp"]) != (1, 0, 0):
            fails.append(("clean session scores TP", (1, 0, 0), (sc["tp"], sc["fn"], sc["fp"])))
        obs, gaps, _ = clean.observed_seconds()
        if not (10.5 <= obs <= 12.5) or gaps:                # 12 s run, 1 Hz heartbeat, no outage
            fails.append(("observed seconds ~ run duration, no gaps", "~12s/0", (obs, gaps)))
        text, n = evidence.report([clean])
        if n or "VERDICT: ACCEPTANCE-GRADE" not in text:
            fails.append(("clean session reports acceptance-grade", 0, n))

        # -- the same run, degraded four ways. Each is a capture that LOOKS fine: the sign lit on
        #    the car, the numbers compute. Each is also a number nobody may report.
        degraded_case = dict(EVIDENCE_CASE)
        degraded_case["gnss"] = False
        degraded_case["absolute_time"] = False
        degraded_case["sign_readback"] = False
        dg = _make_session(tmp, "bench-degraded", degraded_case, "synthetic", None, [[1.0, 12.0]])
        dblk = evidence.blockers(dg)
        for needle in ("hard rule", "detector unpinned", "no IF-3 read-back", "no absolute time"):
            if not _has(dblk, needle):
                fails.append(("degraded session blocks on %r" % needle, True, dblk))
        text, n = evidence.report([dg])
        if not n or "NOT ACCEPTANCE-GRADE" not in text:
            fails.append(("degraded session reports NOT acceptance-grade", ">0", n))

        # -- real and synthetic are never pooled: the recall claim must come from real captures only.
        text, _ = evidence.report([clean, dg])
        if "scored separately and NOT pooled" not in text:
            fails.append(("synthetic sessions are not pooled into the recall claim", True, False))

        # -- a heartbeat gap is an OUTAGE: the box was dark, and those seconds never happened. Left
        #    in the denominator they would silently deflate the false-activation-per-hour rate.
        gap_dir = os.path.join(tmp, "bench-gap")
        os.makedirs(gap_dir)
        beats = []
        for i in range(3):                                   # 0,1,2 s
            beats.append({"seq": i, "rec": {"if": 6, "ts": float(i), "cfg_ver": "aa"}})
        for i in range(3):                                   # 62,63,64 s -- a 60 s hole
            beats.append({"seq": 3 + i, "rec": {"if": 6, "ts": 62.0 + i, "cfg_ver": "aa"}})
        with open(os.path.join(gap_dir, "evidence.log"), "w", encoding="utf-8") as f:
            for b in beats:
                f.write(json.dumps(b) + "\n")
        open(os.path.join(gap_dir, "capture.jsonl"), "w").close()
        _write_gt(gap_dir, "real-field", _SHA, [[0.0, 1.0]])
        gs = evidence.Session(gap_dir)
        obs, gaps, longest = gs.observed_seconds()
        if not (3.9 <= obs <= 4.1) or gaps != 1 or not (59.0 <= longest <= 61.0):
            fails.append(("heartbeat gap excluded from observed time", (4.0, 1, 60.0),
                          (obs, gaps, longest)))

        # -- the two logs must corroborate each other. A lit tick the IF-7 stream never accounts for
        #    means a real activation went unscored, and the reducer only ever reads the IF-7 stream.
        doctored = os.path.join(tmp, "bench-clean", "capture.jsonl")
        with open(doctored, "a", encoding="utf-8") as f:
            f.write(json.dumps({"type": "tick", "ts": 999.0, "sign_on": True, "dets": []}) + "\n")
        dsn = evidence.Session(os.path.join(tmp, "bench-clean"))
        if not _has(evidence.blockers(dsn), "no IF-7 warning interval"):
            fails.append(("cross-check catches a lit tick with no warning interval", True,
                          evidence.blockers(dsn)))

        # -- a torn tail from a power loss mid-append is counted and blocks, never crashes.
        with open(doctored, "a", encoding="utf-8") as f:
            f.write('{"type": "tick", "ts": 1000.0, "sign_on"')
        tsn = evidence.Session(os.path.join(tmp, "bench-clean"))
        if tsn.capture_corrupt != 1 or not _has(evidence.blockers(tsn), "torn line"):
            fails.append(("torn line counted and blocks", 1, tsn.capture_corrupt))

        # -- an unannotated capture is not evidence.
        bare = os.path.join(tmp, "bench-bare")
        os.makedirs(bare)
        try:
            evidence.Session(bare)
            fails.append(("session without ground_truth.json is rejected", "ValueError", "accepted"))
        except ValueError:
            pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
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

    dfails = _device_log_tests()
    if dfails:
        print("DEVICE-LOG SCORER TESTS: FAIL")
        for f in dfails:
            print("  {}: expected {!r} got {!r}".format(f[0], f[1], f[2]))
        return 1
    print("device-log scorer tests: PASS  (harness/evidence.py; CLI = tools/score_capture.py)")
    print("")
    print(_report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
