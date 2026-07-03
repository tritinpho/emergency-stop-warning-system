# harness -- the Level-A (event-level) simulation rig (doc 07 §2).
#
# The harness replaces ONLY the physical ends -- the sensors and the sign -- with
# models. The state machine it drives is the real esw/ SUT. This code is host
# tooling; it does NOT ship to the K230, so it may use conveniences the SUT avoids.
