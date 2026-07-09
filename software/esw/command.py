# IF-8/9/10 command channel -- the authenticated inbound control plane (ICD §5, ADR-0010, ADR-0012).
#
# The TMC / operator sends CONFIG (IF-8), OTA (IF-9), OVERRIDE and ACK (IF-10) to the edge over
# ONE hardened channel. ICD §5 specifies it as signed/authenticated (anti-forge, anti-replay);
# this module is that contract IN CODE -- the receive-side twin of the IF-4 sign-link (esw/if4.py).
# An attacker who can transmit on the uplink must be able to neither ISSUE nor REPLAY a command:
# a frame that fails auth / anti-replay / freshness is REJECTED and changes nothing (fail-loud), so
# perception, the state machine, and the audit log never see a forged command.
#
# Frame (big-endian):  version | ctype | seq | nonce | ts_ms | plen | payload(plen) | HMAC-tag(8)
#   header = 1+1+4+4+6+2 = 18 bytes;  tag = HMAC-SHA256(key, header || payload)[:8].
# The payload is a JSON object: commands are infrequent and ride the OVERSIGHT uplink, not the
# airtime-bound LoRa sign-link, so a self-describing payload is worth the bytes (unlike IF-4's
# packed 29-byte frame). Anti-replay is the SAME two guards as IF-4: seq strictly-monotonic
# (in-session) + ts within replay_window (cross-session). The auth tag covers the exact transmitted
# bytes, so JSON key ordering never affects verification -- the payload is decoded only AFTER auth.
#
# MicroPython-safe subset (byte-identical sim + K230). Shares the ONE crypto primitive (esw/crypto).

import json

from esw.crypto import hmac_sha256, ct_equal, as4

_VERSION = 1
_TAG_LEN = 8
_HDR_LEN = 1 + 1 + 4 + 4 + 6 + 2          # ver, ctype, seq, nonce, ts_ms, plen = 18

CMD_CONFIG = 1     # IF-8 config push (the unit still enforces §7a bounds via params.clamp_config)
CMD_OTA = 2        # IF-9 OTA / restart request (deferred while a warning is asserted)
CMD_OVERRIDE = 3   # IF-10 operator override (non-latching, auto-expiry -- ADR-0010)
CMD_ACK = 4        # IF-10 operator ack (freezes alarm re-escalation -- ADR-0011)

_CMD_NAMES = {1: "config", 2: "ota", 3: "override", 4: "ack"}


def command_name(ctype):
    return _CMD_NAMES.get(ctype, "unknown")


def encode_command(key, ctype, seq, nonce, ts_ms, payload_obj):
    """Build an authenticated command frame: header || json(payload) || truncated-HMAC."""
    body = json.dumps(payload_obj).encode("utf-8")
    header = bytearray()
    header.append(_VERSION)
    header.append(ctype & 0xff)
    header += (seq & 0xffffffff).to_bytes(4, "big")
    header += as4(nonce)
    header += (ts_ms & 0xffffffffffff).to_bytes(6, "big")
    header += (len(body) & 0xffff).to_bytes(2, "big")
    tag = hmac_sha256(key, bytes(header) + body)[:_TAG_LEN]
    return bytes(header) + body + tag


def _bad(reason):
    return {"ok": False, "reason": reason, "ctype": 0, "seq": 0, "payload": None}


def verify_command(key, frame, last_seq, now_ms, replay_window_ms):
    """Return {"ok","reason","ctype","seq","payload"}. ok requires: right version; a KNOWN
    command type; a self-consistent length; a good auth tag; seq strictly > last_seq
    (anti-replay / anti-reorder); the frame ts within replay_window of now (freshness); and a
    well-formed JSON payload. On any failure the caller MUST treat the command as if it never
    arrived (fail-loud). An unknown ctype is rejected here (reason "ctype"), never silently
    dropped downstream -- a version-skewed TMC must show up on the reject counters (FR-21)."""
    if frame is None or len(frame) < _HDR_LEN + _TAG_LEN:
        return _bad("len")
    if frame[0] != _VERSION:
        return _bad("proto")
    if frame[1] not in _CMD_NAMES:
        return _bad("ctype")
    plen = int.from_bytes(frame[16:18], "big")
    if len(frame) != _HDR_LEN + plen + _TAG_LEN:
        return _bad("len")
    header = frame[:_HDR_LEN]
    body = frame[_HDR_LEN:_HDR_LEN + plen]
    tag = frame[_HDR_LEN + plen:]
    want = hmac_sha256(key, bytes(header) + bytes(body))[:_TAG_LEN]
    if not ct_equal(tag, want):
        return _bad("auth")
    seq = int.from_bytes(frame[2:6], "big")
    if last_seq is not None and seq <= last_seq:
        return _bad("replay")
    ts_ms = int.from_bytes(frame[10:16], "big")
    d = now_ms - ts_ms
    if d < 0:
        d = -d
    if d > replay_window_ms:
        return _bad("stale")
    try:
        payload = json.loads(bytes(body).decode("utf-8"))
    except ValueError:
        return _bad("payload")     # authenticated but malformed -> reject, never act on garbage
    return {"ok": True, "reason": "", "ctype": frame[1], "seq": seq, "payload": payload}


class CommandReceiver:
    """Stateful IF-8/9/10 receiver: one anti-replay seq watermark for the channel, fail-loud on
    every reject. The inbound twin of the sign controller's verify side (harness/sign.py). A fresh
    edge boot constructs a fresh receiver (last_seq = None); an OLD replayed command is still blocked
    by ts-freshness, exactly as on the IF-4 reconnect path."""

    def __init__(self, key, replay_window_ms):
        self._key = key
        self._window = replay_window_ms
        self._last_seq = None
        self.rejects = 0            # observability: count + last reason (mirrors sign.rejects)
        self.last_reject = None

    def submit(self, frame, now_ms):
        """Verify one delivered frame. On success advance the anti-replay watermark and return the
        verified command; on failure count it and return the rejection (watermark unchanged)."""
        res = verify_command(self._key, frame, self._last_seq, now_ms, self._window)
        if not res["ok"]:
            self.rejects += 1
            self.last_reject = res["reason"]
            return res
        self._last_seq = res["seq"]
        return res
