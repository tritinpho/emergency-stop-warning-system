# ESW software — Level-A simulation harness + state-machine SUT

This is **workstream #1** from the build plan: the event-level ("Level A") simulation
harness ([doc 07 §2](../docs/07-simulation-methodology.md)) driving the **real** decision
state machine as the system under test (SUT), scored against the **SC-01..30** scenario
oracles ([doc 07 §5](../docs/07-simulation-methodology.md)).

It embodies the three build decisions in **[ADR-0015](../docs/adr/ADR-0015-state-machine-implementation-strategy.md)**:

1. **The SC-01..30 oracles are the executable spec.** The state machine is correct when
   its sign-over-time matches every scenario's oracle. TDD against the board.
2. **Fixed-rate tick execution.** `StateMachine.tick(now, observations, health)` is called
   every cycle (10 Hz in the harness); timers are deadlines against `now`, no wall-clock is
   read inside the SUT (determinism).
3. **MicroPython/CanMV runtime.** `esw/` is the MicroPython-safe subset that runs **byte-identical**
   here (host CPython / MicroPython unix port) and on the K230 — pending the timing spike below.

## Layout

```
software/
  esw/              # THE SUT — ships to the K230. MicroPython-safe subset, no sim-only branches.
    params.py       #   §7a safety-parameter surface + FR-20 clamps
    state_machine.py#   the decision state machine (doc 02 §4)
  harness/          # host tooling — NOT shipped. Replaces only the sensor + sign ends.
    sensors.py      #   scenario script -> IF-2 track events
    sign.py         #   synthetic sign controller + dead-man's switch (IF-4)
    runner.py       #   tick loop, fault injection, oracle comparator
  scenarios/
    catalogue.py    #   SC-01..30 — the executable spec
  run_tests.py      # the board
```

## Run

```
python software/run_tests.py          # from the repo root
micropython run_tests.py              # from software/, on the MicroPython unix port
```

Exit 0 when healthy: every `impl` scenario passes and every `xfail` still fails for its
stated reason. A regressed `impl` or a flipped `xfail` exits 1.

## The board today

**8 passing · 1 intentional red · 21 pending.** The green set covers the happy path, dwell,
pass-through, brief-occlusion hold, multi-vehicle set semantics, and the three fail-safe
blank paths (kill SM / kill box / cut link → sign blanks ≤ `T_signhold`).

## Red → green: how to grow it

1. **SC-19 is the first target (currently red on purpose).** It pushes `T_dwell = 900 s`;
   the oracle expects it clamped to 10 s (FR-20). Wire the clamp in `StateMachine.__init__`:

   ```python
   from esw.params import clamp_config
   if config is not None:
       config, _rejected = clamp_config(config)   # TODO(SC-19) -> this line turns it green
   ```

   (Verified: with this line, SC-19 flips to green.)

2. **Then take the `todo` rows one at a time.** Each `# TODO(SC-xx)` marker in
   `state_machine.py` names the scenario it unblocks — the watchdog (SC-28), the
   occlusion/`CAMERA_OCCLUDED_DEGRADED` hold + `T_degraded_max` (SC-06..09), the sensor-mode
   matrix (SC-25..27), override (SC-16..18), congestion (SC-11), pedestrian onset (SC-12).
   Author the scenario's timeline + oracle in `catalogue.py`, flip its status `todo → impl`,
   implement until green.

## MicroPython / K230 note

`esw/` sticks to the MicroPython-safe subset (no `enum`/`dataclasses`/`typing`, no host-only
stdlib) so the SUT is one codebase in sim and on the K230. Before committing hard to
MicroPython for the safety loop, run the **timing spike**: measure GC-pause / loop-jitter
under YOLO load on the K230 and confirm it stays well inside `T_assert_refresh` (0.5 s) and
`T_signhold` (2 s). See [ADR-0015](../docs/adr/ADR-0015-state-machine-implementation-strategy.md).

## Deliberately not here (yet)

Frame-level (Level B) injection, the real detector / `kmodel`, camera↔radar fusion, and the
concrete IF-4 wire encoding — all deferred to their phase ([doc 07 §2](../docs/07-simulation-methodology.md),
the readiness review). The harness models sensors and the sign; it does **not** model the RF link.
