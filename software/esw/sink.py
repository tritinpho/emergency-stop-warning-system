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
# deleted) without affecting pump()/recover(). The policy here avoids per-tick full-log scans
# (pending() is O(1) arithmetic; pump() early-outs when there is no backlog or no link), but a
# large drain still reads through the log once -- a flash backend can index by seq if needed.
#
# MicroPython-safe subset (byte-identical sim + K230): no f-strings / comprehensions / lambdas /
# sets / json in here -- serialization lives in the injected store.


class Outbox:
    def __init__(self, store, transport=None):
        self.store = store
        self.transport = transport
        self._next_seq = 0
        self._acked_through = -1
        self.recover()

    def recover(self):
        """Rebuild the in-RAM cursor from the durable store (reboot-survival). Idempotent."""
        entries = self.store.load()
        mx = -1
        for e in entries:
            s = e["seq"]
            if s > mx:
                mx = s
        self._next_seq = mx + 1
        self._acked_through = self.store.acked()

    def record(self, records):
        """Durably append each IF-6/IF-7 record with a monotonic seq. Returns the seqs assigned.

        `records` is the list telemetry.step() returned this tick (may be empty). Gating on
        box-alive is the CALLER's job (a dead box emits no records, so nothing is appended and
        the gap in the log is the outage signal) -- this method just persists what it is given."""
        seqs = []
        for rec in records:
            s = self._next_seq
            self.store.append({"seq": s, "rec": rec})
            self._next_seq = s + 1
            seqs.append(s)
        return seqs

    def pump(self, link_up):
        """Forward unacked records in seq order while the uplink is up. At-least-once: a record is
        acked only after transport.send() confirms it; forwarding stops on the first failure so a
        later reconnect resumes cleanly from the same watermark. Returns the count sent this call.
        Early-outs on no-transport / link-down / empty-backlog, so the steady state (everything
        acked) never touches the store -- pump() is called every tick."""
        if self.transport is None or not link_up or self.pending() == 0:
            return 0
        sent = 0
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
