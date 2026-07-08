# IF-4 sign-link frame codec -- the wire contract for the refreshed-SHOW dead-man's
# switch (ICD s3, ADR-0009 s A, ADR-0012, ADR-0014).
#
# ONE source of truth for the IF-4 bytes: the edge actuator ENCODES a SHOW frame, and
# the sign controller (here modelled by harness/sign.py) DECODES + VERIFIES it. The
# ESP32 firmware spec (doc 10) implements the SAME verify() half in C. There is NO
# "blank" / "off" frame: the sign blanks on the ABSENCE of a fresh valid SHOW, never on
# a received command -- so a dead edge box or a cut/jammed link (which send nothing)
# always blank the sign by construction (RQ-H2).
#
# MicroPython-safe subset (byte-identical sim + K230): no f-strings, comprehensions,
# lambdas, typing, enum. hashlib.sha256 is the only primitive (uhashlib on some ports).

try:
    import hashlib
except ImportError:                 # MicroPython ports that only expose uhashlib
    import uhashlib as hashlib

# The HMAC + constant-time compare + 4-byte coercion are SHARED with the IF-8/9/10 command
# channel -- one tested crypto primitive for both hardened channels (esw/crypto.py, ADR-0012).
from esw.crypto import hmac_sha256 as _hmac_sha256, ct_equal as _ct_equal, as4 as _as4

# Wire layout (big-endian). Compact ON PURPOSE: LoRa time-on-air scales with payload
# bytes and IF-4 airtime is duty-cycle-bound (ADR-0014), so these sizes ARE the airtime
# input for doc 10's budget -- freezing the layout here freezes that calculation.
_VERSION = 1
MSG_SHOW = 1                        # the only message type: assert SHOW(message_id)
_TAG_LEN = 8                        # truncated HMAC-SHA256 (64-bit): airtime vs ADR-0012 trade
_HEADER_LEN = 1 + 1 + 1 + 4 + 4 + 4 + 6    # ver,type,msg_id,seq,nonce,cfg_ver,ts_ms = 21
FRAME_LEN = _HEADER_LEN + _TAG_LEN         # = 29 bytes on the wire

# message_id is one byte on the wire; the QCVN-41 message set (ADR-0004) maps id<->meaning.
MSG_ID_STOPPED = 1                  # "STOPPED_VEHICLE_AHEAD" (state_machine.MESSAGE_STOPPED)
_MSG_ID_TEXT = {1: "STOPPED_VEHICLE_AHEAD"}


def to_ms(seconds):
    """Sim works in float seconds; the wire timestamp is integer ms since an agreed epoch."""
    return int(round(seconds * 1000.0))


def message_id_to_text(mid):
    return _MSG_ID_TEXT.get(mid, "UNKNOWN")


def cfg_fingerprint(cfg):
    # 4-byte fingerprint of the active safety config (R10 audit / cfg_ver). Canonical
    # "name=value;" over sorted keys so the hash is stable regardless of dict order.
    # It is authenticated but OPAQUE to the controller (echoed for audit, not interpreted),
    # so float-repr differences across runtimes cannot change a safety decision.
    names = sorted(cfg.keys())
    s = ""
    i = 0
    while i < len(names):
        n = names[i]
        s = s + n + "=" + str(cfg[n]) + ";"
        i += 1
    return hashlib.sha256(s.encode("utf-8")).digest()[:4]


def encode_show(key, message_id, seq, nonce, cfg_ver, ts_ms):
    """Build the authenticated SHOW frame: header || truncated-HMAC(header)."""
    header = bytearray()
    header.append(_VERSION)
    header.append(MSG_SHOW)
    header.append(message_id & 0xff)
    header += (seq & 0xffffffff).to_bytes(4, "big")
    header += _as4(nonce)
    header += _as4(cfg_ver)
    header += (ts_ms & 0xffffffffffff).to_bytes(6, "big")
    tag = _hmac_sha256(key, bytes(header))[:_TAG_LEN]
    return bytes(header) + tag


def _bad(reason):
    return {"ok": False, "reason": reason, "message_id": 0, "seq": 0}


def verify(key, frame, last_seq, now_ms, replay_window_ms):
    """Return {"ok", "reason", "message_id", "seq"}. ok requires: right length/version/
    type; good auth_tag; seq strictly > last_seq (anti-replay / anti-reorder); and the
    frame timestamp within replay_window of now (freshness). A dead box or a cut link
    deliver NO frame -> verify is never reached -> the sign blanks on staleness."""
    if frame is None or len(frame) != FRAME_LEN:
        return _bad("len")
    if frame[0] != _VERSION or frame[1] != MSG_SHOW:
        return _bad("proto")
    header = frame[:_HEADER_LEN]
    tag = frame[_HEADER_LEN:]
    want = _hmac_sha256(key, header)[:_TAG_LEN]
    if not _ct_equal(tag, want):
        return _bad("auth")
    seq = int.from_bytes(frame[3:7], "big")
    if last_seq is not None and seq <= last_seq:
        return _bad("replay")
    ts_ms = int.from_bytes(frame[15:21], "big")
    d = now_ms - ts_ms
    if d < 0:
        d = -d
    if d > replay_window_ms:
        return _bad("stale")
    return {"ok": True, "reason": "", "message_id": frame[2], "seq": seq}
