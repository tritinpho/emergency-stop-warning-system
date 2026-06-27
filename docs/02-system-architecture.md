# 02 — System Architecture

**Project:** Emergency Stop-Lane Automatic Warning System (ESW)
**Status:** Proposed
**Last updated:** 2026-06-26
**Related:** [requirements](01-requirements.md) · [ADRs](adr/README.md) · [risk & safety](04-risk-and-safety.md)

This is the central design document. It describes *how* the system is built and *why* it is shaped
this way. It is faithful to Figure 1 of the proposal (the concept infographic, preserved at
[assets/figure-1-concept-infographic.jpeg](assets/figure-1-concept-infographic.jpeg)) and makes it
buildable.

![Polished system architecture: road geometry (warning sign placed ≥ decision sight distance upstream of the detection zone), the roadside edge unit (sensors → perception → state machine → warning-sign actuator, with an independent health monitor), and a non-critical traffic management center.](assets/architecture-diagram.svg)

*Tiếng Việt: [sơ đồ kiến trúc](assets/architecture-diagram-vi.svg).*

*Overview — the safety-critical loop (blue) runs at the edge; the center (teal) is oversight only;
amber is everything the driver sees. The detailed views follow below.*

---

## 1. Architectural drivers

The shape of this architecture follows directly from the requirements:

| Driver | Architectural response |
|--------|------------------------|
| Safety loop must not depend on the network (NFR-06) | **Edge-local closed loop**; cloud is monitoring-only ([ADR-0002](adr/ADR-0002-edge-vs-cloud-processing.md)). |
| Must work at night / rain / fog (FR-09, NFR-05) | **Multi-sensor**: camera + radar fusion ([ADR-0001](adr/ADR-0001-sensing-modality.md)). |
| No false triggers, no flapping, no stale-ON (FR-03/04/07, NFR-04) | **State machine** with dwell, hysteresis, and a **watchdog** (§4). |
| Fail-safe + fail-loud (FR-10/11) | **Health monitor + defined safe state + heartbeat** (§3, [ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.md)). |
| Reuse infrastructure (FR-17) | **Pluggable actuator** abstraction: own LED sign *or* existing VMS ([ADR-0004](adr/ADR-0004-warning-actuator-integration.md)). |
| Right-size to budget (NFR-12) | Same logical design runs on a **simulation harness** and a **bench rig** (doc 03). |

## 2. Logical architecture (components & responsibilities)

```mermaid
flowchart TB
    subgraph RU["ROADSIDE UNIT — edge, safety-critical"]
        direction TB
        subgraph SENSE["Sensing layer"]
            CAM["Camera driver<br/>frames + timestamps"]
            RAD["Radar driver<br/>range / presence / speed"]
        end
        PERC["Perception<br/>vehicle/person detection in ROI"]
        FUSE["Fusion & tracking<br/>camera + radar → confirmed tracks"]
        SM["Decision state machine<br/>dwell · hysteresis · watchdog"]
        ACT["Actuator abstraction<br/>command: SHOW / CLEAR"]
        HM["Health monitor<br/>self-test · heartbeat · safe-state"]
        BUF["Local store<br/>config · event evidence · outbox"]

        CAM --> PERC
        RAD --> FUSE
        PERC --> FUSE --> SM --> ACT
        SM --> BUF
        HM -. watches .- SENSE
        HM -. watches .- PERC
        HM -. watches .- ACT
        HM --> SM
    end

    ACT --> SIGN["Warning actuator<br/>LED sign / existing VMS"]
    SIGN -. status .-> ACT
    BUF <--> GW["Comms gateway<br/>4G·LTE / fibre, queued"]
    HM --> GW

    GW <--> CENTER

    subgraph CENTER["TRAFFIC MANAGEMENT CENTER — non-critical"]
        direction TB
        ING["Telemetry ingest"]
        MON["Monitoring & alerting<br/>health · activations"]
        AUD["Audit log<br/>immutable event history"]
        OTA["Config & OTA service<br/>signed updates · rollback"]
        DASH["Operator dashboard<br/>status · manual override"]
        ING --> MON --> DASH
        ING --> AUD
        DASH --> OTA
    end

    style RU fill:#eef6ff,stroke:#3b82f6,stroke-width:2px
    style CENTER fill:#f0fdf4,stroke:#22c55e
    style SM fill:#fff7ed,stroke:#f97316,stroke-width:2px
    style HM fill:#fef2f2,stroke:#ef4444
```

**Component responsibilities**

| Component | Responsibility | Key notes |
|-----------|----------------|-----------|
| **Camera / radar drivers** | Acquire timestamped frames and radar returns. | Time sync between sensors matters for fusion. |
| **Perception** | Detect vehicles/persons; keep only detections whose footprint falls inside the ROI polygon. | Lightweight detector + ROI gating ([ADR-0003](adr/ADR-0003-detection-algorithm.md)). |
| **Fusion & tracking** | Associate camera detections with radar returns; produce stable tracks with position + speed + dwell. | Radar resolves "present & stationary" in the dark / rain. |
| **Decision state machine** | The brain. Applies dwell, hysteresis, watchdog; decides SHOW/CLEAR. | The only component that may command the sign. §4. |
| **Actuator abstraction** | Translate SHOW/CLEAR into the concrete sign protocol; read back sign status. | Swappable: own LED sign or existing VMS. |
| **Health monitor** | Self-test every subsystem; emit heartbeat; drive safe state on fault. | Independent watchdog path; see ADR-0005. |
| **Local store** | Hold config, the event-evidence buffer, and a durable outbox for telemetry. | Survives reboots; bounded retention (privacy). |
| **Comms gateway** | Store-and-forward telemetry; receive config/OTA. | Loss-tolerant; never in the safety path. |
| **TMC services** | Monitor, alert, audit, configure, update, override. | Off the critical path — can be offline without unsafe behaviour. |

## 3. Physical / deployment architecture

![Deployment / physical layout: a roadside mast and cabinet hold the camera+radar sensor head, the edge compute (IP65), and solar+battery power; the edge unit watches the detection zone, drives a warning sign placed upstream by ≥ the decision sight distance over a cable/RF link, and connects to the traffic management center over 4G·LTE/fibre.](assets/deployment-diagram.svg)

*Tiếng Việt: [sơ đồ triển khai](assets/deployment-diagram-vi.svg).*

*The roadside unit is one physical site: sensors + edge compute + power on the mast/cabinet, the
sign placed upstream (cable or radio link), and a non-critical uplink to the center. The editable
Mermaid source follows.*

```mermaid
flowchart LR
    subgraph POLE["Roadside mast (≈6–8 m) over the emergency lane"]
        SENSORS["AI camera + radar<br/>(IP65, heated/IR as needed)"]
        EDGE["Edge compute<br/>(e.g. Jetson Orin Nano / Pi+accelerator)<br/>IP65 enclosure"]
        PWR["Power: mains, or<br/>solar panel + battery (≥72h)"]
        SENSORS --- EDGE
        PWR --- EDGE
    end

    EDGE -- "local link<br/>(wired / short-range RF)" --> SIGNCTL["Sign controller"]
    SIGNCTL --> LED["Upstream warning sign<br/>placed ≥ DSD upstream<br/>(gantry VMS or roadside LED)"]
    EDGE -- "4G·LTE / fibre" --> CLOUD[("TMC / cloud<br/>monitoring · audit · OTA")]

    style POLE fill:#eef6ff,stroke:#3b82f6
    style LED fill:#fff7ed,stroke:#f97316
    style CLOUD fill:#f0fdf4,stroke:#22c55e
```

**Placement geometry (critical — see [doc 01 §4](01-requirements.md#4--warning-placement--the-math-the-proposal-omits)):**

```
     traffic ──────────────────────────────────────────────►
   ┌──────────────────────────────────────────────────────┐
   │  through lanes (làn xe 1, làn xe 2)                    │
   ├──────────────────────────────────────────────────────┤
   │  emergency lane (làn dừng khẩn cấp)                    │
   │                          [████ stopped vehicle ████]   │
   └──────────────────────────────────────────────────────┘
        ▲                                  ▲           ▲
     WARNING SIGN                      sensor mast   detection
   (≥ DSD upstream:                   (overlooks      zone / ROI
    ~315 m @100 km/h)                  the ROI)     (vùng phát hiện)
```

The sign is **upstream** of the detection zone by at least the Decision Sight Distance so that
following drivers receive the warning before they reach the hazard. Figure 1 shows two signs (a
gantry VMS and a roadside board); both are valid instances of the same "warning actuator" — choose
per site (ADR-0004).

## 4. The detection→warning state machine

This is where the proposal's "chu trình khép kín" (closed loop) becomes precise. It is the single
authority over the sign and the place where false-trigger, flapping, and stale-ON risks are
controlled.

![Detection-to-warning state machine: the idle → tracking → confirmed → warn-on → warn-hold → clearing cycle, with a watchdog self-loop on warn-on and a central safe state reachable from any state on a critical fault, returning to idle after a self-test passes.](assets/state-machine-diagram.svg)

*Tiếng Việt: [sơ đồ máy trạng thái](assets/state-machine-diagram-vi.svg).*

*Blue = normal monitoring, amber = warning shown, red = fault safe state. Dwell (default 5 s) gates
false triggers; the warn-on ⇄ warn-hold pair with a 10 s hold absorbs occlusion; the watchdog
re-confirms so no warning can stick on; the safe state is reachable from any state. The editable
Mermaid source follows.*

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> TRACKING : object enters ROI
    TRACKING --> IDLE : object leaves before dwell
    TRACKING --> CONFIRMED : stationary ≥ T_dwell (default 5s)
    CONFIRMED --> WARN_ON : command SHOW (≤2s)
    WARN_ON --> WARN_HOLD : object no longer detected
    WARN_HOLD --> WARN_ON : object re-detected (occlusion recovered)
    WARN_HOLD --> CLEARING : absent ≥ T_hold (default 10s)
    CLEARING --> IDLE : command CLEAR + sign status = off
    WARN_ON --> WARN_ON : watchdog re-confirm (bounded refresh)

    IDLE --> SAFE_STATE : critical fault
    TRACKING --> SAFE_STATE : critical fault
    CONFIRMED --> SAFE_STATE : critical fault
    WARN_ON --> SAFE_STATE : critical fault
    SAFE_STATE --> IDLE : fault cleared + self-test pass
```

**Timers & guards**

| Symbol | Default | Purpose | Trade-off |
|--------|---------|---------|-----------|
| `T_dwell` | 5 s (3–10) | Stationary time before "stopped" is declared. | Too low → false alarms from slow/transient vehicles; too high → late warning. |
| `T_hold` | 10 s (5–15) | Keep warning after last detection (hysteresis). | Absorbs brief occlusion; too high → stale warning after a real departure. |
| `T_activate` | ≤ 2 s | Confirmed → sign actually ON. | Bounded by NFR-01. |
| `T_watchdog` | ≤ 30 s | Max time a warning may stay ON without a fresh confirmation or watchdog refresh. | Prevents an indefinite stale-ON if logic wedges (NFR-04). |
| speed gate | ~ <3 km/h | Threshold below which a track counts as "stationary." | Separates "stopped" from "creeping along shoulder." |

**Why each guard exists (mapped to a real failure):**

- *Dwell* → a vehicle that drifts through or briefly touches the shoulder does **not** trigger.
- *Hysteresis (hold)* → a truck passing in the through-lane that momentarily **occludes** the stopped
  car does not cause the warning to blink off/on.
- *Watchdog re-confirm* → if the decision logic ever wedges with the sign ON, the watchdog forces a
  re-evaluation; unconfirmed → CLEAR. **No warning can be "stuck on" forever.**
- *Safe state* → on any critical fault the machine leaves normal operation and escalates (ADR-0005).

## 5. Runtime data flow (happy path)

![Runtime sequence: vehicle stops → sensors feed perception → state machine confirms after a 5 s dwell → sign shown → center notified asynchronously; while the vehicle stays, tracks keep the hold timer reset; on departure, after a 10 s hold the state machine clears the sign and notifies the center.](assets/runtime-sequence-diagram.svg)

*Tiếng Việt: [sơ đồ trình tự](assets/runtime-sequence-diagram-vi.svg).*

*The sign displays "stopped vehicle ahead" (PHÍA TRƯỚC CÓ XE DỪNG KHẨN CẤP). Dashed arrows are
asynchronous/return messages — the TMC notifications are fire-and-forget, so a down link never
stalls the safety loop. The editable Mermaid source follows.*

```mermaid
sequenceDiagram
    autonumber
    participant V as Vehicle
    participant S as Sensors (cam+radar)
    participant P as Perception+Fusion
    participant M as State machine
    participant A as Sign
    participant T as TMC

    V->>S: enters & stops in emergency lane
    S->>P: frames + radar returns (in ROI)
    P->>M: confirmed track, speed≈0, dwell timer running
    Note over M: stationary ≥ T_dwell → CONFIRMED
    M->>A: SHOW "STOPPED VEHICLE AHEAD"
    A-->>M: status = ON
    M-->>T: event{activation, site, ts} (async, non-blocking)
    loop while present
        S->>P: continued detections
        P->>M: track alive (resets hold timer)
    end
    V->>S: departs ROI
    Note over M: absent ≥ T_hold → CLEARING
    M->>A: CLEAR
    A-->>M: status = OFF
    M-->>T: event{clear, site, ts}
```

The TMC interactions (steps to `T`) are **fire-and-forget**: if the link is down, events queue in the
local outbox and the safety loop is unaffected.

## 6. Coverage model

A single roadside unit covers a **bounded segment** (the length its sensors reliably see —
realistically tens to low-hundreds of metres). An emergency lane is continuous, so full coverage is
neither affordable nor in scope. The model is therefore **discrete monitored zones at high-value
locations**:

- approaches to **tunnels, bridges, elevated sections** (Figure-1 use cases);
- **curves / crests** with limited sight distance;
- known **incident hotspots** and lay-by/stop points;
- expressway segments where the operator reports recurring shoulder stops.

For this project, **one pilot zone** (or its simulation) is the scope. Scaling to many zones is a
deployment/CapEx question for the field follow-on, not an architecture change — units are independent
and report to the same TMC.

## 7. Interfaces & contracts (initial)

| Interface | Between | Shape (indicative) |
|-----------|---------|--------------------|
| Detection event | Perception → State machine | `{track_id, class, bbox/range, speed, in_roi, ts}` |
| Sign command | State machine → Actuator | `SHOW(message_id) | CLEAR | STATUS?` returns `{state, lamp_ok, ts}` |
| Heartbeat | Health monitor → TMC | `{site_id, fw_ver, subsystem_health[], state, ts}` at fixed cadence |
| Activation/clear event | State machine → TMC/audit | `{site_id, type, evidence_ref?, ts}` (store-and-forward) |
| Config | TMC → Roadside | `{roi_polygon, T_dwell, T_hold, speed_gate, message_set}` (signed) |
| OTA | TMC → Roadside | signed image + version + rollback token |

Concrete encodings (protobuf/JSON, MQTT/HTTPS for telemetry; the sign vendor's protocol or an
NTCIP-style profile for VMS) are deferred to detailed design; the **abstraction boundaries above are
the architectural commitment.**

## 8. Recommended technology stack (indicative, not binding)

| Layer | Recommendation | Rationale |
|-------|----------------|-----------|
| Edge compute | NVIDIA Jetson Orin Nano *or* Raspberry Pi 5 + Hailo/Coral accelerator | Enough TOPS for a small detector at the edge; low power for solar. |
| Camera | Global-shutter or good-WDR IP camera; IR illumination for night | Handles glare and night per NFR-05. |
| Radar | Automotive-grade 24/77 GHz presence+range radar | Night/fog/rain presence; complements camera (ADR-0001). |
| Perception | Compact detector (YOLO-nano / SSD-Mobilenet class) + ROI gating + simple tracker (SORT/ByteTrack) | Robust, cheap, edge-friendly (ADR-0003). |
| Runtime | Containerised services, systemd-supervised; watchdog process | Restartability + isolation; health monitor independent of perception. |
| Local store | SQLite + ring-buffer for event evidence | Small, durable, bounded retention (privacy). |
| Telemetry | MQTT over TLS, store-and-forward outbox | Loss-tolerant, lightweight. |
| Sign | LED matrix VMS (QCVN-41-compliant) *or* existing operator VMS via its protocol | ADR-0004. |
| Simulation | CARLA / SUMO or a custom 2-D scenario player feeding synthetic detections | Validate the state machine without traffic (doc 03). |
| TMC | Small web service + time-series store + dashboard | Monitoring/audit only; not safety-critical. |

> These are starting points sized to the budget and skills; each is revisited in detailed design and
> the load-bearing ones are argued in the ADRs.

## 9. How this maps to Figure 1

| Figure 1 element (VI) | Architecture component |
|-----------------------|------------------------|
| Camera AI giám sát làn dừng | Camera driver + Perception (+ radar added here) |
| AI nhận diện ô tô đậu trong vùng | Perception + Fusion, ROI-gated |
| Vùng phát hiện (red dashed area) | The ROI polygon / detection zone |
| Bộ xử lý AI / điều khiển | Edge compute: Fusion + **State machine** |
| Hệ thống tự động gửi tín hiệu cảnh báo | Actuator abstraction → sign command |
| Bảng tín hiệu ở đầu làn / gantry VMS | Warning actuator (placed ≥ DSD upstream) |
| Tự động tắt khi xe rời đi | `WARN_HOLD → CLEARING → IDLE` transitions |
| Lợi ích: phát hiện tự động, cảnh báo kịp thời | Met by latency + availability NFRs |

The architecture adds, beyond the infographic: **radar fusion, the dwell/hysteresis/watchdog logic,
the health-monitor + safe-state, DSD-based placement, and the TMC oversight plane** — i.e. the parts
that make it dependable rather than just demonstrable.
