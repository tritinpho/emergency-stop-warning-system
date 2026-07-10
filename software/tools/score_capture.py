#!/usr/bin/env python3
"""Score device capture sessions into an acceptance-evidence report (ADR-0007, doc 01 §5).

This is what you run against what came off the SD card.

    python software/tools/score_capture.py captures/bench-2026-07-11-a [more...]
    python software/tools/score_capture.py --allow-degraded captures/*

Each session is a directory:

    <session>/evidence.log       IF-6 heartbeats + IF-7 audit events (the durable outbox)
    <session>/capture.jsonl      per-tick raw detections + decision
    <session>/ground_truth.json  the human annotation -- see below

ground_truth.json:

    {
      "tier": "real-staged",              // real-field | real-staged | synthetic
      "model_sha256": "<64 hex>",         // of the kmodel that RAN. no hash -> no claim.
      "t_offset": 0.0,                    // annotator clock -> unit tick clock, seconds
      "hazards": [[12.5, 96.0],
                  {"t0": 130.0, "t1": 168.0, "cls": "person"}],
      "notes": "shoulder stop, dusk, light rain"
    }

EXIT CODE. Non-zero when any session is blocked -- an unpinned detector, a synthetic tier, a
capability the unit did not have, a fingerprint that changed mid-session, a torn log, or two logs
that disagree. The report still prints, because the numbers are useful for tuning; what it will
not do is let them be mistaken for an acceptance claim. `--allow-degraded` prints the same report
and exits 0, for when you know exactly why you are looking at degraded numbers.

Nothing here is shipped to the K230.
"""

import argparse
import sys

# Put software/ on the import path (see run_tests.py; this file is two levels down).
_here = __file__
_c1 = max(_here.rfind("/"), _here.rfind("\\"))
_toolsdir = _here[:_c1] if _c1 >= 0 else ""
_c2 = max(_toolsdir.rfind("/"), _toolsdir.rfind("\\"))
if _c2 >= 0:
    _swdir = _toolsdir[:_c2]
elif _toolsdir == "":
    _swdir = ".."
else:
    _swdir = "."
sys.path.insert(0, _swdir if _swdir != "" else ".")

from harness.evidence import Session, report


def main():
    ap = argparse.ArgumentParser(description="Score ESW device capture sessions.")
    ap.add_argument("sessions", nargs="+", help="session directories")
    ap.add_argument("--allow-degraded", action="store_true",
                    help="print the report and exit 0 even when sessions are blocked")
    args = ap.parse_args()

    sessions = []
    for path in args.sessions:
        try:
            sessions.append(Session(path))
        except (OSError, ValueError) as e:
            print("cannot read session %s: %s" % (path, e), file=sys.stderr)
            return 2

    text, n_blockers = report(sessions)
    print("")
    print(text)
    print("")
    if n_blockers and not args.allow_degraded:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
