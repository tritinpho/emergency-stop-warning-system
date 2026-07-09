# K230 detector -> IF-1 detections adapter (doc 02 §2, ADR-0003, ADR-0016).
#
# The on-device "caller" glue: turns the K230 YOLO detector's raw postprocess output
# (aidemo.yolov8_det_postprocess -> boxes[xywh], class_ids, confidences) into the
# detections list esw.perception.Perception.step() consumes:
#     [{cls, bbox:[x1,y1,x2,y2], score}]
# It is the on-device counterpart of the host harness's frames.py -- Perception stays
# detector-agnostic (ADR-0003), so the SAME perception + state machine run in sim and on
# the K230, only the detections' *source* differs.
#
# Vendored baseline: firmware/k230-detector/k230/main.py `collect_vehicle_detections`.
# This GENERALISES it for the merged pipeline (ADR-0016):
#   - keeps our full COCO class set INCLUDING `person` -- their vehicle-only filter dropped
#     pedestrians, which would make a stranded person on the shoulder invisible (SC-12);
#   - normalises label aliases (motorbike->motorcycle, pedestrian->person) so per-class
#     ground footprints (esw.perception) still apply;
#   - maps a single-class "vehicle" model onto the generic car footprint (ADR-0016 backlog
#     #1: the COCO multi-class model is the chosen target; "vehicle" is the fallback).
#
# NO radar fusion here (camera source only) -- fusion is a separate stage (RQ-H1).
# Ships to the K230: MicroPython-safe subset (no f-strings / comprehensions / lambdas).

# Detector label -> the class name esw.perception footprints use.
_CLASS_ALIASES = {
    "car": "car", "truck": "truck", "bus": "bus",
    "motorcycle": "motorcycle", "motorbike": "motorcycle",
    "person": "person", "pedestrian": "person",
    "vehicle": "car",   # single-class model fallback -> generic car footprint (backlog #1)
}

# Classes the safety pipeline acts on; everything else is dropped at the adapter.
_KEEP = ("car", "truck", "bus", "motorcycle", "person")


def detections_from_yolo(boxes, class_ids, confidences, labels,
                         score_min=0.0, min_wh_px=25, keep=None):
    """Convert one K230 YOLO postprocess result to Perception.step() detections.

    boxes[i]       = (x, y, w, h) in inference-frame pixels (top-left corner + size)
    class_ids[i]   = int index into `labels`
    confidences[i] = float score
    labels         = model class-name list (deploy_config `categories`, or COCO)

    Returns [{cls, bbox:[x1,y1,x2,y2], score}] with our class names. Drops off-list
    classes, sub-`min_wh_px` blobs (baseline noise floor), and sub-`score_min` scores
    (default 0.0 -- perception's own two-stage score gate does the real filtering).
    """
    keep_set = _KEEP if keep is None else keep
    out = []
    n = len(boxes)
    i = 0
    while i < n:
        cid = int(class_ids[i])
        if cid < 0 or cid >= len(labels):
            i += 1
            continue
        raw = labels[cid]
        if hasattr(raw, "lower"):
            raw = raw.lower()          # case-insensitive: a model may label "Car"/"CAR"
        name = _CLASS_ALIASES.get(raw, raw)
        if name not in keep_set:
            i += 1
            continue
        score = float(confidences[i])
        if score < score_min:
            i += 1
            continue
        b = boxes[i]
        x = b[0]
        y = b[1]
        w = b[2]
        h = b[3]
        if w < min_wh_px or h < min_wh_px:
            i += 1
            continue
        out.append({"cls": name,
                    "bbox": [int(x), int(y), int(x + w), int(y + h)],
                    "score": score})
        i += 1
    return out
