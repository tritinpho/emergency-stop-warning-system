# The nncase 2.9.0 toolchain container -- the K230 baseline's converter, on any PC.
#
# No nncase wheel exists for this repo's host Python (3.14/Windows), and the toolchain
# version is pinned by the device baseline (Yahboom image 1.4.1 = nncase/kmodel 2.9.0,
# firmware/k230-detector/design-log/AGENTS-k230-baseline.md) -- so the conversion and the
# kmodel SIMULATOR run in here.
#
# DELIBERATELY NO torch / ultralytics: on bare PyPI, ultralytics drags the multi-GB CUDA
# torch stack into the image (measured, and it is what broke the first build of this file).
# The ONNX export runs on the HOST, where ultralytics already lives:
#
#   python software/tools/compile_kmodel.py --export-only            # host: .pt -> .onnx
#   docker build -t esw-nncase:2.9.0 software/tools/nncase
#   docker run --rm -v "<repo>:/w" -w /w esw-nncase:2.9.0 \
#       python software/tools/compile_kmodel.py \
#       --onnx firmware/k230-detector/models/host-parity/yolov8n.onnx \
#       --calib-images "captures/calib-frames/*.jpg" \
#       --out firmware/k230-detector/models/host-parity
#   docker run --rm -v "<repo>:/w" -w /w esw-nncase:2.9.0 \
#       python software/tools/host_yolo_loop.py --selftest --sample <frame.jpg> \
#       --kmodel firmware/k230-detector/models/host-parity/yolov8n_320_int8.kmodel
#
# (On Git Bash prefix docker run with MSYS_NO_PATHCONV=1 so -w /w survives path mangling.)

FROM python:3.10-slim

# The nncase 2.x compiler is .NET-hosted -- without a dotnet runtime `import nncase` dies
# with "Failed to get hostfxr path". nncase 2.9.0's runtimeconfig pins "tfm": "net7.0", so
# 8.0 alone yields "Failed to initialize hostfxr: 0x80008096" (a net7 app will not roll
# forward to a higher major unless opted in) -- install the exact 7.0 runtime it targets.
# Invariant globalization skips the ICU dependency.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh \
    && bash /tmp/dotnet-install.sh --channel 7.0 --runtime dotnet --install-dir /usr/share/dotnet \
    && rm /tmp/dotnet-install.sh
ENV DOTNET_ROOT=/usr/share/dotnet \
    PATH="/usr/share/dotnet:${PATH}" \
    DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1

# numpy pinned <2: nncase 2.9.0 wheels were built in the numpy-1.x era, and opencv 4.10
# headless is the matching cv2. One pip resolve so the set is consistent.
RUN pip install --no-cache-dir \
    "numpy<2" nncase==2.9.0 nncase-kpu==2.9.0 "opencv-python-headless<4.11" onnx

# nncase 2.9.0's libortki.so (its ONNX shape-inference kernels) is marked as requiring an
# executable stack; a hardened loader refuses it and the ONNX import segfaults. execstack and
# patchelf are absent from -slim, so a dependency-free ELF patcher clears the PT_GNU_STACK
# PF_X bit at build time. See clear_execstack.py for the why.
COPY clear_execstack.py /opt/clear_execstack.py
RUN python /opt/clear_execstack.py /usr/local/lib/python3.10/site-packages/nncase/libortki.so

# The k230 PTQ + simulator invoke `nncase.simulator.k230.sc` by name via a shell; pip drops it
# in site-packages, not on PATH, so make it findable and executable.
RUN chmod +x /usr/local/lib/python3.10/site-packages/nncase.simulator.k230.sc \
    && ln -sf /usr/local/lib/python3.10/site-packages/nncase.simulator.k230.sc \
       /usr/local/bin/nncase.simulator.k230.sc

WORKDIR /w
