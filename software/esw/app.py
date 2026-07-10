# The edge application loop -- the ONE canonical wiring of the ESW device (doc 02 3).
#
# Until now the full chain existed only as test fixtures: harness/runner.py wires it for the
# sim and run_integration_tests.py wires a cut-down version for Level-G. NOTHING wired it for
# the K230, so the shipped esw/ subset had never run on a board. This module is that wiring,
# and it is the SAME object everywhere: the Level-H board and
# firmware/k230-detector/esw-app/main.py both build an EdgeApp and call step(). Only the
# injected BACKENDS differ -- there is no sim-only branch in here (ADR-0015 D3).
#
# ORDERING is the safety contract (mirrors harness/runner.py, doc 02 3):
#   1. read the detector       IF-1
#   2. health monitor          derives {camera,radar}, time integrity, force-safe (IF-5)
#   3. adapter -> perception   IF-1 -> IF-2 track events
#   4. state machine           the decision (ADR-0008 / ADR-0013)
#   5. actuator -> radio       IF-4 refresh-or-blank; a force-safe INHIBITS the refresh
#   6. telemetry -> outbox     IF-6/IF-7 audit, durable store-and-forward (non-safety, NFR-06)
#   7. capture                 raw detections + decision -> the acceptance-evidence log
#
# INVARIANT: the sign is refreshed ONLY by step() emitting a frame. There is no "off" command
# (see esw/actuator.py) -- a crashed loop, a dead box, a cut link and a force-safe all blank the
# sign because what they share is that nothing arrives.
#
# BACKENDS -- injected dict; the only thing that differs sim vs K230. Required: detector, radio,
# clock. Everything else is optional, and every MISSING one degrades a named capability that is
# reported LOUDLY at boot rather than silently assumed (ADR-0005).
#
#   detector.labels          list of the loaded model's class names
#   detector.read()          -> (boxes, class_ids, confidences) | None   (None = no fresh frame)
#   radio.send(frame)        transmit one IF-4 frame (bytes)
#   clock.monotonic()        -> float seconds; the tick clock (timers are deadlines against it)
#   clock.wall_ms()          -> int epoch ms | None    (absolute time for the IF-4 freshness guard)
#   clock.gnss_lock()        -> bool
#   sign_status()            -> True | False | None    (IF-3 read-back; None = no read-back)
#   selftest()               -> bool
#   drift()                  -> bool                   (FR-10 calibration-drift residual over tol)
#   commands.poll(now)       -> (override, ota, ack, config_push)   verified IF-8/9/10 only
#   store, transport         esw.sink.Outbox backends (durable evidence, oversight uplink)
#   capture.step(record)     record one tick of raw evidence (recall-N / FA accrual, ADR-0007)
#
# MicroPython-safe subset -- ships to the K230.

from esw.state_machine import StateMachine
from esw.perception import Perception
from esw.health import HealthMonitor
from esw.actuator import Actuator
from esw.telemetry import Telemetry
from esw.sink import Outbox
from esw.k230_adapter import detections_from_yolo, model_capabilities
from esw import if4

# Capabilities whose absence weakens a SAFETY claim (as opposed to oversight convenience).
# Each maps to a claim this unit can no longer make; the boot record names them.
_SAFETY_CAPS = ("sees_person",           # SC-12 pedestrian presence-onset unreachable
                "per_class_footprint",   # truck/bus collapse onto the car footprint
                "sign_readback",         # SC-24 stuck-ON sign undetectable (IF-3)
                "absolute_time",         # IF-4 freshness guard degrades (doc 10 "Time")
                "durable_evidence")      # recall-N / FA never accrue (ADR-0007)


class EdgeApp:
    """One ESW edge unit. Construct with real backends on the K230, fakes on the host."""

    def __init__(self, key, site_id, versions, calib, backends, config=None):
        self.backends = backends
        self.detector = backends["detector"]
        self.radio = backends["radio"]
        self.clock = backends["clock"]
        self._sign_status = backends.get("sign_status")
        self._selftest = backends.get("selftest")
        self._drift = backends.get("drift")
        self._commands = backends.get("commands")
        self._capture = backends.get("capture")
        self._transport = backends.get("transport")

        # The SUT, all real. StateMachine clamps the config (FR-20) and fingerprints what
        # survives, so cfg_ver names the config actually IN FORCE (R10) -- not what was asked for.
        self.sm = StateMachine(config)
        self.cfg = self.sm.cfg
        self.monitor = HealthMonitor(self.sm.cfg)
        self.perception = Perception(calib)      # raises on a mis-wound ROI: fail loud at commissioning
        self.actuator = Actuator(key, self.sm.cfg_ver)

        vers = dict(versions)
        vers["cfg_ver"] = self.sm.cfg_ver
        self.telemetry = Telemetry(site_id, vers)

        store = backends.get("store")
        self.outbox = None
        if store is not None:
            self.outbox = Outbox(store, self._transport)   # recover() resumes a dead unit's log

        self.caps = self._capabilities()
        self.sign_on = False
        self.last_decision = None
        self.ticks = 0
        self._last_tx = None       # IF-4 refresh cadence -- see _tx_due()

    # -- boot ----------------------------------------------------------------------------

    def _capabilities(self):
        """What this unit, with THESE backends and THIS model, can actually claim.

        `model_capabilities` reads the loaded label set: a single-class "vehicle" model still
        lights the sign for a shoulder car, so nothing downstream looks broken while the unit is
        blind to pedestrians. The host sim cannot catch that -- it injects scripted `person`
        labels no such detector would emit. Same shape of trap for a missing IF-3 read-back
        (SC-24 silently unreachable) or a missing store (bench-hours that never accrue)."""
        mc = model_capabilities(self.detector.labels)
        caps = {"sees_person": mc["sees_person"],
                "per_class_footprint": mc["per_class_footprint"],
                "classes": mc["classes"],
                "sign_readback": self._sign_status is not None,
                "absolute_time": self.clock.wall_ms() is not None,
                "durable_evidence": self.outbox is not None,
                "oversight_uplink": self._transport is not None,
                "capture": self._capture is not None,
                # Not a SAFETY cap: without frame_wh the density path is off, which can only make
                # the unit warn MORE (cry-wolf), never less. Reported so it is not assumed present.
                "density_congestion": self.perception.scene_enabled}
        degraded = []
        i = 0
        while i < len(_SAFETY_CAPS):
            name = _SAFETY_CAPS[i]
            if not caps[name]:
                degraded.append(name)
            i += 1
        caps["degraded"] = degraded
        return caps

    def start(self):
        """Boot. Returns the capability record: the first thing in the evidence log is an
        honest statement of what this unit could not do. The caller MUST surface it (print,
        LED, uplink) -- a degraded capability that nobody sees is exactly the silent loss of
        coverage ADR-0005 forbids."""
        now = self.clock.monotonic()
        rec = {"type": "capability",
               "ts": now,
               "site_id": self.telemetry.site_id,
               "severity": "CRITICAL" if self.caps["degraded"] else "INFO",
               "cfg_ver": self.sm.cfg_ver,
               "classes": self.caps["classes"],
               "sees_person": self.caps["sees_person"],
               "per_class_footprint": self.caps["per_class_footprint"],
               "sign_readback": self.caps["sign_readback"],
               "absolute_time": self.caps["absolute_time"],
               "durable_evidence": self.caps["durable_evidence"],
               "oversight_uplink": self.caps["oversight_uplink"],
               "density_congestion": self.caps["density_congestion"],
               "degraded": self.caps["degraded"]}
        if self.outbox is not None:
            self.outbox.record([rec])
        if self._capture is not None:
            self._capture.step(rec)
        return rec

    # -- the loop ------------------------------------------------------------------------

    def _wall_ms(self, now):
        """Absolute epoch ms for the IF-4 anti-replay freshness guard (doc 10 "Time").

        When the clock backend has no absolute time we fall back to the tick clock. The sign
        controller must then be in edge-synced or persistent-seq mode (doc 10 enumerates both),
        and `absolute_time` is reported degraded at boot. We do NOT blank on a time fault: a
        stopped car is still a hazard when the clock drifts (SC-36). Blanking on a CRITICAL
        fault is the health monitor's force-safe (IF-5), not the clock's business."""
        ms = self.clock.wall_ms()
        if ms is None:
            return if4.to_ms(now)
        return ms

    def _tx_due(self, now, asserting):
        """Is an IF-4 refresh due? The cadence is T_assert_refresh (0.5 s), NOT the tick rate.

        The sim can afford to re-transmit every 10 Hz tick; a real bearer cannot. At 10 Hz the
        ADR-0014 433 MHz duty budget is exceeded five-fold, and the dead-man's window (T_signhold
        2.0 s) never needed more than a 4x margin. A FRESH assertion always transmits immediately,
        so activation latency stays inside NFR-01 -- the throttle only governs the repeats."""
        if not asserting:
            self._last_tx = None                 # next SHOW is fresh -> transmits at once
            return False
        if self._last_tx is None:
            return True
        return (now - self._last_tx) >= self.cfg["T_assert_refresh"]

    def step(self, now=None):
        """One fixed-rate cycle. Returns the SM decision. Emits at most one IF-4 frame."""
        if now is None:
            now = self.clock.monotonic()
        self.ticks += 1

        # 1. IF-1. A detector that yields nothing this tick is a DROPPED FRAME, not a dead
        #    camera -- the health monitor's T_sensor_timeout debounce is what tells them apart.
        raw = self.detector.read()
        camera_live = raw is not None

        # 2. Health BEFORE the SM: mode is DERIVED, never injected (FR-10). radar=False always --
        #    the bench build is camera-only (ADR-0001 Rejected 2026-07-10).
        selftest_ok = True
        if self._selftest is not None:
            selftest_ok = self._selftest()
        hm = self.monitor.step(now, {"camera": camera_live, "radar": False},
                               self.clock.gnss_lock(), selftest_ok)

        # 3. IF-1 -> IF-2. On a dropped frame perception coasts the tracks (keeping their ids)
        #    and emits nothing; it never fabricates a detection.
        dets = []
        if camera_live:
            dets = detections_from_yolo(raw[0], raw[1], raw[2], self.detector.labels)
        events = self.perception.step(dets, now)

        # 4. The decision.
        health = {"camera": hm["camera"], "radar": hm["radar"], "time_valid": hm["time_valid"]}
        override = None
        ota = False
        ack = None
        config_push = None
        if self._commands is not None:
            override, ota, ack, config_push = self._commands.poll(now)
        readback = None
        if self._sign_status is not None:
            readback = self._sign_status()
        drift = False
        if self._drift is not None:
            drift = self._drift()
        inputs = {"sign_status": readback is True,   # absent read-back -> no stuck-ON claim
                  "ota": ota,
                  "ack": ack,
                  "config_push": config_push,
                  "drift": drift,
                  "scene": self.perception.scene}     # R14 density (needs calib frame_wh)
        decision = self.sm.tick(now, events, health, override, inputs)

        # 5. IF-4. Silence is how the sign is ALLOWED to blank; a force-safe inhibits the refresh
        #    without routing through a possibly-wedged state machine (IF-5, ADR-0009 A).
        asserting = decision.get("assertion") == "SHOW"
        due = self._tx_due(now, asserting)      # called every tick: it also arms the next fresh SHOW
        frame = None
        if due and not hm["force_safe"]:
            frame = self.actuator.step(now, decision, None, self._wall_ms(now))
        if frame is not None:
            self.radio.send(frame)
            self._last_tx = now

        # The PUBLIC-VISIBLE sign. With an IF-3 read-back that is ground truth. Without one the
        # unit can only report what it COMMANDED -- which is why sign_readback is a reported
        # capability, and why SC-24 (sign wedged ON) is unreachable when it is absent. Note this
        # cannot key off `frame`: between refreshes no frame is sent and the lamp is still lit.
        if readback is not None:
            self.sign_on = readback
        else:
            self.sign_on = asserting and not hm["force_safe"]

        # 6. IF-6/IF-7 oversight. Non-safety: the loop above never waits on it (ADR-0002).
        records = self.telemetry.step(now, decision, hm["status"], self.sign_on)
        if self.outbox is not None:
            self.outbox.record(records)                 # durable-append FIRST
            link_up = True
            if self._transport is not None and hasattr(self._transport, "up"):
                link_up = self._transport.up
            self.outbox.pump(link_up)

        # 7. Acceptance evidence (ADR-0007, doc 01 5). The RAW detections are recorded, not just
        #    the decision: recall/FA are scored against ground truth offline, and re-scoring a
        #    tuning change must not need a second trip to the road.
        if self._capture is not None:
            self._capture.step({"type": "tick",
                                "ts": now,
                                "dets": dets,
                                "events": events,
                                "state": decision.get("state"),
                                "assertion": decision.get("assertion"),
                                "mode": decision.get("mode"),
                                "posture": decision.get("posture"),
                                "alert": decision.get("alert"),
                                "sign_on": self.sign_on,
                                "force_safe": hm["force_safe"],
                                "hm_status": hm["status"],
                                "cfg_ver": decision.get("cfg_ver")})

        self.last_decision = decision
        return decision
