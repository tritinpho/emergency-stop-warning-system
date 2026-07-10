# ADR-0016: Repository consolidation and the K230 perception source

**Status:** Accepted (software / architecture side) — 2026-07-09. The cross-team items (hardware adoption of IF-4, retirement of the MQTT latch from the safety path) are **Proposed** pending ACLAB ELMS.
**Date:** 2026-07-09
**Deciders:** PI / software lead (Tin); hardware/firmware team (ACLAB ELMS) co-owns the cross-team items

## Context

Two repositories describe the same product:

- **This repo** (`tritinpho/emergency-stop-warning-system`) — the architecture and safety spine: docs 00–11 (EN+VI), 15 ADRs, the [ICD](../08-interface-control-document.md), the [traceability matrix](../06-traceability-matrix.md), the [simulation methodology](../07-simulation-methodology.md), and the MicroPython-safe safety stack (`software/esw`, six test boards, CPython + real-MicroPython CI). Its gap: perception is a **scaffold** — it has never run a real detector, a real `kmodel`, or real silicon.
- **The ACLAB ELMS repo** (`KendyKeb/Solar-Powered-Intelligent-Emergency-Lane-Monitoring-and-Warning-System`) — the device-tested hardware prototype: a K230 running YOLOv8n at ~30 FPS, two trained day/night `kmodel`s, a field-usable web ROI-configuration tool, clip-area / ray-cast ROI gating, three environmental noise filters, ESP32 actuation, and CoreIoT MQTT telemetry. Its gap: **no safety architecture** — a two-state presence/absence dwell, a fail-danger sign link, and a cloud-coupled critical path.

They are complementary halves of one system, built by the two teams (software = Tin; hardware/firmware = ACLAB ELMS). Left alone they have begun to **diverge**: the ACLAB ELMS repo grew its own `architecture.md` / `light_control.md` with `TURN_ON`/`TURN_OFF` latch semantics routed through a cloud MQTT broker — which contradict [ADR-0002](ADR-0002-edge-vs-cloud-processing.md) (edge-local safety loop) and the dead-man's switch of [ADR-0005](ADR-0005-fail-safe-and-system-safety.md) / [ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.md) / [ADR-0013](ADR-0013-degraded-hold-unification.md). The duplication is now crystallising at the ESP32 sign controller, which both teams are building with **opposite** safety semantics. A single system-of-record is needed before they diverge further.

## Decision

- **D1 — This repo is the trunk / system-of-record; the merge direction is theirs → ours.** Docs 00–11 + the ADRs remain authoritative. Their standalone `architecture.md` / `light_control.md` are **demoted to a design log** (`firmware/k230-detector/design-log/`) — preserved as the hardware team's engineering record, not as spec.
- **D2 — Vendor the ACLAB ELMS device layer into [`firmware/k230-detector/`](../../firmware/k230-detector/), preserved as a device-tested baseline** behind our interfaces. Their detector output becomes the concrete backend for `esw.perception.Perception.step()` (IF-1 → IF-2); our ground-projection geometry, tracker, and state machine sit on top. Their own "do not silently modernise the device baseline" rule (their `AGENTS.md`) is honoured — the vendored code is the reference; adapters live outside it.
- **D3 — At the seam, the fail-safe design wins.** The IF-4 refresh-or-blank LoRa dead-man's switch ([`firmware/sign-controller`](../../firmware/sign-controller/README.md), [doc 10](../10-if4-sign-controller-firmware-spec.md)) replaces their `LED:ON`/`LED:OFF` MQTT/Wi-Fi latch. CoreIoT MQTT is demoted from the safety path to **non-critical IF-6 telemetry** ([ADR-0002](ADR-0002-edge-vs-cloud-processing.md)).
- **D4 — Harvest the reusable perception assets:** the `LightFilter` and `OverVehiclesFilter` (the latter is their congestion-suppression analog — our R14 / SC-11), the web ROI-config tool + `config.json` schema, and the K230 platform knowledge (C-accelerated postprocess, memory lifecycle, Wi-Fi/LCD bootstrap ordering, Yahboom 1.4.1 baseline).

## Options Considered

### D1 — which repo is the system-of-record
| Option | Assessment |
|---|---|
| **This repo is trunk, theirs → ours (chosen)** | Preserves the safety case, ADRs, ICD, CI; their detector drops into `Perception.step()` by design (built as a pluggable backend). Smallest, cleanest merge. |
| Their repo is trunk, ours → theirs | Re-implements the 12-module safety stack, 15 ADRs, ICD, and dual-runtime CI onto a repo with none; inherits the fail-danger latch + cloud coupling. Rejected. |
| Keep two repos joined by the ICD | Honest for two teams and viable long-term; but the duplication (two ESP32 controllers) and doc divergence are live now, and consolidation was requested. Recorded as the fallback structure. |

### D2 — how their code lands here
| Option | Assessment |
|---|---|
| **Vendor as a preserved baseline + external adapter (chosen)** | Keeps their device-tested code runnable and attributable; the adapter carries all reconciliation, so the baseline stays a clean reference. |
| Port / rewrite into `esw/` style now | Loses the device-tested provenance and risks silently "modernising" APIs their `AGENTS.md` explicitly freezes. Later, not now. |
| Git submodule | Keeps it separate — the opposite of consolidating — and cannot carry our adapters. |

### D3 — the sign-link seam
| Option | Assessment |
|---|---|
| **IF-4 dead-man's switch wins; MQTT → telemetry (chosen)** | The entire safety reframing (fail-safe / fail-loud) lives here; their latch is fail-danger and cloud-coupled. Non-negotiable. |
| Keep their latch for the demo, IF-4 later | Ships the one behaviour we most need to correct — a warning that stays lit on a dead link or dead edge is the top hazard. Rejected. |

## Trade-off Analysis

The consolidation is asymmetric on purpose. Our repo contributes the part that is expensive to reproduce and cheap to extend (a verified safety stack with a pluggable perception seam); their repo contributes the part we cannot simulate our way to (a real detector on real silicon, tuned on real footage). Merging *their perception into our architecture* is a few hundred lines of adapter; merging *our architecture onto their app* is a rewrite. The only place the two genuinely conflict is the sign link — and there the safety case is not a trade: the dead-man's switch is the reason the project was reframed as safety-related. Everything else is additive.

The cost we take on is a **reconciliation backlog** (below): their pragmatic shortcuts — a single-class model, a disabled presence dwell, image-plane ROI, a no-op shake filter, cloud coupling, hardcoded secrets — each need an explicit disposition rather than silent adoption. Documenting that backlog *is* the merge; adopting their code without it would import the fail-danger behaviours along with the good parts.

## Consequences

- **Easier:** one system-of-record; a real detector behind the perception seam; noise filters + ROI tooling + K230 platform knowledge arrive at once; the K230's C-accelerated postprocess partly answers the open [ADR-0015](ADR-0015-state-machine-implementation-strategy.md) D3 timing question (a pure-Python YOLOv8 postprocess loop exhausted the MicroPython heap → the SDK's C `aidemo` path fixed it and held 30 FPS).
- **Harder / carried as backlog** (each tracked in `firmware/k230-detector/README.md`):
  1. **Detector class set** — the *production* `kmodel` is a custom single-class `AnchorBaseDet` ("vehicle"), not COCO; our per-class footprint (car/truck/bus) and pedestrian onset (person, SC-12) need either the COCO `yolov8n` model or a class remap.
  2. **Dwell asymmetry** — their `main.py` runs `PRESENCE_THRESHOLD = 0` (no confirm dwell) → cry-wolf-prone; our configurable `T_dwell` confirm must govern once integrated.
  3. **ROI geometry** — theirs is image-plane bbox∩polygon (overlap ≥ 0.2); ours is ground-projected footprint∩ground-ROI (perspective-correct, PC-11). Ours supersedes; theirs is the near-nadir fallback.
  4. **ShakingFilter is a MicroPython no-op** (needs cv2) — not a real on-device mitigation; must not be counted as one.
  5. **Cloud coupling** — CoreIoT MQTT must stay out of the safety path (ADR-0002); telemetry only.
  6. **Secrets** — the vendored ESP32 / Wi-Fi code carries a hardcoded Wi-Fi password + CoreIoT access token (already public in their repo) → rotate + move to config.
  7. **Model binaries** — two ~7 MB `kmodel`s; a git-LFS-vs-commit decision (kept out of git for now; see `models/README.md`).
- **Unchanged:** radar is absent in **both** repos (RQ-H1); this decision does not touch the sensing-modality gap.
- **Revisit when:** the perception adapter lands and the closed loop (detector → `perception` → `state_machine` → IF-4) runs on the K230; or if the teams choose the two-repo-plus-ICD structure instead.

## Action Items

1. [x] **Perception adapter** — done: [`esw/k230_adapter.py`](../../software/esw/k230_adapter.py) + the Level-G board (`software/run_integration_tests.py`, IT-01..04). **Backlog #1 resolved — the COCO multi-class model (`yolov8n_320`) is the target**, because `esw.perception` needs the class label twice: per-type ground footprint (car/truck/bus) and routing `person` to presence-onset (SC-12). A single-class `"vehicle"` model is a **degraded fallback**, not an equivalent: `model_capabilities()` reports `sees_person=False` and `per_class_footprint=False` so the loss is **loud, never silent** (ADR-0005). ⚠️ The **deployed day/night `kmodel`s are single-class**, so **SC-12 is unreachable on them**; a multi-class retrain needs ACLAB's training pipeline, which is in **no** repo (see [`models/README.md`](../../firmware/k230-detector/models/README.md)).
2. [ ] **Seam reconciliation in the ICD / [doc 09](../09-software-hardware-handoff.md)** — record that IF-4 supersedes the `LED:ON/OFF` latch and that CoreIoT MQTT is IF-6 telemetry only.
3. [ ] **Harvest the noise filters** into the perception path — map `OverVehiclesFilter` onto congestion suppression (R14 / SC-11); wire `LightFilter`; drop `ShakingFilter` from the on-device mitigation count.
4. [ ] **Secrets** — rotate the exposed Wi-Fi password + CoreIoT token; move to `config.json` (backlog #6).
5. [ ] **Model storage** — decide git-LFS vs. an external artifact store for the day/night `kmodel`s (backlog #7).
6. [ ] **Hardware-team sign-off (Proposed → Accepted)** — ACLAB ELMS adopts IF-4 on the ESP32 and retires the MQTT latch from the safety path.
