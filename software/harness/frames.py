# Scripted detection source for the Level-B perception harness (doc 07 §2).
#
# This is the host-side stand-in for the DETECTOR (the K230 kmodel/YOLO): it turns a
# case's scripted object trajectories into the per-frame detection list Perception.step()
# consumes -- image bboxes + class + score. Level A injects IF-2 events directly; Level B
# (this) injects DETECTIONS and runs the REAL perception (ROI gating + tracker) on them.
#
# A case object:
#   {"id","cls","enter","leave","score"?,
#    "bbox":[x1,y1,x2,y2]            # static box, OR
#    "path":[[t,[x1,y1,x2,y2]], ...] # keyframes, linearly interpolated
#    "drop":[[t0,t1], ...]}          # intervals the detector misses it (dropout)
#
# Host-only tooling -- NOT shipped to the K230.


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


def detections_at(case, t):
    """The detector's output at tick t: [{cls, bbox, score}] for every visible object."""
    dets = []
    for trk in case.get("objects", []):
        if not (trk["enter"] <= t < trk["leave"]):
            continue
        if _dropped(trk, t):
            continue
        dets.append({"cls": trk.get("cls", "car"),
                     "bbox": _bbox_at(trk, t),
                     "score": trk.get("score", 0.9)})
    return dets
