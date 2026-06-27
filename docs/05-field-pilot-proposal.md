# 05 — Provincial (cấp sở) Field-Pilot Proposal — draft

**Project:** Emergency Stop-Lane Automatic Warning System (ESW) — field pilot
**Status:** Draft (follow-on to the university-level / cấp trường task)
**Last updated:** 2026-06-26
**Builds on:** [01 requirements](01-requirements.md) · [02 architecture](02-system-architecture.md) · [03 roadmap](03-roadmap-and-phasing.md) · [04 risk & safety](04-risk-and-safety.md) · [ADRs](adr/README.md)

> This is a **draft skeleton** for the provincial-level (cấp sở) R&D task that the university
> prototype is designed to feed. It turns the validated principle into a real on-road pilot. Numbers
> (budget, durations, site counts) are planning placeholders to be finalised with the chosen
> expressway operator and procurement quotes.

---

## 1. The ask, in one paragraph

Take the **validated ESW prototype** from the cấp trường task and run a **real field pilot**: deploy
**2–3 productised roadside units at high-risk expressway sites**, in partnership with the road
operator, operate them on live traffic for **≥ 6 months**, and **measure whether the active warning
actually reduces shoulder-incident risk without crying wolf** — producing a deployable,
QCVN-conformant reference design and a validated safety case that other operators can adopt.

## 2. Origin & justification (xuất xứ)

The university task delivered what a seed grant can: a working closed-loop prototype, measured
bench/simulation metrics, an accepted architecture and ADR set, and a safety-case skeleton
([doc 03 §6](03-roadmap-and-phasing.md)). It deliberately **could not** answer the questions that
decide real-world value, because a bench rig and simulation cannot:

- measure **effectiveness on live traffic** — do following drivers actually slow / change lane, and
  are rear-end conflicts with shoulder-stopped vehicles reduced at instrumented sites?
- measure the **real-world false-alarm rate** across weather, lighting, and traffic density;
- prove **operator/ITS integration** (real VMS, real TMC, real permits);
- establish **public acceptance** and the trust calibration the whole design depends on
  ([doc 04 R2/R7](04-risk-and-safety.md)).

Only a field pilot answers these. The pilot is also aligned with provincial priorities in **smart
transportation (ITS), road safety, and digital transformation of infrastructure management**.

## 3. Objectives

**General.** Design, deploy, and validate a productised ESW at real expressway sites; quantify its
safety effectiveness; deliver a deployable, QCVN-conformant reference design and a validated safety
case; and create the basis for standardisation and commercialisation.

**Specific.**

1. **Productise** the roadside unit to field grade — ruggedised, solar-powered, multi-sensor,
   fail-safe ([ADR-0001](adr/ADR-0001-sensing-modality.md), [ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.md), [ADR-0006](adr/ADR-0006-connectivity-and-power.md)).
2. Establish a **per-site DSD-based siting method** and apply it at the pilot sites
   ([doc 01 §4](01-requirements.md)).
3. Integrate with the operator's **existing VMS/ITS** where present, or install a QCVN-conformant
   **solar LED sign** otherwise ([ADR-0004](adr/ADR-0004-warning-actuator-integration.md)).
4. **Deploy and operate** the units for ≥ 6 months with telemetry to the operator's TMC.
5. **Measure the field acceptance KPIs** ([doc 01 §5](01-requirements.md), field column) plus a
   before/after safety indicator agreed with the operator.
6. Perform a **functional-safety treatment** — hazard analysis, validated safe-state behaviour,
   fault-injection coverage.
7. Meet **data-privacy and security** obligations on a public road ([doc 04 §4](04-risk-and-safety.md)).
8. Produce a **safety case + deployment guideline**, contribute to **standardisation**, and pursue
   **IP / commercialisation** (giải pháp hữu ích / sáng chế) if the novelty is defensible.

## 4. Novelty & scientific contribution

Beyond the prototype's novelty, the pilot contributes the first **field-validated** active
shoulder-incident warning in the Vietnamese context: a **DSD-based siting methodology**, a
**multi-sensor fail-safe reference design**, and — most importantly — **measured on-road
effectiveness and false-alarm data**, which currently do not exist locally. The output is a
reference design + safety case that road authorities and operators can adopt and that can seed a
**national guideline or technical standard**.

## 5. Scope & pilot sites

- **2–3 representative high-risk sites** selected with the operator, e.g. a **tunnel/bridge
  approach**, a **limited-sight curve/crest**, and a **known shoulder-incident hotspot**
  ([doc 02 §6](02-system-architecture.md) coverage model).
- Per site: DSD-based siting, sensor placement, sign (VMS reuse or solar LED), power and
  connectivity solution.
- **Explicitly not** full-corridor continuous coverage — the pilot validates **discrete monitored
  zones**, which is the deployable model.

## 6. Technical approach — from prototype to field

The **logical architecture does not change** ([doc 02](02-system-architecture.md)); the pilot
productises each layer and adds the rigour a public deployment demands.

| Layer | Prototype (cấp trường) | Field pilot (cấp sở) |
|-------|------------------------|----------------------|
| Sensing | bench camera (+ optional radar) | ruggedised **camera + radar**, all-weather, calibrated per site |
| Compute | dev board on a bench | field **edge unit** (IP65, thermal-managed, solar power budget) |
| Sign | LED panel stand-in | **real VMS integration** or QCVN-41 **solar LED** at ≥ DSD upstream |
| Power / connectivity | lab mains | **solar + battery ≥ 72 h**, LTE store-and-forward to the TMC |
| Safety | fail-safe *design* | **hazard analysis + validated safe-state + TMC monitoring/alerting** |
| Evaluation | staged scenarios + injected faults | **live traffic** + injected faults + **before/after** analysis |
| Compliance | principle only | **QCVN 41** conformance, **data-privacy** governance, security hardening |

The [ADRs](adr/README.md) are the design basis and carry forward unchanged; the pilot is where their
"revisit when…" clauses get real data.

## 7. Work plan (indicative, ~18–24 months)

| Phase | Duration | Content | Exit criteria |
|------:|----------|---------|---------------|
| **P1** | 3–4 mo | Operator MOU; site selection; permits; per-site **DSD survey**; finalise specs | Sites + permits secured; siting signed off |
| **P2** | 4–5 mo | **Productise** field unit; **hazard analysis**; sign/VMS integration design; procurement | Units built & bench-accepted; safety analysis complete |
| **P3** | 2–3 mo | **Installation & commissioning** at pilot sites; TMC telemetry integration | Units live; self-test + fault-injection pass on site |
| **P4** | 6 mo | **Field operation & data collection** across seasons/weather | Continuous operation; dataset accumulating |
| **P5** | 2–3 mo | **Evaluation**: KPIs, before/after analysis, fault-injection; **safety case** | KPIs measured vs targets; safety case complete |
| **P6** | 2 mo | Deliverables, **deployment guideline**, standardisation input, IP / commercialisation | Final report & reference design submitted |

## 8. Deliverables

- **2–3 commissioned field units** operating at the pilot sites.
- **Field evaluation report** with measured KPIs and a **before/after safety analysis**.
- **Validated safety case** (hazard analysis, safe-state validation, fault-injection coverage).
- **Per-site DSD siting methodology** (reusable).
- **Deployable reference design** — bill of materials, drawings, integration spec.
- **Deployment guideline / standardisation input** (toward a QCVN/TCVN-aligned recommendation).
- **Data-privacy & security compliance dossier**.
- **Commercialisation plan** and, if warranted, an **IP filing** (giải pháp hữu ích / sáng chế).
- **Scientific dissemination** (conference/journal papers).

## 9. Budget (indicative, order-of-magnitude)

A field pilot is **far larger** than the 20,000,000 VND prototype seed. Indicative envelope (to be
finalised with operator co-funding and procurement quotes):

| Category | Indicative share | Notes |
|----------|------------------|-------|
| Field hardware (2–3 sites: multi-sensor, edge, solar+battery, sign/VMS integration, IP65) | ~35–45% | Largest line; reduced if the operator provides VMS/power in-kind |
| Installation, civil works, permits | ~10–15% | Per operator requirements |
| Personnel (research team, engineering, field ops) | ~20–25% | Across 18–24 months |
| Software productisation + safety/hazard analysis | ~10% | Functional-safety work |
| Data collection, evaluation, travel | ~5–10% | Seasonal coverage |
| Dissemination, IP, contingency | ~5–10% | — |

> Order-of-magnitude indicative total in the **hundreds of millions to ~1.5 billion VND** range,
> heavily dependent on site count and how much the operator contributes in kind (sites, VMS, power,
> TMC access). **Co-funding** is explicitly sought ([doc 03 §1](03-roadmap-and-phasing.md), external
> funding): operator in-kind, ITS-industry partners, and other provincial programmes.

## 10. Partnerships

| Partner | Role (essential unless noted) |
|---------|-------------------------------|
| **Expressway operator** | Sites, existing VMS/TMC, permits, traffic & incident data, in-kind co-funding — **essential** |
| ITS industry vendors | Camera/AI, radar, VMS/LED, IoT, edge hardware |
| Road authority / regulator | QCVN 41 conformance, approvals, standardisation pathway |
| University (PI + team + students) | Design, integration, evaluation, dissemination |

## 11. Acceptance KPIs (field)

From [doc 01 §5](01-requirements.md) (field column), plus pilot-specific safety indicators:

| KPI | Target |
|-----|--------|
| Detection rate / recall — vehicles (day · night/adverse) | ≥ 98% · ≥ 95% |
| Detection rate / recall — pedestrians (day · night) | ≥ 90% · best-effort |
| False activation rate | provisional ≤ 1 per site per week, **operator-calibrated** to the trust threshold ([doc 04 §5](04-risk-and-safety.md#5-open-safety-questions-for-the-team)) |
| Detection / clear latency | ≤ dwell + 2 s · ≤ hold + 2 s (on a confirmed exit) |
| Effective warning lead distance | ≥ DSD on-site (surveyed) |
| **Functional** availability | ≥ 99% |
| Fault-detection coverage | ≥ 95% of the FMEA list |
| **Before/after safety indicator** | measurable reduction in shoulder-incident conflicts / near-misses at instrumented sites (with operator data) |

## 12. Risk management

Carried from [doc 04](04-risk-and-safety.md), with field-specific emphasis:

| Risk | Mitigation |
|------|-----------|
| Operator cooperation / permits slow or fail | Early **MOU**; co-design; start P1 with this gate |
| Site power / connectivity gaps | **Solar + battery + LTE** store-and-forward ([ADR-0006](adr/ADR-0006-connectivity-and-power.md)) |
| Adverse-condition performance | **Camera + radar** + condition-specific acceptance tests |
| Cry-wolf erodes trust | Dwell/hysteresis/watchdog; operator-agreed false-alarm ceiling; trust-calibration review |
| Over-reliance / public acceptance | Frame as an **aid, not a guarantee**; public communication; consistent behaviour |
| Liability ambiguity | **Advisory** framing; audit log; explicit roles in the operator agreement |
| Budget / procurement | Phased spend; co-funding; reduce site count if needed (state the trade-off, don't silently cut) |

## 13. Expected impact

- **Safety:** earlier warning and reduced rear-end conflicts with shoulder-stopped vehicles at
  instrumented high-risk sites; better protection for stranded occupants and rescue crews.
- **Scientific:** the first local **field-validated method and effectiveness dataset**; basis for a
  guideline/standard.
- **Economic:** a deployable product and a commercialisation path with the Vietnamese ITS industry.
- **Policy:** concrete input to smart-transport and road-safety infrastructure programmes.

## 14. Path beyond the pilot

A successful pilot supports a **corridor-scale rollout business case**, a **national guideline or
technical standard**, and **productisation/commercialisation** integrated into operators' ITS — the
trajectory the original proposal anticipated when it framed the cấp sở stage and beyond.
