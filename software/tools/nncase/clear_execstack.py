#!/usr/bin/env python3
"""Clear the executable-stack flag on an ELF64 shared object -- no external tools needed.

nncase 2.9.0 ships `libortki.so` (its ONNX shape-inference kernels) marked as requiring an
executable stack (PT_GNU_STACK with PF_X set). A hardened container loader refuses to grant
it -- "cannot enable executable stack as shared object requires: Invalid argument" -- and the
ONNX import segfaults. execstack and patchelf are absent from python:3.10-slim, so this does
the one edit both would: find the PT_GNU_STACK program header and clear its PF_X bit.

    python clear_execstack.py /path/to/libortki.so
"""
import struct
import sys

PT_GNU_STACK = 0x6474E551
PF_X = 0x1


def clear(path):
    with open(path, "rb") as f:
        data = bytearray(f.read())
    if data[:4] != b"\x7fELF":
        sys.exit("%s: not an ELF file" % path)
    if data[4] != 2:
        sys.exit("%s: not ELF64 (this patcher only handles 64-bit)" % path)
    # ELF64 header: e_phoff @0x20 (8B), e_phentsize @0x36 (2B), e_phnum @0x38 (2B), all LE.
    e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
    e_phnum = struct.unpack_from("<H", data, 0x38)[0]
    changed = False
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from("<I", data, off)[0]      # ELF64 Phdr: p_type, then p_flags
        if p_type == PT_GNU_STACK:
            p_flags = struct.unpack_from("<I", data, off + 4)[0]
            if p_flags & PF_X:
                struct.pack_into("<I", data, off + 4, p_flags & ~PF_X)
                changed = True
                print("%s: cleared PF_X on PT_GNU_STACK (0x%x -> 0x%x)"
                      % (path, p_flags, p_flags & ~PF_X))
            else:
                print("%s: PT_GNU_STACK already non-exec" % path)
    if changed:
        with open(path, "wb") as f:
            f.write(data)
    elif not changed:
        print("%s: nothing to change" % path)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: clear_execstack.py <libfile.so>")
    clear(sys.argv[1])
