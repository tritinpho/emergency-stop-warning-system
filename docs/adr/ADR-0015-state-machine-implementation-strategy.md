# ADR-0015: State-machine implementation strategy — executable spec, execution model, runtime

**Status:** Accepted (software side) — 2026-07-03 (D3 runtime **conditioned** on a confirming K230 timing spike)
**Date:** 2026-07-03
**Deciders:** PI / software lead (Tin)

## Context

The pre-build readiness review found the design layer build-ready: the interface contracts are frozen ([ICD v1](../08-interface-control-document.md)), the state machine is specified at edge level ([doc 02 §4](../02-system-architecture.md) + the §7a parameter surface), and there is a 30-scenario oracle catalogue ([doc 07](../07-simulation-methodology.md)). What remained were three **implementation-level** choices the design ADRs deliberately did not make — they sit below the altitude those ADRs operate at, yet each shapes every line of the state-machine code. This ADR records all three together because in practice they are one coupled decision: *how we build and test the safety loop.* (It intentionally bundles three sub-decisions rather than splitting them into 0015/0016/0017 — they are inseparable when you sit down to write the code.)

## Decision

- **D1 — The SC-01..30 oracles are the executable spec.** The scenario oracles in [doc 07 §5](../07-simulation-methodology.md) are the authoritative, executable specification of the state machine: the code is correct when its sign-over-time matches every oracle. The state diagram ([doc 02 §4](../02-system-architecture.md)) and the 5×4 sensor-mode matrix become documentation the tests enforce. Build TDD-first against the board.
- **D2 — Fixed-rate tick execution.** The machine is a `tick(now, observations, health)` evaluated at a fixed cycle (10 Hz in the harness): recompute the in-ROI track set atomically each tick, evaluate every timer as a deadline against `now`. No wall-clock is read inside the SUT — determinism and exact replay.
- **D3 — MicroPython/CanMV runtime**, one **byte-identical** codebase in the sim harness and on the K230 — **conditioned** on a K230 timing spike confirming GC-pause / jitter stays well inside the safety timers. Fall back to a C core only if the spike fails.

## Options Considered

### D1 — what arbitrates when the three SM representations disagree
| Option | Assessment |
|--------|------------|
| **Scenario oracles SC-01..30 (chosen)** | Executable; mechanically catches drift; doubles as the Phase-3 acceptance backbone |
| State diagram canonical | Familiar, but nothing enforces its consistency with the matrix / scenarios |
| All three co-equal, reconcile in review | Lowest effort, highest chance a latent inconsistency reaches code |

### D2 — runtime shape
| Option | Assessment |
|--------|------------|
| **Fixed-rate tick (chosen)** | Deterministic, watchdog-friendly, trivially replayable against oracles; negligible idle cost |
| Event-driven | Lower idle CPU; timing/ordering harder to reason about and to reproduce |
| Hybrid (event in, tick timers) | More moving parts; only if K230 idle CPU proves to matter |

### D3 — language / runtime (one codebase, sim + K230; [doc 07 §2](../07-simulation-methodology.md) forbids a sim-vs-ship split)
| Option | Assessment |
|--------|------------|
| **MicroPython/CanMV (chosen, spike-confirmed)** | Same runtime as perception; team's existing skill; fastest path. Safety timers (refresh 0.5 s, signhold 2 s, watchdog 30 s) are 40×+ a typical GC pause |
| Portable C / C-core | Strongest determinism, cleaner safety-case; costs a second language on the K230 side and slower iteration |
| Spike first, then decide | Safest epistemically; blocks workstream #1 for days |

## Trade-off Analysis

The three picks share one spine: **make the safety logic cheap to verify.** D1 turns "three representations could drift" into a passing test suite and hands Phase 3 its evidence for free. D2 is what makes the oracles replayable and the fail-safe timers provably correct — an event-driven loop trades that away for idle CPU the K230 does not need to save. D3 is the only pick with a genuine open risk (GC pauses in a safety loop), but the arithmetic is reassuring: the tightest deadline is `T_assert_refresh` at 0.5 s — ~40× a typical MicroPython GC pause — and the sign only blanks after `T_signhold` = 2 s, so a stray pause perturbs nothing. Rather than pay for a second language (C) on dogma, we build in MicroPython and let a cheap spike *confirm* the margin. If the spike surprises us, only D3 flips to a C core; D1/D2 are unaffected.

## Consequences

- **Easier:** one runtime across perception + safety loop; deterministic, replayable tests; the SC board is simultaneously the spec and the acceptance evidence; new behaviour is TDD-driven.
- **Harder:** the SUT must stay in the MicroPython-safe subset (no `enum` / `dataclasses` / `typing`, no host-only stdlib) — kept honest by running the board on the **MicroPython unix port** in CI, not just CPython. The tick rate is itself a safety parameter (too slow blunts NFR-01 latency; too fast wastes solar power) and must be justified.
- **Revisit when:** the K230 timing spike lands (confirm MicroPython, or flip D3 to a C core), or a future heavier on-target workload erodes the GC margin.

## Action Items

1. [ ] **K230 timing spike** — measure GC-pause / loop-jitter under YOLO load; confirm it is `« T_assert_refresh`. This is the gate on D3.
2. [ ] **Wire the FR-20 config clamp** in `StateMachine.__init__` (`esw.params.clamp_config`) → turns **SC-19** green (the scaffold's first red target; verified one-line fix).
3. [ ] **Grow the board** — author the `todo` scenarios and implement to green: watchdog (SC-28), occlusion / `CAMERA_OCCLUDED_DEGRADED` + `T_degraded_max` (SC-06..09), the sensor-mode matrix (SC-25..27), override (SC-16..18), congestion (SC-11), pedestrian onset (SC-12).
4. [ ] **Run the board on the MicroPython unix port in CI** to enforce the subset.
