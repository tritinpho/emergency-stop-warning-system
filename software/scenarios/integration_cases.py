# IT-01.. -- Level-G integration cases (ADR-0016): drive the MERGED pipeline end to end,
# starting from RAW K230 YOLO output (the shape aidemo.yolov8_det_postprocess emits) instead
# of pre-shaped detections. Proves esw.k230_adapter is a faithful on-device counterpart of the
# host harness's frames.py: raw YOLO -> adapter -> REAL perception -> REAL state machine -> sign.
#
# Boxes are xywh in inference-frame pixels (top-left + size), exactly as the K230 emits them;
# the adapter converts to the [x1,y1,x2,y2] Perception expects. Ground contact = 0.05 *
# (bbox_centre_x, bbox_bottom_y) under the shared affine CALIB, so [360,520,80,80] -> centre
# (400,600) -> ground (20 m, 30 m), inside the shoulder ROI (reused from perception_cases).

from scenarios.perception_cases import CALIB   # one source of truth for the affine H + ROI

# A COCO-consistent label subset; class_ids index into this list.
#   person=0, bicycle=1, car=2, motorcycle=3, airplane=4, bus=5, train=6, truck=7
COCO_LABELS = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck"]


def yolo_frame(case, t):
    """The raw K230 postprocess result at time t: (boxes[xywh], class_ids, confidences).

    An object may carry `vx`/`vy` (image-plane px/s) to move at constant velocity from its `xywh`
    at `enter`. Crawling traffic needs this: a queue creeping above the stationarity gate produces
    NO stationary tracks, which is precisely the jam the R14 track-count rule cannot see."""
    boxes, class_ids, confs = [], [], []
    for o in case["objects"]:
        if o["enter"] <= t < o["leave"]:
            b = list(o["xywh"])
            dt = t - o["enter"]
            b[0] = b[0] + o.get("vx", 0.0) * dt
            b[1] = b[1] + o.get("vy", 0.0) * dt
            boxes.append(b)
            class_ids.append(o["cls_id"])
            confs.append(o["score"])
    return boxes, class_ids, confs


CASES = [
    {
        "id": "IT-01", "title": "stopped car in ROI -> sign lights after T_dwell (5 s)",
        "duration": 12.0,
        "objects": [{"cls_id": 2, "score": 0.90, "xywh": [360, 520, 80, 80],
                     "enter": 1.0, "leave": 12.0}],           # ground (20, 30), fully in ROI
        "loop_checks": [{"t": 3.0, "on": False},              # only ~2 s dwell -> still OFF
                        {"t": 10.0, "on": True}],             # confirmed + activated
    },
    {
        "id": "IT-02", "title": "pedestrian in ROI -> lights via presence-onset (person survives adapter)",
        "duration": 10.0,
        # Their vendored collect_vehicle_detections filtered `person` OUT (vehicle-only); the
        # adapter keeps it, so a stranded person on the shoulder still drives the warning (SC-12,
        # T_person_debounce = 1.5 s, no speed gate). This case fails if person is dropped.
        "objects": [{"cls_id": 0, "score": 0.85, "xywh": [360, 520, 80, 80],
                     "enter": 1.0, "leave": 10.0}],
        "loop_checks": [{"t": 0.5, "on": False},              # nothing present yet
                        {"t": 7.0, "on": True}],              # person confirmed
    },
    {
        "id": "IT-03", "title": "car OUTSIDE the ROI -> sign never lights (ROI gating holds)",
        "duration": 12.0,
        "objects": [{"cls_id": 2, "score": 0.90, "xywh": [60, 340, 80, 80],
                     "enter": 1.0, "leave": 12.0}],           # ground x=5, outside ROI
        "loop_checks": [{"t": 3.0, "on": False}, {"t": 10.0, "on": False}],
    },
    {
        "id": "IT-04", "title": "sub-25px blob in ROI -> adapter drops it, sign never lights",
        "duration": 12.0,
        # A 20x20 px blob at an in-ROI ground point. Without the adapter's noise floor it would
        # map to a full car footprint and confirm; the adapter drops it (baseline parity), so OFF.
        "objects": [{"cls_id": 2, "score": 0.90, "xywh": [370, 540, 20, 20],
                     "enter": 1.0, "leave": 12.0}],
        "loop_checks": [{"t": 10.0, "on": False}],
    },
]
