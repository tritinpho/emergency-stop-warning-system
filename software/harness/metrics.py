# Acceptance-evidence reducer (ADR-0007, doc 01 §5, doc 07 §4) -- the OFFLINE analysis that turns
# an IF-7 event log + a ground-truth oracle into the acceptance metrics: recall (with a Wilson
# lower bound), false activation (per-100-scenarios AND per-hour), and detection latency.
#
# Host-only (NOT shipped): it runs over collected logs, so full Python is fine. The SUT emits the
# events (esw/telemetry.py); this consumes them exactly as the offline pipeline will over real
# bench/field captures.
#
# THE HARD RULE (doc 01 §5, doc 07 §1): recall + a Wilson bound computed from SYNTHETIC events the
# loop itself consumes measures the simulator's determinism, not real detection. So recall from
# synthetic runs is tagged S and is NOT a recall claim -- the machinery is real, the number is not.

import math

from esw.telemetry import CLEAR_TYPES


def wilson_lower(k, n, z=1.96):
    """Lower bound of the Wilson score interval for k successes in n trials (default 95%)."""
    if n == 0:
        return 0.0
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    lo = center - margin
    return lo if lo > 0.0 else 0.0


def warn_intervals(events, duration):
    """Reconstruct [on, off] warning intervals from an IF-7 event stream (activation -> clear).
    An interval still open at the end of the log (e.g. a stuck-ON sign) closes at `duration`."""
    intervals = []
    on = None
    for e in events:
        if e.get("if") != 7:
            continue
        if e["type"] == "activation" and on is None:
            on = e["ts"]
        elif e["type"] in CLEAR_TYPES and on is not None:
            intervals.append([on, e["ts"]])
            on = None
    if on is not None:
        intervals.append([on, duration])
    return intervals


def score_scenario(oracle, warns):
    """Classify one scenario. `oracle` = list of [onset, end] intervals where a genuine warnable
    hazard is present (ground truth from the script, INDEPENDENT of the SUT). Returns tp/fn/fp +
    detection latencies.

    A hazard interval with an overlapping warning = TP (detected); with none = FN (missed). A
    warning is an FP (false activation) only if it overlaps NO hazard -- a warning that flaps
    off/on WITHIN one hazard (occlusion blip, forced clear + re-confirm) is a latency/continuity
    story, not a false activation, so it must not inflate the doc 01 §5 FA rates. A correct
    occlusion hold overlaps the hazard, so it scores TP, never a clear-latency failure (doc 07 §4)."""
    tp = fn = 0
    latencies = []
    for hz in oracle:
        found = None
        for i, w in enumerate(warns):
            if w[0] < hz[1] and w[1] > hz[0]:          # any overlap
                found = i
                break
        if found is None:
            fn += 1
        else:
            tp += 1
            latencies.append(warns[found][0] - hz[0])  # warning ON - hazard onset
    fp = 0
    for w in warns:
        hit = False
        for hz in oracle:
            if w[0] < hz[1] and w[1] > hz[0]:          # any overlap with any hazard
                hit = True
                break
        if not hit:
            fp += 1                                    # warned where nothing warnable was
    return {"tp": tp, "fn": fn, "fp": fp, "latencies": latencies}


def aggregate(per_scenario, n_scenarios, total_hours):
    """Combine per-scenario scores into the doc 01 §5 rate metrics."""
    tp = sum(s["tp"] for s in per_scenario)
    fn = sum(s["fn"] for s in per_scenario)
    fp = sum(s["fp"] for s in per_scenario)
    lat = [x for s in per_scenario for x in s["latencies"]]
    n_pos = tp + fn
    return {
        "tp": tp, "fn": fn, "fp": fp, "n_positives": n_pos,
        "recall": (tp / n_pos) if n_pos else None,
        "recall_wilson_lo": wilson_lower(tp, n_pos) if n_pos else None,
        "fa_per_100_scenarios": (fp / n_scenarios * 100.0) if n_scenarios else None,
        "fa_per_hour": (fp / total_hours) if total_hours else None,
        "max_latency": max(lat) if lat else None,
        "mean_latency": (sum(lat) / len(lat)) if lat else None,
    }


def format_report(agg, tier="S (synthetic)"):
    """A human-readable acceptance-evidence report, honestly tagged by tier."""
    L = []
    L.append("ACCEPTANCE-EVIDENCE REPORT  [tier: {}]".format(tier))
    L.append("-" * 64)
    L.append("Positive events (N)       : {}".format(agg["n_positives"]))
    if agg["recall"] is not None:
        L.append("Recall                    : {:.1f}%  ({}/{})".format(
            agg["recall"] * 100, agg["tp"], agg["n_positives"]))
        L.append("  Wilson 95% lower bound  : {:.1f}%".format(agg["recall_wilson_lo"] * 100))
    L.append("False activations         : {}".format(agg["fp"]))
    if agg["fa_per_100_scenarios"] is not None:
        L.append("  per 100 scenarios       : {:.2f}".format(agg["fa_per_100_scenarios"]))
    if agg["fa_per_hour"] is not None:
        L.append("  per sim-hour            : {:.2f}".format(agg["fa_per_hour"]))
    if agg["max_latency"] is not None:
        L.append("Detection latency         : mean {:.2f}s  max {:.2f}s".format(
            agg["mean_latency"], agg["max_latency"]))
    L.append("-" * 64)
    if tier.startswith("S"):
        L.append("NOTE: tier S -- synthetic runs substantiate the MACHINERY and modelled")
        L.append("false-trigger resistance ONLY. Recall from synthetic events is NOT a recall")
        L.append("claim (doc 01 §5 hard rule): the recall N must be REAL captures. Note how the")
        L.append("Wilson bound stays weak until N is large -- this report shows the pipeline is")
        L.append("ready to ingest real staged/field captures and report the bound honestly.")
    return "\n".join(L)
