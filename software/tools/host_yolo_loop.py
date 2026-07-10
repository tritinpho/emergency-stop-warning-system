#!/usr/bin/env python3
"""Host detector-in-the-loop: a REAL pretrained YOLO driving the REAL EdgeApp (tier "host").

Until this tool, every guarantee in the perception stack was proven against our own
model of a detector (harness/frames.py) -- the pipeline had never consumed a real YOLO
frame. This runs ultralytics YOLO (default yolov8n.pt, the same family as the K230's
/sdcard/kmodel/yolov8n_320.kmodel) over real footage -- a video file or a still image --
and feeds every frame's raw detections through the exact device loop:

    adapter -> perception -> state machine -> actuator -> IF-4 frames -> dead-man's switch

Nothing in the chain is mocked: the EdgeApp is the same object the K230 constructs, and
the sign at the far end is harness.sign.Sign verifying real HMAC'd frames. The run writes
a device-format capture session (evidence.log + capture.jsonl + ground_truth.json) that
tools/score_capture.py scores like any SD-card session -- stamped tier "host", which the
scorer treats as a named blocker: a host run validates the PIPELINE (adapter conventions,
tracker association under real detector noise, dwell, congestion, IF-4 cadence), never
the UNIT (the K230 runs an INT8 kmodel behind different optics). The weights that ran are
pinned by SHA-256 into ground_truth.json, so provenance never blocks -- only the tier does.

    # self-test on the bundled ultralytics sample (a bus + pedestrians, jittered):
    python software/tools/host_yolo_loop.py --selftest

    # real footage (calib.json schema = the device's /sdcard/esw/calib.json):
    python software/tools/host_yolo_loop.py --video shoulder.mp4 --calib calib.json \\
        --session captures/host-2026-07-10-a --hazard 12.5:96 --score

    # A/B the vendored ACLAB LightFilter (ADR-0016 backlog #4b) on night footage:
    #   run the same clip twice, once with --light-filter, and score both sessions.

Host-only (NOT shipped to the K230). Needs:  pip install ultralytics
"""

import argparse
import datetime
import hashlib
import json
import os
import random
import sys
import tempfile

# Put software/ on the import path (see score_capture.py; this file is two levels down).
_here = __file__
_c1 = max(_here.rfind("/"), _here.rfind("\\"))
_toolsdir = _here[:_c1] if _c1 >= 0 else ""
_c2 = max(_toolsdir.rfind("/"), _toolsdir.rfind("\\"))
if _c2 >= 0:
    _swdir = _toolsdir[:_c2]
elif _toolsdir == "":
    _swdir = ".."
else:
    _swdir = "."
sys.path.insert(0, _swdir if _swdir != "" else ".")
_REPO_ROOT = os.path.dirname(os.path.abspath(_swdir if _swdir else "."))

try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit("host_yolo_loop needs OpenCV + numpy (they ship with ultralytics):\n"
             "    pip install ultralytics")

from esw import crypto
from esw.app import EdgeApp
from esw.k230_adapter import detections_from_yolo
from esw.params import default_config
from harness.devices import FakeClock, FileCapture, SignLink
from harness.sign import Sign
from harness.store import FileStore

TICK_DT = 0.1            # 10 Hz, the device rate (ADR-0015 D2)
SITE = "host-01"
# A host bench key, like harness/rig.py's -- these sessions exercise the real HMAC path but
# never talk to a real sign controller, so the master is deliberately public and worthless.
KEY = crypto.derive_key(b"esw-host-bench-secret-0123456789abcd", "IF4", SITE)


# ------------------------------------------------------------------- detector backend

class YoloDetector:
    """EdgeApp detector backend (IF-1): ultralytics YOLO on host frames.

    read() returns (boxes[xywh top-left], class_ids, confidences) -- the exact shape
    aidemo.yolov8_det_postprocess emits on the K230, so esw.k230_adapter consumes both
    without knowing which produced them. `conf` defaults LOW (0.1): the adapter passes
    everything through and perception's own two-stage score gate (score_min/score_low)
    does the real filtering, exactly as on the device."""

    def __init__(self, weights, imgsz=320, conf=0.1, preprocess=None):
        try:
            from ultralytics import YOLO
        except ImportError:
            sys.exit("ultralytics is not installed:  pip install ultralytics")
        self.model = YOLO(weights)
        names = self.model.names
        self.labels = [names[i] for i in range(len(names))]
        self.weights_path = getattr(self.model, "ckpt_path", None) or weights
        self.imgsz = imgsz
        self.conf = conf
        self.preprocess = preprocess
        self.frame = None
        self.frames = 0
        self.misses = 0

    def sha256(self):
        """Pin the weights that RAN. A model nobody can identify cannot carry a number
        (harness/evidence.py); host sessions must never block on provenance, only on tier."""
        if not os.path.exists(self.weights_path):
            return None
        h = hashlib.sha256()
        with open(self.weights_path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def set_frame(self, bgr):
        self.frame = bgr

    def read(self):
        if self.frame is None:
            self.misses += 1
            return None                      # no fresh frame == what a dead camera looks like
        self.frames += 1
        img = self.frame if self.preprocess is None else self.preprocess(self.frame)
        r = self.model.predict(img, imgsz=self.imgsz, conf=self.conf, verbose=False)[0]
        boxes = []
        ids = []
        confs = []
        for (x1, y1, x2, y2), c, s in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(),
                                          r.boxes.conf.tolist()):
            boxes.append((x1, y1, x2 - x1, y2 - y1))     # xyxy -> top-left xywh (adapter contract)
            ids.append(int(c))
            confs.append(float(s))
        return boxes, ids, confs


def make_light_preprocess():
    """The vendored ACLAB LightFilter as a detector preprocess (ADR-0016 backlog #4b).

    Mirrors the ESW_LIGHT_FILTER seam in firmware/k230-detector/esw-app/main.py: the filter
    wants planar CHW (the K230's rgb888p), the host has HWC BGR, so this adapter converts in
    and out -- the vendored code itself is untouched (the baseline rule). Enabling it on the
    device is an A/B question; THIS is the instrument that answers it on host footage."""
    nf = os.path.join(_REPO_ROOT, "firmware", "k230-detector", "noise-filters")
    if not os.path.isdir(nf):
        sys.exit("--light-filter: %s not found (run from the repo)" % nf)
    sys.path.insert(0, nf)
    from light_filter import LightFilter
    lf = LightFilter({})

    def preprocess(bgr):
        chw = np.ascontiguousarray(bgr[:, :, ::-1].transpose(2, 0, 1))   # HWC BGR -> CHW RGB
        r = lf.process(chw)
        if not r.success:
            return bgr
        out = np.asarray(r.frame).astype(np.uint8)       # the filter's mask math promotes dtype
        return np.ascontiguousarray(out.transpose(1, 2, 0)[:, :, ::-1])  # CHW RGB -> HWC BGR
    return preprocess


# ------------------------------------------------------------------- frame sources

class VideoSource:
    """Frames from a video file, addressed by tick time. Decodes forward only; past the last
    frame it returns None -- to the EdgeApp that is a dead camera, and the health monitor's
    NEITHER -> blank response is the honest end of a finite clip."""

    def __init__(self, path):
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            sys.exit("cannot open video: %s" % path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.n_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.idx = -1
        self.frame = None
        self.ended = False

    def duration(self):
        return (self.n_frames / self.fps) if self.n_frames else None

    def frame_wh(self):
        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        return [w, h] if w and h else None

    def frame_at(self, t):
        want = int(t * self.fps)
        while not self.ended and self.idx < want:
            ok, f = self.cap.read()
            if not ok:
                self.ended = True
                break
            self.idx += 1
            self.frame = f
        if self.ended and self.idx < want:
            return None
        return self.frame


class StillJitterSource:
    """One still image with seeded per-tick translation jitter: a real detector's boxes on a
    static scene, made to move the few pixels a mast camera moves in wind. This is the
    doc 07 3.1 jitter nuisance, but produced by REAL detector noise instead of our model of
    it -- the windowed+EMA speed estimator (PC-06) must hold stationarity under it."""

    def __init__(self, img, amp_px=3, seed=42):
        self.img = img
        self.amp = amp_px
        self.rng = random.Random(seed)
        self.h, self.w = img.shape[:2]

    def frame_wh(self):
        return [self.w, self.h]

    def frame_at(self, t):
        if self.amp <= 0:
            return self.img
        dx = self.rng.randint(-self.amp, self.amp)
        dy = self.rng.randint(-self.amp, self.amp)
        m = np.float32([[1, 0, dx], [0, 1, dy]])
        return cv2.warpAffine(self.img, m, (self.w, self.h), borderMode=cv2.BORDER_REPLICATE)


# ------------------------------------------------------------------- the loop

def announce(boot):
    print("")
    print("=" * 72)
    print("ESW host detector-in-the-loop -- boot capability report")
    print("  classes seen by the loaded model : %s" % (boot["classes"],))
    print("  sees_person / per_class_footprint: %s / %s"
          % (boot["sees_person"], boot["per_class_footprint"]))
    print("  sign_readback / absolute_time    : %s / %s"
          % (boot["sign_readback"], boot["absolute_time"]))
    print("  durable_evidence / density (R14) : %s / %s"
          % (boot["durable_evidence"], boot["density_congestion"]))
    if boot["degraded"]:
        print("  *** DEGRADED: %s" % (boot["degraded"],))
    print("=" * 72)


def run_session(detector, source, calib, session_dir, duration, hazards, notes,
                progress_every_s=5.0):
    """Run the real EdgeApp over the source and write a device-format session. Returns a
    summary dict; the session on disk is the artifact that outlives it."""
    os.makedirs(session_dir, exist_ok=True)
    ev_path = os.path.join(session_dir, "evidence.log")
    if os.path.exists(ev_path):
        sys.exit("refusing to overwrite an existing session: %s\n"
                 "sessions are evidence -- pick a fresh directory" % ev_path)

    sha = detector.sha256()
    model_name = os.path.basename(detector.weights_path)
    versions = {"fw_ver": "host-loop-0.1",
                "model_ver": "%s@%s" % (model_name, sha[:12] if sha else "unpinned"),
                "calib_ver": calib.get("version", "unversioned")}

    clock = FakeClock(absolute=True, gnss=True)   # host wall clock stands in for GNSS
    sign = Sign(default_config(), KEY)
    link = SignLink(sign)
    backends = {"detector": detector, "radio": link, "clock": clock,
                "sign_status": link.status,
                "store": FileStore(os.path.join(session_dir, "evidence")),
                "capture": FileCapture(os.path.join(session_dir, "capture.jsonl"))}

    app = EdgeApp(KEY, SITE, versions, calib, backends)
    boot = app.start()
    announce(boot)

    steps = int(duration / TICK_DT) + 1
    first_on = None
    every = max(1, int(progress_every_s / TICK_DT))
    for i in range(steps):
        t = round(i * TICK_DT, 3)
        clock.set(t)
        detector.set_frame(source.frame_at(t))
        d = app.step(t)
        link.tick(t)
        if link.on and first_on is None:
            first_on = t
        if i % every == 0:
            print("  [t=%5.1fs] state=%-22s sign=%-3s tx=%-4d frames=%d"
                  % (t, d.get("state"), "ON" if link.on else "off", link.sent,
                     detector.frames))

    gt_path = os.path.join(session_dir, "ground_truth.json")
    if not os.path.exists(gt_path):
        gt = {"tier": "host",
              "model_sha256": sha,
              "t_offset": 0.0,
              "hazards": hazards,
              "notes": notes}
        with open(gt_path, "w", encoding="utf-8") as f:
            json.dump(gt, f, indent=2)
        if not hazards:
            print("\n  NOTE: no hazards annotated -- edit %s before scoring;" % gt_path)
            print("        an unannotated capture is not evidence (harness/evidence.py).")

    classes_seen = set()
    with open(os.path.join(session_dir, "capture.jsonl"), "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            for det in rec.get("dets", []):
                classes_seen.add(det.get("cls"))

    return {"boot": boot, "first_on": first_on, "on_at_end": link.on, "sent": link.sent,
            "ticks": steps, "frames": detector.frames, "misses": detector.misses,
            "classes_seen": classes_seen, "session_dir": session_dir, "sha": sha}


def score(session_dir):
    from harness.evidence import Session, report
    text, n_blockers = report([Session(session_dir)])
    print("")
    print(text)
    return n_blockers


# ------------------------------------------------------------------- self-test

def _selftest_calib(detector, img):
    """An affine bench calibration with the ROI drawn around the sample image's biggest
    vehicle -- the probe uses the same adapter the loop does, so the self-test never
    hand-codes a box the detector didn't emit.

    The metres-per-pixel scale is derived from the detected vehicle itself (a bus is ~12 m),
    the way a real survey anchors H to known dimensions. This is load-bearing, and the first
    thing this tool DISCOVERED: real YOLO boxes at imgsz=320 upscaled to an ~800 px frame
    carry ~2.5 px of quantization noise, and under the PC-cases' 0.05 m/px convention (which
    would make THIS bus 36 m long) that noise reads as up to ~4.7 km/h SMOOTHED on a truly
    static object -- permanently resetting the 3 km/h dwell. Same pixels, plausible scale
    (~0.015 m/px): ~1.4 km/h, comfortable margin. The speed gate's jitter robustness is a
    function of calibration scale, so commissioning must sanity-check H against known object
    sizes -- a wrong-scale H fails exactly like this, silently, with nothing visibly broken."""
    detector.set_frame(img)
    raw = detector.read()
    dets = detections_from_yolo(raw[0], raw[1], raw[2], detector.labels)
    vehicles = [d for d in dets if d["cls"] in ("car", "truck", "bus", "motorcycle")]
    if not vehicles:
        sys.exit("selftest: no vehicle detected in the sample image -- "
                 "detector or weights are broken")
    big = max(vehicles, key=lambda d: (d["bbox"][2] - d["bbox"][0]) * (d["bbox"][3] - d["bbox"][1]))
    bx1, by1, bx2, by2 = big["bbox"]
    s = 12.0 / max(bx2 - bx1, by2 - by1)          # anchor the scale: that vehicle is ~a bus
    x1, y1, x2, y2 = [v * s for v in big["bbox"]]
    m = 2.0                                       # metres of margin around the footprint
    h, w = img.shape[:2]
    return {"H": [[s, 0.0, 0.0], [0.0, s, 0.0], [0.0, 0.0, 1.0]],
            "roi": [(x1 - m, y1 - m), (x2 + m, y1 - m), (x2 + m, y2 + m), (x1 - m, y2 + m)],
            "score_min": 0.4, "score_low": 0.1, "assoc_gate_m": 3.0,
            "track_max_age_s": 2.0, "speed_window_s": 0.5, "speed_alpha": 0.3,
            "frame_wh": [w, h],
            "version": "selftest-affine-%.4fmpx" % s}


def selftest(weights, keep=False):
    """End-to-end proof on the bundled ultralytics sample (a stopped bus + pedestrians on its
    near side): real YOLO -> adapter -> perception -> SM -> HMAC'd IF-4 -> lamp, written out as
    a scoreable host-tier session. Asserts the outcomes, not just survival."""
    import ultralytics
    sample = os.path.join(os.path.dirname(ultralytics.__file__), "assets", "bus.jpg")
    if not os.path.exists(sample):
        sys.exit("selftest: ultralytics sample image not found: %s" % sample)
    img = cv2.imread(sample)

    detector = YoloDetector(weights, imgsz=320, conf=0.1)
    calib = _selftest_calib(detector, img)
    source = StillJitterSource(img, amp_px=3, seed=42)
    duration = 12.0
    session_dir = tempfile.mkdtemp(prefix="esw-host-selftest-")

    summary = run_session(
        detector, source, calib, session_dir, duration,
        hazards=[[0.0, duration]],
        notes="selftest: ultralytics bus.jpg (stopped bus + pedestrians), jitter +/-3px seed 42")

    fails = []

    def check(name, ok, detail=""):
        print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                               (" -- " + str(detail)) if detail else ""))
        if not ok:
            fails.append(name)

    print("\nself-test assertions")
    print("-" * 72)
    boot = summary["boot"]
    check("boot: no degraded safety capability", boot["degraded"] == [], boot["degraded"])
    seen = summary["classes_seen"]
    check("real YOLO frames consumed: vehicle class seen",
          bool(seen & {"car", "truck", "bus", "motorcycle"}), sorted(seen))
    check("real YOLO frames consumed: person seen (SC-12 class survives the adapter)",
          "person" in seen, sorted(seen))
    first_on = summary["first_on"]
    check("sign lights on the stopped hazard",
          first_on is not None and first_on <= 6.5, "first_on=%s" % first_on)
    check("sign still on at end (hazard persists)", summary["on_at_end"])
    if first_on is not None:
        expected = (duration - first_on) / 0.5      # T_assert_refresh cadence, not tick rate
        check("IF-4 refresh throttled to T_assert_refresh (the AP-11 duty lesson)",
              expected - 3 <= summary["sent"] <= expected + 6,
              "sent=%d expected~%.0f (per-tick bug would be ~%d)"
              % (summary["sent"], expected, int((duration - first_on) / TICK_DT)))
    for name in ("evidence.log", "capture.jsonl", "ground_truth.json"):
        check("session file written: %s" % name,
              os.path.exists(os.path.join(session_dir, name)))

    from harness import metrics
    from harness.evidence import Session, blockers, report
    sess = Session(session_dir)
    blk = blockers(sess)
    check("scorer blocks on the host tier ALONE (pinned, capability-complete, corroborated)",
          len(blk) == 1 and "tier 'host'" in blk[0], blk)
    sc = metrics.score_scenario(sess.oracle(), sess.warn_intervals())
    check("scored against ground truth: TP=1 FN=0 FP=0",
          (sc["tp"], sc["fn"], sc["fp"]) == (1, 0, 0), sc)
    text, n_blockers = report([sess])
    check("report is honest: NOT ACCEPTANCE-GRADE", "NOT ACCEPTANCE-GRADE" in text)

    print("-" * 72)
    if keep:
        print("session kept at: %s" % session_dir)
    else:
        import shutil
        shutil.rmtree(session_dir, ignore_errors=True)
    if fails:
        print("SELF-TEST: %d FAILURE(S): %s" % (len(fails), fails))
        return 1
    print("SELF-TEST: PASS -- the pipeline has now consumed real YOLO frames (host tier).")
    return 0


# ------------------------------------------------------------------- cli

def _parse_hazard(spec):
    t0, t1 = spec.split(":")
    return [float(t0), float(t1)]


def main():
    ap = argparse.ArgumentParser(
        description="Run a real pretrained YOLO through the real EdgeApp loop (host tier).")
    ap.add_argument("--selftest", action="store_true",
                    help="end-to-end self-test on the bundled ultralytics sample image")
    ap.add_argument("--keep", action="store_true", help="keep the self-test session directory")
    ap.add_argument("--video", help="video file to run")
    ap.add_argument("--image", help="still image to run (with --jitter-px, like the self-test)")
    ap.add_argument("--calib", help="calibration JSON (the device /sdcard/esw/calib.json schema: "
                                    "H, roi, optional frame_wh/version)")
    ap.add_argument("--session", help="session directory to write (default captures/host-<ts>)")
    ap.add_argument("--duration", type=float,
                    help="seconds to run (default: video length, or 30 for --image)")
    ap.add_argument("--weights", default="yolov8n.pt",
                    help="ultralytics weights (default yolov8n.pt; downloads to CWD on first use)")
    ap.add_argument("--imgsz", type=int, default=320,
                    help="inference size (default 320 = the K230's MODEL_INPUT_SIZE)")
    ap.add_argument("--conf", type=float, default=0.1,
                    help="detector confidence floor (default 0.1: perception's two-stage "
                         "score gate does the real filtering)")
    ap.add_argument("--jitter-px", type=int, default=3, help="still-image jitter amplitude")
    ap.add_argument("--light-filter", action="store_true",
                    help="A/B: run ACLAB's LightFilter as detector preprocess (backlog #4b)")
    ap.add_argument("--hazard", action="append", default=[], metavar="T0:T1",
                    help="annotate a ground-truth hazard interval (repeatable), e.g. 12.5:96")
    ap.add_argument("--score", action="store_true", help="score the session after the run")
    args = ap.parse_args()

    if args.selftest:
        return selftest(args.weights, keep=args.keep)

    if not args.video and not args.image:
        ap.error("one of --selftest, --video or --image is required")
    if not args.calib:
        ap.error("--calib is required with --video/--image (the device calib.json schema); "
                 "there is deliberately NO default -- see esw-app/main.py load_calibration()")

    with open(args.calib, "r", encoding="utf-8") as f:
        calib = json.load(f)
    if "H" not in calib or "roi" not in calib:
        sys.exit("calib.json needs H (3x3 image->ground homography) and roi (CCW ground polygon)")

    preprocess = make_light_preprocess() if args.light_filter else None
    detector = YoloDetector(args.weights, imgsz=args.imgsz, conf=args.conf,
                            preprocess=preprocess)

    if args.video:
        source = VideoSource(args.video)
        duration = args.duration or source.duration()
        if duration is None:
            sys.exit("cannot determine video length; pass --duration")
    else:
        img = cv2.imread(args.image)
        if img is None:
            sys.exit("cannot read image: %s" % args.image)
        source = StillJitterSource(img, amp_px=args.jitter_px)
        duration = args.duration or 30.0

    if "frame_wh" not in calib:
        wh = source.frame_wh()
        if wh:
            calib["frame_wh"] = wh          # R14 density needs it; the source knows it

    session_dir = args.session
    if not session_dir:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        session_dir = os.path.join("captures", "host-" + stamp)

    hazards = [_parse_hazard(h) for h in args.hazard]
    notes = "host run: %s | weights %s | imgsz %d | light_filter %s" % (
        args.video or args.image, args.weights, args.imgsz, args.light_filter)
    summary = run_session(detector, source, calib, session_dir, duration, hazards, notes)

    print("")
    print("session written: %s" % summary["session_dir"])
    print("  ticks=%d frames=%d misses=%d classes=%s first_on=%s tx=%d"
          % (summary["ticks"], summary["frames"], summary["misses"],
             sorted(summary["classes_seen"]), summary["first_on"], summary["sent"]))
    print("  score it:  python software/tools/score_capture.py %s" % summary["session_dir"])

    if args.score:
        score(summary["session_dir"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
