#!/usr/bin/env python3
"""Compile YOLOv8n to a K230 kmodel with the baseline toolchain (nncase 2.9.0) -- on a PC.

This is the CONVERSION half of a retrain pipeline, built and proven on the stock model
before anyone commits to training: ultralytics ONNX export (imgsz 320, the device's
MODEL_INPUT_SIZE) -> nncase import -> PTQ INT8 (calibrated on sample frames) -> target
k230 -> .kmodel, pinned by SHA-256 with a manifest. The artifact drives host_yolo_loop's
`--kmodel` simulator backend, so host-tier sessions can exercise the QUANTIZED model --
shrinking the host-vs-device gap to optics and runtime.

TWO machines, because the dependency sets must never meet: ultralytics (torch) lives on the
HOST, nncase lives in the toolchain CONTAINER -- on bare PyPI ultralytics drags the multi-GB
CUDA torch stack, so the container deliberately has neither (see nncase/Dockerfile).

    # 1. HOST: .pt -> .onnx (ultralytics is installed here)
    python software/tools/compile_kmodel.py --export-only

    # 2. CONTAINER: .onnx -> k230 INT8 kmodel + manifest + simulator smoke
    docker build -t esw-nncase:2.9.0 software/tools/nncase
    docker run --rm -v "<repo>:/w" -w /w esw-nncase:2.9.0 \\
        python software/tools/compile_kmodel.py \\
        --onnx firmware/k230-detector/models/host-parity/yolov8n.onnx \\
        --sample <some-frame.jpg> --out firmware/k230-detector/models/host-parity

Calibration honesty: PTQ ranges come from the frames you pass via --calib-images (your own
footage stills are the right choice); the fallback is jitter-augmented copies of --sample,
which is enough for a parity instrument and nowhere near enough for a production
quantization -- the manifest records exactly what was used.

The input convention is float32 RGB NCHW /255 (ultralytics'), applied identically at
calibration, at simulation (host_yolo_loop.KmodelSimDetector) and in this script's smoke
test -- the kmodel never sees a preprocessing the consumer does not apply.
"""

import argparse
import datetime
import glob
import hashlib
import json
import os
import sys

import numpy as np

IMGSZ = 320


def letterbox_blob(bgr, imgsz=IMGSZ):
    """BGR frame -> (float32 NCHW RGB /255 blob, scale, pad) with gray letterbox padding --
    the ultralytics convention, mirrored by host_yolo_loop.KmodelSimDetector."""
    import cv2
    h, w = bgr.shape[:2]
    r = min(imgsz / h, imgsz / w)
    nh, nw = int(round(h * r)), int(round(w * r))
    top = (imgsz - nh) // 2
    left = (imgsz - nw) // 2
    canvas = np.full((imgsz, imgsz, 3), 114, dtype=np.uint8)
    canvas[top:top + nh, left:left + nw] = cv2.resize(bgr, (nw, nh))
    blob = canvas[:, :, ::-1].astype(np.float32) / 255.0        # BGR -> RGB, /255
    return np.ascontiguousarray(blob.transpose(2, 0, 1))[None], r, (left, top)


def _sample_paths(calib_glob, sample):
    if calib_glob:
        paths = sorted(glob.glob(calib_glob))
        if not paths:
            sys.exit("--calib-images matched nothing: %s" % calib_glob)
        return paths, "user frames: %s (%d)" % (calib_glob, len(paths))
    if sample:
        return [sample], "jitter-augmented --sample %s (PARITY-GRADE ONLY, not production PTQ)" % sample
    try:
        import ultralytics
    except ImportError:
        sys.exit("no --calib-images / --sample, and ultralytics is not installed here "
                 "(the container deliberately has no torch): pass --sample <frame.jpg>")
    assets = os.path.join(os.path.dirname(ultralytics.__file__), "assets")
    paths = [os.path.join(assets, n) for n in ("bus.jpg", "zidane.jpg")]
    return paths, "ultralytics sample images (PARITY-GRADE ONLY, not production PTQ)"


def export_onnx(weights, out_dir):
    try:
        from ultralytics import YOLO
    except ImportError:
        sys.exit("ONNX export needs ultralytics -- run `compile_kmodel.py --export-only` "
                 "on the HOST (pip install ultralytics), not in the toolchain container")
    model = YOLO(weights)
    onnx_path = model.export(format="onnx", imgsz=IMGSZ, opset=13, simplify=True)
    dst = os.path.join(out_dir, os.path.basename(onnx_path))
    if os.path.abspath(onnx_path) != os.path.abspath(dst):
        os.replace(onnx_path, dst)
    return dst


def compile_kmodel(onnx_path, samples, out_path):
    """ONNX -> k230 kmodel, PTQ INT8. The set_tensor_data call shape changed across nncase
    2.x minors, so both known forms are tried -- whichever the pinned 2.9.0 accepts is
    recorded in the manifest by the caller printing our return value."""
    import nncase

    compile_options = nncase.CompileOptions()
    compile_options.target = "k230"
    compile_options.preprocess = False          # consumers feed the exact float blob above
    compile_options.dump_ir = False
    compile_options.dump_asm = False
    compiler = nncase.Compiler(compile_options)

    with open(onnx_path, "rb") as f:
        model_content = f.read()
    import_options = nncase.ImportOptions()
    compiler.import_onnx(model_content, import_options)

    ptq_options = nncase.PTQTensorOptions()
    ptq_options.samples_count = len(samples)
    api_form = None
    try:
        ptq_options.set_tensor_data([[s] for s in samples])     # 2.x list-of-inputs form
        api_form = "list[list[ndarray]]"
    except (TypeError, RuntimeError):
        ptq_options.set_tensor_data(
            np.concatenate([s.reshape(-1) for s in samples]).astype(np.float32).tobytes())
        api_form = "flat bytes"
    compiler.use_ptq(ptq_options)
    compiler.compile()
    kmodel = compiler.gencode_tobytes()
    with open(out_path, "wb") as f:
        f.write(kmodel)
    return api_form


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def smoke(kmodel_path, image_path):
    """Run the compiled kmodel in the nncase simulator on one image and decode it with the
    same postprocess the sim backend uses: the compile is not 'done' until the INT8 model
    still finds a vehicle and a person in the sample scene."""
    import cv2
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from host_yolo_loop import KmodelSimDetector
    det = KmodelSimDetector(kmodel_path)
    det.set_frame(cv2.imread(image_path))
    raw = det.read()
    if raw is None:
        return False, "simulator returned nothing"
    from esw.k230_adapter import detections_from_yolo
    dets = detections_from_yolo(raw[0], raw[1], raw[2], det.labels)
    classes = sorted(set(d["cls"] for d in dets))
    ok = bool(set(classes) & {"car", "truck", "bus"}) and "person" in classes
    return ok, "decoded classes: %s" % classes


def main():
    ap = argparse.ArgumentParser(description="YOLOv8n -> K230 kmodel (nncase 2.9.0) + manifest.")
    ap.add_argument("--weights", default="yolov8n.pt", help="(host, --export-only) .pt weights")
    ap.add_argument("--export-only", action="store_true",
                    help="HOST step: export the ONNX and stop (needs ultralytics)")
    ap.add_argument("--onnx", default=None,
                    help="CONTAINER step: pre-exported ONNX to compile (skips ultralytics)")
    ap.add_argument("--out", default="firmware/k230-detector/models/host-parity",
                    help="output directory")
    ap.add_argument("--sample", default=None,
                    help="an image for the simulator smoke test + fallback PTQ calibration")
    ap.add_argument("--calib-images", default=None,
                    help="glob of frames for PTQ calibration (use YOUR footage; fallback: "
                         "jitter-augmented --sample -- parity-grade only)")
    ap.add_argument("--samples", type=int, default=8,
                    help="calibration sample count (images are jitter-augmented up to this)")
    args = ap.parse_args()

    # software/ on the path for the smoke test's imports.
    sw = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, sw)

    os.makedirs(args.out, exist_ok=True)

    if args.export_only:
        onnx_path = export_onnx(args.weights, args.out)
        print("ONNX exported: %s" % onnx_path)
        print("weights sha256: %s" % sha256(args.weights))
        print("next: compile it in the toolchain container (see software/tools/nncase/Dockerfile)")
        return 0

    import cv2
    import nncase

    # nncase exposes no __version__ attribute; the package metadata carries it.
    try:
        import importlib.metadata as _md
        nncase_ver = _md.version("nncase")
    except Exception:
        nncase_ver = "unknown"

    if args.onnx:
        print("[1/4] using pre-exported ONNX: %s" % args.onnx)
        onnx_path = args.onnx
        if not os.path.exists(onnx_path):
            sys.exit("no such ONNX: %s (host step: compile_kmodel.py --export-only)" % onnx_path)
    else:
        print("[1/4] ONNX export (imgsz %d, opset 13)" % IMGSZ)
        onnx_path = export_onnx(args.weights, args.out)

    print("[2/4] PTQ calibration set")
    paths, calib_desc = _sample_paths(args.calib_images, args.sample)
    samples = []
    rng = np.random.RandomState(42)
    while len(samples) < args.samples:
        p = paths[len(samples) % len(paths)]
        img = cv2.imread(p)
        if img is None:
            sys.exit("cannot read calibration image: %s" % p)
        if len(samples) >= len(paths):          # jitter-augment beyond the raw images
            dx, dy = rng.randint(-6, 7), rng.randint(-6, 7)
            m = np.float32([[1, 0, dx], [0, 1, dy]])
            img = cv2.warpAffine(img, m, (img.shape[1], img.shape[0]),
                                 borderMode=cv2.BORDER_REPLICATE)
        samples.append(letterbox_blob(img)[0])
    print("      %d samples -- %s" % (len(samples), calib_desc))

    print("[3/4] nncase %s compile -> k230 INT8" % nncase_ver)
    kmodel_path = os.path.join(args.out, "yolov8n_320_int8.kmodel")
    api_form = compile_kmodel(onnx_path, samples, kmodel_path)
    digest = sha256(kmodel_path)

    print("[4/4] simulator smoke test")
    ok, detail = smoke(kmodel_path, paths[0])
    print("      %s -- %s" % ("PASS" if ok else "FAIL", detail))

    manifest = {
        "kmodel": os.path.basename(kmodel_path),
        "sha256": digest,
        "bytes": os.path.getsize(kmodel_path),
        "built": datetime.date.today().isoformat(),
        "source_weights": os.path.basename(args.weights),
        "source_weights_sha256": sha256(args.weights) if os.path.exists(args.weights) else None,
        "source_onnx": os.path.basename(onnx_path),
        "source_onnx_sha256": sha256(onnx_path),
        "toolchain": {"nncase": nncase_ver, "target": "k230",
                      "opset": 13, "imgsz": IMGSZ, "ptq": "int8",
                      "set_tensor_data_form": api_form},
        "input": "float32 RGB NCHW /255, 320x320 letterbox(114)",
        "calibration": calib_desc,
        "smoke": detail,
        "purpose": ("host-parity instrument for tools/host_yolo_loop.py --kmodel; also the "
                    "proven conversion path a future retrain would reuse (models/README.md)"),
    }
    mpath = os.path.join(args.out, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print("")
    print("kmodel : %s (%d bytes)" % (kmodel_path, manifest["bytes"]))
    print("sha256 : %s" % digest)
    print("manifest: %s" % mpath)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
