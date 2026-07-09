#!/usr/bin/env python3
"""Bench driver for the sign-controller firmware -- the doc 10 §7 conformance rig.

Drives the REAL wire bytes (software/esw/if4.py::encode_show -- the same codec the
edge and the Level-A board use) at the firmware over USB serial, and scores the
sign behaviour it reports. Semi-automates the bench half of the conformance table:

    C1  valid refresh at T_assert_refresh -> lit, steady, no flicker      (SC-01)
    C2* kill the sender (we just stop)    -> blanks <= T_signhold         (SC-21)
    C4* cut the link (same stimulus here) -> blanks <= T_signhold         (SC-23)
    C5  frames MAC'd with a wrong key     -> never lights; rejects climb  (SC-33)
    C6  replay a captured frame post-blank-> never re-lights              (SC-34)
    C7  reboot-fresh LOW seq after blank  -> re-lights on valid refresh   (SC-15)

  * On this bench, "kill the edge box" (C2), "power it off" (C3) and "cut the
    link" (C4) are the same stimulus -- frames stop arriving. C3 with a real
    separate edge box, and C8 (wedged-panel IF-3 read-back), remain physical
    tests on the rig.

Usage:
    python bench_send.py --port COM5              # run the full sequence
    python bench_send.py --port COM5 --soak       # continuous valid refresh (demo / Tier-2 soak)
    python bench_send.py --port COM5 --master X --site SITE-01   # non-dev key

The default key matches the firmware's built-in dev key (see tools/gen_vectors.py);
--master/--site derive per doc 10 §5 / esw/crypto.derive_key, so a provisioned
board (K<64hex>) is driven the same way.
"""

import argparse
import os
import re
import sys
import threading
import time
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[3] / "software"
sys.path.insert(0, str(_SOFTWARE))

from esw import if4                      # noqa: E402
from esw.crypto import derive_key        # noqa: E402

try:
    import serial                        # pyserial (installed with esptool/platformio)
except ImportError:
    print("pyserial missing: python -m pip install pyserial")
    sys.exit(2)

T_ASSERT_REFRESH = 0.5   # esw/params.py §7a
T_SIGNHOLD = 2.0
T_ACTIVATE = 2.0

DEV_MASTER = b"esw-dev-master-not-for-deployment"
DEV_SITE = "SITE-DEV"

_STAT_RE = re.compile(r"^STAT on=(\d) .*?acc=(\d+) rej=(\d+) auth=(\d+) replay=(\d+) "
                      r"stale=(\d+) len=(\d+) proto=(\d+) sync=(\d)")


class Board:
    """Serial link + a reader thread that tracks the firmware's reported state."""

    def __init__(self, port, baud):
        self.ser = serial.Serial(port, baud, timeout=0.2)
        self.lock = threading.Lock()
        self.stat = None            # last parsed STAT dict
        self.on = None              # latest sign state (STAT or SIGN lines)
        self.on_changes = []        # (t_mono, on) transitions, from SIGN lines
        self.raw = []               # (t_mono, line) tail for diagnostics
        self._stop = False
        self.rx = threading.Thread(target=self._reader, daemon=True)
        self.rx.start()

    def _reader(self):
        while not self._stop:
            try:
                line = self.ser.readline()
            except serial.SerialException:
                break
            if not line:
                continue
            text = line.decode("utf-8", "replace").strip()
            t = time.monotonic()
            with self.lock:
                self.raw.append((t, text))
                if len(self.raw) > 400:
                    del self.raw[:200]
                m = _STAT_RE.match(text)
                if m:
                    g = [int(x) for x in m.groups()]
                    self.stat = {"on": g[0], "acc": g[1], "rej": g[2], "auth": g[3],
                                 "replay": g[4], "stale": g[5], "len": g[6],
                                 "proto": g[7], "sync": g[8]}
                    self.on = g[0] == 1
                elif text.startswith("SIGN "):
                    on = text == "SIGN on"
                    self.on = on
                    self.on_changes.append((t, on))

    def send_line(self, s):
        self.ser.write((s + "\n").encode("ascii"))

    def sync_clock(self):
        self.send_line("T%d" % int(time.time() * 1000))

    def wait(self, pred, timeout):
        """Poll the reader state until pred() or timeout; returns pred()'s final value."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self.lock:
                if pred():
                    return True
            time.sleep(0.05)
        with self.lock:
            return pred()

    def counters(self):
        with self.lock:
            return dict(self.stat) if self.stat else None

    def close(self):
        self._stop = True
        try:
            self.ser.close()
        except serial.SerialException:
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", required=True, help="serial port, e.g. COM5 or /dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--master", default=None, help="key master secret (default: the dev master)")
    ap.add_argument("--site", default=DEV_SITE, help="site id for key derivation")
    ap.add_argument("--key-hex", default=None, help="raw 32-byte link key, hex (overrides master/site)")
    ap.add_argument("--soak", action="store_true", help="just refresh forever (demo / Tier-2 soak)")
    args = ap.parse_args()

    if args.key_hex:
        key = bytes.fromhex(args.key_hex)
    else:
        master = args.master.encode() if args.master else DEV_MASTER
        key = derive_key(master, "IF4", args.site)
    wrong_key = derive_key(b"attacker-master", "IF4", args.site)

    seq = [100]

    def frame(k=key, seq_override=None, ts_ms=None):
        if seq_override is None:
            seq[0] += 1
            s = seq[0]
        else:
            s = seq_override
        return if4.encode_show(
            k, if4.MSG_ID_STOPPED, s,
            int.from_bytes(os.urandom(4), "big"), 0x0BADF00D,
            if4.to_ms(time.time()) if ts_ms is None else ts_ms)

    b = Board(args.port, args.baud)
    print("opened %s; waiting for the board..." % args.port)
    b.send_line("S")
    if not b.wait(lambda: b.stat is not None, 5.0):
        print("FAIL: no STAT from the board in 5 s -- is the firmware flashed and the port right?")
        b.close()
        sys.exit(1)
    b.sync_clock()
    time.sleep(0.3)

    if args.soak:
        print("soak: valid refresh every %.1fs (Ctrl-C to stop)" % T_ASSERT_REFRESH)
        n = 0
        try:
            while True:
                b.send_line(frame().hex())
                n += 1
                if n % 10 == 0:
                    b.sync_clock()
                    c = b.counters()
                    print("  sent=%d  %s" % (n, c))
                time.sleep(T_ASSERT_REFRESH)
        except KeyboardInterrupt:
            pass
        finally:
            b.close()
        return

    results = []

    def record(name, ok, detail):
        results.append((name, ok, detail))
        print("  %-4s %s  %s" % ("PASS" if ok else "FAIL", name, detail))

    # ---- C1: valid refresh -> lit within T_activate, steady while refreshed --------
    print("C1: valid refresh at T_assert_refresh for 6 s")
    captured = frame()                       # keep one real frame for the C6 replay
    b.send_line(captured.hex())
    lit = b.wait(lambda: b.on is True, T_ACTIVATE + 0.5)
    flicker = False
    t_end = time.monotonic() + 6.0
    while time.monotonic() < t_end:
        b.send_line(frame().hex())
        time.sleep(T_ASSERT_REFRESH)
        if lit and b.on is False:
            flicker = True
    record("C1", lit and not flicker,
           "lit=%s flicker=%s (expect lit, no flicker)" % (lit, flicker))

    # ---- C2/C4: stop sending -> blanks <= T_signhold --------------------------------
    print("C2/C4: refresh stops (edge dead / link cut)")
    t_stop = time.monotonic()
    blanked = b.wait(lambda: b.on is False, T_SIGNHOLD + 1.0)
    dt = time.monotonic() - t_stop
    record("C2/C4", blanked and dt <= T_SIGNHOLD + 0.7,
           "blanked=%s after %.2fs (budget %.1fs + margin)" % (blanked, dt, T_SIGNHOLD))

    # ---- C5: forged frames (wrong key) -> never lights, auth rejects climb ----------
    print("C5: forged frames for 4 s")
    before = b.counters()
    lit_during_forge = False
    t_end = time.monotonic() + 4.0
    while time.monotonic() < t_end:
        b.send_line(frame(k=wrong_key).hex())
        time.sleep(T_ASSERT_REFRESH)
        if b.on:
            lit_during_forge = True
    b.send_line("S")
    time.sleep(0.5)
    after = b.counters()
    auth_climbed = after and before and after["auth"] > before["auth"]
    record("C5", not lit_during_forge and auth_climbed,
           "lit=%s auth %s->%s (expect dark, climbing)" %
           (lit_during_forge, before and before["auth"], after and after["auth"]))

    # ---- C6: replay the captured valid frame after blank -> never re-lights ---------
    print("C6: replay a captured frame (now stale) after blank")
    time.sleep(max(0.0, T_SIGNHOLD - 0.5))   # ensure well past the freshness window
    lit_on_replay = False
    for _ in range(4):
        b.send_line(captured.hex())
        time.sleep(0.3)
        if b.on:
            lit_on_replay = True
    b.send_line("S")
    time.sleep(0.5)
    c6 = b.counters()
    replay_rejected = c6 and (c6["stale"] > (after["stale"] if after else 0) or
                              c6["replay"] > (after["replay"] if after else 0))
    record("C6", not lit_on_replay and replay_rejected,
           "lit=%s stale/replay rejects climbed=%s" % (lit_on_replay, replay_rejected))

    # ---- C7: reboot-fresh LOW seq re-asserts after blank -----------------------------
    print("C7: fresh valid frame with LOW seq (rebooted edge) re-lights")
    b.sync_clock()
    relit = False
    t_end = time.monotonic() + T_ACTIVATE + 1.0
    while time.monotonic() < t_end and not relit:
        b.send_line(frame(seq_override=1).hex())   # far below C1's watermark
        time.sleep(T_ASSERT_REFRESH)
        relit = b.on is True
    record("C7", relit, "relit=%s (session reset must allow a low-seq re-assert)" % relit)
    # leave the sign to blank naturally

    b.close()
    n_pass = sum(1 for _, ok, _ in results if ok)
    print("\nbench: %d/%d PASS" % (n_pass, len(results)))
    print("still physical: C3 (power off a real edge box), C8 (wedged-panel IF-3 read-back).")
    sys.exit(0 if n_pass == len(results) else 1)


if __name__ == "__main__":
    main()
