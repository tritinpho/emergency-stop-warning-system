# K230 detection models (`kmodel`)

The trained/converted YOLO models the K230 KPU runs. This directory holds the **I/O
configs** (`deploy_config.json`); the **binaries are intentionally not committed** yet —
see *Binary storage* below.

## The two production models

Both are custom-trained, converted with nncase/kmodel **2.9.0** for the Yahboom image
**1.4.1** baseline (see [`../design-log/AGENTS-k230-baseline.md`](../design-log/AGENTS-k230-baseline.md)).

| Variant | File | Size | SHA-256 |
|---|---|---|---|
| **day** | `best_AnchorBaseDet_can2_5_s_20260704215736.kmodel` | 7 544 512 B (7.2 MiB) | `0447a2a38dc092e2415666af085b61e715736ada890b19b80e3d4ffc32de8b17` |
| **night** | `best_AnchorBaseDet_can2_5_s_20260702232105.kmodel` | 7 551 688 B (7.2 MiB) | `728bd75913975785415fcbb4bf3ab0416ae6d5379f443ebf60351294ac1a0a8d` |

Shared config (both `deploy_config.json`): `model_type = AnchorBaseDet`, input `320×320`,
`mean = [0.485,0.456,0.406]`, `std = [0.229,0.224,0.225]`, 3-scale anchors, `nms_option = false`.

## ⚠️ Finding: the production model is single-class `"vehicle"`

`deploy_config.json` for **both** models declares `num_classes: 1`, `categories: ["vehicle"]`.
That is **not** the COCO YOLOv8n (car / truck / bus / person) that `k230/main.py` loads
via `MODEL_PATH = ".../yolov8n_320.kmodel"`. So the repo carries **two detector paths**:

- a generic **COCO `yolov8n_320`** (80 classes, incl. `person`) — what `main.py` references;
- these **custom single-class `AnchorBaseDet`** day/night models — what was actually trained
  and deployed (dated 2026-07-04 / 07-02).

This is **backlog #1** in [ADR-0016](../../../docs/adr/ADR-0016-repo-consolidation-and-perception-source.md).
Our `esw.perception` uses the class for per-type ground footprint (car/truck/bus sizes) and
routes `person` to presence-onset (SC-12). A single `"vehicle"` class **loses both**. The
adapter (task #6) must either target the COCO model, or add a class remap and accept that
pedestrian handling needs the COCO/person path. Decide before the closed-loop integration.

## Binary storage (open decision — backlog #7)

The two `.kmodel`s are ~7 MiB each (~15 MiB total). They are **not committed** to keep this
merge reversible and avoid pinning a binary-in-git choice prematurely. Options for Tin:

1. **git-LFS** — `git lfs track "*.kmodel"`, then commit. Keeps them versioned with the code;
   needs LFS on every clone. Recommended if the models version alongside firmware.
2. **External artifact store** — release asset / object storage, retrieved at deploy time by
   SHA (table above). Keeps the git repo lean.

Until then, retrieve from the source repo (verify against the SHA-256 above). **The source
repo is private** — you need to be granted access, and an unauthenticated clone will 404:

```bash
gh repo clone KendyKeb/Solar-Powered-Intelligent-Emergency-Lane-Monitoring-and-Warning-System
# day:   model/mp_deployment_source_day/best_AnchorBaseDet_can2_5_s_20260704215736.kmodel
# night: model/mp_deployment_source_night/best_AnchorBaseDet_can2_5_s_20260702232105.kmodel
```

Place the binary next to its `deploy_config.json` (`models/day/`, `models/night/`) and on the
K230 SD card at the path `main.py` expects.
