# Perception pipeline -- the real IF-1 -> IF-2 path (doc 02 §2, ADR-0003).
#
# Turns raw per-frame DETECTIONS (image bboxes + class from a detector) into stable
# IF-2 track events (doc 08 §2) for the decision state machine. Three stages:
#   1. ROI gating  -- project each detection's ground footprint through the per-site
#      homography and measure its ROI overlap (esw/geometry.py).
#   2. Tracking    -- associate detections across frames, hold stable track_ids through
#      brief misses, and estimate a jitter-robust ground speed.
#   3. IF-2 emit   -- assemble {track_id, class, footprint, in_roi, range_m, speed_kph,
#      sensor_source, ts} per track per cycle.
#
# TRACKER (ByteTrack/Kalman-lite, MicroPython-safe -- no numpy):
#   - constant-velocity PREDICTION: each track predicts its position to the current tick,
#     so association gates on where the object should be, not where it last was;
#   - COASTING: an unmatched track is kept (same track_id) for track_max_age_s, so a brief
#     dropout / occlusion does NOT switch the id or restart the state machine's dwell;
#   - TWO-STAGE association: high-score detections match first, then low-score detections
#     (usually discarded) recover tracks through a confidence dip -- the ByteTrack idea.
#   A track emits an IF-2 event only on frames it is actually detected -- perception never
#   fabricates a detection during a dropout (absence is the state machine's job, ADR-0008/9).
#
# SPEED is estimated over a short baseline (speed_window_s) and EMA-smoothed (speed_alpha):
#   frame-to-frame differencing turns a few px of box jitter into a false >speed_gate reading
#   (a stopped car reads as "moving" and never confirms); a windowed + smoothed estimate
#   rejects zero-mean jitter while still tracking real motion.
#
# DETECTOR-AGNOSTIC: the ML backend (a YOLO `kmodel` on the K230's KPU, or a stub in
# sim) is NOT here -- the caller runs it and passes its output to step(). That keeps
# this pipeline byte-identical sim/K230 with no sim-only branch. Radar fusion is a
# separate stage (blocked on the radar procurement, RQ-H1); events are camera-sourced.
#
# Ships to the K230: MicroPython-safe subset.

from esw.geometry import bbox_ground_point, footprint_box, footprint_projected, overlap_fraction

# Class -> ground footprint (width_m, length_m). First-order sizes (doc 02 §4).
_DEFAULT_FOOTPRINT = {
    "car": (2.0, 4.5), "truck": (2.5, 8.0), "bus": (2.6, 11.0),
    "motorcycle": (0.8, 2.0), "person": (0.6, 0.6),
}


def default_calibration(roi):
    """A minimal calibration around a given ground ROI polygon (identity image scale).
    Real deployments supply a surveyed homography + ROI at commissioning."""
    return {"H": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "roi": roi, "score_min": 0.4, "score_low": 0.1, "assoc_gate_m": 3.0,
            "track_max_age_s": 2.0, "speed_window_s": 0.5, "speed_alpha": 0.3}


class Perception:
    def __init__(self, calib):
        # calib: H (3x3 image->ground homography), roi (CCW convex ground polygon),
        # score_min (spawn/high-assoc threshold), score_low (low-assoc recovery floor),
        # assoc_gate_m (max association distance), track_max_age_s (coast buffer),
        # speed_window_s (speed baseline), speed_alpha (speed EMA).
        self.h = calib["H"]
        self.roi = calib["roi"]
        self.score_min = calib.get("score_min", 0.4)
        self.score_low = calib.get("score_low", 0.1)
        self.assoc_gate = calib.get("assoc_gate_m", 3.0)
        # track_ttl_s kept as a fallback name for the coast buffer (back-compat).
        self.max_age = calib.get("track_max_age_s", calib.get("track_ttl_s", 2.0))
        self.speed_window = calib.get("speed_window_s", 0.5)
        self.speed_alpha = calib.get("speed_alpha", 0.3)
        # Footprint model: "box" = first-order axis-aligned class box (default); "projected"
        # = perspective base-projection + depth extrusion (needs a real perspective H).
        self.footprint_mode = calib.get("footprint_mode", "box")
        self.footprint = calib.get("footprint", _DEFAULT_FOOTPRINT)
        self.tracks = {}          # track_id -> track record
        self._next_id = 1

    def _new_id(self):
        tid = self._next_id
        self._next_id += 1
        return tid

    def _predict(self, tr, now):
        """Constant-velocity prediction of a track's position to `now`."""
        dt = now - tr["ts"]
        return (tr["pos"][0] + tr["vel"][0] * dt, tr["pos"][1] + tr["vel"][1] * dt)

    def _greedy(self, cands, tids, pred, used_tracks):
        """Greedy nearest-neighbour assoc of `cands` to available `tids`, gated by
        assoc_gate against each track's PREDICTED position. Returns (assign {tid: cand},
        unmatched [cand, ...]); marks assigned tids in used_tracks. No lambdas: the pair
        list sorts on its leading distance field (tuples compare lexicographically)."""
        pairs = []
        ci = 0
        for c in cands:
            for tid in tids:
                if tid in used_tracks:
                    continue
                px, py = pred[tid]
                dx = c["pos"][0] - px
                dy = c["pos"][1] - py
                d = (dx * dx + dy * dy) ** 0.5
                if d <= self.assoc_gate:
                    pairs.append((d, ci, tid))
            ci += 1
        pairs.sort()
        assign = {}
        used_cands = set()
        for pr in pairs:
            tid = pr[2]
            cidx = pr[1]
            if tid in used_tracks or cidx in used_cands:
                continue
            used_tracks.add(tid)
            used_cands.add(cidx)
            assign[tid] = cands[cidx]
        unmatched = []
        ci = 0
        for c in cands:
            if ci not in used_cands:
                unmatched.append(c)
            ci += 1
        return assign, unmatched

    def _init_track(self, cand, now):
        return {"pos": cand["pos"], "vel": (0.0, 0.0), "ts": now, "cls": cand["cls"],
                "speed": 0.0, "hist": [(now, cand["pos"])], "lost_since": None,
                "bbox": cand["bbox"]}

    def _update_track(self, tid, cand, now):
        """Fold a matched detection into a track: windowed velocity + EMA speed."""
        tr = self.tracks[tid]
        tr["hist"].append((now, cand["pos"]))
        while len(tr["hist"]) > 1 and (now - tr["hist"][0][0]) > self.speed_window:
            tr["hist"].pop(0)
        t0, p0 = tr["hist"][0]
        dtw = now - t0
        if dtw > 0.0:
            vx = (cand["pos"][0] - p0[0]) / dtw
            vy = (cand["pos"][1] - p0[1]) / dtw
        else:
            vx, vy = tr["vel"]
        inst_kph = (vx * vx + vy * vy) ** 0.5 * 3.6
        tr["speed"] = self.speed_alpha * inst_kph + (1.0 - self.speed_alpha) * tr["speed"]
        tr["vel"] = (vx, vy)
        tr["pos"] = cand["pos"]
        tr["cls"] = cand["cls"]
        tr["bbox"] = cand["bbox"]
        tr["ts"] = now
        tr["lost_since"] = None

    def step(self, detections, now):
        """One perception cycle. detections = [{cls, bbox:[x1,y1,x2,y2], score}].
        Returns the IF-2 track events (doc 08 §2) for this tick."""
        # Split detections by confidence: high (>= score_min) associate first and may spawn
        # tracks; low (>= score_low) only recover an existing track (ByteTrack two-stage).
        highs = []
        lows = []
        for d in detections:
            sc = d.get("score", 1.0)
            if sc < self.score_low:
                continue
            gx, gy = bbox_ground_point(self.h, d["bbox"])
            cand = {"pos": (gx, gy), "cls": d.get("cls", "car"), "score": sc,
                    "bbox": d["bbox"]}
            if sc >= self.score_min:
                highs.append(cand)
            else:
                lows.append(cand)

        tids = list(self.tracks.keys())
        pred = {}
        for tid in tids:
            pred[tid] = self._predict(self.tracks[tid], now)

        used_tracks = set()
        assign_hi, unmatched_hi = self._greedy(highs, tids, pred, used_tracks)
        rem = []
        for tid in tids:
            if tid not in used_tracks:
                rem.append(tid)
        assign_lo, _ = self._greedy(lows, rem, pred, used_tracks)

        seen = set()
        for tid in assign_hi:
            self._update_track(tid, assign_hi[tid], now)
            seen.add(tid)
        for tid in assign_lo:
            self._update_track(tid, assign_lo[tid], now)
            seen.add(tid)
        for c in unmatched_hi:                        # a high-score det with no track -> new
            tid = self._new_id()
            self.tracks[tid] = self._init_track(c, now)
            seen.add(tid)

        # Coast unmatched tracks (keep the id, predicting) up to track_max_age_s, then retire.
        # This is what lets a real track survive a brief dropout with no id switch.
        for tid in list(self.tracks.keys()):
            if tid in seen:
                continue
            tr = self.tracks[tid]
            if tr["lost_since"] is None:
                tr["lost_since"] = now
            if (now - tr["ts"]) > self.max_age:
                del self.tracks[tid]

        # Emit IF-2 events only for tracks actually detected this frame (sorted for a stable
        # order). Coasting tracks emit nothing -- perception does not fabricate detections.
        events = []
        ids = list(seen)
        ids.sort()
        for tid in ids:
            tr = self.tracks[tid]
            w, length = self.footprint.get(tr["cls"], self.footprint["car"])
            if self.footprint_mode == "projected":
                fp = footprint_projected(self.h, tr["bbox"], length)
            else:
                fp = footprint_box(tr["pos"][0], tr["pos"][1], w, length)
            in_roi = overlap_fraction(fp, self.roi)
            gx, gy = tr["pos"]
            events.append({
                "track_id": "P%d" % tid,
                "cls": tr["cls"],
                "footprint": fp,
                "in_roi": in_roi,
                "range_m": (gx * gx + gy * gy) ** 0.5,   # geometric range (radar refines later)
                "speed_kph": tr["speed"],
                "sensor_source": "camera",
                "ts": now,
            })
        return events
