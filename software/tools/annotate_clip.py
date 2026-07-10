#!/usr/bin/env python3
"""Ground-truth annotation helper: turn a clip + a capture session into hazards a human vouches for.

The acceptance campaign needs hundreds of annotated hazard intervals (doc 01 §5: recall-N must
be REAL captures), and hand-editing `ground_truth.json` against a video does not scale. This
tool does two things:

  ANNOTATE (a window opens; for humans):
      python software/tools/annotate_clip.py --video clip.mp4 --gt captures/host-a/ground_truth.json
    Step through the clip and mark hazard intervals; `s` writes them into the ground truth's
    `hazards` list. Keys:  space play/pause · a/d +-1 frame · A/D +-1 s · [ mark start ·
    ] mark end (closes the interval) · p toggle class (vehicle/person) · y accept next proposal ·
    n reject next proposal · u undo last confirmed · s save · q save+quit · ESC quit WITHOUT saving

  PROPOSE (headless):
      python software/tools/annotate_clip.py --propose captures/host-a
    Read the session's capture.jsonl and derive CANDIDATE intervals (spans where an in-ROI
    track existed). Candidates are written to `hazards_proposed` -- NEVER to `hazards`. The
    scorer reads only `hazards` (harness/evidence.py), so an unreviewed proposal can never
    leak into a recall number.

THE HONESTY RULE, which is why proposals are quarantined: candidates come from the DETECTOR
under test, so they can only ever bound events the detector FOUND. The hazards it missed --
the false negatives, the exact thing recall exists to count -- are invisible to proposals by
construction. Accepting proposals speeds up marking the bounds of true positives; it does not
replace watching the clip. Watch the whole clip.

Host-only (NOT shipped). Annotation UI needs OpenCV (ships with ultralytics).
"""

import argparse
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

ROI_GATE = 0.5          # an event this far in-ROI marks the tick "occupied" (roi_overlap_gate)
MIN_SPAN_S = 1.0        # candidates shorter than this are noise, not hazards
BRIDGE_GAP_S = 2.0      # occupied spans closer than this merge (dropout must not split a hazard)
PAD_S = 0.5             # widen each candidate: onset/exit are exactly where the detector is weak


# ------------------------------------------------------------------- ground truth io

def load_gt(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"tier": "real-staged", "model_sha256": None, "t_offset": 0.0,
            "hazards": [], "notes": ""}


def save_gt(path, gt):
    """Write atomically enough for a laptop: temp file + replace, so a crash mid-write never
    leaves a torn ground truth next to a good capture."""
    d = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(d):
        os.makedirs(d)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".gt.tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(gt, f, indent=2)
    os.replace(tmp, path)


def normalize_hazards(hazards):
    """Uniform [{t0, t1, cls}] from the two schema forms evidence.py accepts."""
    out = []
    for h in hazards:
        if isinstance(h, dict):
            out.append({"t0": float(h["t0"]), "t1": float(h["t1"]),
                        "cls": h.get("cls", "vehicle")})
        else:
            out.append({"t0": float(h[0]), "t1": float(h[1]), "cls": "vehicle"})
    return out


def to_schema(hazards):
    """Back to the compact schema: bare pairs for vehicles, dicts only when cls matters."""
    out = []
    for h in sorted(hazards, key=lambda x: x["t0"]):
        if h.get("cls", "vehicle") == "vehicle":
            out.append([round(h["t0"], 2), round(h["t1"], 2)])
        else:
            out.append({"t0": round(h["t0"], 2), "t1": round(h["t1"], 2), "cls": h["cls"]})
    return out


# ------------------------------------------------------------------- propose

def occupied_ticks(capture_path):
    """[(ts, occupied)] per tick record: occupied = any IF-2 event >= ROI_GATE in-ROI."""
    out = []
    if not os.path.exists(capture_path):
        sys.exit("no capture.jsonl at %s -- run the session first" % capture_path)
    with open(capture_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue                      # torn tail: the scorer counts it, we just skip
            if rec.get("type") != "tick":
                continue
            occ = False
            for e in rec.get("events", []):
                if e.get("in_roi", 0.0) >= ROI_GATE:
                    occ = True
                    break
            out.append((float(rec["ts"]), occ))
    return out


def spans_from_ticks(ticks, bridge_gap_s=BRIDGE_GAP_S, min_span_s=MIN_SPAN_S, pad_s=PAD_S):
    """Merge occupied ticks into candidate intervals. Bridging spans dropout (a briefly
    coasted track must not split one hazard into two); padding widens the bounds because
    onset/exit are exactly where a detector under test is least trustworthy."""
    spans = []
    start = None
    last = None
    for ts, occ in ticks:
        if occ:
            if start is None:
                start = ts
            last = ts
        elif start is not None and ts - last > bridge_gap_s:
            spans.append((start, last))
            start = None
    if start is not None:
        spans.append((start, last))
    merged = []
    for s, e in spans:
        if merged and s - merged[-1][1] <= bridge_gap_s:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    out = []
    for s, e in merged:
        if e - s >= min_span_s:
            out.append({"t0": max(0.0, s - pad_s), "t1": e + pad_s, "cls": "vehicle"})
    return out


def propose(session_dir):
    """Derive candidates from the session's own capture log into hazards_proposed. NEVER
    touches `hazards`: the scorer must only ever see intervals a human confirmed."""
    gt_path = os.path.join(session_dir, "ground_truth.json")
    gt = load_gt(gt_path)
    cands = spans_from_ticks(occupied_ticks(os.path.join(session_dir, "capture.jsonl")))
    gt["hazards_proposed"] = to_schema(cands)
    gt["hazards_proposed_note"] = (
        "DRAFT from the detector under test (annotate_clip.py --propose). Proposals can only "
        "bound events the detector FOUND; missed hazards are invisible here by construction. "
        "Review in the annotate UI (y/n) or by hand, then delete this field.")
    save_gt(gt_path, gt)
    print("%d candidate interval(s) -> %s (field: hazards_proposed)" % (len(cands), gt_path))
    for c in cands:
        print("  [%8.2f, %8.2f]" % (c["t0"], c["t1"]))
    print("hazards (human-confirmed) untouched: %d" % len(gt.get("hazards", [])))
    return 0


# ------------------------------------------------------------------- annotate ui

class Marks:
    """The annotation state, GUI-free so it is testable: confirmed hazards, pending
    proposals, an open interval being marked, and an undo stack."""

    def __init__(self, gt):
        self.gt = gt
        self.hazards = normalize_hazards(gt.get("hazards", []))
        self.proposed = normalize_hazards(gt.get("hazards_proposed", []))
        self.open_t0 = None
        self.cls = "vehicle"
        self._undo = []

    def mark_start(self, t):
        self.open_t0 = t

    def mark_end(self, t):
        if self.open_t0 is None or t <= self.open_t0:
            return False
        self.hazards.append({"t0": self.open_t0, "t1": t, "cls": self.cls})
        self._undo.append("mark")
        self.open_t0 = None
        return True

    def toggle_cls(self):
        self.cls = "person" if self.cls == "vehicle" else "vehicle"
        return self.cls

    def accept_next(self):
        if not self.proposed:
            return None
        h = self.proposed.pop(0)
        self.hazards.append(h)
        self._undo.append("accept")
        return h

    def reject_next(self):
        if not self.proposed:
            return None
        h = self.proposed.pop(0)
        self._undo.append(("reject", h))
        return h

    def undo(self):
        if not self._undo:
            return False
        op = self._undo.pop()
        if op == "mark":
            self.hazards.pop()
        elif op == "accept":
            self.proposed.insert(0, self.hazards.pop())
        else:                                   # ("reject", h)
            self.proposed.insert(0, op[1])
        return True

    def into_gt(self):
        self.gt["hazards"] = to_schema(self.hazards)
        if self.proposed:
            self.gt["hazards_proposed"] = to_schema(self.proposed)
        else:
            self.gt.pop("hazards_proposed", None)
            self.gt.pop("hazards_proposed_note", None)
        return self.gt


def annotate(video_path, gt_path):
    try:
        import cv2
    except ImportError:
        sys.exit("the annotation UI needs OpenCV:  pip install ultralytics")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        sys.exit("cannot open video: %s" % video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    dur = total / fps if total else 0.0
    marks = Marks(load_gt(gt_path))

    print(__doc__.split("THE HONESTY RULE")[1].join(["THE HONESTY RULE", ""]).split("\n\n")[0])

    idx = 0
    playing = False
    frame = None

    def seek(i):
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(i, total - 1)))

    def bar(img, t):
        h, w = img.shape[:2]
        y = h - 24
        cv2.rectangle(img, (0, y), (w, h), (30, 30, 30), -1)
        def px(tt):
            return int(w * (tt / dur)) if dur else 0
        for hz in marks.hazards:
            cv2.rectangle(img, (px(hz["t0"]), y + 4), (px(hz["t1"]), h - 4), (0, 200, 0), -1)
        for hz in marks.proposed:
            cv2.rectangle(img, (px(hz["t0"]), y + 4), (px(hz["t1"]), h - 4), (0, 165, 255), 2)
        if marks.open_t0 is not None:
            cv2.rectangle(img, (px(marks.open_t0), y + 4), (px(t), h - 4), (0, 255, 255), -1)
        cv2.line(img, (px(t), y), (px(t), h), (255, 255, 255), 2)
        cv2.putText(img, "t=%.2fs cls=%s confirmed=%d proposed=%d" %
                    (t, marks.cls, len(marks.hazards), len(marks.proposed)),
                    (8, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

    while True:
        if playing or frame is None:
            ok, f = cap.read()
            if ok:
                frame = f
                idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
            else:
                playing = False
        t = idx / fps
        disp = frame.copy()
        bar(disp, t)
        cv2.imshow("annotate -- see terminal for keys", disp)
        k = cv2.waitKey(int(1000 / fps) if playing else 30) & 0xFF
        if k == ord(" "):
            playing = not playing
        elif k == ord("d"):
            playing = False; seek(idx + 1); frame = None
        elif k == ord("a"):
            playing = False; seek(idx - 1); frame = None
        elif k == ord("D"):
            playing = False; seek(idx + int(fps)); frame = None
        elif k == ord("A"):
            playing = False; seek(idx - int(fps)); frame = None
        elif k == ord("["):
            marks.mark_start(t)
        elif k == ord("]"):
            marks.mark_end(t)
        elif k == ord("p"):
            marks.toggle_cls()
        elif k == ord("y"):
            marks.accept_next()
        elif k == ord("n"):
            marks.reject_next()
        elif k == ord("u"):
            marks.undo()
        elif k == ord("s"):
            save_gt(gt_path, marks.into_gt())
            print("saved: %s (%d hazards)" % (gt_path, len(marks.hazards)))
        elif k == ord("q"):
            save_gt(gt_path, marks.into_gt())
            print("saved: %s (%d hazards)" % (gt_path, len(marks.hazards)))
            break
        elif k == 27:
            print("quit WITHOUT saving")
            break
    cap.release()
    cv2.destroyAllWindows()
    return 0


# ------------------------------------------------------------------- selftest

def selftest():
    """Headless test of everything that decides what a recall number sees: the proposal
    extraction, the hazards/hazards_proposed quarantine, and the Marks undo model."""
    fails = []

    def check(name, ok, detail=""):
        print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                               (" -- " + str(detail)) if detail else ""))
        if not ok:
            fails.append(name)

    print("selftest assertions")
    print("-" * 74)
    d = tempfile.mkdtemp(prefix="esw-annotate-selftest-")

    # A synthetic session: in-ROI track 2..10 s with a 1 s dropout at 5 (must bridge), a
    # 0.3 s blip at 20 (must be discarded), a second hazard 30..35.
    def tick(ts, in_roi):
        return {"type": "tick", "ts": ts,
                "events": [{"track_id": "T1", "in_roi": 0.9}] if in_roi else []}
    with open(os.path.join(d, "capture.jsonl"), "w", encoding="utf-8") as f:
        t = 0.0
        while t < 40.0:
            occ = (2.0 <= t < 5.0) or (6.0 <= t < 10.0) or (20.0 <= t < 20.3) \
                  or (30.0 <= t < 35.0)
            f.write(json.dumps(tick(round(t, 1), occ)) + "\n")
            t += 0.1
    with open(os.path.join(d, "ground_truth.json"), "w", encoding="utf-8") as f:
        json.dump({"tier": "real-staged", "hazards": [[1.0, 2.0]], "t_offset": 0.0}, f)

    propose(d)
    gt = load_gt(os.path.join(d, "ground_truth.json"))
    props = normalize_hazards(gt.get("hazards_proposed", []))
    check("dropout bridged: 2..5 + 6..10 -> ONE candidate", len(props) == 2,
          [(p["t0"], p["t1"]) for p in props])
    check("candidate 1 covers ~[1.5, 10.4] (padded)",
          props and abs(props[0]["t0"] - 1.5) < 0.2 and abs(props[0]["t1"] - 10.4) < 0.2,
          props and (props[0]["t0"], props[0]["t1"]))
    check("0.3 s blip discarded, 30..35 kept", len(props) == 2 and
          abs(props[1]["t0"] - 29.5) < 0.2 and abs(props[1]["t1"] - 35.4) < 0.2,
          props and (props[-1]["t0"], props[-1]["t1"]))
    check("QUARANTINE: `hazards` untouched by --propose",
          gt.get("hazards") == [[1.0, 2.0]], gt.get("hazards"))

    m = Marks(gt)
    m.accept_next()
    check("accept moves proposal -> hazards", len(m.hazards) == 2 and len(m.proposed) == 1)
    m.undo()
    check("undo(accept) restores the proposal", len(m.hazards) == 1 and len(m.proposed) == 2)
    m.reject_next()
    m.undo()
    check("undo(reject) restores the proposal", len(m.proposed) == 2)
    m.mark_start(50.0)
    check("mark_end before start refused", m.mark_end(49.0) is False)
    m.mark_end(55.0)
    m.toggle_cls()
    m.mark_start(60.0)
    m.mark_end(61.0)
    check("manual marks land with class", len(m.hazards) == 3 and
          m.hazards[-1]["cls"] == "person", m.hazards[-1] if m.hazards else None)
    m.accept_next()
    m.accept_next()
    out = m.into_gt()
    check("all proposals resolved -> hazards_proposed field removed",
          "hazards_proposed" not in out and "hazards_proposed_note" not in out)
    check("saved hazards sorted by t0",
          [h["t0"] for h in normalize_hazards(out["hazards"])]
          == sorted(h["t0"] for h in normalize_hazards(out["hazards"])))
    save_gt(os.path.join(d, "ground_truth.json"), out)
    back = load_gt(os.path.join(d, "ground_truth.json"))
    check("round-trip preserves tier + count", back["tier"] == "real-staged"
          and len(back["hazards"]) == len(out["hazards"]))

    print("-" * 74)
    if fails:
        print("SELF-TEST: %d FAILURE(S): %s" % (len(fails), fails))
        return 1
    print("SELF-TEST: PASS -- proposals stay quarantined until a human moves them.")
    return 0


# ------------------------------------------------------------------- cli

def main():
    ap = argparse.ArgumentParser(
        description="Annotate hazard intervals for a capture session's ground_truth.json.")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--propose", metavar="SESSION_DIR",
                    help="derive DRAFT candidates from the session's capture.jsonl "
                         "(written to hazards_proposed, never hazards)")
    ap.add_argument("--video", help="clip to annotate (opens a window)")
    ap.add_argument("--gt", help="ground_truth.json to edit (with --video)")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.propose:
        return propose(args.propose)
    if args.video:
        if not args.gt:
            ap.error("--video needs --gt <ground_truth.json>")
        return annotate(args.video, args.gt)
    ap.error("one of --selftest, --propose, --video is required")


if __name__ == "__main__":
    sys.exit(main())
