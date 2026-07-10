# The K230 detector, as an esw.app.EdgeApp backend (IF-1).
#
# PROVENANCE: EswDetector's preprocess/postprocess and load_model_config's guard are a faithful
# mirror of the vendored baseline `k230/main.py` (ObjectDetectionApp, load_model_config) -- the
# code ACLAB ELMS device-tested at ~30 FPS. It is mirrored rather than imported because their
# main.py is a ~2800-line application script that runs the whole ELMS app on import. Per
# ADR-0016 the device baseline is not to be modernised: if their inference core changes, change
# this to match, do not "improve" it here.
#
# The one deliberate difference is upstream of here: their collect_vehicle_detections() filtered
# `person` out. We keep every COCO class the adapter cares about and let esw.k230_adapter do the
# filtering, because a stranded person on the shoulder must still drive the warning (SC-12).

from libs.AIBase import AIBase
from libs.AI2D import Ai2d
from libs.PipeLine import ScopedTiming
from libs.Utils import letterbox_pad_param
from media.media import ALIGN_UP
import aidemo
import nncase_runtime as nn
import ujson
import ulab.numpy as np

# What the device actually loads. `k230/main.py::load_model_config` refuses every AnchorBaseDet /
# best_* path, so the two custom single-class kmodels are dead and the SD-card fallback runs.
FALLBACK_KMODEL = "/sdcard/kmodel/yolov8n_320.kmodel"

COCO80 = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake",
    "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop",
    "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush",
]


def load_model_config(mode="day"):
    """Resolve the kmodel + label set, keeping the baseline's AnchorBaseDet guard.

    Deleting that guard -- or renaming a kmodel so it no longer matches "best_" -- silently loads
    a single-class model. The unit would still light the sign for a shoulder car while being blind
    to pedestrians, and every host scenario would stay green. EdgeApp's boot capability report is
    what turns that from a silent loss into a CRITICAL record (esw/app.py, ADR-0005)."""
    path = "/sdcard/model/mp_deployment_source_%s/deploy_config.json" % mode
    try:
        f = open(path, "r")
        try:
            conf = ujson.load(f)
        finally:
            f.close()
        kmodel = "/sdcard/model/mp_deployment_source_%s/%s" % (mode, conf["kmodel_path"])
        if "AnchorBaseDet" in kmodel or "best_" in kmodel:
            raise ValueError("AnchorBaseDet not supported, forcing fallback")
        return {"kmodel_path": kmodel,
                "labels": conf.get("categories", COCO80),
                "confidence_threshold": conf.get("confidence_threshold", 0.5),
                "nms_threshold": conf.get("nms_threshold", 0.2)}
    except Exception as e:
        print("[MODEL] %s config unusable (%s) -- falling back to %s" % (mode, e, FALLBACK_KMODEL))
        return {"kmodel_path": FALLBACK_KMODEL, "labels": COCO80,
                "confidence_threshold": 0.5, "nms_threshold": 0.2}


class EswDetector(AIBase):
    """YOLOv8 on the KPU. run(img) -> (boxes[xywh], class_ids, confidences) or []."""

    def __init__(self, kmodel_path, labels, model_input_size=None, rgb888p_size=None,
                 display_size=None, max_boxes_num=20, confidence_threshold=0.5,
                 nms_threshold=0.2, debug_mode=0):
        model_input_size = model_input_size or [320, 320]
        rgb888p_size = rgb888p_size or [320, 320]
        display_size = display_size or [640, 480]
        super().__init__(kmodel_path, model_input_size, rgb888p_size, debug_mode)
        self.labels = labels
        self.model_input_size = model_input_size
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.max_boxes_num = max_boxes_num
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0], 16), rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0], 16), display_size[1]]
        self.debug_mode = debug_mode
        self.ai2d = Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT, nn.ai2d_format.NCHW_FMT,
                                 np.uint8, np.uint8)

    def config_preprocess(self, input_image_size=None):
        with ScopedTiming("set preprocess config", self.debug_mode > 0):
            size = input_image_size if input_image_size else self.rgb888p_size
            top, bottom, left, right, self.scale = letterbox_pad_param(
                self.rgb888p_size, self.model_input_size)
            self.ai2d.pad([0, 0, 0, 0, top, bottom, left, right], 0, [128, 128, 128])
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build([1, 3, size[1], size[0]],
                            [1, 3, self.model_input_size[1], self.model_input_size[0]])

    def preprocess(self, input_np):
        with ScopedTiming("preprocess", self.debug_mode > 0):
            return [self.ai2d.run(input_np)]

    def postprocess(self, results):
        with ScopedTiming("postprocess", self.debug_mode > 0):
            new_result = results[0][0].transpose()
            return aidemo.yolov8_det_postprocess(
                new_result.copy(),
                [self.rgb888p_size[1], self.rgb888p_size[0]],
                [self.model_input_size[1], self.model_input_size[0]],
                [self.display_size[1], self.display_size[0]],
                len(self.labels), self.confidence_threshold, self.nms_threshold,
                self.max_boxes_num)


class K230Detector:
    """The EdgeApp `detector` backend: .labels and .read().

    read() must distinguish two things the loop treats very differently:
      * a frame that contained NO objects  -> ([], [], [])  the camera is ALIVE and saw nothing
      * no frame / a failed inference      -> None          a dropped frame, or a dead camera

    Returning [] for a dead camera would make the unit permanently, silently blind: the health
    monitor would call the camera healthy and the state machine would sit in IDLE forever."""

    def __init__(self, pipeline, det):
        self.pl = pipeline
        self.det = det
        self.labels = det.labels
        self.misses = 0
        self.frames = 0

    def read(self):
        img = self.pl.get_frame()
        if img is None:
            self.misses += 1
            return None
        try:
            res = self.det.run(img)
        except Exception as e:                 # inference failure is a dropped frame, never an empty one
            print("[DET] inference error:", e)
            self.misses += 1
            return None
        self.frames += 1
        if not res or len(res) < 3:
            return [], [], []
        return res[0], res[1], res[2]
