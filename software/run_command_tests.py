#!/usr/bin/env python3
# Level-F command board: drive the authenticated IF-8/9/10 command channel (esw/command.py) through
# the REAL loop and score each case against its oracle. Proves the receive-side security surface
# (ADR-0012, ICD §5): a genuine override / OTA / ack drives the state machine, while a forged,
# replayed, or stale command frame is rejected upstream and changes nothing (fail-loud). The
# inbound twin of SC-33/34 (the IF-4 sign-link) on the Level-A board.
#
#   python software/run_command_tests.py     (from the repo root)
#
# Exit 0 when every CMD case matches its oracle; 1 otherwise. Host-only (the command feed builds
# frames with esw.command over a host key); the shipped esw/command.py is covered under MicroPython
# by tools/mpy_smoke.py.

import sys

# Put software/ on the import path on both CPython and MicroPython. mpy's `os` has no
# `os.path`, so derive this script's directory from __file__ by hand -- uniform across runtimes.
_here = __file__
_cut = _here.rfind("/")
_bs = _here.rfind("\\")
if _bs > _cut:
    _cut = _bs
sys.path.insert(0, _here[:_cut] if _cut >= 0 else ".")

from harness.runner import run_scenario, evaluate
from scenarios.command_cases import COMMAND_CASES


def main():
    print("")
    print("ESW Level-F command board -- authenticated IF-8/9/10 channel (ADR-0012 / ICD §5)")
    print("-" * 74)
    n_pass = 0
    surprises = []
    for case in COMMAND_CASES:
        fails = evaluate(case, run_scenario(case))
        if fails:
            surprises.append((case["id"], fails))
            print("{:<8} {:<6} {}".format(case["id"], "FAIL", case["title"]))
        else:
            n_pass += 1
            print("{:<8} {:<6} {}".format(case["id"], "PASS", case["title"]))
    print("-" * 74)
    if surprises:
        for sid, fails in surprises:
            for f in fails:
                print("  {} t={} expected {!r} got {!r}".format(sid, f[0], f[1], f[2]))
        print("{} / {} command cases pass".format(n_pass, len(COMMAND_CASES)))
        return 1
    print("{} / {} command cases pass".format(n_pass, len(COMMAND_CASES)))
    print("command board OK -- genuine commands drive the SM; forged/replayed/stale are inert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
