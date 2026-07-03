# esw -- Emergency Stop-Lane Warning: the safety-loop SUT.
#
# This package is the "system under test": the SAME code runs in the Level-A
# simulation harness (host CPython / MicroPython unix port) and on the K230
# (CanMV/MicroPython). Per doc 07 §2 there are NO sim-only branches in here.
# Keep it to the MicroPython-safe Python subset: no enum, no dataclasses, no
# typing, no f-strings-only features beyond 3.4, no host-only stdlib.
