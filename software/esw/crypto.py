# Shared authenticated-channel crypto primitives.
#
# ONE implementation of the HMAC + constant-time compare used by BOTH hardened wire channels:
# the IF-4 sign-link (esw/if4.py, transmit) and the IF-8/9/10 command channel (esw/command.py,
# receive). A control plane that lights a roadside sign and one that reconfigures / overrides the
# unit must not drift onto two different (and differently-bugged) crypto paths (ADR-0012), so the
# primitive lives here and both channels import it. SC-33/34 (sign-link) and the CMD-* board
# (command channel) both exercise it, so any change is caught byte-identically on both sides.
#
# Hand-rolled HMAC-SHA256 (RFC 2104) because MicroPython has no `hmac` module -- only uhashlib.
# MicroPython-safe subset (no f-strings / comprehensions / lambdas / typing).

try:
    import hashlib
except ImportError:                 # MicroPython ports that only expose uhashlib
    import uhashlib as hashlib


def hmac_sha256(key, msg):
    """Standard HMAC (RFC 2104) over SHA-256. Returns the full 32-byte digest; callers
    truncate to their tag length (both channels use 8 bytes: airtime vs ADR-0012 trade)."""
    block = 64
    if len(key) > block:
        key = hashlib.sha256(key).digest()
    k = bytearray(block)
    i = 0
    while i < len(key):
        k[i] = key[i]
        i += 1
    ipad = bytearray(block)
    opad = bytearray(block)
    i = 0
    while i < block:
        ipad[i] = k[i] ^ 0x36
        opad[i] = k[i] ^ 0x5c
        i += 1
    inner = hashlib.sha256(bytes(ipad) + msg).digest()
    return hashlib.sha256(bytes(opad) + inner).digest()


def derive_key(master, channel, site_id):
    """Per-site, per-channel link key: HMAC(master, "esw-key-v1|" + channel + "|" + site_id).

    Binds the CHANNEL ("IF4" sign-link vs "CMD" command uplink) and the unit's SITE ID into
    the key itself, so a frame MAC'd for one unit or channel can never verify on another --
    even if a fleet is (mis)provisioned from one master secret, and with NO change to the
    wire format or the per-frame MAC (doc 10 s5 keeps its layout; provisioning simply
    installs the derived key on both ends). This turns the ADR-0012 "per-unit keys" policy
    into a mechanism instead of a hope."""
    if not isinstance(channel, (bytes, bytearray)):
        channel = channel.encode("utf-8")
    if not isinstance(site_id, (bytes, bytearray)):
        site_id = site_id.encode("utf-8")
    return hmac_sha256(master, b"esw-key-v1|" + bytes(channel) + b"|" + bytes(site_id))


def ct_equal(a, b):
    """Length-fixed, no early exit -- do not leak an auth-tag oracle by timing."""
    if len(a) != len(b):
        return False
    diff = 0
    i = 0
    while i < len(a):
        diff |= a[i] ^ b[i]
        i += 1
    return diff == 0


def as4(b):
    """Coerce a nonce/cfg_ver field (int or bytes-like) to exactly 4 bytes, big-endian."""
    if isinstance(b, int):
        return (b & 0xffffffff).to_bytes(4, "big")
    out = bytearray(4)
    i = 0
    n = len(b)
    while i < 4:
        if i < n:
            out[i] = b[i]
        i += 1
    return bytes(out)
