#!/usr/bin/env python3
# Level-A harness entrypoint: run the SC-01..30 board.
#
#   python software/run_tests.py            (from the repo root)
#   python run_tests.py                     (from software/)
#   micropython run_tests.py                (MicroPython unix port)
#
# Exit code 0 when the harness is healthy: every "impl" scenario passes and every
# "xfail" scenario still fails for its stated reason. A surprise (an impl fail or
# an xfail that started passing) exits 1 -- an impl regression, or "flip xfail->impl".

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scenarios.catalogue import SCENARIOS
from harness.runner import run_scenario, evaluate


def main():
    n_pass = n_xfail = n_todo = 0
    surprises = []
    print("")
    print("ESW Level-A harness -- SC-01..30 scenario board")
    print("-" * 68)
    for sc in SCENARIOS:
        sid = sc["id"]
        status = sc["status"]
        title = sc["title"]
        if status == "todo":
            n_todo += 1
            print("{:<6} {:<7} {}".format(sid, "todo", title))
            continue

        fails = evaluate(sc, run_scenario(sc))
        if status == "impl":
            if fails:
                surprises.append((sid, "impl scenario FAILED (regression)", fails))
                print("{:<6} {:<7} {}".format(sid, "FAIL", title))
            else:
                n_pass += 1
                print("{:<6} {:<7} {}".format(sid, "PASS", title))
        elif status == "xfail":
            if fails:
                n_xfail += 1
                print("{:<6} {:<7} {}  <- red->green target".format(sid, "xfail", title))
            else:
                surprises.append((sid, "xfail scenario now PASSES -> flip status to 'impl'", []))
                print("{:<6} {:<7} {}".format(sid, "XPASS", title))

    print("-" * 68)
    print("{} passed, {} expected-fail (TDD target), {} pending".format(n_pass, n_xfail, n_todo))
    if surprises:
        print("")
        print("SURPRISES (harness not healthy):")
        for sid, msg, fails in surprises:
            print("  {}: {}".format(sid, msg))
            for (t, exp, got) in fails:
                print("     t={}s expected={} got={}".format(t, exp, got))
        return 1
    if n_todo or n_xfail:
        print("harness OK -- implement a 'todo' or a red target to grow the green set.")
    else:
        print("harness OK -- all SC-01..30 green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
