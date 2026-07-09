# Durable evidence outbox -- store-and-forward for IF-6/IF-7 records (ADR-0007, doc 01 5, doc 08 4).
#
# The telemetry emitter (esw/telemetry.py) turns each tick's decision into fingerprinted audit
# RECORDS; it does not persist or ship them. That is this module. The acceptance-evidence spine
# only closes if those records survive to a durable log the offline reducer (harness/metrics.py)
# can read over continuous bench-hours -- not vanish with the process on a reboot or a cut link.
#
# Policy, stated as invariants:
#   * DURABLE FIRST. Every record is appended to the store BEFORE anything is forwarded, so a
#     power loss can never lose an already-observed event -- the durable log is the evidence
#     artifact the reducer consumes; the forward is only oversight (NFR-06, non-safety).
#   * AT-LEAST-ONCE, IN ORDER. Records forward in seq order; a record is acked only after the
#     transport confirms it. A crash between send and ack re-sends -> the remote may see a record
#     twice, so the consumer dedups by (site_id, seq). Never at-most-once (no silent loss).
#   * SURVIVE REBOOT. All forward state is a single durable watermark (the highest contiguously
#     acked seq). recover() rebuilds the in-RAM cursor from the store, so a fresh Outbox over the
#     same store resumes exactly where the dead one stopped.
#
# Like esw/actuator.py (wire) and esw/telemetry.py (transport), this is PURE POLICY over an
# injected backend. The `store` (durable bytes) and `transport` (remote forward) are device
# backends: in the harness they are a host file + a fake link (harness/store.py); on the K230 the
# same policy runs over a flash-file store + the real oversight uplink. No sim-only branch.
#
# The `store` backend contract (tiny on purpose, so a flash port is trivial):
#     append(entry)  -- durably persist entry = {"seq": int, "rec": <record>}
#     load()         -- return every entry in seq order (recover + the offline reducer read this)
#     ack(seq)       -- durably record the forward watermark (highest contiguously-forwarded seq)
#     acked()        -- return that watermark, or -1 if nothing forwarded yet
#
# GROWTH is the backend's responsibility: the log is the evidence artifact, so entries at or
# below the ack watermark may be ARCHIVED/ROTATED off the primary store (never silently
# deleted) without affecting pump()/recover(). The per-tick path never re-reads the store:
# records forward from a BOUNDED in-RAM tail of recent appends (steady state = append one,
# send one, zero store reads -- a flash log must not be re-parsed once per heartbeat, SK-08).
# Only a DEEP backlog (an outage that overflowed the tail, or a fresh boot over a backlog)
# falls back to an in-order store scan, and only until the drain catches the tail again.
#
# MicroPython-safe subset (byte-identical sim + K230): no f-strings / comprehensions / lambdas /
# sets / json in here -- serialization lives in the injected store.

_TAIL_MAX = 64      # RAM bound on the recent-appends tail; beyond this a drain scans the store


class Outbox:
    def __init__(self, store, transport=None):
        self.store = store
        self.transport = transport
        self._next_seq = 0
        self._acked_through = -1
        self._tail = []             # unacked entries appended THIS process life (bounded)
        self.recover()

    def recover(self):
        """Rebuild the in-RAM cursor from the durable store (reboot-survival). Idempotent.
        The RAM tail starts empty: any pre-existing backlog is only in the store, so the
        first drain after a reboot takes the store-scan path, then hands back to the tail."""
        entries = self.store.load()
        mx = -1
        for e in entries:
            s = e["seq"]
            if s > mx:
                mx = s
        self._next_seq = mx + 1
        self._acked_through = self.store.acked()
        self._tail = []

    def record(self, records):
        """Durably append each IF-6/IF-7 record with a monotonic seq. Returns the seqs assigned.

        `records` is the list telemetry.step() returned this tick (may be empty). Gating on
        box-alive is the CALLER's job (a dead box emits no records, so nothing is appended and
        the gap in the log is the outage signal) -- this method just persists what it is given.
        Each entry is also kept in the bounded RAM tail so the steady-state pump() never
        re-reads the store; overflow drops the OLDEST tail entries (they stay durable and a
        deep drain recovers them via the scan path)."""
        seqs = []
        for rec in records:
            s = self._next_seq
            entry = {"seq": s, "rec": rec}
            self.store.append(entry)
            self._next_seq = s + 1
            seqs.append(s)
            self._tail.append(entry)
            if len(self._tail) > _TAIL_MAX:
                self._tail.pop(0)
        return seqs

    def pump(self, link_up):
        """Forward unacked records in seq order while the uplink is up. At-least-once: a record is
        acked only after transport.send() confirms it; forwarding stops on the first failure so a
        later reconnect resumes cleanly from the same watermark. Returns the count sent this call.

        Early-outs on no-transport / link-down / empty-backlog. The steady state (backlog small
        enough to live in the RAM tail) drains WITHOUT touching the store (SK-08); only a deep
        backlog -- the tail overflowed during a long outage, or a fresh recover() found stored
        backlog -- falls back to ONE in-order store scan, until the drain catches the tail."""
        if self.transport is None or not link_up or self.pending() == 0:
            return 0
        sent = 0
        # Prune tail entries already acked (e.g. by an earlier scan drain).
        while self._tail and self._tail[0]["seq"] <= self._acked_through:
            self._tail.pop(0)
        if self._tail and self._tail[0]["seq"] == self._acked_through + 1:
            # RAM path: the tail is contiguous from the watermark -> no store read.
            while self._tail:
                e = self._tail[0]
                if not self.transport.send(e):
                    return sent
                self._acked_through = e["seq"]
                self.store.ack(e["seq"])
                self._tail.pop(0)
                sent = sent + 1
            return sent
        # Deep-backlog path: the records after the watermark predate the RAM tail.
        for e in self.store.load():
            if e["seq"] <= self._acked_through:
                continue
            if not self.transport.send(e):
                break
            self._acked_through = e["seq"]
            self.store.ack(e["seq"])
            sent = sent + 1
        return sent

    def pending(self):
        """How many durably-stored records are not yet forwarded (oversight backlog depth).
        O(1): the outbox assigns seqs contiguously and acks contiguously, so the backlog is
        pure cursor arithmetic -- no store scan on the per-tick path."""
        n = self._next_seq - self._acked_through - 1
        return n if n > 0 else 0

    def next_seq(self):
        """The seq the next appended record will get -- exposed for reboot-resume assertions."""
        return self._next_seq
