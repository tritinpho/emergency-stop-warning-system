# Architecture Decision Records (ADRs)

Each ADR captures one load-bearing decision: the context, the options weighed, the choice, and the
consequences. They follow the standard ADR format. All are **Proposed** until the project team
accepts them.

| ADR | Decision | Status |
|-----|----------|--------|
| [ADR-0001](ADR-0001-sensing-modality.md) | Sensing modality — camera + radar fusion (not camera-only) | Proposed |
| [ADR-0002](ADR-0002-edge-vs-cloud-processing.md) | Run the safety loop at the edge; cloud is monitoring-only | Proposed |
| [ADR-0003](ADR-0003-detection-algorithm.md) | Lightweight detector + ROI gating + dwell logic (not heavy end-to-end DL, not pure background subtraction) | Proposed |
| [ADR-0004](ADR-0004-warning-actuator-integration.md) | Pluggable actuator — reuse existing VMS where present, dedicated solar LED sign otherwise | Proposed |
| [ADR-0005](ADR-0005-fail-safe-and-system-safety.md) | Fail-safe posture, safe state, and health escalation | Proposed |
| [ADR-0006](ADR-0006-connectivity-and-power.md) | Connectivity & power — solar+battery option, store-and-forward telemetry | Proposed |

**Scope note (in lieu of a separate ADR):** the deployment **coverage model is discrete monitored
zones at high-value locations**, not continuous coverage, and the funded scope is **one pilot zone /
its simulation**. Rationale and detail live in [doc 02 §6](../02-system-architecture.md#6-coverage-model)
and [doc 03](../03-roadmap-and-phasing.md).

## Conventions

- One decision per file, numbered `ADR-NNNN`.
- Status lifecycle: **Proposed → Accepted → (Deprecated | Superseded by ADR-XXXX)**.
- Supersede rather than rewrite history: a reversed decision gets a new ADR that supersedes the old.
