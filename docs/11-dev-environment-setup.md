# 11 — Development-Environment Setup Runbook (the three build environments)

**Project:** Emergency Stop-Lane Automatic Warning System (ESW / ELMS)
**Status:** Living runbook — first executed on the software lead's machine 2026-07-09 (§5).
**Last updated:** 2026-07-09
**Owns:** how a team member gets a working toolchain for each of the three build modules.
**Consumes:** [doc 02 §8](02-system-architecture.md#8-recommended-technology-stack-indicative-not-binding) (tech stack), [doc 10](10-if4-sign-controller-firmware-spec.md) (IF-4 firmware), [spikes runbook](../software/spikes/README.md) (the D3 gate), [ADR-0015](adr/ADR-0015-state-machine-implementation-strategy.md).

> 🇻🇳 Phiên bản tiếng Việt: [11-dev-environment-setup.vi.md](11-dev-environment-setup.vi.md).

The project has **three programmable modules**, and each needs its own environment:

| Module | What it is in the architecture | Environment |
|---|---|---|
| **AI camera** | The edge unit — a Kendryte **K230** running CanMV/MicroPython; [`software/esw/`](../software/README.md) ships to it **byte-identical** (ADR-0015 D3) | CanMV IDE + firmware image + `mpremote` |
| **CoreIOT server** | The TMC **oversight plane** — IF-6/7 telemetry up, IF-8/9/10 commands down ([ICD §4–5](08-interface-control-document.md)); **non-critical by design** (ADR-0002) | A CoreIOT account + device token + `paho-mqtt` |
| **ESP32 (YoloUno)** | The **sign controller** — the IF-4 dead-man's switch specified in [doc 10](10-if4-sign-controller-firmware-spec.md) | PlatformIO + [`firmware/sign-controller/`](../firmware/sign-controller/README.md) |

The order below is deliberate: §1 (common) unblocks everything; §2–§4 are independent of
each other and can be done per-person as the hardware/accounts arrive.

---

## 1. Common baseline (every machine, ~10 minutes)

1. **Git + Python ≥ 3.10** (3.12 recommended). The simulation boards are **stdlib-only
   on purpose** (the SUT must stay MicroPython-safe), so there is no `requirements.txt`
   for the core — the pip installs below are for the *hardware-facing* tools only.
2. Clone and prove the software workstream runs:

   ```
   git clone https://github.com/tritinpho/emergency-stop-warning-system
   cd emergency-stop-warning-system
   python software/run_tests.py             # 43 scenarios, exit 0
   python software/run_perception_tests.py  # and the other four boards likewise
   python software/tools/mp_safe_check.py software/esw
   ```

3. Install the hardware-facing tools:

   ```
   python -m pip install --user esptool mpremote platformio paho-mqtt
   ```

   **Windows PATH note:** pip's `--user` scripts land in
   `%APPDATA%\Python\Python312\Scripts`, which is usually **not** on `PATH`. Either add
   that directory to `PATH`, or skip the problem entirely by invoking every tool as a
   module — `python -m esptool`, `python -m mpremote`, `python -m platformio` — as this
   runbook does throughout.

4. *(Optional, for local MicroPython-unix runs of the shipped subset)* **Docker** or WSL.
   CI already runs the Level-A/C boards + smoke under `micropython/unix:v1.28.0` on every
   push, so this is only needed to reproduce that locally:

   ```
   docker run --rm -v "$PWD/software:/w" -w /w micropython/unix:v1.28.0 micropython run_tests.py
   ```

**You know §1 worked when:** all six boards print their PASS banner and exit 0.

---

## 2. Module 1 — the AI camera (K230, CanMV/MicroPython)

**Why this environment matters most:** the K230 runs the *safety loop*. The shipped
[`software/esw/`](../software/README.md) subset is already **proven portable** (CI runs it
under the real MicroPython unix port), but **ADR-0015 D3 is still an assumption on the
physical board** — the [K230 timing spike](../software/spikes/README.md) is the gate, and
it is *blocked on board access*. Setting up this environment is what unblocks it.

### 2.1 Host tools

| Tool | What for | Install |
|---|---|---|
| **CanMV IDE** | Camera preview, file manager, REPL | download from the Kendryte CanMV release page (`github.com/kendryte/canmv_ide`) |
| **`mpremote`** | Scriptable file copy + REPL over USB serial | done in §1 (`python -m mpremote`) |
| **nncase** | detector → `kmodel` conversion | **deferred** with the detector workstream (ADR-0003); `pip install nncase nncase-kpu` when it starts |

### 2.2 Board bring-up

1. **Firmware image:** download the CanMV-K230 image matching the team's board variant
   (Kendryte releases: `github.com/kendryte/canmv_k230`; Sipeed boards also publish
   variants — record the **exact version** you flash, the spike report asks for it).
2. **Flash to microSD** (the K230 boots from SD): write the `.img` with balenaEtcher /
   Rufus / `dd`. Insert, power via USB-C.
3. **Serial:** the board enumerates as a USB-CDC serial port (`COMx`). Check:

   ```
   python -m mpremote connect list
   python -m mpremote connect COMx repl     # Ctrl-] to exit
   ```

4. **Deploy the SUT** (the shipped subset only — the harness never ships):

   ```
   python -m mpremote connect COMx fs cp -r software/esw :/sdcard/esw
   ```

   (Some CanMV builds mount the writable FS at `/flash` instead of `/sdcard` — `fs ls :/`
   shows which; adjust the target.)

### 2.3 The acceptance gate — run the timing spike

This is the actual *deliverable* of the camera environment (ADR-0015 AI#1):

```
python -m mpremote connect COMx fs cp software/spikes/k230_timing_spike.py :/sdcard/
# then follow software/spikes/README.md §4: start the YOLO demo first (real KPU/heap
# contention), run the spike in a second session, record the table + VERDICT line.
```

**You know §2 worked when:** `mpremote repl` gives a MicroPython prompt,
`import esw` succeeds on the board, and the spike prints its table (the PASS/FAIL
*verdict* then belongs to the ADR-0015 D3 decision, not to this runbook).

---

## 3. Module 2 — the CoreIOT oversight server

**Scope guard first (ADR-0002):** the safety loop **never depends on this module**. IF-6/7
telemetry is store-and-forward (an outage queues locally, [`esw/sink.py`](../software/esw/sink.py)
proves nothing is lost), and IF-8/9/10 commands are authenticated end-to-end in
[`esw/command.py`](../software/esw/command.py) — CoreIOT is the *transport and dashboard*,
never the authority. That is why this module's setup is an account + a smoke test, not a
safety artifact.

CoreIOT (`coreiot.io`) is a Vietnamese IoT platform built on **ThingsBoard** (per its own
docs; operated by ADT, the OhStem ecosystem), so the device API is the ThingsBoard MQTT
convention: device **access token** as the MQTT username (password ignored), telemetry to
`v1/devices/me/telemetry`, server→device RPC on `v1/devices/me/rpc/request/+`. The broker
is **`app.coreiot.io:1883`** — the same constant OhStem's own client SDK ships
(`ohstem-public/coreiot-client-sdk`).

> ⚠️ **Open item for the oversight-plane decision:** [ICD §2](08-interface-control-document.md)
> specifies IF-6/7 as **MQTT over TLS**, but as of 2026-07-09 CoreIOT exposed **plaintext
> 1883 only** (8883 closed). Acceptable for bench telemetry — the channel is non-safety and
> the command channel carries its own HMAC (ADR-0012) — but the TLS posture must be
> resolved (CoreIOT roadmap, a TLS-terminating relay, or a different broker) before any
> field pilot. Recorded here so it can't silently become "the way it is".

### 3.1 Account + device

1. Register at the CoreIOT portal (`app.coreiot.io/signup` — self-registration is open,
   the platform is free for education use) and sign in.
2. Create a device for your bench unit (Devices → **Add device**), name it after the
   site id you'll use (e.g. `SITE-DEV`).
3. Copy the device's **access token** (device page → *Manage credentials / Copy access
   token*). Treat it like a password — it is not a secret *key* in the ADR-0012 sense
   (the command channel has its own HMAC), but it does gate writes to your dashboard.

### 3.2 The smoke test

[`software/tools/coreiot_smoke.py`](../software/tools/coreiot_smoke.py) proves the path in
three steps — DNS/TCP reachability (no credentials), MQTT token auth, then publishing
**one real IF-6 heartbeat built by the real emitter** (`esw/telemetry.py`, stamped with the
real §7a config fingerprint) and subscribing to the RPC topic (the direction the IF-8/9/10
binding will ride):

```
python software/tools/coreiot_smoke.py                          # reachability only
python software/tools/coreiot_smoke.py --token <ACCESS_TOKEN>   # the full three steps
python software/tools/coreiot_smoke.py --token ... --tls        # production posture (8883)
python software/tools/coreiot_smoke.py --token ... --wait-rpc 30  # + prove server->device
```

**You know §3 worked when:** the script prints `PASS: the IF-6 record landed on CoreIOT.`
and the device's **Latest telemetry** on the dashboard shows the `if`/`site_id`/
`sensor_mode`/`posture`/`state` fields.

**Deliberately not here:** the durable outbox's real MQTT backend (the
[`esw/sink.py`](../software/esw/sink.py) pump over this transport) is its own workstream —
the smoke test proves the road is open, not that the truck route is scheduled.

**Useful references:** CoreIOT docs (`coreiot.io/docs`, Vietnamese); OhStem's device SDKs
for CoreIOT — Arduino/ESP32 `github.com/ohstem-public/coreiot-client-sdk`, MicroPython
`github.com/AITT-VN/yolouno_extension_core_iot` — handy as worked examples of the
ThingsBoard device API, though ESW's edge telemetry will bind through `esw/sink.py`, not
an app-style SDK.

---

## 4. Module 3 — the ESP32 sign controller (YoloUno)

**What this module is:** the other end of the safety loop — the IF-4 dead-man's switch
([doc 10](10-if4-sign-controller-firmware-spec.md)). The firmware scaffold implementing the
doc 10 contract **already exists** at [`firmware/sign-controller/`](../firmware/sign-controller/README.md):
the C mirror of `esw/if4.verify()`, the two-guard anti-replay, the
recompute-from-freshness blank rule, boot-time conformance vectors generated from the
Python reference codec, and a host bench that scores doc 10 §7 rows C1–C7.

**The board:** OhStem **Yolo:UNO** — ESP32-S3 **N16R8** (16 MB flash, 8 MB PSRAM, per
OhStem's own PlatformIO board definition), Uno form factor, **native USB-C**
(`0x303A:0x1001` — no UART-bridge driver needed on Windows 10/11), BOOT button on GPIO0,
onboard D13 LED on GPIO48 and WS2812 RGB pixel on GPIO45. The firmware's YoloUno env uses
those two onboard indicators as the **zero-wiring bench sign** (LED/red pixel = SHOW,
dark = blank). There is no YoloUno entry in the PlatformIO registry;
[`firmware/sign-controller/boards/esp32s3-n16r8.json`](../firmware/sign-controller/boards/esp32s3-n16r8.json)
carries the board definition.

### 4.1 Build + flash

```
cd firmware/sign-controller
python -m platformio run                        # build (first run downloads the toolchain)
python -m platformio run -t upload              # flash over USB-C
python -m platformio device monitor -b 115200   # expect: BOOT ... / KEY dev ... / VECTORS PASS 16/16
```

If upload can't open the port: hold **BOOT** (GPIO0), tap **RESET**, release BOOT
(manual download mode), retry; afterwards tap RESET once to run.

*Alternative toolchains, for completeness:* Arduino IDE works via OhStem's boards package
(Boards Manager URL
`https://raw.githubusercontent.com/AITT-VN/ohstem_arduino_board/main/package_xcon_index.json`,
board **"Yolo UNO (ESP32-S3)"**) — fine for quick experiments, but the sign-controller
deliverable stays a PlatformIO project (reproducible, CI-able). OhStem also ships a
**MicroPython** firmware for this board (browser-flash at `fw.ohstem.vn`, used by their
block IDE) — **not** what the sign controller uses: doc 10's dead-man's switch is the
C/Arduino firmware here, and flashing OhStem's MicroPython replaces it.

### 4.2 Bench the dead-man's switch

With the board flashed and on `COMx`:

```
python tools/bench_send.py --port COMx          # C1, C2/C4, C5, C6, C7 scored automatically
python tools/bench_send.py --port COMx --soak   # continuous refresh (demo / Tier-2 soak)
```

The bench drives the **real 29-byte frames from the real Python codec** at the board, so a
PASS here is the same contract the Level-A board pins in simulation (SC-01/21/23/33/34/15).

**You know §4 worked when:** the boot log prints `VECTORS PASS 16/16` and the bench prints
`bench: 5/5 PASS`. C3 (physically power off a real edge box) and C8 (wedged-panel IF-3
read-back) remain physical-rig tests — see the
[conformance table](../firmware/sign-controller/README.md#conformance-status-doc-10-7).

---

## 5. Machine status — first execution (software lead's Windows 11 machine, 2026-07-09)

Done by this runbook's first execution; re-run the commands to reproduce on any machine.

| Item | Status 2026-07-09 |
|---|---|
| Python 3.12.2 | ✅ pre-existing |
| esptool 5.3.1 · mpremote 1.28.0 · paho-mqtt 2.1.0 · PlatformIO 6.1.19 | ✅ installed (`--user`; PATH note in §1.3) |
| PlatformIO `espressif32 @ 7.0.1` platform + ESP32-S3 toolchain | ✅ installed; `firmware/sign-controller` **builds green** on the YoloUno N16R8 board def (RAM ~5.8 %) |
| Six simulation boards + `mp_safe_check` | ✅ all PASS on this tree |
| CoreIOT broker reachability | ✅ `app.coreiot.io:1883` DNS + TCP open from this network |
| CoreIOT account + device token | ⬜ user action (§3.1) — then the smoke test's steps 2–3 |
| CanMV IDE + K230 firmware image | ⬜ download when the board is in hand (§2.1–2.2) |
| K230 board access | ⬜ with Nhóm ACLAB ELMS — **blocks the ADR-0015 D3 spike** |
| YoloUno board in hand | ⬜ flash + bench per §4 when available |
| Docker/WSL (local `micropython-unix`) | ⬜ optional — CI already covers it |

---

## 6. Thuật ngữ (VI glossary)

| EN | VI |
|---|---|
| dev environment / toolchain | môi trường lập trình / bộ công cụ |
| flash (firmware) | nạp (firmware) |
| serial port / REPL | cổng nối tiếp / REPL |
| device access token | mã truy cập thiết bị |
| broker (MQTT) | máy chủ trung gian MQTT |
| bench (test) | kiểm thử trên bàn (bench) |
| dead-man's switch | cơ chế tự ngắt an toàn |
| smoke test | kiểm tra nhanh (smoke test) |
