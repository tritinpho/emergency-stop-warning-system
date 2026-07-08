#!/usr/bin/env python3
# Level-E sink board: exercise the durable evidence outbox (esw/sink.py) over the host file store
# (harness/store.py) -- the store-and-forward layer that persists the IF-6/IF-7 records the
# acceptance-evidence reducer consumes (ADR-0007, doc 01 5, doc 08 4). Six properties:
#
#   SK-01 durability across reboot  -- records + the resume cursor survive an object-loss reboot
#   SK-02 flaky link, no loss       -- a link that fails then recovers still delivers all, in order
#   SK-03 outage + partial resume   -- a mid-burst drop resumes from the watermark, no re-send
#   SK-04 crash between send + ack   -- a lost ack re-sends (at-least-once); dedup by seq -> no loss
#   SK-05 reducer equivalence        -- metrics off the DURABLE LOG == metrics in-process (faithful)
#   SK-06 gated on box-alive         -- a dead box logs nothing; the gap in the log IS the outage
#
#   python software/run_sink_tests.py     (from the repo root)
#
# Host-only (the FileStore uses the filesystem + json), so this board runs on CPython in CI; the
# SHIPPED esw/sink.py is covered under MicroPython by tools/mpy_smoke.py. Exit 0 iff all pass.

import sys
import json
import tempfile

# Put software/ on the import path on both CPython and MicroPython. mpy's `os` has no
# `os.path`, so derive this script's directory from __file__ by hand -- uniform across runtimes.
_here = __file__
_cut = _here.rfind("/")
_bs = _here.rfind("\\")
if _bs > _cut:
    _cut = _bs
sys.path.insert(0, _here[:_cut] if _cut >= 0 else ".")

from esw.sink import Outbox
from harness.store import FileStore, FakeTransport, json_default
from harness.runner import run_scenario
from harness import metrics
from scenarios.evidence_cases import EVIDENCE


def _events_of(timeline):
    out = []
    for r in timeline:
        for e in r.get("events", []):
            out.append(e)
    return out


def _recs_of(store):
    """The original records read back from the durable log, in seq order."""
    return [e["rec"] for e in store.load()]


def _sample_records(n):
    """n well-formed IF-7-ish records (payload shape is opaque to the outbox)."""
    out = []
    for i in range(n):
        out.append({"if": 7, "type": "e%d" % i, "ts": float(i)})
    return out


# --- SK-01 -- durability across a reboot --------------------------------------
def sk01(tmp):
    fails = []
    path = tmp + "/sk01"
    ob = Outbox(FileStore(path))
    ob.record(_sample_records(3))

    # "Reboot": drop the Outbox + FileStore, reopen a fresh FileStore over the SAME files.
    store2 = FileStore(path)
    ob2 = Outbox(store2)
    loaded = store2.load()

    if len(loaded) != 3:
        fails.append(("SK-01 all records survive reboot", 3, len(loaded)))
    if [e["seq"] for e in loaded] != [0, 1, 2]:
        fails.append(("SK-01 seq order preserved", [0, 1, 2], [e["seq"] for e in loaded]))
    if loaded[0]["rec"]["type"] != "e0":
        fails.append(("SK-01 payload preserved", "e0", loaded[0]["rec"].get("type")))
    if ob2.next_seq() != 3:
        fails.append(("SK-01 next_seq resumes after survivors", 3, ob2.next_seq()))
    return fails


# --- SK-02 -- a flaky link loses nothing --------------------------------------
def sk02(tmp):
    fails = []
    store = FileStore(tmp + "/sk02")
    tr = FakeTransport()
    ob = Outbox(store, tr)
    ob.record(_sample_records(6))

    tr.fail_next = 3                      # first three forward attempts fail (link flapping)
    for _ in range(3):
        ob.pump(True)                    # each stops on the first failure -> 0 delivered, no loss
    if ob.pending() != 6:
        fails.append(("SK-02 nothing forwarded while link flaps", 6, ob.pending()))

    ob.pump(True)                        # link steady -> drains everything, in order
    if tr.unique_seqs() != [0, 1, 2, 3, 4, 5]:
        fails.append(("SK-02 all delivered after recovery", [0, 1, 2, 3, 4, 5], tr.unique_seqs()))
    if tr.seqs() != [0, 1, 2, 3, 4, 5]:
        fails.append(("SK-02 delivered in seq order, no dup", [0, 1, 2, 3, 4, 5], tr.seqs()))
    if ob.pending() != 0:
        fails.append(("SK-02 backlog clear", 0, ob.pending()))
    return fails


# --- SK-03 -- uplink outage, then partial-burst resume from the watermark ------
def sk03(tmp):
    fails = []
    store = FileStore(tmp + "/sk03")
    tr = FakeTransport()
    ob = Outbox(store, tr)
    ob.record(_sample_records(6))

    tr.up = False                        # uplink down: buffer, forward nothing
    ob.pump(True)
    if tr.delivered != [] or ob.pending() != 6:
        fails.append(("SK-03 nothing forwarded while uplink down", (0, 6),
                      (len(tr.delivered), ob.pending())))

    tr.up = True
    tr.deliver_max = 3                   # link returns but drops after 3 (mid-burst)
    ob.pump(True)
    if tr.unique_seqs() != [0, 1, 2] or ob.pending() != 3:
        fails.append(("SK-03 partial burst forwards 0..2", ([0, 1, 2], 3),
                      (tr.unique_seqs(), ob.pending())))

    tr.deliver_max = None                # fully back -> resume from the watermark at seq 3
    ob.pump(True)
    if tr.seqs() != [0, 1, 2, 3, 4, 5]:
        fails.append(("SK-03 resume from watermark, no re-send of 0..2", [0, 1, 2, 3, 4, 5], tr.seqs()))
    if ob.pending() != 0:
        fails.append(("SK-03 backlog clear", 0, ob.pending()))
    return fails


# --- SK-04 -- a crash between send and ack re-sends (at-least-once, never lost) -
def sk04(tmp):
    fails = []
    path = tmp + "/sk04"
    store = FileStore(path)
    store.ack_persist = False            # model a crash that loses the not-yet-committed watermark
    tr = FakeTransport()
    ob = Outbox(store, tr)
    ob.record(_sample_records(4))

    ob.pump(True)                        # all four reach the remote, but no ack is committed to disk
    if tr.unique_seqs() != [0, 1, 2, 3]:
        fails.append(("SK-04 records reached the remote before the crash", [0, 1, 2, 3], tr.unique_seqs()))

    # Crash + reboot: fresh store/outbox over the same files; acks persist again this time.
    store2 = FileStore(path)             # ack_persist defaults True
    ob2 = Outbox(store2, tr)             # recover() reads watermark -1 -> re-forwards everything
    ob2.pump(True)

    if len(tr.delivered) != 8:
        fails.append(("SK-04 at-least-once: lost ack forces a re-send", 8, len(tr.delivered)))
    if tr.unique_seqs() != [0, 1, 2, 3]:
        fails.append(("SK-04 dedup by seq collapses duplicates, no loss", [0, 1, 2, 3], tr.unique_seqs()))
    if ob2.pending() != 0:
        fails.append(("SK-04 backlog clear after resend acked", 0, ob2.pending()))
    return fails


# --- SK-05 -- metrics off the durable log == metrics in-process ----------------
def sk05(tmp):
    fails = []
    ev = EVIDENCE[0]                     # EV-01: a clean day positive (car stops -> detected)

    tl = run_scenario(ev)               # normal in-process path (what Level-D reduces today)
    events_a = _events_of(tl)
    wi_a = metrics.warn_intervals(events_a, ev["duration"])
    sc_a = metrics.score_scenario(ev["oracle"], wi_a)

    store = FileStore(tmp + "/sk05")
    ob = Outbox(store)                   # no transport -> a pure durable evidence log
    run_scenario(ev, outbox=ob)         # SAME run, records teed into the sink
    events_b = _recs_of(store)          # ...then read back from the DURABLE LOG
    wi_b = metrics.warn_intervals(events_b, ev["duration"])
    sc_b = metrics.score_scenario(ev["oracle"], wi_b)

    # Faithful conduit: the durable log holds exactly the in-process records, once both pass through
    # the same serialization (the store hex-encodes the bytes cfg_ver; events_b already round-tripped
    # it, so normalize events_a the same way for an honest full-record compare).
    events_a_norm = json.loads(json.dumps(events_a, default=json_default))
    if events_a_norm != events_b:
        fails.append(("SK-05 durable log == in-process records (every field, in order)",
                      len(events_a), len(events_b)))
    if wi_a != wi_b:
        fails.append(("SK-05 same warning intervals", wi_a, wi_b))
    if sc_a != sc_b:
        fails.append(("SK-05 same recall/FA/latency score", sc_a, sc_b))
    if not events_b:
        fails.append(("SK-05 non-vacuous: the log actually captured events", ">0", 0))
    return fails


# --- SK-06 -- a dead box logs nothing; the gap is the outage --------------------
def sk06(tmp):
    fails = []
    base = {"id": "SK-06", "duration": 12.0,
            "tracks": [{"id": "T1", "enter": 1.0, "leave": 40.0, "speed": 0.0, "in_roi": 1.0}]}

    # Positive control: a live box keeps logging (heartbeats) past t=6.
    store_ctl = FileStore(tmp + "/sk06c")
    run_scenario(base, outbox=Outbox(store_ctl))
    ts_ctl = [e["rec"]["ts"] for e in store_ctl.load()]
    if not ts_ctl or max(ts_ctl) < 6.0:
        fails.append(("SK-06 control: live box logs past 6 s", ">=6.0", max(ts_ctl) if ts_ctl else None))

    # Kill the box at t=6: nothing is emitted at/after death, so no record carries ts >= 6.
    killed = dict(base)
    killed["faults"] = [{"kind": "kill_box", "t": 6.0}]
    store_k = FileStore(tmp + "/sk06k")
    run_scenario(killed, outbox=Outbox(store_k))
    ts_k = [e["rec"]["ts"] for e in store_k.load()]
    if not ts_k:
        fails.append(("SK-06 box logged before it died", ">0 records", 0))
    elif max(ts_k) >= 6.0:
        fails.append(("SK-06 dead box emits nothing after death (gap = outage)", "<6.0", max(ts_k)))
    return fails


_TESTS = [
    ("SK-01", "durability across reboot", sk01),
    ("SK-02", "flaky link loses nothing", sk02),
    ("SK-03", "outage + partial-burst resume", sk03),
    ("SK-04", "crash between send/ack -> at-least-once", sk04),
    ("SK-05", "reducer equivalence (durable log == in-process)", sk05),
    ("SK-06", "gated on box-alive (gap = outage)", sk06),
]


def main():
    print("")
    print("ESW Level-E sink board -- durable evidence outbox (esw/sink.py; ADR-0007 / doc 01 5)")
    print("-" * 68)
    tmp = tempfile.mkdtemp(prefix="esw-sink-")
    n_pass = 0
    surprises = []
    for sid, title, fn in _TESTS:
        fails = fn(tmp)
        if fails:
            surprises.append((sid, fails))
            print("{:<7} {:<6} {}".format(sid, "FAIL", title))
        else:
            n_pass += 1
            print("{:<7} {:<6} {}".format(sid, "PASS", title))
    print("-" * 68)
    if surprises:
        for sid, fails in surprises:
            for f in fails:
                print("  {} {}: expected {!r} got {!r}".format(sid, f[0], f[1], f[2]))
        print("{} / {} sink cases pass".format(n_pass, len(_TESTS)))
        return 1
    print("{} / {} sink cases pass".format(n_pass, len(_TESTS)))
    print("sink board OK -- records persist, survive reboot, forward at-least-once, reduce identically.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
