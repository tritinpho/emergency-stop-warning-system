#!/usr/bin/env python3
"""Survey-to-calibration helper + the scale sanity check that the host-loop finding made mandatory.

A calib.json is load-bearing (doc 02 §4): the ROI gate and the footprint model work in METRES,
and host_yolo_loop's first discovery was that a wrong-scale homography fails SILENTLY -- real
detector noise at imgsz-320 reads as several km/h of smoothed "motion" on a truly static object
under an over-scaled H, permanently resetting the dwell while nothing looks broken. So this tool
does two things, and refuses to hand you a calibration without the second:

  1. BUILD -- four image points of a rectangle whose real size you know (lane-width x a measured
     length of marking, a parking bay, a carpet on the bench) -> image->ground homography via
     cv2.getPerspectiveTransform; ROI clicked/given in image space and projected to a CCW ground
     polygon (the exact validation esw.perception applies at boot).

  2. CHECK -- run the real detector over sample frames and compare each vehicle detection's
     MEASURED ground width (its bbox base corners through H) against the pipeline's own class
     priors (esw.perception._DEFAULT_FOOTPRINT: car 2.0 m, truck 2.5, bus 2.6, motorcycle 0.8).
     Vehicles only: their widths are rigid; person boxes are pose-inflated, and footprint LENGTH
     is *assigned* from the prior, so width is the one honest scale observable. A pooled median
     ratio outside [0.75, 1.33] warns; outside [0.5, 2.0] FAILS (exit 1) with the correction
     factor to apply to your surveyed rectangle.

    # build from a frame + a known 3.75 x 10 m rectangle of lane marking, then check it:
    python software/tools/make_calib.py --frame clip.mp4 \\
        --rect 412,655 866,641 700,404 486,412 --rect-size 3.75x10 \\
        --roi 300,700 900,700 760,380 420,380 --out calib.json

    # click the points instead of typing them (a window opens; for humans, not CI):
    python software/tools/make_calib.py --frame clip.mp4 --click --rect-size 3.75x10 --out calib.json

    # re-check an existing calibration against new footage:
    python software/tools/make_calib.py --check-only --calib calib.json --footage clip.mp4

Point order for --rect: near-left, near-right, far-right, far-left (as seen on screen). The
ground frame puts near-left at (0,0), x across the road (the rectangle's WIDTH), y down-range.

Host-only (NOT shipped). Needs:  pip install ultralytics
"""

import argparse
import datetime
import hashlib
import json
import os
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

try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit("make_calib needs OpenCV + numpy (they ship with ultralytics):\n"
             "    pip install ultralytics")

from esw.geometry import apply_homography, is_convex_ccw
from esw.k230_adapter import detections_from_yolo
from esw.perception import _DEFAULT_FOOTPRINT, Perception

# Rigid-width classes only -- see the module docstring for why persons are excluded.
_CHECK_CLASSES = ("car", "truck", "bus", "motorcycle")
WARN_BAND = (0.75, 1.33)
FAIL_BAND = (0.5, 2.0)
MIN_SAMPLES = 3


# ------------------------------------------------------------------- frames

def first_frame(path):
    img = cv2.imread(path)
    if img is not None:
        return img
    cap = cv2.VideoCapture(path)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        sys.exit("cannot read an image or a video frame from: %s" % path)
    return frame


def sample_frames(path, n):
    """Up to n frames, evenly spaced. An image yields itself n times -- the detector is
    deterministic on identical input, so the extra samples add nothing, but a --click session
    on a still is a legitimate bench setup and the pooled-median maths stays uniform."""
    img = cv2.imread(path)
    if img is not None:
        return [img] * n
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        sys.exit("cannot open footage: %s" % path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    out = []
    if total <= 0:
        while len(out) < n:
            ok, f = cap.read()
            if not ok:
                break
            out.append(f)
    else:
        for i in range(n):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(i * max(1, total // n)))
            ok, f = cap.read()
            if ok:
                out.append(f)
    cap.release()
    if not out:
        sys.exit("no frames decodable from: %s" % path)
    return out


# ------------------------------------------------------------------- build

def build_h(rect_img_pts, rect_w, rect_l):
    """Image->ground homography from 4 image points of a known rect (near-left, near-right,
    far-right, far-left) mapped to (0,0), (W,0), (W,L), (0,L): x across the road, y down-range."""
    src = np.float32(rect_img_pts)
    dst = np.float32([(0.0, 0.0), (rect_w, 0.0), (rect_w, rect_l), (0.0, rect_l)])
    m = cv2.getPerspectiveTransform(src, dst)
    h = [[float(m[r][c]) for c in range(3)] for r in range(3)]
    for (x, y), (gx, gy) in zip(rect_img_pts, dst.tolist()):
        px, py = apply_homography(h, x, y)
        if abs(px - gx) > 1e-3 or abs(py - gy) > 1e-3:
            sys.exit("homography round-trip failed (%.4f, %.4f) != (%.1f, %.1f) -- "
                     "degenerate rectangle points?" % (px, py, gx, gy))
    return h


def project_roi(h, roi_img_pts):
    """ROI clicked in IMAGE space -> ground polygon, wound CCW -- validated with the exact
    predicate esw.perception applies at boot, so a calib this tool emits cannot be refused."""
    ground = [apply_homography(h, x, y) for (x, y) in roi_img_pts]
    if not is_convex_ccw(ground):
        ground = list(reversed(ground))
    if not is_convex_ccw(ground):
        sys.exit("projected ROI is not a convex polygon -- re-click the corners in order "
                 "around the region (no zig-zag); esw.perception would refuse it at boot")
    return [[float(x), float(y)] for (x, y) in ground]


def calib_version(h):
    tag = hashlib.sha256(json.dumps(h).encode("utf-8")).hexdigest()[:8]
    return "make_calib-%s-%s" % (datetime.date.today().isoformat(), tag)


# ------------------------------------------------------------------- check

def measure_widths(frames, h, weights, imgsz, conf):
    """{cls: [measured ground widths]} over all vehicle detections in `frames`. The width is
    the distance between the bbox base corners projected through H -- the same contact line
    esw.geometry.footprint_projected uses, so the check measures what the pipeline will see."""
    from host_yolo_loop import YoloDetector      # sibling module (same tools/ directory)
    det = YoloDetector(weights, imgsz=imgsz, conf=conf)
    widths = {}
    for frame in frames:
        det.set_frame(frame)
        raw = det.read()
        if raw is None:
            continue
        for d in detections_from_yolo(raw[0], raw[1], raw[2], det.labels):
            if d["cls"] not in _CHECK_CLASSES:
                continue
            x1, y1, x2, y2 = d["bbox"]
            blx, bly = apply_homography(h, x1, y2)
            brx, bry = apply_homography(h, x2, y2)
            w = ((brx - blx) ** 2 + (bry - bly) ** 2) ** 0.5
            widths.setdefault(d["cls"], []).append(w)
    return widths


def _median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def scale_check(frames, h, weights="yolov8n.pt", imgsz=320, conf=0.25):
    """Returns (verdict, pooled_ratio, table). verdict: 'PASS' | 'WARN' | 'FAIL' | 'NO-DATA'.
    pooled_ratio = median over every vehicle detection of measured_width / class prior width;
    1.0 means the surveyed rectangle and the detector agree about how big the world is."""
    widths = measure_widths(frames, h, weights, imgsz, conf)
    ratios = []
    table = []
    for cls in _CHECK_CLASSES:
        ws = widths.get(cls, [])
        if not ws:
            continue
        prior = _DEFAULT_FOOTPRINT[cls][0]
        med = _median(ws)
        table.append((cls, len(ws), med, prior, med / prior))
        ratios.extend(w / prior for w in ws)
    if len(ratios) < MIN_SAMPLES:
        return "NO-DATA", None, table
    pooled = _median(ratios)
    if FAIL_BAND[0] <= pooled <= FAIL_BAND[1]:
        verdict = "PASS" if WARN_BAND[0] <= pooled <= WARN_BAND[1] else "WARN"
    else:
        verdict = "FAIL"
    return verdict, pooled, table


def report_check(verdict, pooled, table):
    print("")
    print("scale sanity check -- measured ground width vs the pipeline's class priors")
    print("-" * 74)
    for cls, n, med, prior, ratio in table:
        print("  %-11s n=%-3d median %.2f m   prior %.2f m   ratio %.2f"
              % (cls, n, med, prior, ratio))
    if verdict == "NO-DATA":
        print("  fewer than %d vehicle detections -- cannot judge the scale. Point the check"
              % MIN_SAMPLES)
        print("  at footage WITH vehicles before trusting this calibration.")
        return
    print("  pooled ratio %.2f -> %s" % (pooled, verdict))
    if verdict != "PASS":
        print("  the world this H describes is %.1fx %s than the detector believes."
              % (pooled if pooled >= 1 else 1 / pooled,
                 "larger" if pooled > 1 else "smaller"))
        print("  Re-measure the surveyed rectangle; a corrected size of roughly "
              "W/%.2f x L/%.2f would reconcile them." % (pooled, pooled))
        print("  An over-scaled H is the silent dwell-killer host_yolo_loop documented: "
              "pixel noise reads as km/h.")


# ------------------------------------------------------------------- click ui

def collect_points(frame, want, title):
    """Click points on a window; ENTER/SPACE accepts, u undoes, ESC aborts. For humans --
    the CLI point arguments are the scriptable path and the one CI exercises."""
    pts = []
    disp = frame.copy()

    def redraw():
        d = frame.copy()
        for i, (x, y) in enumerate(pts):
            cv2.circle(d, (int(x), int(y)), 4, (0, 0, 255), -1)
            cv2.putText(d, str(i + 1), (int(x) + 6, int(y) - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        return d

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            pts.append((float(x), float(y)))

    cv2.namedWindow(title)
    cv2.setMouseCallback(title, on_mouse)
    while True:
        cv2.imshow(title, redraw() if pts else disp)
        k = cv2.waitKey(30) & 0xFF
        if k in (13, 32) and len(pts) >= want:      # ENTER / SPACE
            break
        if k == ord("u") and pts:
            pts.pop()
        if k == 27:
            cv2.destroyWindow(title)
            sys.exit("aborted")
    cv2.destroyWindow(title)
    return pts


# ------------------------------------------------------------------- selftest

def selftest(weights):
    """Machinery test on the bundled ultralytics sample: build an H that declares the detected
    bus's base span to be exactly a bus width (2.6 m) -> the check must agree (~1.0); re-declare
    the same span to be 0.9 m (a mis-survey) -> the check must FAIL and say by how much. The
    real use anchors on an independent rectangle (lane markings); anchoring on the detection
    itself here is what makes the expected ratios exact."""
    import ultralytics
    sample = os.path.join(os.path.dirname(ultralytics.__file__), "assets", "bus.jpg")
    img = cv2.imread(sample)
    if img is None:
        sys.exit("selftest: cannot read %s" % sample)

    from host_yolo_loop import YoloDetector
    det = YoloDetector(weights, imgsz=320, conf=0.25)
    det.set_frame(img)
    raw = det.read()
    dets = detections_from_yolo(raw[0], raw[1], raw[2], det.labels)
    buses = [d for d in dets if d["cls"] in ("bus", "truck", "car")]
    if not buses:
        sys.exit("selftest: no vehicle detected in the sample image")
    big = max(buses, key=lambda d: (d["bbox"][2] - d["bbox"][0]) * (d["bbox"][3] - d["bbox"][1]))
    x1, y1, x2, y2 = big["bbox"]

    fails = []

    def check(name, ok, detail=""):
        print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                               (" -- " + str(detail)) if detail else ""))
        if not ok:
            fails.append(name)

    print("selftest assertions")
    print("-" * 74)

    # A synthetic survey rectangle on the vehicle's base line, declared to be one bus wide.
    rect_img = [(x1, y2), (x2, y2), (x2, y2 - 40), (x1, y2 - 40)]
    h_good = build_h(rect_img, 2.6, 3.0)
    gx, gy = apply_homography(h_good, x1, y2)
    check("H round-trip: near-left corner -> (0,0)", abs(gx) < 1e-3 and abs(gy) < 1e-3,
          "(%.4f, %.4f)" % (gx, gy))

    roi = project_roi(h_good, [(x1 - 60, y2 + 30), (x2 + 60, y2 + 30),
                               (x2 + 60, y1 - 30), (x1 - 60, y1 - 30)])
    check("projected ROI is convex CCW (the boot predicate)", is_convex_ccw(roi))
    calib = {"H": h_good, "roi": roi, "frame_wh": [img.shape[1], img.shape[0]],
             "footprint_mode": "projected", "version": calib_version(h_good)}
    try:
        Perception(calib)
        check("esw.perception accepts the emitted calibration", True)
    except (ValueError, KeyError) as e:
        check("esw.perception accepts the emitted calibration", False, e)
    tmp = os.path.join(tempfile.mkdtemp(prefix="esw-calib-selftest-"), "calib.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(calib, f, indent=2)
    check("calib.json written", os.path.exists(tmp), tmp)

    frames = [img] * 6
    verdict, pooled, table = scale_check(frames, h_good, weights)
    report_check(verdict, pooled, table)
    check("correct survey -> scale check PASS with ratio ~1",
          verdict == "PASS" and pooled is not None and 0.85 <= pooled <= 1.15,
          "verdict=%s pooled=%s" % (verdict, pooled))

    h_bad = build_h(rect_img, 0.9, 3.0)          # the same span mis-surveyed as 0.9 m
    verdict_b, pooled_b, table_b = scale_check(frames, h_bad, weights)
    report_check(verdict_b, pooled_b, table_b)
    check("mis-survey (2.6 m declared as 0.9 m) -> scale check FAIL",
          verdict_b == "FAIL" and pooled_b is not None and pooled_b < 0.5,
          "verdict=%s pooled=%s" % (verdict_b, pooled_b))

    print("-" * 74)
    if fails:
        print("SELF-TEST: %d FAILURE(S): %s" % (len(fails), fails))
        return 1
    print("SELF-TEST: PASS -- surveys become calibrations, and a wrong one is refused loudly.")
    return 0


# ------------------------------------------------------------------- cli

def _pt(s):
    x, y = s.split(",")
    return (float(x), float(y))


def _wxl(s):
    w, l = s.lower().split("x")
    return float(w), float(l)


def main():
    ap = argparse.ArgumentParser(
        description="Build a surveyed calib.json and sanity-check its scale with the detector.")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--frame", help="image or video: the frame the survey points refer to")
    ap.add_argument("--rect", nargs=4, type=_pt, metavar="X,Y",
                    help="4 image points of the known rectangle: near-left near-right "
                         "far-right far-left")
    ap.add_argument("--rect-size", type=_wxl, metavar="WxL",
                    help="the rectangle's real size in metres, e.g. 3.75x10")
    ap.add_argument("--roi", nargs="+", type=_pt, metavar="X,Y",
                    help="ROI corners in image pixels (>=3, in order around the region)")
    ap.add_argument("--click", action="store_true",
                    help="collect --rect (4 pts) and --roi points by clicking on the frame")
    ap.add_argument("--out", default="calib.json", help="output path (default calib.json)")
    ap.add_argument("--check-only", action="store_true",
                    help="skip building: check an existing --calib against --footage")
    ap.add_argument("--calib", help="existing calib.json (with --check-only)")
    ap.add_argument("--footage", help="footage for the scale check (default: --frame)")
    ap.add_argument("--no-check", action="store_true",
                    help="build without the detector check (NOT recommended -- a wrong-scale "
                         "H fails silently; see host_yolo_loop)")
    ap.add_argument("--samples", type=int, default=12, help="frames to sample for the check")
    ap.add_argument("--weights", default="yolov8n.pt")
    ap.add_argument("--imgsz", type=int, default=320)
    ap.add_argument("--conf", type=float, default=0.25)
    args = ap.parse_args()

    if args.selftest:
        return selftest(args.weights)

    if args.check_only:
        if not args.calib or not args.footage:
            ap.error("--check-only needs --calib and --footage")
        with open(args.calib, "r", encoding="utf-8") as f:
            calib = json.load(f)
        frames = sample_frames(args.footage, args.samples)
        verdict, pooled, table = scale_check(frames, calib["H"], args.weights,
                                             args.imgsz, args.conf)
        report_check(verdict, pooled, table)
        return 0 if verdict == "PASS" else (2 if verdict == "NO-DATA" else 1)

    if not args.frame:
        ap.error("--frame is required to build (or use --selftest / --check-only)")
    if not args.rect_size:
        ap.error("--rect-size WxL is required: the real size of the surveyed rectangle")
    frame = first_frame(args.frame)

    rect = args.rect
    roi = args.roi
    if args.click:
        rect = collect_points(frame, 4, "click 4 rect corners: near-L near-R far-R far-L, "
                                        "then ENTER")
        roi = collect_points(frame, 3, "click ROI corners in order, then ENTER")
    if not rect or len(rect) != 4:
        ap.error("need exactly 4 --rect points (or --click)")
    if not roi or len(roi) < 3:
        ap.error("need >=3 --roi points (or --click)")

    w, l = args.rect_size
    h = build_h(rect, w, l)
    ground_roi = project_roi(h, roi)
    calib = {"H": h, "roi": ground_roi,
             "frame_wh": [frame.shape[1], frame.shape[0]],
             "footprint_mode": "projected",
             "version": calib_version(h)}
    Perception(calib)                    # the boot-time validation, run at build time
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(calib, f, indent=2)
    print("calibration written: %s  (version %s)" % (args.out, calib["version"]))

    if args.no_check:
        print("WARNING: scale check SKIPPED (--no-check). A wrong-scale H fails silently -- "
              "run --check-only before trusting this file.")
        return 0
    footage = args.footage or args.frame
    frames = sample_frames(footage, args.samples)
    verdict, pooled, table = scale_check(frames, h, args.weights, args.imgsz, args.conf)
    report_check(verdict, pooled, table)
    if verdict == "NO-DATA":
        print("calibration written but UNVERIFIED -- re-run --check-only against footage "
              "with vehicles.")
        return 2
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
