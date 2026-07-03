# ADR-0006: Connectivity & power — solar+battery option, store-and-forward telemetry

**Status:** Proposed
**Date:** 2026-06-26
**Deciders:** PI, technical lead, field/installation engineer

## Context

The proposal does not address two field realities that decide whether a roadside unit can be sited at
all: **where does power come from** and **how does it talk to the TMC**. Emergency-lane hotspots
(tunnel approaches, bridges, remote expressway segments) often lack convenient mains power and have
patchy cellular coverage. These constraints interact with earlier decisions: edge-local processing
([ADR-0002](ADR-0002-edge-vs-cloud-processing.md)) already removed the *safety* dependence on the
network, and the perception choice ([ADR-0003](ADR-0003-detection-algorithm.md)) was kept within a
solar-friendly power budget. This ADR fixes the power and connectivity strategy consistent with both.

Forces: siting freedom vs mains availability, power budget (drives sensor/compute choices), telemetry
needs vs intermittent links, cost, and maintenance.

## Decision

- **Power:** support **mains where available, and solar panel + battery otherwise**, sized for
  **≥ 72 h autonomy without sun** (NFR-07). This makes the power budget a first-class design
  constraint that bounds sensor and compute selection.
- **Connectivity:** **4G/LTE (or fibre where present) for telemetry/OTA**, used in a
  **store-and-forward** manner — events and heartbeats queue locally and sync opportunistically.
  Optionally **LoRaWAN** as a low-power side-channel for heartbeats where cellular is poor. The
  safety loop **never** depends on any of these.

> **Not the sign link.** The LoRa/LoRaWAN mentioned here is the **non-safety** edge→TMC telemetry
> side-channel. The edge→**sign** link (IF-4) is safety-critical and is specified separately in
> [ADR-0014](ADR-0014-sign-link-bearer.md) — do not conflate the two: the IF-4 bearer inherits
> authentication, anti-replay, and refreshed-assertion timing that a telemetry side-channel does not.

## Options Considered

### Option A: Assume mains + always-on cellular
| Dimension | Assessment |
|-----------|------------|
| Siting freedom | **Low** — only powered, well-covered sites |
| Cost | Low (no solar/battery) |
| Field realism | Poor for the named hotspots |

**Pros:** simplest.
**Cons:** excludes exactly the tunnel/bridge/remote sites the system targets; couples operation to
link availability if not paired with edge autonomy.

### Option B: Solar+battery option + store-and-forward telemetry, edge-autonomous *(chosen)*
| Dimension | Assessment |
|-----------|------------|
| Siting freedom | **High** — powered or off-grid |
| Cost | Moderate (solar/battery where needed) |
| Field realism | Good; tolerant of link gaps |
| Power discipline | Forces an efficient sensor/compute budget (a feature) |

**Pros:** sitable almost anywhere; resilient to outages; bounded data egress (privacy/cost); the
power ceiling keeps the design lean.
**Cons:** solar sizing/maintenance; compute/sensor choices must respect the power envelope.

### Option C: Off-grid + satellite/expensive backhaul, richer telemetry
**Pros:** connectivity anywhere.
**Cons:** cost and power over budget; unnecessary given edge autonomy already removes the safety need
for connectivity.

## Trade-off Analysis

Option A quietly assumes away the deployment problem and would strand the project at lab sites.
Because the safety loop is already edge-autonomous, **connectivity can be best-effort**, which makes
store-and-forward over ordinary cellular sufficient and cheap — no need for Option C's premium
backhaul. Solar+battery buys the **siting freedom** the use case demands; the resulting power ceiling
is a useful forcing function that keeps sensing/compute efficient (and consistent with ADR-0001/0003).
Option B is the balanced choice.

## Consequences

- **Easier:** deploy at the high-value off-grid hotspots; resilient to power/link interruptions; low,
  private data egress.
- **Harder:** solar/battery sizing, enclosure thermal design, and field maintenance; a hard power
  budget that sensor/compute choices must honour; store-and-forward sync logic (ordering, retention,
  backpressure). The **gate-grade mmWave radar** ([ADR-0001](ADR-0001-sensing-modality.md)) draws more
  than a generic presence unit — its power is a **first-class input to this budget**, reconciled like its
  cost was ([doc 03 §1](../03-roadmap-and-phasing.md#1-scope--budget-reality-check-read-first)).
- **Revisit when:** a corridor offers reliable mains + fibre (simplify to Option A locally), or
  richer real-time central analytics justify premium backhaul.

## Action Items

1. [ ] Compute the site energy budget (sensors + compute + sign signalling) and size panel + battery
       for ≥72 h autonomy — **including the gate-grade mmWave radar's draw**, which exceeds the
       generic-presence assumption in [ADR-0001](ADR-0001-sensing-modality.md); fold it in once the
       module is selected.
2. [ ] Select the cellular module/plan; design the store-and-forward outbox (retention, ordering).
3. [ ] Evaluate LoRaWAN as a heartbeat side-channel for low-coverage sites.
4. [ ] Specify the outdoor enclosure (IP65+, thermal) for sensors, compute, and battery.
