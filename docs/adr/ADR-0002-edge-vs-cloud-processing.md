# ADR-0002: Run the safety loop at the edge; cloud is monitoring-only

**Status:** Accepted (software side) — 2026-06-27
**Date:** 2026-06-26
**Deciders:** PI, technical lead

## Context

The proposal names a "central processor" (bộ xử lý trung tâm) without locating it. Where the
detect→decide→warn loop runs is a load-bearing decision because the loop is **safety-related and
latency-bound** (warning ON within ≈ dwell + 2 s, NFR-01) and the field environment has **intermittent
connectivity** (roadside cellular, tunnels, remote expressway segments).

Forces: latency, availability when the WAN is down, bandwidth/cost of moving video, privacy (raw
video leaving the roadside), and the operational need for central monitoring and updates.

## Decision

**The safety-critical loop runs entirely on an edge device at the roadside** (sensing → perception →
fusion → state machine → sign command). The **cloud / TMC is non-critical**: it receives telemetry
and events (store-and-forward), provides monitoring, audit, configuration, and OTA — but the roadside
unit must operate correctly with the WAN fully offline.

## Options Considered

### Option A: Edge-local loop, cloud for oversight *(chosen)*
| Dimension | Assessment |
|-----------|------------|
| Latency | **Low & deterministic** (no WAN round-trip) |
| Availability | **High** — survives WAN outage |
| Bandwidth/cost | Low — only events/heartbeats leave |
| Privacy | Strong — inference on-device, no raw-video upload |
| Compute cost | One capable edge box per site |

**Pros:** meets latency and offline requirements; minimal data egress (privacy + cost); robust.
**Cons:** per-site edge hardware; OTA/model management across distributed units.

### Option B: Cloud/central processing (stream sensors to a server)
| Dimension | Assessment |
|-----------|------------|
| Latency | **High & variable** — WAN-bound |
| Availability | **Poor** — WAN outage disables warning |
| Bandwidth/cost | High — continuous video uplink |
| Privacy | Weak — raw video off-site |
| Compute cost | Centralised (cheaper per unit, but…) |

**Pros:** central compute; easier model updates; thinner roadside hardware.
**Cons:** a network outage becomes a **safety outage**; latency unsuitable for a warning loop;
expensive continuous uplink; raw-video privacy exposure. Disqualifying for a safety function.

### Option C: Hybrid — edge does the loop, cloud assists with heavy/secondary analytics
| Dimension | Assessment |
|-----------|------------|
| Latency | Low for the safety loop |
| Availability | High for the safety loop |
| Complexity | Higher (two compute tiers) |

**Pros:** keeps the safety loop local while allowing richer offline analytics centrally.
**Cons:** more moving parts than needed now; the cloud analytics are out of current scope.

## Trade-off Analysis

For a safety warning, **availability and latency dominate**. Option B couples the warning's
correctness to the cellular network — unacceptable. Option A satisfies latency, offline operation,
privacy, and cost, at the price of distributed edge management — a solved, ordinary operational
concern (addressed by OTA in [ADR-0005](ADR-0005-fail-safe-and-system-safety.md) and the TMC plane).
Option C is Option A plus future analytics; we adopt A's boundary now and leave the hybrid door open
(it is a superset, not a contradiction).

## Consequences

- **Easier:** deterministic latency; works in tunnels/outages; cheap, private (no raw egress).
- **Harder:** fleet management of edge devices (config, OTA, version skew) — handled by the TMC
  config/OTA service and signed updates.
- **Revisit when:** a future, non-safety analytics workload (corridor-wide incident analytics)
  justifies promoting to the Option C hybrid.

## Action Items

1. [ ] Fix the edge/cloud boundary in the interface contracts ([doc 02 §7](../02-system-architecture.md#7-interfaces--contracts-initial)).
2. [ ] Specify store-and-forward semantics for the telemetry outbox (ordering, retention, backpressure).
3. [ ] Confirm the chosen edge device meets the perception latency budget on-device.
