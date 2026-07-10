# Offline scorer for DEVICE evidence (ADR-0007, doc 01 §5) -- reads the logs a real unit writes
# and turns them into an acceptance-evidence report, or refuses to.
#
# harness/metrics.py does the arithmetic (recall, Wilson bound, false-activation, latency). It
# takes an IF-7 event stream and a ground-truth oracle, and in the sim both come from the same
# script. Neither is true of a real capture: the events come off an SD card written by a unit
# whose model, config and capabilities are whatever they happened to be, and the oracle comes from
# a human watching video. This module is what stands between those two facts and a number someone
# might put in a report.
#
# It does three things metrics.py cannot:
#
#   1. OBSERVED HOURS, not wall-clock hours. False activations per hour needs a denominator of
#      hours the unit was actually WATCHING. A dead box emits no heartbeats, so a gap in the IF-6
#      stream is an outage -- those hours never happened and must not dilute the FA rate.
#
#   2. PROVENANCE. Every record is fingerprinted (fw/cfg/model/calib, R10). If cfg_ver changes
#      mid-session, two different machines produced the events and their scores cannot be pooled.
#      If the detector is unpinned -- and today's is: /sdcard/kmodel/yolov8n_320.kmodel has no
#      recorded SHA-256 anywhere (firmware/k230-detector/models/README.md) -- then the report
#      describes a model nobody can identify, reproduce, or re-run.
#
#   3. CAPABILITY. EdgeApp writes a boot `capability` record naming what the unit could not do
#      (esw/app.py). A unit whose model cannot see `person` may not contribute to pedestrian
#      recall. A unit with no IF-3 read-back logged what it COMMANDED, not what a driver saw. A
#      unit with no absolute time has no clock the annotation can be aligned against.
#
# Any of these is a BLOCKER: the report still prints -- the numbers are useful for tuning -- but it
# is stamped NOT ACCEPTANCE-GRADE and the CLI exits non-zero. That is the deliberate answer to the
# open question in models/README.md: yes, the acceptance evidence refuses to run against an
# unpinned detector.
#
# Host-only (NOT shipped).

import json
import os

from harness import metrics

HEARTBEAT_PERIOD_S = 1.0        # esw/telemetry.py _HEARTBEAT_EVERY
GAP_TOL_PERIODS = 3.0           # a heartbeat gap wider than this is an outage, not jitter

REAL_TIERS = ("real-field", "real-staged")
# "host" = a REAL pretrained detector on REAL footage, but a host runtime (tools/host_yolo_loop.py).
# Distinct from "synthetic" (scripted detections) AND from the real tiers: it validates the
# pipeline -- adapter conventions, tracker association under real detector noise, dwell, IF-4
# cadence -- never the unit, whose INT8 kmodel, camera and optics all differ.
KNOWN_TIERS = REAL_TIERS + ("host", "synthetic")

_VERSION_KEYS = ("fw_ver", "cfg_ver", "model_ver", "calib_ver")


# ---------------------------------------------------------------------------- reading

def read_jsonl(path):
    """Every COMPLETE line. A torn tail from a power loss mid-append is skipped and counted, never
    a crash -- the same stance the store takes on load(). Returns (records, n_corrupt)."""
    if not os.path.exists(path):
        return [], 0
    out = []
    corrupt = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                corrupt += 1
    return out, corrupt


def _norm_hazards(raw, t_offset=0.0):
    """Ground truth as [[t0,t1], ...] or [{"t0":..,"t1":..,"cls":"person"}, ...] -> uniform dicts.
    `t_offset` shifts the annotator's timebase onto the unit's tick clock."""
    out = []
    for h in raw:
        if isinstance(h, dict):
            t0, t1, cls = h["t0"], h["t1"], h.get("cls", "vehicle")
        else:
            t0, t1, cls = h[0], h[1], "vehicle"
        out.append({"t0": t0 + t_offset, "t1": t1 + t_offset, "cls": cls})
    return out


class Session:
    """One capture session: a directory holding what a unit wrote plus what a human annotated.

        <dir>/evidence.log     IF-6/IF-7 records (the durable outbox; esw/sink.py)
        <dir>/capture.jsonl    per-tick raw detections + decision (esw/app.py capture backend)
        <dir>/ground_truth.json
    """

    def __init__(self, path):
        self.path = path
        self.id = os.path.basename(os.path.normpath(path))

        gt_path = os.path.join(path, "ground_truth.json")
        if not os.path.exists(gt_path):
            raise ValueError("%s: no ground_truth.json -- an unannotated capture is not evidence"
                             % self.id)
        with open(gt_path, "r", encoding="utf-8") as f:
            gt = json.load(f)
        self.tier = gt.get("tier", "synthetic")
        self.model_sha256 = gt.get("model_sha256")
        self.notes = gt.get("notes", "")
        self.hazards = _norm_hazards(gt.get("hazards", []), gt.get("t_offset", 0.0))

        wrapped, self.evidence_corrupt = read_jsonl(os.path.join(path, "evidence.log"))
        self.records = [w["rec"] for w in wrapped if "rec" in w]   # unwrap {"seq":..,"rec":..}
        self.ticks, self.capture_corrupt = read_jsonl(os.path.join(path, "capture.jsonl"))

        self.boot = None
        for r in self.records:
            if r.get("type") == "capability":
                self.boot = r
                break

    # -- derived facts ------------------------------------------------------

    def events(self):
        return [r for r in self.records if r.get("if") == 7]

    def heartbeats(self):
        return [r for r in self.records if r.get("if") == 6]

    def span(self):
        """(first, last) timestamp in the EVIDENCE stream. Deliberately not the capture file's
        span: warn_intervals() closes a still-open warning at `last`, so if the capture log could
        extend it, a spurious lit tick would retroactively place itself inside a warning and the
        cross-check that exists to catch it would pass. The IF-7 event stream is the authority on
        when the session's events ended; capture.jsonl is corroboration, never the ruler."""
        ts = [r["ts"] for r in self.records if "ts" in r]
        return (min(ts), max(ts)) if ts else (0.0, 0.0)

    def observed_seconds(self):
        """Seconds the unit was demonstrably WATCHING, from IF-6 heartbeat continuity.

        Wall-clock duration would count the hours a dead box spent dark, silently deflating the
        false-activation rate: the missing heartbeats ARE the outage (esw/telemetry.py gates on
        box-alive). Returns (seconds, n_gaps, longest_gap).

        Only the spans BETWEEN consecutive beats are credited, so a session with a single
        heartbeat observes zero seconds -- you cannot bound an interval from one sample. Erring
        short inflates the FA-per-hour rate, which is the safe direction to be wrong in."""
        ts = sorted(r["ts"] for r in self.heartbeats())
        if len(ts) < 2:
            return 0.0, 0, 0.0
        tol = HEARTBEAT_PERIOD_S * GAP_TOL_PERIODS
        total = 0.0
        gaps = 0
        longest = 0.0
        for i in range(1, len(ts)):
            dt = ts[i] - ts[i - 1]
            if dt <= tol:
                total += dt
            else:
                gaps += 1
                longest = max(longest, dt)
        return total, gaps, longest

    def provenance(self):
        """The version fingerprints seen across this session's records. More than one value for
        any key means the session spans a reconfiguration or a reflash: not one machine, not one
        pooled score."""
        seen = {k: set() for k in _VERSION_KEYS}
        for r in self.records:
            for k in _VERSION_KEYS:
                if r.get(k) is not None:
                    seen[k].add(r[k])
        out = {k: sorted(seen[k]) for k in _VERSION_KEYS}
        out["consistent"] = all(len(seen[k]) <= 1 for k in _VERSION_KEYS)
        return out

    def warn_intervals(self):
        _, last = self.span()
        return metrics.warn_intervals(self.events(), last)

    def oracle(self):
        return [[h["t0"], h["t1"]] for h in self.hazards]


# ---------------------------------------------------------------------------- cross-check

def cross_check(session):
    """Do the two logs tell the same story?

    The capture log always writes a tick whose sign state CHANGED (esw-app/backends.py
    `_interesting`), so every lamp transition survives subsampling. If capture shows the sign lit
    at some tick and the IF-7 stream has no warning interval covering it, one of the two logs is
    lying -- and since the reducer only ever reads the IF-7 stream, a silent disagreement here is
    exactly how a real activation goes unscored."""
    problems = []
    warns = session.warn_intervals()
    for t in session.ticks:
        if t.get("type") != "tick" or not t.get("sign_on"):
            continue
        ts = t["ts"]
        covered = any(w[0] <= ts <= w[1] for w in warns)
        if not covered:
            problems.append("capture shows sign ON at t=%.1fs with no IF-7 warning interval" % ts)
            break                                    # one is enough; they come in runs
    for w in warns:
        lit = [t for t in session.ticks
               if t.get("type") == "tick" and w[0] <= t.get("ts", -1) <= w[1] and t.get("sign_on")]
        if session.ticks and not lit:
            problems.append("IF-7 warning [%.1f, %.1f] with no lit tick in the capture log"
                            % (w[0], w[1]))
            break
    return problems


# ---------------------------------------------------------------------------- gates

def blockers(session):
    """Every reason this session's numbers are not an acceptance claim. Empty list = it is one."""
    out = []

    if session.tier not in KNOWN_TIERS:
        out.append("unknown tier %r (expected one of %s)" % (session.tier, list(KNOWN_TIERS)))
    elif session.tier == "host":
        out.append("tier 'host': a real detector on real footage, but a HOST runtime -- this "
                   "validates the pipeline, not the unit (the K230 runs an INT8 kmodel behind "
                   "different optics); acceptance needs device-tier captures")
    elif session.tier not in REAL_TIERS:
        out.append("tier '%s': recall from synthetic events measures simulator determinism, "
                   "not detection (doc 01 §5 hard rule)" % session.tier)

    if not session.hazards:
        out.append("no annotated hazards: nothing to score against")

    prov = session.provenance()
    if not prov["consistent"]:
        changed = [k for k in _VERSION_KEYS if len(prov[k]) > 1]
        out.append("version fingerprint changed mid-session (%s): two machines, one log"
                   % ", ".join(changed))
    if not session.model_sha256:
        out.append("detector unpinned: ground_truth.json declares no model_sha256, so the model "
                   "these numbers describe cannot be identified or re-run "
                   "(firmware/k230-detector/models/README.md)")

    boot = session.boot
    if boot is None:
        out.append("no boot capability record: the unit never stated what it could not do")
    else:
        if not boot.get("durable_evidence", True):
            out.append("unit booted without durable evidence: this log cannot be complete")
        if not boot.get("sign_readback", True):
            out.append("no IF-3 read-back: activation/clear events record what the unit COMMANDED, "
                       "not the lamp a driver saw (a wedged lamp is invisible, SC-24)")
        if not boot.get("absolute_time", True):
            out.append("no absolute time (GNSS/PPS): the log's timebase is seconds-since-boot, so "
                       "the annotation's alignment to it cannot be independently verified")
        if not boot.get("sees_person", True):
            for h in session.hazards:
                if h["cls"] == "person":
                    out.append("session annotates a `person` hazard but the loaded model cannot "
                               "see one (sees_person=False): this recall claim is unreachable")
                    break

    if session.evidence_corrupt:
        out.append("%d torn line(s) in evidence.log: the event stream has holes"
                   % session.evidence_corrupt)
    if session.capture_corrupt:
        out.append("%d torn line(s) in capture.jsonl" % session.capture_corrupt)

    out.extend(cross_check(session))
    return out


# ---------------------------------------------------------------------------- report

def _hms(seconds):
    s = int(seconds)
    return "%d:%02d:%02d" % (s // 3600, (s % 3600) // 60, s % 60)


def score_sessions(sessions):
    """Score each session and pool by tier. Real and synthetic are NEVER pooled together."""
    rows = []
    for s in sessions:
        sc = metrics.score_scenario(s.oracle(), s.warn_intervals())
        obs, gaps, longest = s.observed_seconds()
        rows.append({"session": s, "score": sc, "observed_s": obs, "gaps": gaps,
                     "longest_gap": longest, "blockers": blockers(s)})
    return rows


def _pool(rows, tiers):
    sel = [r for r in rows if r["session"].tier in tiers]
    if not sel:
        return None, 0.0, 0
    hours = sum(r["observed_s"] for r in sel) / 3600.0
    agg = metrics.aggregate([r["score"] for r in sel], n_scenarios=len(sel), total_hours=hours)
    return agg, hours, len(sel)


def report(sessions):
    """The full report. Returns (text, n_blockers)."""
    rows = score_sessions(sessions)
    n_blockers = sum(len(r["blockers"]) for r in rows)

    L = []
    L.append("DEVICE ACCEPTANCE-EVIDENCE REPORT")
    L.append("=" * 78)
    L.append("")
    L.append("{:<22} {:<14} {:>9} {:>4} {:>4} {:>4} {:>4} {:>9}".format(
        "session", "tier", "observed", "hz", "TP", "FN", "FP", "blockers"))
    L.append("-" * 78)
    for r in rows:
        s = r["session"]
        L.append("{:<22} {:<14} {:>9} {:>4} {:>4} {:>4} {:>4} {:>9}".format(
            s.id[:22], s.tier[:14], _hms(r["observed_s"]), len(s.hazards),
            r["score"]["tp"], r["score"]["fn"], r["score"]["fp"], len(r["blockers"]) or "-"))
        if r["gaps"]:
            L.append("  {:<20} {} heartbeat gap(s), longest {:.1f}s -- those seconds are NOT "
                     "counted as observed".format("", r["gaps"], r["longest_gap"]))
    L.append("")

    real_agg, real_hours, n_real = _pool(rows, REAL_TIERS)
    if real_agg:
        L.append(metrics.format_report(
            real_agg, tier="REAL captures ({} session(s), {} observed)".format(
                n_real, _hms(real_hours * 3600)),
            rate_label="per observed hour"))
    else:
        L.append("No real captures. There is no recall claim to make -- only synthetic or")
        L.append("host-tier sessions, which substantiate the machinery and the pipeline, not")
        L.append("the unit's detection (doc 01 §5).")
    L.append("")

    syn_agg, syn_hours, n_syn = _pool(rows, ("synthetic",))
    if syn_agg and real_agg:
        L.append("(%d synthetic session(s) scored separately and NOT pooled into the above: "
                 "recall %s)" % (n_syn, "{:.0%}".format(syn_agg["recall"])
                                 if syn_agg["recall"] is not None else "n/a"))
        L.append("")

    host_agg, host_hours, n_host = _pool(rows, ("host",))
    if host_agg:
        L.append("(%d host-tier session(s) scored separately and NOT pooled into any claim: a "
                 "real detector on a host runtime validates the pipeline, not the unit -- "
                 "recall %s over %s observed)"
                 % (n_host, "{:.0%}".format(host_agg["recall"])
                    if host_agg["recall"] is not None else "n/a", _hms(host_hours * 3600)))
        L.append("")

    if n_blockers:
        L.append("GATES -- why this is not (yet) an acceptance claim")
        L.append("-" * 78)
        for r in rows:
            if not r["blockers"]:
                continue
            L.append("  %s:" % r["session"].id)
            for b in r["blockers"]:
                L.append("    * %s" % b)
        L.append("")
        L.append("VERDICT: NOT ACCEPTANCE-GRADE (%d blocker(s) across %d session(s))"
                 % (n_blockers, len(rows)))
        L.append("The numbers above pool every session, blocked ones included. They are useful for")
        L.append("tuning. They are not a recall claim, and must not be reported as one.")
    else:
        L.append("VERDICT: ACCEPTANCE-GRADE -- every session is a real, pinned, capability-complete")
        L.append("capture with a consistent fingerprint and a corroborated event log.")
    return "\n".join(L), n_blockers
