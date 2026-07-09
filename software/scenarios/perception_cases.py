# PC-01.. -- Level-B perception cases (doc 07 §2): exercise the REAL perception pipeline
# (detector-agnostic ROI gating + tracker) on scripted detections and score its IF-2 output.
#
# Level A (catalogue.py) injects IF-2 events and tests the state machine. Level B
# (here) injects DETECTIONS (image bboxes) and tests the perception that PRODUCES those events
# -- ROI overlap geometry, track association/continuity, and speed estimation.
#
# Synthetic calibration: an affine image->ground homography at 0.05 m/px, and a shoulder ROI
# as a convex CCW ground quad. Object bboxes are in image pixels; ground contact =
# 0.05 * (bbox_centre_x, bbox_bottom_y). So pixel (400, 600) -> ground (20 m, 30 m), inside ROI.
#
# A per-checkpoint check may assert: n_detected, n_in_roi (in_roi >= roi_overlap_gate),
# speed_max / speed_min (km/h, over in-ROI tracks), max_in_roi_lt / max_in_roi_gt (the peak
# overlap fraction). A case may also assert `n_ids` (distinct track_ids over the WHOLE run --
# the ID-switch metric) and `loop_checks` [{t, on}] (the sign state from the closed loop:
# detections -> perception -> state machine -> sign). PC-06.. add the doc 07 §3.1 nuisances.

CALIB = {
    "H": [[0.05, 0.0, 0.0], [0.0, 0.05, 0.0], [0.0, 0.0, 1.0]],   # 0.05 m/px, affine
    "roi": [(10.0, 20.0), (25.0, 20.0), (25.0, 40.0), (10.0, 40.0)],  # shoulder ROI (CCW, m)
    "score_min": 0.4, "score_low": 0.1, "assoc_gate_m": 3.0,
    "track_max_age_s": 2.0,      # coast a lost track this long before retiring its id
    "speed_window_s": 0.5, "speed_alpha": 0.3,   # jitter-robust speed (baseline + EMA)
}

# A PERSPECTIVE camera calibration (≈6 m mast, 20° down-tilt, f≈500 px) for PC-11. The
# affine CALIB above has no perspective for a camera/depth footprint to exploit; here a real
# image->ground homography exists, so the projected footprint earns its keep near the ROI edge.
PERSP_CALIB = {
    "H": [[-0.11005911, 0.0, 35.21891663],
          [0.0, 0.03764243, -60.74505305],
          [0.0, -0.01723696, 1.0]],
    "roi": [(2.0, 15.0), (5.0, 15.0), (5.0, 55.0), (2.0, 55.0)],   # shoulder strip (CCW, m)
    "footprint_mode": "projected",
    "score_min": 0.4, "score_low": 0.1, "assoc_gate_m": 3.0,
    "track_max_age_s": 2.0, "speed_window_s": 0.5, "speed_alpha": 0.3,
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

    # --- PC-06..10: doc 07 §3.1 detector-nuisance robustness (the hardening increment) ---

    {
        "id": "PC-06", "title": "Box jitter on a stopped car -> no fake speed, still confirms",
        "duration": 22.0, "seed": 7,
        # A real stopped car, fully in ROI, with +/-4 px per-frame bbox jitter. Raw
        # frame-to-frame speed would spike to ~13 km/h (> the 3 km/h gate) and the car would
        # never confirm; the windowed + EMA estimate keeps it < gate so it confirms normally.
        "objects": [{"id": "gt1", "cls": "car", "enter": 1.0, "leave": 22.0,
                     "bbox": [360, 520, 440, 600], "jitter_px": 4.0}],   # ground (20, 30)
        "n_ids": 1,                                                       # jitter must not split the track
        "checks": [{"t": 8.0, "n_in_roi": 1, "speed_max": 2.5},          # jitter can't fake > gate
                   {"t": 14.0, "n_in_roi": 1, "speed_max": 2.5},
                   {"t": 20.0, "n_in_roi": 1, "speed_max": 2.5}],
        "loop_checks": [{"t": 12.0, "on": True}, {"t": 20.0, "on": True}],  # confirms despite jitter
    },
    {
        "id": "PC-07", "title": "Brief dropout -> track survives, no ID switch, no spurious clear",
        "duration": 25.0,
        # A confirmed stopped car; the detector misses it for 1.5 s (> the 1 s naive TTL).
        # Coasting keeps the SAME track_id, so the state machine holds the warning (no early
        # clear) and never restarts the dwell.
        "objects": [{"id": "gt1", "cls": "car", "enter": 1.0, "leave": 25.0,
                     "bbox": [360, 520, 440, 600], "drop": [[11.0, 12.5]]}],
        "n_ids": 1,                                                       # ONE id across the dropout
        "checks": [{"t": 10.0, "n_detected": 1, "n_in_roi": 1},
                   {"t": 11.8, "n_detected": 0},                         # detector is dark here
                   {"t": 13.0, "n_detected": 1, "n_in_roi": 1}],         # re-acquired, same id
        "loop_checks": [{"t": 10.0, "on": True}, {"t": 11.8, "on": True},   # held THROUGH the gap
                        {"t": 13.0, "on": True}, {"t": 20.0, "on": True}],
    },
    {
        "id": "PC-08", "title": "Transient false positives (shadow / headlight) -> never confirm",
        "duration": 10.0, "seed": 5,
        # No real vehicle. A flickering in-ROI shadow blip (present < T_dwell) and a fast
        # headlight sweep across the ROI. Neither dwells stationary long enough to confirm --
        # a jittering / false detection must NOT produce a false in-ROI confirmation.
        "false_detections": [
            {"id": "fp1", "cls": "car", "enter": 2.0, "leave": 5.5,      # in ROI (20, 30)
             "bbox": [360, 520, 440, 600], "jitter_px": 3.0, "drop": [[3.0, 3.3], [4.2, 4.5]]},
            {"id": "fp2", "cls": "car", "enter": 6.0, "leave": 7.0,      # headlight sweep, fast
             "path": [[6.0, [60, 560, 140, 600]], [7.0, [560, 560, 640, 600]]]},  # ground x 5->30
        ],
        "checks": [{"t": 2.5, "n_detected": 1, "max_in_roi_gt": 0.5}],   # blip IS seen, in ROI...
        "loop_checks": [{"t": 3.0, "on": False}, {"t": 5.0, "on": False},   # ...but never confirms
                        {"t": 6.5, "on": False}, {"t": 9.5, "on": False}],
    },
    {
        "id": "PC-09", "title": "Class confusion on a stopped car -> track stable, no spurious clear",
        "duration": 25.0,
        # A confirmed stopped car whose label flickers car->truck (bigger footprint) and even
        # car->person (which uses a different SM warrant path). Association is class-agnostic,
        # so the id is stable and the ROI overlap stays above gate -> the warning never drops.
        "objects": [{"id": "gt1", "cls": "car", "enter": 1.0, "leave": 25.0,
                     "bbox": [360, 520, 440, 600],
                     "confuse": [[7.0, 8.0, "truck"], [12.0, 13.0, "person"], [16.0, 17.0, "truck"]]}],
        "n_ids": 1,
        "checks": [{"t": 7.5, "n_in_roi": 1, "max_in_roi_gt": 0.9},      # mislabelled truck, still in ROI
                   {"t": 12.5, "n_in_roi": 1},                           # mislabelled person, still tracked
                   {"t": 20.0, "n_in_roi": 1}],
        "loop_checks": [{"t": 10.0, "on": True}, {"t": 12.5, "on": True},   # person flicker doesn't clear
                        {"t": 20.0, "on": True}],
    },
    {
        "id": "PC-10", "title": "Low-confidence dip (partial occlusion) -> two-stage recovers the track",
        "duration": 25.0,
        # The detector's score dips to 0.2 (below score_min 0.4) for 1.2 s -- a partial
        # occlusion. ByteTrack-style second-stage association matches the low-score box to the
        # existing track, so it stays detected (no gap) and keeps its id.
        "objects": [{"id": "gt1", "cls": "car", "enter": 1.0, "leave": 25.0,
                     "bbox": [360, 520, 440, 600], "score_drops": [[11.0, 12.2, 0.2]]}],
        "n_ids": 1,                                                       # recovered, not re-IDed
        "checks": [{"t": 10.0, "n_detected": 1, "n_in_roi": 1},
                   {"t": 11.5, "n_detected": 1, "n_in_roi": 1},          # low-score box still tracked
                   {"t": 13.0, "n_detected": 1, "n_in_roi": 1}],
        "loop_checks": [{"t": 10.0, "on": True}, {"t": 11.5, "on": True}, {"t": 20.0, "on": True}],
    },
    {
        "id": "PC-11", "title": "Perspective footprint -> faithful ROI overlap (no first-order cry-wolf)",
        "duration": 15.0, "calib": PERSP_CALIB,
        # A stationary car whose TRUE footprint is only ~45% inside the ROI (below the 50%
        # gate). Under a perspective camera the axis-aligned first-order box over-counts to
        # ~58% -> a FALSE in-ROI confirmation (cry-wolf, the dominant project risk). The
        # projected footprint reads ~42% -> correctly out, so the sign never lights.
        "objects": [{"id": "gt1", "cls": "car", "enter": 1.0, "leave": 15.0,
                     "bbox": [383, 133, 430, 172]}],
        "n_ids": 1,
        "checks": [{"t": 8.0, "n_detected": 1, "n_in_roi": 0,
                    "max_in_roi_gt": 0.35, "max_in_roi_lt": 0.5}],   # ~0.42, not the box's ~0.58
        "loop_checks": [{"t": 10.0, "on": False}],                    # no false confirmation
    },
]
