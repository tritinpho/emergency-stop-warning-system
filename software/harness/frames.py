# Scripted detection source for the Level-B perception harness (doc 07 §2, §3.1).
#
# This is the host-side stand-in for the DETECTOR (the K230 kmodel/YOLO): it turns a
# case's scripted object trajectories into the per-frame detection list Perception.step()
# consumes -- image bboxes + class + score. Level A injects IF-2 events directly; Level B
# (this) injects DETECTIONS and runs the REAL perception (ROI gating + tracker) on them.
#
# It is NOT a clean oracle feed -- it injects the doc 07 §3.1 camera-channel NUISANCES so
# the perception + state machine are proven robust to a real detector's misbehaviour:
#   - DETECTION DROPOUT  -- `drop` windows the object is missed (occlusion / a dropped frame)
#   - FALSE POSITIVES    -- `false_detections`: blips with no ground-truth object (shadow,
#                           headlight sweep, debris) -- must never reach a confirmed warning
#   - BOX JITTER         -- `jitter_px`: per-frame noise on the bbox (footprint/overlap +
#                           speed robustness) -- must not fake a >speed_gate reading
#   - CLASS CONFUSION    -- `confuse` windows relabel the object (car/truck/.../person)
#   - LOW-CONFIDENCE DIP -- `score_drops` windows drop the detector score (partial occlusion)
#
# Nuisances are DETERMINISTIC: jitter is seeded per (case seed, object id, tick), so a run
# reproduces exactly (doc 07 §8) and the score-run and closed-loop-run see identical frames.
#
# A case object:
#   {"id","cls","enter","leave","score"?,
#    "bbox":[x1,y1,x2,y2]            # static box, OR
#    "path":[[t,[x1,y1,x2,y2]], ...] # keyframes, linearly interpolated
#    "drop":[[t0,t1], ...]           # intervals the detector misses it (dropout)
#    "jitter_px": float              # per-frame uniform bbox jitter amplitude (pixels)
#    "confuse":[[t0,t1,"cls"], ...]  # relabel the class during [t0,t1)
#    "score_drops":[[t0,t1,score],...]} # lower the detector score during [t0,t1)
# A case may also carry `false_detections` (same shape) and a `seed` (default 0).
#
# Host-only tooling -- NOT shipped to the K230 (random / comprehensions are fine here).

import random


def _bbox_at(trk, t):
    if "bbox" in trk:
        return trk["bbox"]
    path = trk["path"]
    if t <= path[0][0]:
        return path[0][1]
    if t >= path[-1][0]:
        return path[-1][1]
    for i in range(1, len(path)):
        t0, b0 = path[i - 1]
        t1, b1 = path[i]
        if t0 <= t <= t1:
            a = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return [b0[k] + a * (b1[k] - b0[k]) for k in range(4)]
    return path[-1][1]


def _dropped(trk, t):
    for w in trk.get("drop", []):
        if w[0] <= t < w[1]:
            return True
    return False


def _class_at(trk, t):
    for w in trk.get("confuse", []):
        if w[0] <= t < w[1]:
            return w[2]              # class-confusion window overrides the true label
    return trk.get("cls", "car")


def _score_at(trk, t):
    for w in trk.get("score_drops", []):
        if w[0] <= t < w[1]:
            return w[2]              # low-confidence dip (partial occlusion)
    return trk.get("score", 0.9)


def _jitter_bbox(bbox, jpx, seed, oid, t):
    """Deterministic per-frame bbox jitter: seeded by (case seed, object id, tick) so the
    same tick always yields the same box -- reproducible, and identical across runs."""
    if jpx <= 0.0:
        return bbox
    rng = random.Random("%d:%s:%.3f" % (seed, oid, t))
    return [bbox[k] + rng.uniform(-jpx, jpx) for k in range(4)]


def _emit(trk, t, seed):
    """The detector's report for one scripted object at tick t (None if not visible)."""
    if not (trk["enter"] <= t < trk["leave"]):
        return None
    if _dropped(trk, t):
        return None
    bbox = _jitter_bbox(_bbox_at(trk, t), trk.get("jitter_px", 0.0), seed, trk["id"], t)
    return {"cls": _class_at(trk, t), "bbox": bbox, "score": _score_at(trk, t)}


def detections_at(case, t):
    """The detector's output at tick t: [{cls, bbox, score}] for every visible object,
    ground-truth AND injected false positives -- with per-object nuisances applied."""
    seed = case.get("seed", 0)
    dets = []
    for trk in case.get("objects", []):
        d = _emit(trk, t, seed)
        if d is not None:
            dets.append(d)
    for trk in case.get("false_detections", []):
        d = _emit(trk, t, seed)
        if d is not None:
            dets.append(d)
    return dets
