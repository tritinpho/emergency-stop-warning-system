# PC-01.. -- Level-B perception cases (doc 07 §2): exercise the REAL perception pipeline
# (detector-agnostic ROI gating + tracker) on scripted detections and score its IF-2 output.
#
# Level A (SC-01..30, catalogue.py) injects IF-2 events and tests the state machine. Level B
# (here) injects DETECTIONS (image bboxes) and tests the perception that PRODUCES those events
# -- ROI overlap geometry, track association/continuity, and speed estimation.
#
# Synthetic calibration: an affine image->ground homography at 0.05 m/px, and a shoulder ROI
# as a convex CCW ground quad. Object bboxes are in image pixels; ground contact =
# 0.05 * (bbox_centre_x, bbox_bottom_y). So pixel (400, 600) -> ground (20 m, 30 m), inside ROI.
#
# A check may assert: n_detected, n_in_roi (in_roi >= roi_overlap_gate), speed_max / speed_min
# (km/h, over in-ROI tracks), max_in_roi_lt / max_in_roi_gt (the peak overlap fraction).

CALIB = {
    "H": [[0.05, 0.0, 0.0], [0.0, 0.05, 0.0], [0.0, 0.0, 1.0]],   # 0.05 m/px, affine
    "roi": [(10.0, 20.0), (25.0, 20.0), (25.0, 40.0), (10.0, 40.0)],  # shoulder ROI (CCW, m)
    "score_min": 0.4, "assoc_gate_m": 3.0, "track_ttl_s": 1.0,
}

CASES = [
    {
        "id": "PC-01", "title": "Car stopped inside ROI -> in_roi ~ 1.0, speed ~ 0",
        "duration": 25.0,
        "objects": [{"id": "gt1", "cls": "car", "enter": 1.0, "leave": 25.0,
                     "bbox": [360, 520, 440, 600]}],   # ground (20, 30), fully in ROI
        "checks": [{"t": 5.0, "n_detected": 1, "n_in_roi": 1, "speed_max": 0.5},
                   {"t": 15.0, "n_in_roi": 1, "speed_max": 0.5}],
    },
    {
        "id": "PC-02", "title": "Pass-through outside ROI -> detected, never in_roi",
        "duration": 8.0,
        "objects": [{"id": "gt1", "cls": "car", "enter": 1.0, "leave": 7.0,
                     "path": [[1.0, [60, 340, 140, 420]],     # ground x=5 (outside ROI)
                              [6.0, [60, 620, 140, 700]]]}],
        "checks": [{"t": 3.0, "n_detected": 1, "n_in_roi": 0},
                   {"t": 5.0, "n_in_roi": 0}],
    },
    {
        "id": "PC-03", "title": "Footprint straddles ROI edge -> partial in_roi below gate",
        "duration": 16.0,
        "objects": [{"id": "gt1", "cls": "car", "enter": 1.0, "leave": 16.0,
                     "bbox": [466, 520, 546, 600]}],   # ground (25.3, 30): ~0.35 overlap
        "checks": [{"t": 8.0, "n_detected": 1, "n_in_roi": 0,
                    "max_in_roi_gt": 0.2, "max_in_roi_lt": 0.5}],
    },
    {
        "id": "PC-04", "title": "Two vehicles stopped in ROI -> two stable in-ROI tracks",
        "duration": 20.0,
        "objects": [{"id": "gt1", "cls": "car", "enter": 1.0, "leave": 20.0,
                     "bbox": [360, 520, 440, 600]},    # ground (20, 30)
                    {"id": "gt2", "cls": "car", "enter": 1.0, "leave": 20.0,
                     "bbox": [260, 480, 340, 560]}],   # ground (15, 28)
        "checks": [{"t": 8.0, "n_detected": 2, "n_in_roi": 2}],
    },
    {
        "id": "PC-05", "title": "Vehicle moving through ROI then stopping -> speed tracks",
        "duration": 13.0,
        "objects": [{"id": "gt1", "cls": "car", "enter": 1.0, "leave": 13.0,
                     "path": [[1.0, [260, 560, 340, 600]],    # ground x=15
                              [5.0, [420, 560, 500, 600]],    # ground x=23 (~2 m/s -> 7.2 km/h)
                              [12.0, [420, 560, 500, 600]]]}],  # held -> speed decays to 0
        "checks": [{"t": 3.0, "n_in_roi": 1, "speed_min": 5.0, "speed_max": 10.0},  # moving
                   {"t": 8.0, "n_in_roi": 1, "speed_max": 1.0}],                     # stopped
    },
]
