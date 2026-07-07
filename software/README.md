# ESW software — Level-A/B simulation harness + perception & state-machine SUT

This is **workstream #1** from the build plan: the event-level ("Level A") simulation
harness ([doc 07 §2](../docs/07-simulation-methodology.md)) driving the **real** decision
state machine as the system under test (SUT), scored against the **SC-01..37** scenario
oracles ([doc 07 §5](../docs/07-simulation-methodology.md)). A second board adds the
**Level-B** perception stage (IF-1→IF-2) — the real ROI-gating + tracking pipeline driven by
scripted *detections* (with doc 07 §3.1 detector nuisances) — scored against **PC-01..11**.

It embodies the three build decisions in **[ADR-0015](../docs/adr/ADR-0015-state-machine-implementation-strategy.md)**:

1. **The SC-01..37 oracles are the executable spec.** The state machine is correct when
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
    perception.py   #   IF-1→IF-2 pipeline: ROI gating + ByteTrack-lite tracker (ADR-0003)
    geometry.py     #   homography + ROI-overlap + first-order & projected footprints
    if4.py          #   IF-4 wire codec: authenticated SHOW frame + verify (doc 08 §3, doc 10)
    actuator.py     #   IF-4 edge-side refresh-or-blank driver (no "off" command)
    health.py       #   health monitor: derives {camera,radar}, time integrity, force-safe (FR-10/NFR-16/IF-5)
  harness/          # host tooling — NOT shipped. Replaces only the sensor + sign ends.
    sensors.py      #   Level-A: scenario script -> IF-2 track events (+ gnss/self-test liveness)
    frames.py       #   Level-B: scenario -> detector output + doc 07 §3.1 nuisances
    sign.py         #   sign controller: decodes+verifies real IF-4 frames + dead-man's switch
    runner.py       #   tick loop, health monitor, fault injection, oracle comparator
  scenarios/
    catalogue.py        #   SC-01..37 — Level-A executable spec (the state machine)
    perception_cases.py #   PC-01.. — Level-B perception cases (IF-1→IF-2)
    health_cases.py     #   HM-01.. — Level-C health-monitor unit cases
  run_tests.py            # Level-A state-machine board
  run_perception_tests.py # Level-B perception board
  run_health_tests.py     # Level-C health-monitor board
```

## Run

```
python software/run_tests.py             # Level A — SC-01..37 state-machine board
python software/run_perception_tests.py  # Level B — perception (IF-1→IF-2) board
python software/run_health_tests.py      # Level C — health-monitor (FR-10/NFR-16/IF-5) board
micropython run_tests.py                 # from software/, on the MicroPython unix port
```

All exit 0 when healthy and 1 on any surprise. **Level A** injects IF-2 events and tests the
decision logic — now with the **real health monitor** in the loop deriving the sensor mode; **Level
B** injects *detections* (image bboxes) and runs the **real** perception (ROI gating + tracker) that
produces those events (doc 07 §2) — and closes the loop through the real state machine to the sign;
**Level C** unit-tests the health monitor (`esw/health.py`) in isolation. The detector itself (a
K230 `kmodel`) is a drop-in backend behind `Perception.step()`, so the perception pipeline is
byte-identical in sim and on the board.

## The boards today

**Level A — `run_tests.py`: 37 passing · 0 red · 0 pending** (`exit 0`). The full SC-01..37
catalogue: the happy path, dwell / creep / cold-start, pass-through, the set-based occlusion
policy (`WARN_HOLD → CAMERA_OCCLUDED_DEGRADED → T_degraded_max` forced clear, incl. the
weak-(b) stale-ON guard), the FULL / CAMERA-ONLY / RADAR-ONLY / NEITHER sensor-mode matrix
(BLIND-TO-NEW), the watchdog, congestion suppression, pedestrian presence-onset, the
motorcycle small-RCS case, warm reboot, operator override (force-on / force-off / mute,
out-of-policy clamp), OTA-deferral, calibration-drift, sign-stuck → SAFE_STATE, alarm dedup /
re-escalate, the three fail-safe blank paths (kill SM / kill box / cut link → sign blanks
≤ `T_signhold`), the **IF-4 auth path** (SC-33/34: forged and replayed `SHOW` frames are
rejected — an attacker on the link can neither light nor sustain the sign), and the **health
monitor in the loop** (SC-35 derived-health debounce, SC-36 GNSS/PPS loss → DEGRADED-not-blanked,
SC-37 independent force-safe blanks the sign despite `SHOW`). The state machine's sign assertions
now drive the **real `esw/if4` frame codec** through the actuator to the controller, so the board
verifies the exact bytes the ESP32 firmware will (doc 10); the sensor mode is now **derived** by
the real health monitor, not injected.

**Level B — `run_perception_tests.py`: 11 passing + closed loop** (`exit 0`). PC-01..05 cover
the pipeline plumbing (ROI overlap, track continuity, speed). PC-06..11 harden it against the
doc 07 §3.1 detector nuisances: box **jitter** (windowed + EMA speed rejects a fake >`speed_gate`
reading — raw frame-differencing would report ~16 km/h on a stopped car), a brief **dropout**
(coasting keeps one `track_id` — no ID switch, no spurious clear), transient **false positives**
(shadow / headlight → never confirm), **class confusion** (class-agnostic association stays
stable), a **low-confidence dip** (ByteTrack two-stage recovery), and a **perspective footprint**
that reads ROI overlap faithfully where the first-order box would cry-wolf (0.42 vs 0.58 at a
0.50 gate). The closed loop runs detections → real perception → real state machine → sign.

**Level C — `run_health_tests.py`: 6 passing** (`exit 0`). HM-01..06 unit-test the health monitor
(`esw/health.py`) in isolation: sensor liveness with a **debounce** (a brief dropout doesn't flap
the mode; a sustained loss reports the sensor DOWN), radar-dead-from-boot, **time integrity**
(GNSS/PPS loss → `time_valid` false past the hold-over, re-lock → valid), and the **independent
force-safe** (a critical self-test failure trips IF-5). The monitor derives the `{camera, radar}`
health the state machine consumes, so the FULL/CAMERA-ONLY/RADAR-ONLY/NEITHER mode is computed,
not injected. `T_sensor_timeout` defaults to 0 (react immediately, conservative) — tune it up for
anti-flap; absolute-time hold-over across a multi-hour outage is field-deferred (NFR-16).

## Extending the board

The catalogue is the spec: to add a behaviour, author its scenario (timeline + oracle) in
`catalogue.py`, then grow `state_machine.py` until the board is green again. A checkpoint may
assert the sign state (`on`) and/or any disposition field the runner records
(`state` / `posture` / `mode` / `alert` / `override` / `ota_deferred` / `alarm_count`), so an
oracle can pin the *disposition*, not just whether the sign is lit (doc 07 §4). Occlusion /
degraded tests shrink the safety timers via `config_push` (within the FR-20 bounds) for fast
deterministic runs. Keep every change inside `esw/`'s MicroPython-safe subset — it ships
byte-identical to the K230.

The Level-B `perception_cases.py` works the same way: a case injects *detections* (with the
`jitter_px` / `drop` / `confuse` / `score_drops` / `false_detections` nuisances) and asserts
the perception output at each checkpoint (`n_detected` / `n_in_roi` / `speed_*` / `max_in_roi_*`),
the whole-run `n_ids` (the ID-switch metric), and/or the closed-loop sign via `loop_checks` — so
a case can prove a nuisance never causes a false confirmation and a real track is never dropped.

## MicroPython / K230 note

`esw/` sticks to the MicroPython-safe subset (no `enum`/`dataclasses`/`typing`, no host-only
stdlib) so the SUT is one codebase in sim and on the K230. Before committing hard to
MicroPython for the safety loop, run the **timing spike**: measure GC-pause / loop-jitter
under YOLO load on the K230 and confirm it stays well inside `T_assert_refresh` (0.5 s) and
`T_signhold` (2 s). See [ADR-0015](../docs/adr/ADR-0015-state-machine-implementation-strategy.md).

## Deliberately not here (yet)

The real detector / `kmodel` (a drop-in backend behind `Perception.step()`) and camera↔radar
fusion (blocked on the RQ-H1 radar procurement) are deferred to their phase
([doc 07 §2](../docs/07-simulation-methodology.md), the readiness review). The concrete IF-4 wire
encoding **now exists** (`esw/if4.py` + `esw/actuator.py`, doc 10); what remains deferred is the
**RF link itself** — Level B injects scripted *detections*, not rendered camera frames, and the
harness models the sensors and the sign controller but **not** the LoRa PHY (airtime / range /
duty are the [ADR-0014](../docs/adr/ADR-0014-sign-link-bearer.md) bench tests).
