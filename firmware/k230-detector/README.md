# firmware/k230-detector — the ACLAB ELMS K230 perception layer (vendored)

This subtree is the **device-tested K230 detector** from the hardware/firmware team
(ACLAB ELMS), vendored into this repo per [ADR-0016](../../docs/adr/ADR-0016-repo-consolidation-and-perception-source.md).
It is the real perception backend that this repo's `software/esw` safety stack was
built to sit on top of — a K230 running YOLOv8n at ~30 FPS with a field-usable ROI
tool and environmental noise filters.

## Provenance

- **Source:** `https://github.com/KendyKeb/Solar-Powered-Intelligent-Emergency-Lane-Monitoring-and-Warning-System`
- **Vendored at:** upstream `main` @ `1c68370` (2026-07-09).
- **Authors:** ACLAB ELMS (Đình Ý / `ydtTran`, Nghĩa Dũng / `dungisme142`, Duy Mạnh / `Manh Pham Duy`).
- **Copied verbatim — one exception.** The `.py` under `k230/`, `noise-filters/`, and
  `esp32-legacy/` are vendored unchanged **except that hardcoded secrets were removed**
  (ADR-0016 backlog #6; see [Local modifications — secrets](#local-modifications-secrets)
  below). No runtime API, logic, or timing was modernised.

### The baseline rule (from their `AGENTS.md`)

Treat the vendored `k230/` as the **authoritative, device-tested runtime baseline**.
Do **not** edit it to fit our style or "modernise" its CanMV/`aidemo` APIs. The target
is the Yahboom SD-card image **1.4.1** (2025-08-20), nncase/kmodel toolchain **2.9.0**.
All reconciliation with our interfaces happens in an **adapter outside this subtree**
(see the seam below), so this stays a clean reference. The full baseline note is
preserved at [`design-log/AGENTS-k230-baseline.md`](design-log/AGENTS-k230-baseline.md).

## The seam — how their detector meets our safety stack

Their `k230/main.py` today does the whole loop itself: detect → ROI-gate → dwell →
emit `LED:ON/OFF`. Under [ADR-0016](../../docs/adr/ADR-0016-repo-consolidation-and-perception-source.md)
the merged pipeline keeps **their detector** and replaces **their dwell + sign link**
with ours:

```
K230 KPU (their kmodel)                          <- keep: real detector
   -> collect_vehicle_detections(boxes,cls,conf) <- their extractor
   -> [ADAPTER] -> detections[{cls,bbox,score}]  <- IF-1  (task #6, not yet built)
   -> esw.perception.Perception.step()           <- ours: ground projection + tracker -> IF-2
   -> esw.state_machine.tick()                    <- ours: dwell, occlusion, watchdog, congestion
   -> esw.actuator (IF-4, refresh-or-blank)       <- ours: dead-man's switch over LoRa
   -> firmware/sign-controller (ESP32)            <- ours: replaces esp32-legacy/
```

Their CoreIoT MQTT stays, but **demoted to non-critical IF-6 telemetry** — it is no
longer in the safety path (a stopped-vehicle warning must not depend on a cloud broker;
[ADR-0002](../../docs/adr/ADR-0002-edge-vs-cloud-processing.md)).

The adapter (`collect_vehicle_detections` → `Perception.step()` shape) and its closed-loop
integration test are **task #6, not yet built** — this commit vendors the baseline and
records the contract; the wiring is the next slice.

## Layout

```
k230/                 # VENDORED device app (baseline — do not modernise)
  main.py             #   production loop: YOLOv8n -> ROI clip-area -> dwell -> ESP32 TCP + MQTT
  setup_roi.py        #   web ROI-config tool (port 8081) — harvest as commissioning tooling (D4)
  test_mqtt_roi.py    #   standalone camera+MQTT smoke
  connect_wifi.py     #   LVGL/touch Wi-Fi bootstrap (see design-log troubleshooting note)
noise-filters/        # VENDORED environmental filters (host CPython + ulab/MicroPython)
  light_filter.py     #   REAL on-device: ulab highlight compression (V>240 clamp)
  overvehicles_filter.py #  REAL: density -> scene-busy == our congestion suppression (R14/SC-11)
  shaking_filter.py   #   NO-OP under MicroPython (needs cv2) — do NOT count as a mitigation
  main.py, result/    #   their filter harness + result dataclasses
esp32-legacy/
  yolouno-mqtt.py     # SUPERSEDED by firmware/sign-controller (IF-4). Kept for reference only.
models/               # kmodel I/O configs (+ binary-storage decision) — see models/README.md
design-log/           # their design record — DEMOTED, not authoritative
  architecture.md, light_control.md, init_state.md, flowchart.md, function.md,
  k230_hardware.md, deployment_guide.md, progress.md, troubleshooting_wifi_bootstrap.md
  demo.md             #   their prototype demo scope — §2.1 lists the laptop dashboard we do not build
  ui.md               #   Yahboom LVGL 8.3 app-UI baseline; refs `k230-firmware/`, a vendor image not in either repo
  setup_roi_development_log.md, test_mqtt_roi_development_log.md
```

## Reconciliation backlog (from ADR-0016 §Consequences)

Each is a real behaviour difference between their baseline and our architecture. Status
here; dispositions in [ADR-0016](../../docs/adr/ADR-0016-repo-consolidation-and-perception-source.md).

| # | Item | Their baseline | Our target | Status |
|---|---|---|---|---|
| 1 | Detector class set | production `kmodel` = single class `"vehicle"` | per-class footprint car/truck/bus + person (SC-12) | open — COCO model or class remap (task #6) |
| 2 | Confirm dwell | `PRESENCE_THRESHOLD = 0` (lights on 1st frame) | configurable `T_dwell` confirm | open — SM governs after adapter |
| 3 | ROI geometry | image-plane bbox∩polygon ≥ 0.2 | ground-projected footprint∩ROI (PC-11) | ours supersedes; theirs = near-nadir fallback |
| 4 | Shake mitigation | `ShakingFilter` = MicroPython no-op | real stabilisation (field) | **do not count** as on-device mitigation |
| 5 | Cloud coupling | CoreIoT MQTT in the control path | edge-local; MQTT = IF-6 telemetry only | open — demote in ICD (task #7) |
| 6 | Secrets | hardcoded Wi-Fi pw + CoreIoT token (already public) | rotate + move to `config.json` | **config move done** (2026-07-09, [details](#local-modifications-secrets)); **rotation pending ACLAB ELMS** |
| 7 | Model binaries | two ~7 MB `kmodel`s | git-LFS vs external store | open — see `models/README.md` |

<a id="local-modifications-secrets"></a>

## Local modifications — secrets (ADR-0016 backlog #6)

The vendored baseline shipped **hardcoded Wi-Fi and CoreIoT credentials**, copied
verbatim from the upstream repo. That repo is **private**, and this one is **public** —
so vendoring the literals here would have been a **first disclosure**, not a re-disclosure.
Per ADR-0016 backlog #6 the literals here have been **replaced with
empty placeholders sourced from `config.json` / `sys_config.json`** — the same device
mechanism the baseline already uses (`load_wifi_credentials()` / `load_mqtt_config()`).
This is the standard **secrets exception** to the "do not modernise the device baseline"
rule (their `AGENTS.md`): no runtime API, logic, or timing was touched, and every file
stays runnable — Wi-Fi/MQTT simply won't authenticate until real credentials are supplied
via config.

| File | Secret removed (now empty `""` / `None` placeholder) |
|---|---|
| `esp32-legacy/yolouno-mqtt.py` | lab Wi-Fi password; CoreIoT `DEVICE_IOT_02` access token. *(This file had no config reader; a minimal `config.json` loader was added to match the K230 app.)* |
| `k230/main.py` | lab Wi-Fi password (×2: fallback default + `WIFI_PRESETS`); CoreIoT `DEVICE_IOT_01` access token fallback |
| `k230/setup_roi.py` | lab Wi-Fi password fallback |
| `k230/test_mqtt_roi.py` | lab Wi-Fi password fallback |

`k230/connect_wifi.py` was already clean (it only reads `sys_config.json`). The pre-existing
dummy values (`"123"`) in the test/setup scripts are not credentials and were left as-is.

**Where the real credentials live** (device-side, nothing committed): `/sdcard/config.json`
— `{"wifi": {"ssid", "password"}, "server": {"access_token"}}` — with the firmware's
`/sdcard/configs/sys_config.json` (`WLAN` section) as the secondary Wi-Fi source.

> ### ⚠️ Action required — ACLAB ELMS must ROTATE the credentials
> Removing the literals from our vendored copy does **not** invalidate them. The lab
> Wi-Fi password and **both** CoreIoT device access tokens (`DEVICE_IOT_01`,
> `DEVICE_IOT_02`) remain live, and remain committed in the upstream repo and its git
> history. Upstream is private, so they are not published — but they are plaintext in a
> shared history, and one `Settings → Change visibility` away from being. They must be
> rotated **at the source** — the Wi-Fi AP and the CoreIoT/ThingsBoard device
> provisioning — which only ACLAB ELMS can do; no change on our side can. Tracked
> as ADR-0016 action item #4 (backlog #6).
>
> **Do not make the upstream repo public before rotating.**

## What is authoritative

- **Authoritative spec:** this repo's docs 00–11 + ADRs. If `design-log/architecture.md`
  or `design-log/light_control.md` disagree with an ADR, **the ADR wins** — those files
  are the hardware team's design record, preserved but demoted by ADR-0016 D1.
- **Authoritative device baseline:** `k230/` (runtime behaviour), per their `AGENTS.md`.
- **Authoritative sign-link contract:** [doc 10](../../docs/10-if4-sign-controller-firmware-spec.md)
  + [`firmware/sign-controller`](../sign-controller/README.md). `esp32-legacy/` is superseded.
