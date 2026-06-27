# Architecture Decision Records (ADRs)

Each ADR captures one load-bearing decision: the context, the options weighed, the choice, and the
consequences. They follow the standard ADR format. The **software-owned** decisions were **accepted
(software side) on 2026-06-27**; the rest remain **Proposed**, pending the owning team's sign-off
(hardware / firmware / ops / regulator) — the Status column names who.

| ADR | Decision | Status |
|-----|----------|--------|
| [ADR-0001](ADR-0001-sensing-modality.md) | Sensing modality — camera + radar fusion (not camera-only) | Proposed — **hardware + business** |
| [ADR-0002](ADR-0002-edge-vs-cloud-processing.md) | Run the safety loop at the edge; cloud is monitoring-only | **Accepted (sw)** 2026-06-27 |
| [ADR-0003](ADR-0003-detection-algorithm.md) | Lightweight detector + ROI gating + dwell logic (not heavy end-to-end DL, not pure background subtraction) | **Accepted (sw)** 2026-06-27 |
| [ADR-0004](ADR-0004-warning-actuator-integration.md) | Pluggable actuator — reuse existing VMS where present, dedicated solar LED sign otherwise | Proposed — **hardware + ops/regulator** |
| [ADR-0005](ADR-0005-fail-safe-and-system-safety.md) | Fail-safe posture, safe state, health escalation, and the dead-man's-switch safe-state path | **Accepted (sw)** 2026-06-27 |
| [ADR-0006](ADR-0006-connectivity-and-power.md) | Connectivity & power — solar+battery option, store-and-forward telemetry | Proposed — **hardware** |
| [ADR-0007](ADR-0007-validation-and-data-strategy.md) | Validation & data strategy — what bench/sim proves vs. field-deferred; the data-acquisition plan | **Accepted (sw)** 2026-06-27 |
| [ADR-0008](ADR-0008-detection-persistence-and-multitrack.md) | Detection persistence — occlusion vs. departure, radar-corroborated hold, multi-track set semantics | **Accepted (sw)** 2026-06-27 |
| [ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.md) | Fail-safe actuation placement (sign-controller dead-man's switch), asymmetric degraded modes, renewable occlusion hold | Proposed — **hardware/firmware** (logic ratified via 0013) |
| [ADR-0010](ADR-0010-operator-override-and-manual-control.md) | Operator override & manual-control policy — bounded, fail-loud, heartbeat-honoring (never latch, never silently persist) | **Accepted (sw)** 2026-06-27 · ops scope pending |
| [ADR-0011](ADR-0011-operator-concept-and-alarm-management.md) | Operator concept of operations & alarm management — the staffed, bounded response path "fail loud" depends on (dedup, severities, re-escalation) | Proposed — **ops/business** |
| [ADR-0012](ADR-0012-security-and-threat-model.md) | Security posture & consolidated threat model — scopes the NFR-09 claim to an enumerated surface (sign link, override, config/OTA, sensor denial) | Proposed — **hardware/ops** (sw auth done) |
| [ADR-0013](ADR-0013-degraded-hold-unification.md) | Degraded-hold unification — a camera-unverified warning (occlusion *or* fault) is bounded by `T_degraded_max`; closes the unbounded RADAR-ONLY hold + enumerates the warning × sensor-mode matrix | **Accepted (sw)** 2026-06-27 |

**Scope note (in lieu of a separate ADR):** the deployment **coverage model is discrete monitored
zones at high-value locations**, not continuous coverage, and the funded scope is **one pilot zone /
its simulation**. Rationale and detail live in [doc 02 §6](../02-system-architecture.md#6-coverage-model)
and [doc 03](../03-roadmap-and-phasing.md).

## Conventions

- One decision per file, numbered `ADR-NNNN`.
- Status lifecycle: **Proposed → Accepted → (Deprecated | Superseded by ADR-XXXX)**.
- Supersede rather than rewrite history: a reversed decision gets a new ADR that supersedes the old.
