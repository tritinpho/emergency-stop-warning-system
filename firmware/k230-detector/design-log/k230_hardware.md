# Yahboom K230 AI Vision Recognition Camera Module Specifications

Tài liệu này chứa thông số kỹ thuật và cấu hình phần cứng của thiết bị **Yahboom K230 AI Vision Recognition Camera Module** được sử dụng trong dự án.

## Tổng quan

Yahboom K230 AI Vision Recognition Camera Module là một camera AI thông minh hiệu năng cao, thiết kế cho các ứng dụng thị giác máy và edge computing. Sản phẩm tích hợp sẵn camera, màn hình cảm ứng, WiFi và bộ xử lý AI mạnh mẽ, giúp người dùng triển khai nhanh các bài toán nhận dạng hình ảnh mà không cần hệ thống phức tạp. Đây là giải pháp lý tưởng cho giáo dục STEM, robot, IoT và các dự án AI nhúng.

Sản phẩm sử dụng chip K230 kiến trúc RISC-V với năng lực xử lý AI lên đến 6 TOPS, hỗ trợ hơn 30 chức năng AI có sẵn như nhận dạng khuôn mặt, nhận dạng vật thể, theo dõi đối tượng, nhận dạng tư thế người, mã QR/Barcode và biển báo,... Giao diện đồ họa được cài đặt sẵn cho phép trải nghiệm và thử nghiệm AI trực quan.

Hỗ trợ lập trình bằng MicroPython thông qua CanMV IDE, dễ dàng kết nối với các vi điều khiển và máy tính nhúng như ESP32, STM32 hay Raspberry Pi.

---

## Thông số kỹ thuật chi tiết

| Thành phần | Thông số chi tiết |
| :--- | :--- |
| **Model** | Yahboom K230 AI Vision Recognition Camera Module |
| **CPU** | **CPU 0**: RISC-V @ 0.8 GHz, 32KB I-cache, 32KB D-cache, 128KB L2 cache<br>**CPU 1**: RISC-V @ 1.6 GHz, 32KB I-cache, 32KB D-cache, 256KB L2 cache, RVV 1.0 128-bit |
| **RAM** | 1 GB LPDDR4 |
| **KPU (AI Accelerator)** | 6 TOPS, hỗ trợ định dạng INT8 và INT6<br>- *ResNet-50*: > 85 fps @ INT8<br>- *MobileNet-V2*: > 670 fps @ INT8<br>- *YOLOv5s*: > 36 fps @ INT8 |
| **DPU** | Engine đo chiều sâu ánh sáng cấu trúc 3D, độ phân giải tối đa 1920 × 1080 |
| **VPU** | Mã hóa/giải mã H.264 & H.265 (tối đa 4096 × 4096)<br>- *Mã hóa*: 3840 × 2160 @ 20 fps<br>- *Giải mã*: 3840 × 2160 @ 40 fps<br>- *Codec JPEG*: tối đa 8K (8192 × 8192) |
| **Màn hình** | LCD cảm ứng điện dung 2.4 inch, độ phân giải 640 × 480 (ST7701 hoặc tương thích) |
| **Camera** | HD 2MP tích hợp sẵn (Cảm biến GC2093) |
| **Kết nối mạng** | Card mạng WiFi tích hợp |
| **Lưu trữ** | Khe cắm thẻ nhớ TF/MicroSD (mặc định đi kèm thẻ 8GB đã cài đặt OS) |
| **Nguồn cấp** | 5 V qua cổng Type-C hoặc 5 V qua chân GPIO (Công suất ~4 W, Dòng hoạt động ~0.8 A) |
| **Giao tiếp tích hợp** | Microphone, buzzer, đèn RGB, cổng loa, cổng quạt, cổng Type-C, giao tiếp Serial, GPIO mở rộng |
| **Kích thước & Nút** | 72 × 46 × 18.7 mm, Trọng lượng: 64.9 g<br>Nút Reset + Nút chức năng tùy chỉnh (KEY) |
| **Môi trường lập trình** | MicroPython thông qua CanMV IDE |

---

## Bộ sản phẩm bao gồm

1. Yahboom K230 Deluxe Kit x 1
2. Thẻ nhớ MicroSD 8GB cài sẵn Hệ điều hành (CanMV OS) x 1

---

## Baseline firmware của dự án

`k230-firmware/` là bản sao nội dung SD-card đã chạy trên thiết bị và là nguồn chuẩn cho mọi code K230 được tạo hoặc chỉnh sửa trong repository này.

| Thuộc tính | Giá trị chuẩn | Nguồn |
| :--- | :--- | :--- |
| Image release | `1.4.1` — phát hành `2025-08-20` | `k230-firmware/Version.txt` |
| Build time | `2025-08-20 12:19:26 CST` | `k230-firmware/revision.txt` |
| GUI OS | `YAHBOOM K230 GUI 2.0` | `configs/sys_config.json` |
| Hardware revision | `1.4` | `configs/sys_config.json` |
| nncase/kmodel toolchain | `2.9.0` | tài liệu burn firmware và các `deploy_config.json` |
| GUI framework | LVGL `8.3` | tài liệu GUI Yahboom |

> `SYS_INFO.fw_version: "1.0"` trong `sys_config.json` là metadata của GUI, không phải version image SD-card. Màn hình Settings hiện cũng không đọc giá trị này mà hiển thị firmware là `--`. Khi xác định compatibility, luôn dùng `Version.txt` và toolchain nncase.

## Kiến trúc phần mềm runtime

Luồng xử lý chuẩn trên thiết bị:

```text
main.py / app
    │
    ├── PipeLine ── Sensor CH0 (YUV420) ──> Display video layer
    │           └── Sensor CH2 (RGB888 planar) ──> ndarray
    │
    ├── AIBase ──> Ai2d preprocess ──> nncase KPU ──> output tensors
    │
    ├── aidemo postprocess ──> boxes/classes/scores
    │
    └── ARGB8888 OSD ──> Display OSD layer
```

Các thành phần tương thích nằm trong `k230-firmware/libs/`:

- `PipeLine.py`: sở hữu sensor, display, media buffers và OSD.
- `AIBase.py`: nạp `.kmodel`, gán tensor input, chạy KPU và lấy tensor output.
- `AI2D.py`: crop, pad, resize, affine và tạo tensor đầu vào cho model.
- `Utils.py`: alignment, màu, letterbox và chuyển đổi layout ảnh.
- `YOLO.py`: contract tham chiếu cho classify/detect/segment/OBB.

Code mới phải ưu tiên các implementation này thay vì sao chép API từ một phiên bản CanMV upstream khác.

## Camera và display pipeline

| Kênh / lớp | Format | Mục đích | Setting chuẩn |
| :--- | :--- | :--- | :--- |
| Sensor CH0 | `PIXEL_FORMAT_YUV_SEMIPLANAR_420` | Video trực tiếp ra display | bind vào `Display.LAYER_VIDEO1` |
| Sensor CH1 | `PIXEL_FORMAT_RGB_565` | Capture/GUI phụ trợ | mặc định `640 × 480` |
| Sensor CH2 | `PIXEL_FORMAT_RGB_888_PLANAR` | Input cho AI | width phải căn 16 pixel |
| OSD | `image.ARGB8888` | ROI, label, bounding box | `Display.LAYER_OSD3` |
| LCD | ST7701 | Hiển thị tích hợp | mode `lcd`, `640 × 480` |

`PipeLine.create()` trong baseline khởi tạo sensor ở 30 fps, dù tham số public hiện có default `fps=60`. Không được suy luận FPS thực tế chỉ từ default của hàm; implementation tạo `Sensor(fps=30)` trên các board được hỗ trợ.

Thứ tự khởi tạo chuẩn:

1. Tạo `PipeLine` với `rgb888p_size`, `display_size`, `display_mode`.
2. Gọi `pl.create()` để reset/config sensor, init display và media buffers, rồi chạy sensor.
3. Tạo model app và gọi `config_preprocess()`.
4. Trong vòng lặp: `pl.get_frame()` → `app.run()` → `draw_result()` → `pl.show_image()`.
5. Khi thoát: `app.deinit()` trước, sau đó `pl.destroy()`.

## Quy ước kích thước và tensor

Ba quy ước cùng tồn tại và không được tráo thứ tự:

| Ngữ cảnh | Quy ước |
| :--- | :--- |
| Kích thước application/model/display | `[width, height]` |
| Shape tensor AI2D | `[1, 3, height, width]` (`NCHW`) |
| Tham số kích thước của `aidemo` postprocess | `[height, width]` |

Width của `rgb888p_size` và `display_size` được căn lên bội số 16 bằng `ALIGN_UP`. Với YOLO detection, preprocessing chuẩn là:

1. Tính padding bằng `letterbox_pad_param(input_size, model_input_size)`.
2. Pad theo `[0, 0, 0, 0, top, bottom, left, right]` với màu `[128, 128, 128]`.
3. Resize bằng `nn.interp_method.tf_bilinear` và `nn.interp_mode.half_pixel`.
4. Build AI2D input/output theo NCHW.

Postprocess YOLOv8 detection sử dụng `aidemo.yolov8_det_postprocess`. Model, input size, danh sách label, số class, threshold và postprocess phải được xem là một bộ tham số thống nhất; không được đổi riêng một thành phần.

## Setting mặc định của image

Các giá trị dưới đây mô tả image baseline, không phải cấu hình production bắt buộc:

| Nhóm | Setting baseline |
| :--- | :--- |
| Sensor CH1 | `640 × 480` |
| Display brightness | `69` |
| Wallpaper | `/sdcard/resources/wallpaper.png` |
| Wi-Fi station | tắt (`status: 0`), credential placeholder |
| Access point | SSID `YAHBOOM-K230`, tắt mặc định, password mẫu `12345678` |
| Sound volume | `59` |
| Language | English |
| Face recognition safety | bật |
| Keyword spotting safety | tắt |

Credential và API key trong image chỉ là dữ liệu cấu hình mẫu/thiết bị. Không tái sử dụng chúng khi sinh code, không commit credential production và không coi chúng là secret hợp lệ.

## Baseline cho code generation

- Trước khi sinh code, tìm example gần nhất trong `k230-firmware/apps/` hoặc `k230-firmware/src/`, rồi kiểm tra contract trong `k230-firmware/libs/`.
- Đối chiếu thêm chương tương ứng trong `K230-docs/`; nếu docs và code chạy được khác nhau, ưu tiên firmware baseline và ghi lại sai khác.
- Dùng đúng `.kmodel` đã build bằng nncase `2.9.0`, hoặc convert lại model và kiểm thử trực tiếp trên K230.
- Với COCO YOLOv8, giữ đủ 80 labels và tạo bảng màu cho toàn bộ labels để tránh truy cập vượt mảng.
- Luôn xử lý trường hợp `PipeLine.get_frame()` trả về `None` và luôn giải phóng KPU, sensor, display, media buffers trong nhánh cleanup.
- Chỉ thay đổi resolution, display mode, sensor channel hoặc preprocessing khi có lý do phần cứng/model rõ ràng và đã kiểm thử trên thiết bị.
