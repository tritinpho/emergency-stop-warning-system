# Perception pipeline -- the real IF-1 -> IF-2 path (doc 02 §2, ADR-0003).
#
# Turns raw per-frame DETECTIONS (image bboxes + class from a detector) into stable
# IF-2 track events (doc 08 §2) for the decision state machine. Three stages:
#   1. ROI gating  -- project each detection's ground footprint through the per-site
#      homography and measure its ROI overlap (esw/geometry.py).
#   2. Tracking    -- associate detections across frames (greedy nearest-neighbour),
#      hold stable track_ids, estimate ground speed from footprint displacement.
#   3. IF-2 emit   -- assemble {track_id, class, footprint, in_roi, range_m, speed_kph,
#      sensor_source, ts} per track per cycle.
#
# DETECTOR-AGNOSTIC: the ML backend (a YOLO `kmodel` on the K230's KPU, or a stub in
# sim) is NOT here -- the caller runs it and passes its output to step(). That keeps
# this pipeline byte-identical sim/K230 with no sim-only branch. Radar fusion is a
# separate stage (blocked on the radar procurement, RQ-H1); events are camera-sourced.
#
# Ships to the K230: MicroPython-safe subset.

from esw.geometry import bbox_ground_point, footprint_box, overlap_fraction

# Class -> ground footprint (width_m, length_m). First-order sizes (doc 02 §4).
_DEFAULT_FOOTPRINT = {
    "car": (2.0, 4.5), "truck": (2.5, 8.0), "bus": (2.6, 11.0),
    "motorcycle": (0.8, 2.0), "person": (0.6, 0.6),
}


def default_calibration(roi):
    """A minimal calibration around a given ground ROI polygon (identity image scale).
    Real deployments supply a surveyed homography + ROI at commissioning."""
    return {"H": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "roi": roi, "score_min": 0.4, "assoc_gate_m": 3.0, "track_ttl_s": 1.0}


class Perception:
    def __init__(self, calib):
        # calib: H (3x3 image->ground homography), roi (CCW convex ground polygon),
        # score_min, assoc_gate_m (max association distance), track_ttl_s.
        self.h = calib["H"]
        self.roi = calib["roi"]
        self.score_min = calib.get("score_min", 0.4)
        self.assoc_gate = calib.get("assoc_gate_m", 3.0)
        self.track_ttl = calib.get("track_ttl_s", 1.0)
        self.footprint = calib.get("footprint", _DEFAULT_FOOTPRINT)
        self.tracks = {}          # track_id -> {"pos", "ts", "cls", "speed"}
        self._next_id = 1

    def _new_id(self):
        tid = self._next_id
        self._next_id += 1
        return tid

    def _associate(self, cands, now):
        """Greedy nearest-neighbour association against tracks that existed at the start
        of this frame; returns [{tid, cls, pos, speed_kph}]. Unmatched -> new track."""
        existing = list(self.tracks.keys())
        used = set()
        matched = []
        for c in cands:
            best = None
            best_d = self.assoc_gate
            for tid in existing:
                if tid in used:
                    continue
                tr = self.tracks[tid]
                dx = c["pos"][0] - tr["pos"][0]
                dy = c["pos"][1] - tr["pos"][1]
                d = (dx * dx + dy * dy) ** 0.5
                if d <= best_d:
                    best_d = d
                    best = tid
            if best is None:
                tid = self._new_id()
                self.tracks[tid] = {"pos": c["pos"], "ts": now,
                                    "cls": c["cls"], "speed": 0.0}
                matched.append({"tid": tid, "cls": c["cls"], "pos": c["pos"], "speed": 0.0})
            else:
                used.add(best)
                tr = self.tracks[best]
                dt = now - tr["ts"]
                if dt > 0.0:
                    dx = c["pos"][0] - tr["pos"][0]
                    dy = c["pos"][1] - tr["pos"][1]
                    speed = ((dx * dx + dy * dy) ** 0.5) / dt * 3.6   # m/s -> km/h
                else:
                    speed = tr["speed"]
                tr["pos"] = c["pos"]
                tr["ts"] = now
                tr["cls"] = c["cls"]
                tr["speed"] = speed
                matched.append({"tid": best, "cls": c["cls"], "pos": c["pos"], "speed": speed})
        # age out tracks not seen within the TTL (perception continuity, not the SM's hold)
        stale = []
        for tid in self.tracks:
            if (now - self.tracks[tid]["ts"]) > self.track_ttl:
                stale.append(tid)
        for tid in stale:
            del self.tracks[tid]
        return matched

    def step(self, detections, now):
        """One perception cycle. detections = [{cls, bbox:[x1,y1,x2,y2], score}].
        Returns the IF-2 track events (doc 08 §2) for this tick."""
        cands = []
        for d in detections:
            if d.get("score", 1.0) < self.score_min:
                continue
            gx, gy = bbox_ground_point(self.h, d["bbox"])
            cands.append({"cls": d.get("cls", "car"), "pos": (gx, gy)})

        events = []
        for a in self._associate(cands, now):
            w, length = self.footprint.get(a["cls"], self.footprint["car"])
            fp = footprint_box(a["pos"][0], a["pos"][1], w, length)
            in_roi = overlap_fraction(fp, self.roi)
            gx, gy = a["pos"]
            events.append({
                "track_id": "P%d" % a["tid"],
                "cls": a["cls"],
                "footprint": fp,
                "in_roi": in_roi,
                "range_m": (gx * gx + gy * gy) ** 0.5,   # geometric range (radar refines later)
                "speed_kph": a["speed"],
                "sensor_source": "camera",
                "ts": now,
            })
        return events
