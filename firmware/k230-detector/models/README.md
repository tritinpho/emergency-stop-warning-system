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

## ⚠️ Finding: these `kmodel`s are **dead** — `main.py` refuses to load them

`deploy_config.json` for **both** models declares `num_classes: 1`, `categories: ["vehicle"]`,
`model_type: AnchorBaseDet`. But [`k230/main.py`](../k230/main.py) `load_model_config()` guards
against exactly that:

```python
kmodel_path = f".../mp_deployment_source_{mode}/{deploy_conf['kmodel_path']}"
if "AnchorBaseDet" in kmodel_path or "best_" in kmodel_path:
    raise ValueError("AnchorBaseDet not supported, forcing fallback")   # -> except:
```

Both configs point at `best_AnchorBaseDet_*.kmodel`, so the guard **always** fires, the
`except` **always** runs, and the device **always** loads the fallback:
`/sdcard/kmodel/yolov8n_320.kmodel` with the **full 80-class COCO label list**. ACLAB's own
comment calls the custom models *"old"*.

Three consequences:

1. **These two binaries are never executed.** They are a dead training run, not the production
   detector. Store them for provenance; do not treat them as the thing that runs.
2. **The real detector is stock COCO YOLOv8n**, so `person` (class 0) *is* emitted and **SC-12 is
   reachable on the device**. Per-class footprints work too.
3. **Day/night switching is inert.** `mode` only picks a config path; both paths raise and land on
   the same fallback. `design-log/demo.md` §2.2 lists auto day/night switching as out of scope —
   in fact it is **non-functional**, not merely unscoped.

This resolves **backlog #1** in [ADR-0016](../../../docs/adr/ADR-0016-repo-consolidation-and-perception-source.md):
the device already made the choice. `esw.perception` needs the class label for per-type ground
footprint (car/truck/bus) *and* to route `person` to presence-onset (SC-12) — and COCO supplies both.

### Decision (2026-07-10): target COCO; a single-class model is a *degraded* mode, reported loudly

`esw.k230_adapter.model_capabilities(labels)` derives what a loaded model's label set can
actually carry, and the Level-G board asserts it both ways:

| Label set | `sees_person` | `per_class_footprint` | SC-12 reachable? |
|---|---|---|---|
| COCO 80-class (what the device loads) | ✅ | ✅ | **yes** |
| `["vehicle"]` (what these configs declare) | ❌ | ❌ (all → `car`) | no |

The guard is not redundant just because `main.py` currently forces the fallback. Delete that
`raise ValueError` — or rename a `kmodel` so it no longer matches `"best_"` — and the device
silently loads a single-class model. It would still light the sign for a shoulder car, so
**nothing downstream looks broken** while the unit is blind to pedestrians. The host sim cannot
catch it either: it injects scripted `person` labels no single-class detector would emit, so
all 88 scenarios stay green over a dead SC-12. Silent loss of coverage is what
[ADR-0005](../../../docs/adr/ADR-0005-fail-safe-and-system-safety.md) forbids, so the capability
is now an explicit, tested fact rather than an assumption.

### ⚠️ The real detector is an unversioned file nobody pins

`/sdcard/kmodel/yolov8n_320.kmodel` is what actually runs. It is **in neither repo** — it ships
on the Yahboom image / SD card. Nothing records its **version, provenance, or SHA-256**, and
nothing would notice if it were swapped, corrupted, or silently upgraded. The two `kmodel`s
catalogued above are pinned by hash; the model the safety case actually depends on is not.

That is the real gap, and it is the opposite of what this file said before 2026-07-10. **Open
question for Tin:** capture `yolov8n_320.kmodel`'s SHA-256 and record it here alongside the
others, and decide whether the ROI/acceptance evidence should refuse to run against an unpinned
detector.

A domain-tuned (multi-class, day/night) retrain remains worthwhile — the stock COCO model is not
trained on Vietnamese expressway shoulders at night. That needs ACLAB's **training pipeline**
(no dataset, labels, `.pt`/`.onnx`, or nncase config exists in *any* repo). But it is an
**improvement**, not a repair: nothing is currently broken by its absence.

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
