# Device backends for esw.app.EdgeApp on the K230 (CanMV / MicroPython).
#
# EdgeApp is the shipped loop; these are the four things it needs from the world -- a radio, a
# clock, durable storage, and an evidence log. Nothing here makes a safety decision.
#
# The IF-4 bearer today is the bench UART to the ESP32 sign controller (firmware/sign-controller,
# doc 10): hex-encoded frames, one per line. LoRa (SX1276, ADR-0014) is a drop-in -- the SAME 29
# bytes, sent by radio instead of written to a UART -- and is deliberately not written until the
# ADR-0014 gating tests (bench airtime, duty class, range at 25 mW ERP) resolve.

import time

try:
    import binascii
except ImportError:
    import ubinascii as binascii
try:
    import ujson as json
except ImportError:
    import json


def _wire_safe(rec):
    """Records stamp cfg_ver as raw bytes (esw.params.cfg_fingerprint). JSON cannot carry bytes,
    so hex-encode them here. Every durable/transport backend must do this; harness/store.py does
    the same. A cleanup could have telemetry stamp a hex fingerprint and delete both copies."""
    out = {}
    for k in rec:
        v = rec[k]
        if isinstance(v, bytes) or isinstance(v, bytearray):
            out[k] = binascii.hexlify(v).decode()
        else:
            out[k] = v
    return out


class EdgeClock:
    """The tick clock, and deliberately NOT an absolute one.

    This build has no GNSS/PPS receiver (RQ-H3 is unmet), so wall_ms() returns None: EdgeApp then
    stamps IF-4 frames with the tick clock and reports `absolute_time` degraded at boot. That is
    consistent only because sync() puts the sign controller on the SAME clock (doc 10 "Time",
    edge-synced mode, the `T<ms>` line). Fit a GNSS receiver and this class returns real epoch ms,
    the controller stops needing sync(), and the capability stops being degraded."""

    def __init__(self):
        self.t0 = time.ticks_ms()

    def monotonic(self):
        return time.ticks_diff(time.ticks_ms(), self.t0) / 1000.0

    def ms(self):
        return time.ticks_diff(time.ticks_ms(), self.t0)

    def wall_ms(self):
        return None

    def gnss_lock(self):
        return False


class UartRadio:
    """IF-4 transmit. There is no send-off path, because there is no off command: the sign blanks
    when frames stop arriving. Nothing in here may ever grow a `clear()`."""

    def __init__(self, uart):
        self.uart = uart
        self.sent = 0

    def send(self, frame):
        self.uart.write(binascii.hexlify(frame) + b"\n")
        self.sent += 1

    def sync(self, edge_ms):
        """Put the controller on our clock (doc 10 edge-synced mode). Re-sent periodically: the
        controller's freshness guard rejects a frame whose stamp drifts outside the replay window,
        which would blank the sign -- fail-safe, but a nuisance outage."""
        self.uart.write(b"T" + str(int(edge_ms)).encode() + b"\n")


class UartSignStatus:
    """IF-3 read-back. The controller prints `SIGN on` / `SIGN off` on every lamp transition; this
    is the only way the unit can learn its lamp is physically wedged (SC-24, AP-06). Without it the
    fault is undetectable and EdgeApp reports `sign_readback` degraded (AP-07)."""

    def __init__(self, uart):
        self.uart = uart
        self.on = False
        self._buf = b""

    def __call__(self):
        n = self.uart.any()
        if n:
            self._buf = self._buf + self.uart.read(n)
        while True:
            i = self._buf.find(b"\n")
            if i < 0:
                break
            line = self._buf[:i].strip()
            self._buf = self._buf[i + 1:]
            if line[:5] == b"SIGN ":
                self.on = line[5:] == b"on"
        if len(self._buf) > 512:               # a chattering controller must not grow us unbounded
            self._buf = b""
        return self.on


class FlashStore:
    """esw.sink.Outbox store on the SD card: an append-only JSON-lines data log plus a separate
    one-line ack watermark, so recording the forward position never rewrites the evidence.

    The data log is the acceptance-evidence artifact (ADR-0007). Entries at or below the watermark
    may be archived off, never silently deleted."""

    def __init__(self, path="/sdcard/esw/evidence"):
        self.data_path = path + ".log"
        self.ack_path = path + ".ack"

    def append(self, entry):
        f = open(self.data_path, "a")
        try:
            f.write(json.dumps({"seq": entry["seq"], "rec": _wire_safe(entry["rec"])}) + "\n")
        finally:
            f.close()

    def load(self):
        out = []
        try:
            f = open(self.data_path, "r")
        except OSError:
            return out
        try:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass                       # a torn tail from a power loss mid-append: skip, never crash
        finally:
            f.close()
        return out

    def ack(self, seq):
        f = open(self.ack_path, "w")
        try:
            f.write(str(seq))
        finally:
            f.close()

    def acked(self):
        try:
            f = open(self.ack_path, "r")
        except OSError:
            return -1
        try:
            s = f.read().strip()
        finally:
            f.close()
        try:
            return int(s)
        except ValueError:
            return -1


class CaptureLog:
    """The acceptance-evidence capture (ADR-0007, doc 01 §5).

    Writes the RAW detections alongside the decision, not just the decision: recall and
    false-activation are scored offline against ground truth, and re-scoring a tuning change must
    not require another trip to the road. This is the file that makes recall-N accrue -- without
    it a unit can run for a month and produce no reportable number.

    `every` subsamples the tick stream (10 Hz is more than evidence needs); a tick that changes the
    sign, the state, or the detection count is ALWAYS written, so no event is ever subsampled away."""

    def __init__(self, path="/sdcard/esw/capture.jsonl", every=5, max_bytes=64 * 1024 * 1024):
        self.path = path
        self.every = every
        self.max_bytes = max_bytes
        self.n = 0
        self.written = 0
        self.dropped = 0
        self._prev = None
        self._full = False

    def _interesting(self, rec):
        key = (rec.get("sign_on"), rec.get("state"), rec.get("force_safe"), len(rec.get("dets", [])))
        if key != self._prev:
            self._prev = key
            return True
        return False

    def step(self, rec):
        self.n += 1
        if not self._interesting(rec) and (self.n % self.every) != 0:
            return
        if self._full:
            self.dropped += 1
            return
        try:
            f = open(self.path, "a")
            try:
                f.write(json.dumps(_wire_safe(rec)) + "\n")
                self.written += 1
                if f.tell() > self.max_bytes:   # a full card must not wedge the safety loop
                    self._full = True
                    print("[CAPTURE] %s at size cap -- capture stopped, safety loop unaffected"
                          % self.path)
            finally:
                f.close()
        except OSError as e:
            self.dropped += 1
            self._full = True
            print("[CAPTURE] write failed (%s) -- capture stopped, safety loop unaffected" % e)
