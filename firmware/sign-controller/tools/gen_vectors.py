#!/usr/bin/env python3
"""Generate the firmware's IF-4 conformance vectors FROM the Python reference codec.

The one-source-of-truth rule (doc 10 / esw/if4.py): the edge encodes, the controller
verifies. This script runs the REAL `esw.if4.encode_show` + `esw.crypto.derive_key`
to emit two headers the firmware compiles in:

    src/dev_key.h       -- the bench/dev link key (derive_key(dev master, "IF4", dev site))
    src/test_vectors.h  -- frames + expected verdicts for the on-boot self-test

So the C `if4_verify` is proven against the exact bytes the Python edge produces --
a cross-language conformance check that runs on every boot, before any bench test.

Regenerate after any change to esw/if4.py or esw/crypto.py:
    python firmware/sign-controller/tools/gen_vectors.py
"""

import sys
from pathlib import Path

# repo/firmware/sign-controller/tools/gen_vectors.py -> repo/software on sys.path
_SOFTWARE = Path(__file__).resolve().parents[3] / "software"
sys.path.insert(0, str(_SOFTWARE))

from esw import if4                      # noqa: E402
from esw.crypto import derive_key        # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[1] / "src"

# ---- the bench/dev key -- NEVER a deployment key ------------------------------------
# Real provisioning (per-unit master, secure storage, rotation) is the doc 10 §8.3 open
# handoff. The bench tools (bench_send.py) derive the same key, so host and firmware
# agree without any key ever crossing the serial link in normal use.
DEV_MASTER = b"esw-dev-master-not-for-deployment"
DEV_SITE = "SITE-DEV"
DEV_KEY = derive_key(DEV_MASTER, "IF4", DEV_SITE)

# ---- vectors -------------------------------------------------------------------------
# Each: (name, frame_bytes, have_last, last_seq, now_ms, window_ms, expect, exp_mid, exp_seq)
# expect strings match the if4_result_t enum names in if4_verify.h.
WINDOW = 2000  # REPLAY_WINDOW_MS default = T_signhold (doc 10 §4)
TS = 1_000_000_000  # an arbitrary agreed-epoch transmit time, ms


def _v():
    k = DEV_KEY
    ok = if4.encode_show(k, if4.MSG_ID_STOPPED, seq=10, nonce=0xA1B2C3D4,
                         cfg_ver=0x0BADF00D, ts_ms=TS)
    assert len(ok) == if4.FRAME_LEN == 29

    flipped_tag = bytearray(ok)
    flipped_tag[-1] ^= 0x01                      # one bit in the auth tag
    flipped_body = bytearray(ok)
    flipped_body[2] ^= 0x01                      # message_id changed after MAC'ing

    wrong_key = if4.encode_show(derive_key(DEV_MASTER, "IF4", "SITE-OTHER"),
                                if4.MSG_ID_STOPPED, 10, 0xA1B2C3D4, 0x0BADF00D, TS)
    wrong_chan = if4.encode_show(derive_key(DEV_MASTER, "CMD", DEV_SITE),
                                 if4.MSG_ID_STOPPED, 10, 0xA1B2C3D4, 0x0BADF00D, TS)

    bad_ver = bytearray(ok); bad_ver[0] = 2
    bad_type = bytearray(ok); bad_type[1] = 2

    low_seq = if4.encode_show(k, if4.MSG_ID_STOPPED, 1, 0x00000001, 0x0BADF00D, TS)

    return [
        # the happy path, fresh frame, no session watermark
        ("ok_basic",        ok,          0, 0,  TS + 100,          WINDOW, "IF4_OK",        1, 10),
        # freshness boundary: |now-ts| == window is still OK (strictly-greater rejects)
        ("ok_edge_fresh",   ok,          0, 0,  TS + WINDOW,       WINDOW, "IF4_OK",        1, 10),
        ("ok_seq_advance",  ok,          1, 9,  TS + 100,          WINDOW, "IF4_OK",        1, 10),
        # doc 10 §4 guard 2: after a blank the session resets -> a rebooted edge's LOW seq
        # re-asserts (this is SC-15 on the Level-A board)
        ("ok_reconnect_low_seq", low_seq, 0, 0, TS + 100,          WINDOW, "IF4_OK",        1, 1),
        # doc 10 §4 guard 1: in-session replay / reorder
        ("rej_replay_equal", ok,         1, 10, TS + 100,          WINDOW, "IF4_REJ_REPLAY", 0, 0),
        ("rej_replay_older", ok,         1, 11, TS + 100,          WINDOW, "IF4_REJ_REPLAY", 0, 0),
        # auth: tag bit, body bit, wrong site key, wrong CHANNEL key (derive_key binding)
        ("rej_auth_tag_bit", bytes(flipped_tag),  0, 0, TS + 100,  WINDOW, "IF4_REJ_AUTH",  0, 0),
        ("rej_auth_body_bit", bytes(flipped_body), 0, 0, TS + 100, WINDOW, "IF4_REJ_AUTH",  0, 0),
        ("rej_auth_wrong_site", wrong_key,  0, 0, TS + 100,        WINDOW, "IF4_REJ_AUTH",  0, 0),
        ("rej_auth_wrong_channel", wrong_chan, 0, 0, TS + 100,     WINDOW, "IF4_REJ_AUTH",  0, 0),
        # freshness: too old, and (clock-skew symmetric) too far in the future
        ("rej_stale_old",   ok,          0, 0,  TS + WINDOW + 1,   WINDOW, "IF4_REJ_STALE", 0, 0),
        ("rej_stale_future", ok,         0, 0,  TS - WINDOW - 1,   WINDOW, "IF4_REJ_STALE", 0, 0),
        # parse rejects
        ("rej_len_short",   ok[:-1],     0, 0,  TS + 100,          WINDOW, "IF4_REJ_LEN",   0, 0),
        ("rej_len_long",    ok + b"\x00", 0, 0, TS + 100,          WINDOW, "IF4_REJ_LEN",   0, 0),
        ("rej_proto_version", bytes(bad_ver),  0, 0, TS + 100,     WINDOW, "IF4_REJ_PROTO", 0, 0),
        ("rej_proto_type",  bytes(bad_type),   0, 0, TS + 100,     WINDOW, "IF4_REJ_PROTO", 0, 0),
    ]


def _c_bytes(b):
    return ", ".join("0x%02x" % x for x in b)


def main():
    vecs = _v()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    key_h = OUT_DIR / "dev_key.h"
    key_h.write_text(
        "// GENERATED by tools/gen_vectors.py -- do not edit by hand.\n"
        "// DEV/BENCH key only: derive_key(%r, \"IF4\", %r) via esw/crypto.py.\n"
        "// Real per-unit provisioning is the doc 10 §8.3 open handoff (NVS + rotation).\n"
        "#pragma once\n"
        "#include <stdint.h>\n\n"
        "#define ESW_DEV_SITE_ID \"%s\"\n"
        "static const uint8_t ESW_DEV_KEY[32] = { %s };\n"
        % (DEV_MASTER.decode(), DEV_SITE, DEV_SITE, _c_bytes(DEV_KEY)),
        encoding="utf-8",
    )

    lines = [
        "// GENERATED by tools/gen_vectors.py FROM the Python reference codec (esw/if4.py).",
        "// Do not edit by hand; regenerate after any esw/if4.py or esw/crypto.py change.",
        "// The firmware runs these through if4_verify() at boot (and on the 'V' command):",
        "// a cross-language conformance check against the exact bytes the edge produces.",
        "#pragma once",
        "#include <stdint.h>",
        '#include "if4_verify.h"',
        "",
        "typedef struct {",
        "    const char *name;",
        "    const uint8_t *frame;",
        "    uint16_t frame_len;",
        "    uint8_t have_last;",
        "    uint32_t last_seq;",
        "    int64_t now_ms;",
        "    int64_t window_ms;",
        "    if4_result_t expect;",
        "    uint8_t exp_message_id;",
        "    uint32_t exp_seq;",
        "} if4_vector_t;",
        "",
    ]
    for name, frame, have_last, last_seq, now_ms, window, expect, mid, seq in vecs:
        lines.append("static const uint8_t VEC_%s[%d] = { %s };"
                     % (name, len(frame), _c_bytes(frame)))
    lines.append("")
    lines.append("static const if4_vector_t IF4_VECTORS[] = {")
    for name, frame, have_last, last_seq, now_ms, window, expect, mid, seq in vecs:
        lines.append('    { "%s", VEC_%s, %d, %d, %du, %dLL, %dLL, %s, %d, %du },'
                     % (name, name, len(frame), have_last, last_seq, now_ms, window,
                        expect, mid, seq))
    lines.append("};")
    lines.append("#define IF4_N_VECTORS (sizeof(IF4_VECTORS) / sizeof(IF4_VECTORS[0]))")
    lines.append("")
    (OUT_DIR / "test_vectors.h").write_text("\n".join(lines), encoding="utf-8")

    print("wrote %s (%d-byte dev key)" % (key_h, len(DEV_KEY)))
    print("wrote %s (%d vectors)" % (OUT_DIR / "test_vectors.h", len(vecs)))


if __name__ == "__main__":
    main()
