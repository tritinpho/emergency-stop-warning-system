# The nncase 2.9.0 toolchain container -- the K230 baseline's converter, on any PC.
#
# No nncase wheel exists for this repo's host Python (3.14/Windows), and the toolchain
# version is pinned by the device baseline (Yahboom image 1.4.1 = nncase/kmodel 2.9.0,
# firmware/k230-detector/design-log/AGENTS-k230-baseline.md) -- so the conversion and the
# kmodel SIMULATOR run in here. torch is installed from the CPU index first so ultralytics
# does not drag the multi-GB CUDA wheels into the image.
#
#   docker build -t esw-nncase:2.9.0 software/tools/nncase
#   docker run --rm -v "<repo>:/w" -w /w esw-nncase:2.9.0 \
#       python software/tools/compile_kmodel.py --out firmware/k230-detector/models/host-parity
#   docker run --rm -v "<repo>:/w" -w /w esw-nncase:2.9.0 \
#       python software/tools/host_yolo_loop.py --selftest \
#       --kmodel firmware/k230-detector/models/host-parity/yolov8n_320_int8.kmodel

FROM python:3.10-slim

# libgl/libglib: opencv (an ultralytics dependency) needs them even headless on -slim.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "numpy<2" \
    && pip install --no-cache-dir nncase==2.9.0 nncase-kpu==2.9.0 \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install --no-cache-dir ultralytics onnx

WORKDIR /w
