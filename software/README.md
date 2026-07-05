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
    perception.py   #   IF-1→IF-2 pipeline: ROI gating + tracker (detector-agnostic, ADR-0003)
    geometry.py     #   ground-plane homography + ROI-overlap geometry
  harness/          # host tooling — NOT shipped. Replaces only the sensor + sign ends.
    sensors.py      #   Level-A: scenario script -> IF-2 track events
    frames.py       #   Level-B: scenario script -> detector output (image bboxes)
    sign.py         #   synthetic sign controller + dead-man's switch (IF-4)
    runner.py       #   tick loop, fault injection, oracle comparator
  scenarios/
    catalogue.py        #   SC-01..30 — Level-A executable spec (the state machine)
    perception_cases.py #   PC-01.. — Level-B perception cases (IF-1→IF-2)
  run_tests.py            # Level-A state-machine board
  run_perception_tests.py # Level-B perception board
```

## Run

```
python software/run_tests.py             # Level A — SC-01..30 state-machine board
python software/run_perception_tests.py  # Level B — perception (IF-1→IF-2) board
micropython run_tests.py                 # from software/, on the MicroPython unix port
```

Both exit 0 when healthy and 1 on any surprise. **Level A** injects IF-2 events and tests the
decision logic; **Level B** injects *detections* (image bboxes) and runs the **real** perception
(ROI gating + tracker) that produces those events (doc 07 §2) — and closes the loop through the
real state machine to the sign. The detector itself (a K230 `kmodel`) is a drop-in backend behind
`Perception.step()`, so the perception pipeline is byte-identical in sim and on the board.

## The board today

**30 passing · 0 red · 0 pending** — the full SC-01..30 catalogue is green (`exit 0`). Coverage:
the happy path, dwell / creep / cold-start, pass-through, the set-based occlusion policy
(`WARN_HOLD → CAMERA_OCCLUDED_DEGRADED → T_degraded_max` forced clear, incl. the weak-(b)
stale-ON guard), the FULL / CAMERA-ONLY / RADAR-ONLY / NEITHER sensor-mode matrix (BLIND-TO-NEW),
the watchdog, congestion suppression, pedestrian presence-onset, the motorcycle small-RCS case,
warm reboot, operator override (force-on / force-off / mute, out-of-policy clamp), OTA-deferral,
calibration-drift, sign-stuck → SAFE_STATE, alarm dedup / re-escalate, and the three fail-safe
blank paths (kill SM / kill box / cut link → sign blanks ≤ `T_signhold`).

## Extending the board

The catalogue is the spec: to add a behaviour, author its scenario (timeline + oracle) in
`catalogue.py`, then grow `state_machine.py` until the board is green again. A checkpoint may
assert the sign state (`on`) and/or any disposition field the runner records
(`state` / `posture` / `mode` / `alert` / `override` / `ota_deferred` / `alarm_count`), so an
oracle can pin the *disposition*, not just whether the sign is lit (doc 07 §4). Occlusion /
degraded tests shrink the safety timers via `config_push` (within the FR-20 bounds) for fast
deterministic runs. Keep every change inside `esw/`'s MicroPython-safe subset — it ships
byte-identical to the K230.

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
