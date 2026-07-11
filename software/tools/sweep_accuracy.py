#!/usr/bin/env python3
"""Accuracy sweep: one clip, a grid of detector settings, scored side by side (host tier).

The no-retrain accuracy levers -- input resolution (imgsz), confidence floor, the adapter's
small-box floor (min_wh_px), and ROI-crop inference -- are only worth anything if you can MEASURE
what each one buys. This runs the SAME footage through the SAME real EdgeApp (via host_yolo_loop,
so there is no second code path) once per (imgsz x conf [x min_wh x crop]) cell, scores every cell
against the same annotated hazards, and prints a table so you can see the recall / latency / cost
trade before spending any of it on the K230 -- where a bigger imgsz costs KPU latency (the ADR-0015
D3 timing question), so you want to know the recall it buys FIRST.

Every cell is a real host-tier session on disk. None is acceptance-grade -- host tier is a named
blocker (harness/evidence.py), because the K230 runs an INT8 kmodel behind different optics -- but
the RELATIVE comparison across cells is exactly what picks a setting. Detector = ultralytics YOLO
(the kmodel simulator is minutes-per-frame, useless for a sweep; use host_yolo_loop --kmodel for a
single-frame parity spot-check instead).

    # sweep resolution x confidence on a shoulder clip, plus the ROI-crop A/B:
    python software/tools/sweep_accuracy.py --video shoulder.mp4 --calib calib.json \\
        --hazard 12.5:96 --imgsz 320,416,512,640 --conf 0.1,0.25 --roi-crop

    # also sweep the small-box floor:
    python software/tools/sweep_accuracy.py --video night.mp4 --calib calib.json \\
        --hazard 8:40 --imgsz 320,512 --conf 0.1 --min-wh 10,25

    python software/tools/sweep_accuracy.py --selftest      # tiny grid on the bundled bus.jpg

Host-only. Needs:  pip install ultralytics
"""

import argparse
import json
import os
import sys
import tempfile

# Put software/ on the import path (mirror host_yolo_loop.py; this file is two levels down).
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
sys.path.insert(0, _toolsdir if _toolsdir != "" else ".")   # so `import host_yolo_loop` resolves

import host_yolo_loop as hyl                                 # noqa: E402  (after path setup)
from harness import metrics                                 # noqa: E402
from harness.evidence import Session                        # noqa: E402


# ------------------------------------------------------------------- one cell

def _det_hit_rate(session_dir):
    """Fraction of ticks on which the detector produced >=1 kept detection. A binary hazard
    (caught / missed) hides how ROBUSTLY a setting sees the object; this is the margin signal --
    more detected frames = more slack against dropout before the dwell resets."""
    hits = 0
    total = 0
    path = os.path.join(session_dir, "capture.jsonl")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") != "tick":
                continue
            total += 1
            if rec.get("dets"):
                hits += 1
    return (hits / total) if total else 0.0


def run_cell(weights, make_source, calib, out_dir, duration, hazards,
             imgsz, conf, min_wh, crop, roi_pad):
    """Run one grid cell (fresh detector + rewound source) and score it. Returns a result row."""
    base = hyl.YoloDetector(weights, imgsz=imgsz, conf=conf)
    cell_calib = dict(calib)
    if min_wh is not None:
        cell_calib["min_wh_px"] = min_wh

    source = make_source()
    detector = base
    crop_applied = False
    if crop:
        fwh = cell_calib.get("frame_wh") or source.frame_wh()
        cb = hyl.roi_crop_box(cell_calib, fwh, roi_pad) if fwh else None
        if cb is not None:
            detector = hyl.RoiCropDetector(base, cb)
            crop_applied = True

    label = "imgsz%d_conf%.2f_mw%s_crop%d" % (imgsz, conf,
                                              min_wh if min_wh is not None else "def",
                                              1 if crop_applied else 0)
    session_dir = os.path.join(out_dir, label)
    summary = hyl.run_session(detector, source, cell_calib, session_dir, duration,
                              hazards=hazards, notes="sweep " + label, quiet=True)

    sess = Session(session_dir)
    sc = metrics.score_scenario(sess.oracle(), sess.warn_intervals())
    return {"imgsz": imgsz, "conf": conf, "min_wh": min_wh, "crop": crop_applied,
            "tp": sc["tp"], "fn": sc["fn"], "fp": sc["fp"],
            "first_on": summary["first_on"], "frames": summary["frames"],
            "det_hit": _det_hit_rate(session_dir), "infer_ms": detector.mean_infer_ms(),
            "session_dir": session_dir}


# ------------------------------------------------------------------- reporting

def _rank_key(r):
    """Best = most recall, then earliest, then most robust, then cheapest. first_on None = worst."""
    first_on = r["first_on"] if r["first_on"] is not None else 1e9
    return (-r["tp"], r["fn"], r["fp"], first_on, -r["det_hit"], r["infer_ms"])


def print_table(rows):
    print("")
    print(" imgsz  conf  min_wh crop  det_hit  first_on   TP  FN  FP  infer_ms")
    print(" -----  ----  ------ ----  -------  --------   --  --  --  --------")
    for r in rows:
        fo = ("%.1fs" % r["first_on"]) if r["first_on"] is not None else "  none"
        print(" %5d  %4.2f  %6s  %3s  %5.0f%%  %8s  %3d %3d %3d  %7.1f" % (
            r["imgsz"], r["conf"],
            str(r["min_wh"]) if r["min_wh"] is not None else "def",
            "yes" if r["crop"] else "no",
            100.0 * r["det_hit"], fo, r["tp"], r["fn"], r["fp"], r["infer_ms"]))
    best = sorted(rows, key=_rank_key)[0]
    print("")
    print(" best (recall > earliest > robust > cheapest): imgsz %d / conf %.2f / min_wh %s / crop %s"
          % (best["imgsz"], best["conf"],
             str(best["min_wh"]) if best["min_wh"] is not None else "default",
             "yes" if best["crop"] else "no"))
    print(" all cells are host-tier (NOT acceptance-grade); this is a relative comparison, not a"
          " recall claim.")
    return best


# ------------------------------------------------------------------- grid

def _int_list(s):
    out = []
    for part in s.split(","):
        part = part.strip()
        if part != "":
            out.append(int(part))
    return out


def _float_list(s):
    out = []
    for part in s.split(","):
        part = part.strip()
        if part != "":
            out.append(float(part))
    return out


def build_grid(imgszs, confs, min_whs, crops):
    cells = []
    for imgsz in imgszs:
        for conf in confs:
            for mw in min_whs:
                for crop in crops:
                    cells.append((imgsz, conf, mw, crop))
    return cells


def run_sweep(weights, make_source, calib, out_dir, duration, hazards,
              imgszs, confs, min_whs, crops):
    cells = build_grid(imgszs, confs, min_whs, crops)
    print("sweep: %d cells x %.0fs clip = %d cell-runs" % (len(cells), duration, len(cells)))
    rows = []
    n = 0
    for (imgsz, conf, mw, crop) in cells:
        n += 1
        print("  [%d/%d] imgsz=%d conf=%.2f min_wh=%s crop=%s ..."
              % (n, len(cells), imgsz, conf, mw if mw is not None else "def", crop))
        rows.append(run_cell(weights, make_source, calib, out_dir, duration, hazards,
                             imgsz, conf, mw, crop, roi_pad=48))
    return rows


# ------------------------------------------------------------------- self-test

def selftest(weights):
    """Tiny grid on the bundled ultralytics sample: proves the instrument runs, scores, and ranks.
    Two imgsz cells over a stopped bus (dwell clears in the 7.5 s window -> a real TP to score)."""
    try:
        import cv2
        import ultralytics
    except ImportError:
        sys.exit("selftest needs ultralytics (+ cv2):  pip install ultralytics")
    sample = os.path.join(os.path.dirname(ultralytics.__file__), "assets", "bus.jpg")
    if not os.path.exists(sample):
        sys.exit("selftest: sample image not found: %s" % sample)
    img = cv2.imread(sample)

    probe = hyl.YoloDetector(weights, imgsz=320, conf=0.1)
    calib = hyl._selftest_calib(probe, img)          # ROI around the bus, scale from its size

    duration = 7.5
    hazards = [[0.0, duration]]
    out_dir = tempfile.mkdtemp(prefix="esw-sweep-selftest-")

    def make_source():
        return hyl.StillJitterSource(img, amp_px=3, seed=42)

    rows = run_sweep(weights, make_source, calib, out_dir, duration, hazards,
                     imgszs=[320, 416], confs=[0.1], min_whs=[None], crops=[False])
    best = print_table(rows)

    fails = []

    def check(name, ok, detail=""):
        print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name, (" -- " + str(detail)) if detail else ""))
        if not ok:
            fails.append(name)

    print("\nself-test assertions\n" + "-" * 72)
    check("grid produced a row per cell", len(rows) == 2, len(rows))
    check("detector actually saw the bus in every cell (det_hit > 0)",
          all(r["det_hit"] > 0.0 for r in rows), [round(r["det_hit"], 2) for r in rows])
    check("stopped bus scored as a true positive in every cell (TP=1, FN=0)",
          all(r["tp"] == 1 and r["fn"] == 0 for r in rows),
          [(r["tp"], r["fn"]) for r in rows])
    check("inference time was measured (infer_ms > 0)",
          all(r["infer_ms"] > 0.0 for r in rows), [round(r["infer_ms"], 1) for r in rows])
    check("best-cell selection returns a cell from the grid", best in rows)

    import shutil
    shutil.rmtree(out_dir, ignore_errors=True)
    print("-" * 72)
    if fails:
        print("SELF-TEST: %d FAILURE(S): %s" % (len(fails), fails))
        return 1
    print("SELF-TEST: PASS -- the accuracy sweep runs, scores against ground truth, and ranks.")
    return 0


# ------------------------------------------------------------------- cli

def main():
    ap = argparse.ArgumentParser(
        description="Sweep detector settings over one clip and score each against ground truth.")
    ap.add_argument("--selftest", action="store_true", help="tiny grid on the bundled bus.jpg")
    ap.add_argument("--video", help="video file to sweep")
    ap.add_argument("--image", help="still image to sweep (seeded jitter, like the self-test)")
    ap.add_argument("--calib", help="calibration JSON (the device /sdcard/esw/calib.json schema)")
    ap.add_argument("--hazard", action="append", default=[], metavar="T0:T1",
                    help="ground-truth hazard interval (repeatable), e.g. 12.5:96")
    ap.add_argument("--weights", default="yolov8n.pt", help="ultralytics weights (default yolov8n.pt)")
    ap.add_argument("--imgsz", default="320,416,512,640", help="comma list of inference sizes")
    ap.add_argument("--conf", default="0.1,0.25", help="comma list of confidence floors")
    ap.add_argument("--min-wh", default="", help="comma list of adapter small-box floors (px); "
                                                 "empty = calib/default only")
    ap.add_argument("--roi-crop", action="store_true",
                    help="add a crop-off/crop-on axis (see host_yolo_loop.roi_crop_box)")
    ap.add_argument("--roi-pad", type=int, default=48, help="ROI crop padding, source px (default 48)")
    ap.add_argument("--jitter-px", type=int, default=3, help="still-image jitter amplitude")
    ap.add_argument("--duration", type=float, help="seconds per cell (default: video length, or 30)")
    ap.add_argument("--out", help="directory for the per-cell sessions (default a temp dir)")
    ap.add_argument("--keep", action="store_true", help="keep the per-cell session directories")
    args = ap.parse_args()

    if args.selftest:
        return selftest(args.weights)

    if not args.video and not args.image:
        ap.error("one of --selftest, --video or --image is required")
    if not args.calib:
        ap.error("--calib is required (the device calib.json schema)")
    if not args.hazard:
        ap.error("--hazard is required: a sweep with no ground truth cannot score recall")

    try:
        import cv2                                     # noqa: F401  (VideoSource/StillJitter use it)
    except ImportError:
        sys.exit("needs OpenCV + numpy:  pip install ultralytics")

    with open(args.calib, "r", encoding="utf-8") as f:
        calib = json.load(f)
    if "H" not in calib or "roi" not in calib:
        sys.exit("calib.json needs H (3x3 image->ground homography) and roi (CCW ground polygon)")

    if args.video:
        probe = hyl.VideoSource(args.video)
        duration = args.duration or probe.duration()
        if duration is None:
            sys.exit("cannot determine video length; pass --duration")
        if "frame_wh" not in calib and probe.frame_wh():
            calib["frame_wh"] = probe.frame_wh()
        path = args.video

        def make_source():
            return hyl.VideoSource(path)               # rewound per cell (forward-only decoder)
    else:
        import cv2
        img = cv2.imread(args.image)
        if img is None:
            sys.exit("cannot read image: %s" % args.image)
        duration = args.duration or 30.0
        if "frame_wh" not in calib:
            calib["frame_wh"] = [img.shape[1], img.shape[0]]
        jitter = args.jitter_px

        def make_source():
            return hyl.StillJitterSource(img, amp_px=jitter)

    imgszs = _int_list(args.imgsz)
    confs = _float_list(args.conf)
    min_whs = _int_list(args.min_wh) if args.min_wh.strip() != "" else [None]
    crops = [False, True] if args.roi_crop else [False]
    hazards = [hyl._parse_hazard(h) for h in args.hazard]

    out_dir = args.out or tempfile.mkdtemp(prefix="esw-sweep-")
    os.makedirs(out_dir, exist_ok=True)

    rows = run_sweep(args.weights, make_source, calib, out_dir, duration, hazards,
                     imgszs, confs, min_whs, crops)
    print_table(rows)
    print("\nper-cell sessions: %s" % out_dir)
    if not args.keep and not args.out:
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)
        print("(removed; pass --keep or --out to retain them)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
