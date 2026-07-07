#!/usr/bin/env python3
# MicroPython-safety gate for esw/ -- the shipped subset that runs byte-identical
# on the host and on the K230 (ADR-0015 D3). esw/ must stay inside the conservative
# MicroPython/CanMV subset the K230 build supports, so this gate rejects constructs
# and stdlib imports that a minimal MicroPython target may not provide.
#
#   python software/tools/mp_safe_check.py                 # checks software/esw
#   python software/tools/mp_safe_check.py path/to/pkg     # checks any dir
#
# Exits 0 when clean, 1 (with a line-listed report) on any violation. This runs on
# CPython (it needs the `ast` module); the companion CI job additionally *executes*
# the boards under the real MicroPython unix port -- the AST gate enforces the subset,
# the mpy run proves the code actually loads and runs under MicroPython semantics.

import ast
import os
import sys

# Syntactic constructs outside the conservative subset (README "MicroPython / K230 note").
BAD_NODES = {
    ast.ListComp: "list comprehension",
    ast.SetComp: "set comprehension",
    ast.DictComp: "dict comprehension",
    ast.GeneratorExp: "generator expression",
    ast.Lambda: "lambda",
    ast.JoinedStr: "f-string",
}
# Top-level module names a minimal MicroPython build does not ship (or that pull in
# host-only numerics). hashlib is allowed *only* via the `try import hashlib / except
# import uhashlib` fallback pattern, which parses clean here (a plain Import node).
BAD_IMPORT_ROOTS = ("numpy", "np", "typing", "enum", "dataclasses", "abc")


def check_file(path):
    problems = []
    f = open(path, "r", encoding="utf-8")
    try:
        src = f.read()
    finally:
        f.close()
    tree = ast.parse(src, filename=path)
    base = os.path.basename(path)
    for node in ast.walk(tree):
        for bad_t, label in BAD_NODES.items():
            if isinstance(node, bad_t):
                problems.append("%s:%d  %s" % (base, getattr(node, "lineno", 0), label))
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = getattr(node, "module", None) or ""
            names = [a.name for a in node.names]
            for m in [mod] + names:
                if m and m.split(".")[0] in BAD_IMPORT_ROOTS:
                    problems.append("%s:%d  import %s" % (base, node.lineno, m))
    return problems


def iter_py(root):
    if os.path.isfile(root):
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        if "__pycache__" in dirpath:
            continue
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join("software", "esw")
    if not os.path.exists(root):
        # allow running from inside software/
        alt = os.path.join("esw") if os.path.basename(os.getcwd()) == "software" else root
        root = alt if os.path.exists(alt) else root
    if not os.path.exists(root):
        print("mp_safe_check: path not found: %s" % root)
        return 2
    problems = []
    n = 0
    for path in iter_py(root):
        n += 1
        problems.extend(check_file(path))
    if problems:
        print("MP-UNSAFE constructs found under %s:" % root)
        for p in problems:
            print("  " + p)
        return 1
    print("OK: %s (%d files) is MicroPython-safe" % (root, n))
    print("    (no f-strings/comprehensions/lambdas; no numpy/typing/enum/dataclasses/abc imports).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
