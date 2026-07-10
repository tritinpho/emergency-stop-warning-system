# ESW software — Level-A/B simulation harness + perception & state-machine SUT

This is **workstream #1** from the build plan: the event-level ("Level A") simulation
harness ([doc 07 §2](../docs/07-simulation-methodology.md)) driving the **real** decision
state machine as the system under test (SUT), scored against the **SC-01..47** scenario
oracles ([doc 07 §5](../docs/07-simulation-methodology.md)). A second board adds the
**Level-B** perception stage (IF-1→IF-2) — the real ROI-gating + tracking pipeline driven by
scripted *detections* (with doc 07 §3.1 detector nuisances) — scored against **PC-01..12**.

It embodies the three build decisions in **[ADR-0015](../docs/adr/ADR-0015-state-machine-implementation-strategy.md)**:

1. **The SC-01..47 oracles are the executable spec.** The state machine is correct when
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
    telemetry.py    #   IF-6 heartbeat + IF-7 audit-event emitter (fingerprinted; doc 08 §4, doc 02 §7)
    sink.py         #   durable evidence outbox: store-and-forward IF-6/IF-7 records (ADR-0007, doc 08 §4)
    crypto.py       #   shared HMAC-SHA256 + constant-time compare (both hardened channels; ADR-0012)
    command.py      #   IF-8/9/10 auth command channel: verify override/OTA/ack (doc 08 §5, ADR-0012)
    app.py          #   THE DEVICE LOOP — wires all of the above; backends injected (K230 = firmware/k230-detector/esw-app/)
  harness/          # host tooling — NOT shipped. Replaces only the sensor + sign ends.
    sensors.py      #   Level-A: scenario script -> IF-2 track events (+ gnss/self-test liveness)
    frames.py       #   Level-B: scenario -> detector output + doc 07 §3.1 nuisances
    sign.py         #   sign controller: decodes+verifies real IF-4 frames + dead-man's switch
    runner.py       #   tick loop, health monitor, telemetry, fault injection, oracle comparator
    metrics.py      #   acceptance-evidence reducer: recall+Wilson, false-activation, latency (ADR-0007)
    store.py        #   Level-E: file-backed durable store + fake uplink for the evidence outbox
    evidence.py     #   offline scorer for DEVICE logs: observed-hours, provenance + capability gates
    rig.py          #   the EdgeApp bench rig (shared by Levels D and H)
    commands.py     #   Level-F: scenario commands -> authenticated IF-8/9/10 frames (+ forged/replay)
    devices.py      #   Level-H: host backends for esw/app.py (camera, radio, clock, store, capture)
  scenarios/
    catalogue.py        #   SC-01..47 — Level-A executable spec (the state machine)
    perception_cases.py #   PC-01.. — Level-B perception cases (IF-1→IF-2)
    health_cases.py     #   HM-01.. — Level-C health-monitor unit cases
    evidence_cases.py   #   EV-01.. — Level-D acceptance-evidence set (with ground-truth oracles)
    command_cases.py    #   CMD-01.. — Level-F authenticated-command cases (IF-8/9/10)
    app_cases.py        #   AP-01.. — Level-H device-loop cases (esw/app.py end to end)
  run_tests.py            # Level-A state-machine board
  run_perception_tests.py # Level-B perception board
  run_health_tests.py     # Level-C health-monitor board
  run_metrics.py          # Level-D acceptance-evidence board (reducer unit tests + sample report)
  run_sink_tests.py       # Level-E durable-evidence-outbox board (store-and-forward, at-least-once)
  run_command_tests.py    # Level-F authenticated command-channel board (IF-8/9/10 override/OTA/ack)
  run_integration_tests.py # Level-G merged K230 pipeline (raw YOLO -> adapter -> perception -> SM -> sign, ADR-0016)
  run_app_tests.py         # Level-H the device application loop (esw/app.py) under host backends
```

## Run

```
python software/run_tests.py             # Level A — SC-01..47 state-machine board
python software/run_perception_tests.py  # Level B — perception (IF-1→IF-2) board
python software/run_health_tests.py      # Level C — health-monitor (FR-10/NFR-16/IF-5) board
python software/run_metrics.py           # Level D — acceptance-evidence reducer + sample report
python software/run_sink_tests.py        # Level E — durable evidence outbox (store-and-forward)
python software/run_command_tests.py     # Level F — authenticated command channel (IF-8/9/10)
python software/run_integration_tests.py # Level G — merged K230 pipeline (adapter→perception→SM→sign)
python software/run_app_tests.py         # Level H — the device loop (esw/app.py), incl. boot capability report
python software/tools/mp_safe_check.py software/esw   # MicroPython-safety AST lint on esw/
python software/tools/mpy_smoke.py        # esw smoke: perception + geometry + sink + command + adapter + app loop
python software/tools/score_capture.py <session-dir>...   # score real device captures (exits 1 unless acceptance-grade)

# Host detector-in-the-loop (needs `pip install ultralytics`, NOT required by any board or CI):
# a REAL pretrained YOLOv8n driving the REAL EdgeApp over a video/still, written out as a
# device-format session the scorer grades at tier "host" — validates the pipeline (adapter,
# tracker under real detector noise, dwell, IF-4 cadence), never the unit (INT8 kmodel differs).
python software/tools/host_yolo_loop.py --selftest
python software/tools/host_yolo_loop.py --video clip.mp4 --calib calib.json --hazard 12.5:96 --score
python software/tools/host_yolo_loop.py --video night.mp4 --calib calib.json --light-filter  # backlog #4b A/B

# The shipped esw/ subset also RUNS under the real MicroPython unix port (not just CPython):
cd software && micropython run_tests.py && micropython run_health_tests.py && micropython tools/mpy_smoke.py
```

Both are enforced in CI on every push/PR ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)): a
**cpython** job runs all eight boards + the AST lint + the smoke, and a **micropython** job runs the
shipped subset under `micropython/unix:v1.28.0` — see the *MicroPython / K230 note* below.

Boards A–C, E, and F exit 0 when healthy and 1 on any surprise; D exits 0 when the reducer unit tests pass
(the report is informational). **Level A** injects IF-2 events and tests the decision logic — now
with the **real health monitor** in the loop deriving the sensor mode and the **real telemetry
emitter** producing the audit log; **Level B** injects *detections* (image bboxes) and runs the
**real** perception (ROI gating + tracker) that produces those events (doc 07 §2) — and closes the
loop through the real state machine to the sign; **Level C** unit-tests the health monitor
(`esw/health.py`) in isolation; **Level D** reduces the IF-7 event log against ground-truth oracles
into the doc 01 §5 acceptance metrics; **Level E** proves the durable evidence outbox (`esw/sink.py`)
persists that IF-7 log, survives reboot, and forwards it at-least-once — so the metrics can be reduced
from a durable artifact, not just in-process; **Level F** proves the authenticated IF-8/9/10 command
channel — a forged, replayed, or stale override / OTA / ack is rejected before it reaches the state
machine. The detector itself (a K230 `kmodel`) is a drop-in backend behind `Perception.step()`, so the
perception pipeline is byte-identical in sim and on the board.

## The boards today

**Level A — `run_tests.py`: 47 passing · 0 red · 0 pending** (`exit 0`). The full SC-01..47
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
SC-37 independent force-safe blanks the sign despite `SHOW`), plus five code-review regressions:
**radar-corroboration gap tolerance** (SC-39 — *simulation-only: [ADR-0001](../docs/adr/ADR-0001-sensing-modality.md) is Rejected, so no radar beat ever arrives on the real unit and this path never runs; see doc 04 R20*: one missed radar beat holds the occlusion warning —
`T_corr_tolerance` — while sustained silence still loud-clears at `T_hold` from the *last*
corroboration), the **post-blackout watchdog re-arm** (SC-40: recovering from a > `T_watchdog`
NEITHER outage re-holds quietly instead of firing a spurious watchdog CRITICAL), and **class-flicker
warrant isolation** (SC-41/42: the person presence clock is its own onset, so one relabelled tick
can neither fast-clear a confirmed pedestrian's occlusion hold nor let `T_person_debounce` stand in
for a vehicle's full `T_dwell`) with the **bystander congestion filter** (SC-43: R14 counts stationary
*vehicles* — three people standing near the road are not a jam and cannot suppress a genuine
shoulder warning). The state machine's sign assertions
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
not injected. **On the real unit only `CAMERA-ONLY` and `NEITHER` are reachable** — radar was
rejected for this phase ([ADR-0001](../docs/adr/ADR-0001-sensing-modality.md)), so the unit sits
permanently in `CAMERA-ONLY`/`DEGRADED` (doc 04 R21) and the occlusion hold never arms (R20). The
`FULL` / `RADAR-ONLY` paths are exercised in simulation and retained for the cấp sở project.
`T_sensor_timeout` defaults to 0 (react immediately, conservative) — tune it up for
anti-flap; absolute-time hold-over across a multi-hour outage is field-deferred (NFR-16).

**Level D — `run_metrics.py`: reducer unit tests + a sample acceptance report** (`exit 0` on the
unit tests). The SUT now emits the **IF-6 heartbeat + IF-7 audit events** (`esw/telemetry.py`,
each fingerprinted with cfg/model/calib/fw versions, R10); the offline **reducer** (`harness/
metrics.py`) turns that event log + each scenario's ground-truth oracle into the doc 01 §5 metrics:
**recall with a Wilson 95% lower bound**, **false activation** (per-100-scenarios *and* per-hour),
and detection latency. The board pins the reducer math (Wilson, interval reconstruction, TP/FP/FN,
rates) and prints a report over the EV-01..06 evidence set. **It is honestly tiered S (synthetic):**
per the doc 01 §5 hard rule, recall from synthetic events is **not** a recall claim — the recall N
must be **real captures**. The sample report makes the point visible: 4/4 synthetic positives is
100% recall but only a **~51% Wilson lower bound** — the machinery is real and ready to ingest real
staged/field captures; the *number* waits on them.

**Level E — `run_sink_tests.py`: 8 passing** (`exit 0`). SK-01..08 exercise the durable evidence
outbox (`esw/sink.py`) over the host file store (`harness/store.py`): records **survive an
object-loss reboot** with the seq cursor intact (SK-01), a **flaky link** loses nothing and delivers
in order (SK-02), an **uplink outage** buffers then resumes from the watermark with no re-send
(SK-03), a **crash between send and ack** re-sends so the contract is **at-least-once** — the consumer
dedups by seq, never a silent loss (SK-04), the acceptance metrics reduced from the **durable log**
are **identical** to the in-process path (SK-05, the faithful-conduit proof), a **dead box** logs
nothing so the gap in the log is the outage (SK-06), a **torn tail line** (crash mid-append) never
bricks `recover()` — the crash-consistent read skips it, counted loud, and the next append heals the
unterminated line (SK-07), and the steady-state `pump()` drains a **bounded in-RAM tail** so the
per-tick path never re-parses the growing flash log — only a deep post-outage backlog falls back to
an in-order store scan, still losing nothing (SK-08). The store-and-forward *policy* ships in `esw/`;
the durable store and the oversight uplink are drop-in backends (a host file + a fake link here;
flash + MQTT on the K230). This surfaced one honest fix: the audit record stamped `cfg_ver` as raw
`bytes`, so any durable/wire serializer must encode it (the store hex-encodes it) — a future cleanup
could have telemetry stamp a hex fingerprint so the record is natively wire-safe.

**Level F — `run_command_tests.py`: 16 passing** (`exit 0`). CMD-01..16 drive the authenticated
IF-8/9/10 command channel (`esw/command.py`) through the real loop — the receive-side twin of the
IF-4 sign-link. A **valid** override lights an otherwise-dark sign, a valid OTA request defers behind
an active warning, a valid operator ack freezes alarm re-escalation, and a valid **config-push**
retunes the live unit (CMD-09: `T_dwell` 5→3 s makes a parked car confirm earlier) — the positive
controls; their **forged** (wrong-key → `auth`), **replayed** (seq ≤ watermark → `replay`), and
**stale** (ts outside the freshness window → `stale`) counterparts are rejected upstream and change
nothing, so an attacker who can transmit can neither force the sign, trigger a restart, silence the
operator escalation (NFR-09 / NFR-15), nor reconfigure the unit. An **unknown command type** (a
version-skewed TMC / fuzzed uplink) is rejected loud at verify (CMD-13 → `ctype`), never silently
dropped in dispatch, and an authenticated frame whose payload is **not a JSON object** is rejected
at verify too (CMD-15 → `payload`) — every consumer keys into the payload, so a non-object must be
inert, never a crash further down the safety loop. The **IF-8 config** path adds three
guards on top of auth: an out-of-§7a value is clamped and reported fail-loud (CMD-10, FR-20/21),
**NaN — which defeats every numeric bound check — is refused outright, keeping last-good** (CMD-14),
and the bounded safety backstops (`T_signhold` / `T_watchdog` / `T_degraded_max` / …) are **boot-only** —
a runtime push to one is refused (CMD-11), so no live reconfiguration can move a fail-safe invariant.
The same NaN lesson is applied to **IF-10 override timing fields**: a `mute` with a NaN expiry would
neither clamp nor ever expire (a forever-mute — mandatory auto-expiry defeated by one malformed
field), so non-numeric / NaN `issued`/`expiry` are rejected `malformed` and the warning stays up
(CMD-16).
A runtime push also **re-fingerprints `cfg_ver`**, so IF-4 frames and IF-6/7 audit records always
bind to the config in force (R10), never the boot config a push has replaced.
The auth is the same HMAC + two-guard anti-replay as IF-4 (shared `esw/crypto.py`, with per-site /
per-channel **key derivation** — `crypto.derive_key(master, "IF4"|"CMD", site_id)` — so a frame
MAC'd for one unit or channel can never verify on another); the command
*policy* ships in `esw/`, the wire transport is a drop-in backend.

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
stdlib) so the SUT is one codebase in sim and on the K230. CI enforces this two ways
(`.github/workflows/ci.yml`): `tools/mp_safe_check.py` **AST-lints** esw/ for out-of-subset
constructs, and — the stronger check — the Level-A and Level-C boards plus `tools/mpy_smoke.py`
(perception + geometry + sink + command) actually **run under the MicroPython unix port** (`micropython/unix:v1.28.0`),
so all twelve shipped modules are proven to load and run under real MicroPython semantics, not just
parse clean. (This surfaced a real bug the AST lint could never catch: the board entrypoints used
`os.path`, which MicroPython's `os` does not provide — so `micropython run_tests.py` had never
actually run until the bootstrap was made mpy-safe.) A green CPython board is necessary but **not
sufficient** — the K230 runs CanMV/MicroPython, not CPython.

Still deferred to the hardware: the **timing spike** — measure GC-pause / loop-jitter under YOLO
load on the K230 and confirm it stays well inside `T_assert_refresh` (0.5 s) and `T_signhold` (2 s).
That needs the board; the CI mpy run proves *portability*, the spike proves *timing*.
See [ADR-0015](../docs/adr/ADR-0015-state-machine-implementation-strategy.md).

## Deliberately not here (yet)

The real detector / `kmodel` (a drop-in backend behind `Perception.step()`) and camera↔radar
fusion (blocked on the RQ-H1 radar procurement) are deferred to their phase
([doc 07 §2](../docs/07-simulation-methodology.md), the readiness review). The concrete IF-4 wire
encoding **now exists** (`esw/if4.py` + `esw/actuator.py`, doc 10); what remains deferred is the
**RF link itself** — Level B injects scripted *detections*, not rendered camera frames, and the
harness models the sensors and the sign controller but **not** the LoRa PHY (airtime / range /
duty are the [ADR-0014](../docs/adr/ADR-0014-sign-link-bearer.md) bench tests). The durable evidence
**outbox** (`esw/sink.py`) and the authenticated **IF-8/9/10 command channel** (`esw/command.py`,
override / OTA / ack / config) likewise now exist — including **runtime config-push** (IF-8:
§7a-clamped, fail-loud, safety backstops boot-only) — but the real **transport bindings** are still
drop-in backends: telemetry forwards to a fake uplink (the reducer runs offline over the durable log),
and commands arrive as harness-built frames rather than over a live MQTT/HTTPS link.
