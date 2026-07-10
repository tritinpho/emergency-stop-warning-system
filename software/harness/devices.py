# Host backends for esw.app.EdgeApp (Level-H). NOT shipped.
#
# EdgeApp is the real device loop; these are the four things a bench cannot supply for real:
# a camera, a radio, a clock, and an operator. Everything between them -- adapter, perception,
# state machine, actuator, health monitor, telemetry, outbox -- is the SAME code the K230 runs.
#
# The radio is deliberately not a stub: SignLink hands the actuator's real IF-4 frame bytes to
# harness.sign.Sign, which decodes and verifies them exactly as the ESP32 firmware does. A test
# that lights the sign here has driven authenticated frames through a real dead-man's switch.

from esw import if4


class FakeClock:
    """The tick clock. `absolute=False` models a unit with no GNSS fix and no hold-over left.

    wall_ms() returns the tick clock in ms, which is also what harness.sign.Sign checks frames
    against -- so edge and controller agree by construction here. On a real unit they agree only
    if a GNSS/PPS source or doc-10 edge-sync keeps them inside the replay window; that is why
    `absolute_time` is a boot-reported capability and not an assumption."""

    def __init__(self, absolute=True, gnss=True):
        self.t = 0.0
        self.absolute = absolute
        self.gnss = gnss

    def set(self, t):
        self.t = t

    def monotonic(self):
        return self.t

    def wall_ms(self):
        return if4.to_ms(self.t) if self.absolute else None

    def gnss_lock(self):
        return self.gnss


class ScriptedDetector:
    """A camera + detector driven by a scenario script.

    `frame_fn(case, t)` returns raw YOLO `(boxes, class_ids, confidences)` -- the exact shape
    aidemo.yolov8_det_postprocess emits on the K230. `blind` windows return None: no fresh frame,
    which is what a dropped frame AND a dead camera both look like from here. Only the health
    monitor's T_sensor_timeout debounce distinguishes them, which is the point."""

    def __init__(self, case, frame_fn, labels, blind=()):
        self.case = case
        self.frame_fn = frame_fn
        self.labels = labels
        self.blind = blind
        self.t = 0.0
        self.reads = 0

    def set(self, t):
        self.t = t

    def read(self):
        self.reads += 1
        for w in self.blind:
            if w[0] <= self.t < w[1]:
                return None
        return self.frame_fn(self.case, self.t)


class SignLink:
    """The IF-4 radio + the sign controller on the other end of it.

    `send()` queues the frame; `tick(t)` delivers it and runs the dead-man's switch, exactly the
    ordering harness/runner.py uses. `status()` reports the PREVIOUS tick's lamp state, because
    the IF-3 read-back a real edge sees is one cycle stale.

    `link_up=False` cuts the link (frames vanish); `can_turn_off=False` wedges the lamp ON
    (SC-24). Both are the hardware faults the switch exists to survive."""

    def __init__(self, sign):
        self.sign = sign
        self._pending = None
        self.on = False
        self.sent = 0

    def send(self, frame):
        self._pending = frame
        self.sent += 1

    def tick(self, t):
        if self._pending is not None:
            self.sign.receive(t, self._pending)
            self._pending = None
        self.on = self.sign.update(t)
        return self.on

    def status(self):
        return self.on

    @property
    def rejects(self):
        return self.sign.rejects


class ListCapture:
    """The acceptance-evidence capture backend, in RAM. The device writes the same records as
    JSON lines to the SD card (firmware/k230-detector/esw-app/backends.py). What matters is that
    the RAW detections are kept, not just the decision: recall and false-activation are scored
    offline against ground truth, and re-scoring a tuning change must not need another trip to
    the road."""

    def __init__(self):
        self.records = []

    def step(self, record):
        self.records.append(record)

    def ticks(self):
        return [r for r in self.records if r.get("type") == "tick"]


class RamStore:
    """The esw.sink.Outbox store contract, in RAM: append / load / ack / acked.

    A real unit always has durable storage (flash on the K230), so the Level-H default is a store
    that exists rather than one that is absent -- otherwise every case would boot reporting
    `durable_evidence` degraded and the report would stop meaning anything. AP-10 swaps this for
    the file-backed store, which is the one that survives the simulated power loss."""

    def __init__(self):
        self.entries = []
        self.watermark = -1

    def append(self, entry):
        self.entries.append(entry)

    def load(self):
        return list(self.entries)

    def ack(self, seq):
        self.watermark = seq

    def acked(self):
        return self.watermark


class ScriptedCommands:
    """Verified IF-8/9/10 commands, already through esw.command.verify_command upstream.

    EdgeApp consumes only VERIFIED commands -- authentication is the command channel's job
    (harness/commands.py exercises forged/replayed frames against it, CMD-01..12). This backend
    is the post-verification tap, so a Level-H case can push a config or an override without
    re-litigating crypto that already has its own board."""

    def __init__(self, override=(), ota=(), config_push=()):
        self.override = override        # [(t0, t1, {"mode": ...}), ...]
        self.ota = ota                  # [(t0, t1), ...]
        self.config_push = config_push  # [(t, {"T_dwell": 3.0}), ...]
        self._fired = []

    def poll(self, now):
        ov = None
        for w in self.override:
            if w[0] <= now < w[1]:
                ov = w[2]
        ota = False
        for w in self.ota:
            if w[0] <= now < w[1]:
                ota = True
        push = None
        for w in self.config_push:      # one-shot: a push governs from the tick it lands
            if abs(now - w[0]) < 1e-9 and w[0] not in self._fired:
                self._fired.append(w[0])
                push = w[1]
        return ov, ota, None, push


class Selftest:
    """The critical self-test (compute / memory / link / sign checks). Failing it for longer than
    the monitor's tolerance triggers the independent force-safe (IF-5) -- the third dead-man's
    switch layer, which blanks the sign WITHOUT routing through a possibly-wedged state machine."""

    def __init__(self, fail=()):
        self.fail = fail
        self.t = 0.0

    def set(self, t):
        self.t = t

    def __call__(self):
        for w in self.fail:
            if w[0] <= self.t < w[1]:
                return False
        return True
