# Durable-store + transport backends for the evidence outbox (esw/sink.py).
#
# Host-only (NOT shipped) -- full Python is fine here. These are the sim stand-ins for the two
# device backends the byte-identical Outbox POLICY (esw/sink.py) runs over. On the K230 the same
# policy runs over a flash-file store + the real oversight uplink; here it runs over an ordinary
# file + a controllable fake link, so the sink's durability and at-least-once behaviour are
# exercised on the host with no board.
#
# FileStore proves DURABILITY by actually round-tripping the filesystem: it writes an append-only
# JSON-lines data log plus a separate one-line ack-watermark file. A "reboot" is modelled as
# dropping the Outbox + FileStore objects and constructing a fresh FileStore over the SAME paths;
# recover() must then rebuild every record and the forward watermark. (The sim models a reboot as
# object-loss with the file intact; true power-loss durability additionally needs fsync/flash
# commit on the K230 -- a field concern, out of bench scope.)

import json
import os


def json_default(o):
    """Serialize record fields json.dumps cannot handle natively. The telemetry audit record
    stamps cfg_ver as the raw `bytes` fingerprint (if4.cfg_fingerprint) -- fine in RAM for the
    in-process reducer, but a durable log or an MQTT wire needs a string, so bytes are hex-encoded
    here. Any durable/transport backend (this file store, the real K230 outbox) must own this; a
    future cleanup could have telemetry stamp a hex fingerprint so the record is natively wire-safe."""
    if isinstance(o, (bytes, bytearray)):
        return bytes(o).hex()
    raise TypeError("not JSON serializable: %r" % (o,))


class FileStore:
    def __init__(self, path):
        # Two sibling files so the append-only data log is never rewritten to update the watermark.
        self.data_path = path + ".log"
        self.ack_path = path + ".ack"
        # `ack_persist=False` models a crash that loses an in-flight, not-yet-committed watermark
        # (the record was sent, the ack had not reached durable storage). Used by the SK-04
        # at-least-once test; True in every normal run.
        self.ack_persist = True
        # Torn lines seen by the LAST load() (a crash mid-append leaves an unterminated tail).
        # Counted loud (FR-21 spirit), never a crash -- see load(). SK-07 pins this.
        self.corrupt_lines = 0
        self._healed = False

    def append(self, entry):
        f = open(self.data_path, "a")
        if not self._healed:
            # First append of this process life starts on a FRESH line: a torn tail from a
            # crash mid-append has no newline, and without this it would concatenate with
            # (and corrupt) the next record ever written. Blank lines are skipped by load().
            f.write("\n")
            self._healed = True
        f.write(json.dumps(entry, default=json_default) + "\n")
        f.close()

    def load(self):
        if not os.path.exists(self.data_path):
            return []
        out = []
        self.corrupt_lines = 0
        f = open(self.data_path, "r")
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                # A torn append (crash/power-loss mid-write): the record never fully
                # persisted, so the crash-consistent read is every COMPLETE line. Counted,
                # never silent, and never a crash -- recover() must not brick the evidence
                # subsystem at boot over an uncommitted tail (mirrors the ack-file stance).
                self.corrupt_lines += 1
        f.close()
        return out

    def ack(self, seq):
        if not self.ack_persist:
            return
        f = open(self.ack_path, "w")
        f.write(str(seq))
        f.close()

    def acked(self):
        if not os.path.exists(self.ack_path):
            return -1
        f = open(self.ack_path, "r")
        v = f.read().strip()
        f.close()
        try:
            return int(v) if v else -1
        except ValueError:
            return -1   # corrupt watermark (torn write) -> re-forward from scratch:
            #             at-least-once holds, the consumer dedups by seq -- never crash the outbox


class FakeTransport:
    """A controllable remote-forward sink for exercising at-least-once + reconnect.

    `up` gates the link (an uplink outage). `fail_next` forces the next N sends to fail then
    recover (a flaky link). `deliver_max` caps how many records land before sends start failing (a
    link that drops mid-burst -> the outbox must resume from its watermark). Everything accepted is
    appended to `delivered` -- INCLUDING duplicates when a record is re-sent after a crash -- so a
    test can assert both at-least-once (every seq delivered >= once) and that a consumer dedup by
    seq collapses the duplicates with no loss."""

    def __init__(self):
        self.up = True
        self.fail_next = 0
        self.deliver_max = None
        self.delivered = []

    def send(self, entry):
        if not self.up:
            return False
        if self.fail_next > 0:
            self.fail_next = self.fail_next - 1
            return False
        if self.deliver_max is not None and len(self.delivered) >= self.deliver_max:
            return False
        self.delivered.append(entry)
        return True

    def seqs(self):
        """seqs delivered, in delivery order (may contain duplicates -> at-least-once)."""
        out = []
        for e in self.delivered:
            out.append(e["seq"])
        return out

    def unique_seqs(self):
        """The set of distinct seqs delivered, as a sorted list (consumer dedup by seq)."""
        seen = {}
        for e in self.delivered:
            seen[e["seq"]] = True
        out = list(seen.keys())
        out.sort()
        return out
