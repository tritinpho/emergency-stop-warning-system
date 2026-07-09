# ADR-0016: Hợp nhất kho mã và nguồn khối tri giác (perception) K230

**Trạng thái:** Đã chấp nhận (phía phần mềm / kiến trúc) — 2026-07-09. Các hạng mục liên-nhóm (nhóm phần cứng áp dụng IF-4, loại bỏ chốt MQTT khỏi đường an toàn) đang ở trạng thái **Đề xuất**, chờ nhóm ACLAB ELMS.
**Ngày:** 2026-07-09
**Người quyết định:** Chủ nhiệm / trưởng nhóm phần mềm (Tin); nhóm phần cứng/firmware (ACLAB ELMS) đồng sở hữu các hạng mục liên-nhóm

## Bối cảnh

Hai kho mã cùng mô tả một sản phẩm:

- **Kho này** (`tritinpho/emergency-stop-warning-system`) — xương sống kiến trúc và an toàn: tài liệu 00–11 (EN+VI), 15 ADR, [ICD](../08-interface-control-document.vi.md), [ma trận truy vết](../06-traceability-matrix.vi.md), [phương pháp mô phỏng](../07-simulation-methodology.vi.md), và ngăn xếp an toàn tương thích MicroPython (`software/esw`, sáu bảng kiểm thử, CI trên CPython + MicroPython thật). Khoảng trống: khối tri giác vẫn là **giàn giáo (scaffold)** — chưa từng chạy bộ nhận diện thật, `kmodel` thật, hay silicon thật.
- **Kho ACLAB ELMS** (`KendyKeb/Solar-Powered-Intelligent-Emergency-Lane-Monitoring-and-Warning-System`) — nguyên mẫu phần cứng đã kiểm thử trên thiết bị: một K230 chạy YOLOv8n ~30 FPS, hai `kmodel` ngày/đêm đã huấn luyện, công cụ web cấu hình ROI dùng được tại thực địa, lọc ROI theo diện tích cắt / ray-cast, ba bộ lọc nhiễu môi trường, điều khiển đèn qua ESP32, và telemetry MQTT lên CoreIoT. Khoảng trống: **không có kiến trúc an toàn** — chỉ một máy trạng thái hai trạng thái hiện diện/vắng mặt, một đường liên kết đèn **nguy hiểm khi lỗi (fail-danger)**, và đường tới hạn phụ thuộc đám mây.

Đây là hai nửa bổ sung cho nhau của cùng một hệ thống, do hai nhóm dựng (phần mềm = Tin; phần cứng/firmware = ACLAB ELMS). Nếu để nguyên, chúng đã bắt đầu **phân kỳ**: kho ACLAB ELMS tự sinh ra `architecture.md` / `light_control.md` riêng với ngữ nghĩa chốt `TURN_ON`/`TURN_OFF` định tuyến qua một broker MQTT đám mây — mâu thuẫn với [ADR-0002](ADR-0002-edge-vs-cloud-processing.vi.md) (vòng an toàn tại biên) và cơ chế tự ngắt an toàn (dead-man's switch) của [ADR-0005](ADR-0005-fail-safe-and-system-safety.vi.md) / [ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.vi.md) / [ADR-0013](ADR-0013-degraded-hold-unification.vi.md). Sự trùng lặp nay kết tinh tại bộ điều khiển đèn ESP32 — nơi cả hai nhóm đang dựng với ngữ nghĩa an toàn **trái ngược**. Cần một nguồn tham chiếu chuẩn duy nhất trước khi hai bên phân kỳ thêm.

## Quyết định

- **D1 — Kho này là gốc (trunk) / nguồn tham chiếu chuẩn; hướng hợp nhất là của họ → của ta.** Tài liệu 00–11 + các ADR vẫn là chuẩn. `architecture.md` / `light_control.md` độc lập của họ bị **hạ cấp thành nhật ký thiết kế** (`firmware/k230-detector/design-log/`) — giữ lại như hồ sơ kỹ thuật của nhóm phần cứng, không phải đặc tả.
- **D2 — Đưa lớp thiết bị của ACLAB ELMS vào [`firmware/k230-detector/`](../../firmware/k230-detector/), giữ nguyên như một baseline đã kiểm thử trên thiết bị**, nằm sau các giao diện của ta. Đầu ra bộ nhận diện của họ trở thành backend cụ thể cho `esw.perception.Perception.step()` (IF-1 → IF-2); hình học chiếu-xuống-mặt-đất, bộ theo dõi (tracker) và máy trạng thái của ta nằm bên trên. Tôn trọng quy tắc "không âm thầm hiện đại hóa baseline thiết bị" của chính họ (`AGENTS.md` của họ) — mã đã đưa vào là bản tham chiếu; adapter nằm bên ngoài nó.
- **D3 — Tại điểm giáp ranh (seam), thiết kế an-toàn-khi-lỗi thắng.** Cơ chế tự ngắt an toàn IF-4 làm mới-hoặc-làm-trống qua LoRa ([`firmware/sign-controller`](../../firmware/sign-controller/README.md), [tài liệu 10](../10-if4-sign-controller-firmware-spec.vi.md)) thay cho chốt `LED:ON`/`LED:OFF` qua MQTT/Wi-Fi của họ. MQTT CoreIoT bị hạ cấp khỏi đường an toàn xuống **telemetry IF-6 không tới hạn** ([ADR-0002](ADR-0002-edge-vs-cloud-processing.vi.md)).
- **D4 — Thu hoạch các tài sản tri giác tái dùng được:** `LightFilter` và `OverVehiclesFilter` (cái sau là bản tương đương chống ùn tắc của họ — R14 / SC-11 của ta), công cụ web cấu hình ROI + lược đồ `config.json`, và tri thức nền tảng K230 (hậu xử lý tăng tốc bằng C, vòng đời bộ nhớ, thứ tự khởi tạo Wi-Fi/LCD, baseline Yahboom 1.4.1).

## Các phương án đã cân nhắc

### D1 — kho nào là nguồn tham chiếu chuẩn
| Phương án | Đánh giá |
|---|---|
| **Kho này là gốc, của họ → của ta (đã chọn)** | Giữ được hồ sơ an toàn, ADR, ICD, CI; bộ nhận diện của họ cắm vào `Perception.step()` đúng như thiết kế (vốn dựng như backend cắm-thay-được). Hợp nhất nhỏ nhất, sạch nhất. |
| Kho của họ là gốc, của ta → của họ | Phải dựng lại ngăn xếp an toàn 12 module, 15 ADR, ICD, CI song-runtime lên một kho không có gì; kế thừa chốt fail-danger + phụ thuộc đám mây. Bác bỏ. |
| Giữ hai kho nối bằng ICD | Trung thực với mô hình hai nhóm và khả thi lâu dài; nhưng sự trùng lặp (hai bộ điều khiển ESP32) và phân kỳ tài liệu đang xảy ra ngay bây giờ, và yêu cầu là hợp nhất. Ghi nhận như cấu trúc dự phòng. |

### D2 — mã của họ vào đây bằng cách nào
| Phương án | Đánh giá |
|---|---|
| **Đưa vào như baseline được giữ nguyên + adapter bên ngoài (đã chọn)** | Giữ mã đã kiểm thử của họ chạy được và ghi công được; adapter gánh toàn bộ việc hòa giải, nên baseline vẫn là bản tham chiếu sạch. |
| Chuyển/viết lại theo phong cách `esw/` ngay | Mất xuất xứ "đã kiểm thử trên thiết bị" và có nguy cơ âm thầm "hiện đại hóa" các API mà `AGENTS.md` của họ đóng băng. Để sau, không phải bây giờ. |
| Git submodule | Giữ nó tách biệt — trái ngược với hợp nhất — và không mang được adapter của ta. |

### D3 — điểm giáp ranh đường liên kết đèn
| Phương án | Đánh giá |
|---|---|
| **Cơ chế tự ngắt an toàn IF-4 thắng; MQTT → telemetry (đã chọn)** | Toàn bộ việc tái định khung an toàn (an-toàn-khi-lỗi / báo-lỗi-rõ) nằm ở đây; chốt của họ là fail-danger và phụ thuộc đám mây. Không thương lượng. |
| Giữ chốt của họ cho demo, IF-4 sau | Xuất xưởng đúng hành vi ta cần sửa nhất — đèn còn sáng khi đứt liên kết hoặc hộp biên chết là mối nguy hàng đầu. Bác bỏ. |

## Phân tích đánh đổi

Việc hợp nhất bất đối xứng một cách có chủ đích. Kho của ta đóng góp phần đắt để tái tạo và rẻ để mở rộng (ngăn xếp an toàn đã kiểm chứng với điểm giáp ranh tri giác cắm-thay-được); kho của họ đóng góp phần ta không thể mô phỏng mà có được (bộ nhận diện thật trên silicon thật, tinh chỉnh trên cảnh quay thật). Đưa *tri giác của họ vào kiến trúc của ta* là vài trăm dòng adapter; đưa *kiến trúc của ta lên ứng dụng của họ* là viết lại. Nơi duy nhất hai bên thực sự mâu thuẫn là đường liên kết đèn — và ở đó hồ sơ an toàn không phải một đánh đổi: cơ chế tự ngắt an toàn chính là lý do dự án được tái định khung thành hệ thống liên quan an toàn. Mọi thứ còn lại đều có tính cộng thêm.

Cái giá ta gánh là một **danh sách việc cần hòa giải** (bên dưới): các lối tắt thực dụng của họ — mô hình một-lớp, dwell hiện-diện bị vô hiệu, ROI trong mặt phẳng ảnh, bộ lọc rung là no-op, phụ thuộc đám mây, bí mật hardcode — mỗi thứ cần một quyết định xử lý minh nhiên thay vì tiếp nhận âm thầm. Ghi lại danh sách đó *chính là* việc hợp nhất; tiếp nhận mã của họ mà không có nó sẽ nhập luôn các hành vi fail-danger cùng với các phần tốt.

## Hệ quả

- **Dễ hơn:** một nguồn tham chiếu chuẩn; một bộ nhận diện thật sau điểm giáp ranh tri giác; bộ lọc nhiễu + công cụ ROI + tri thức nền tảng K230 về cùng lúc; hậu xử lý tăng tốc bằng C của K230 trả lời một phần câu hỏi định thời D3 còn mở của [ADR-0015](ADR-0015-state-machine-implementation-strategy.vi.md) (vòng lặp hậu xử lý YOLOv8 thuần Python làm cạn heap MicroPython → đường C `aidemo` của SDK khắc phục và giữ 30 FPS).
- **Khó hơn / gánh dưới dạng backlog** (mỗi mục theo dõi trong `firmware/k230-detector/README.md`):
  1. **Tập lớp của bộ nhận diện** — `kmodel` *sản xuất* là `AnchorBaseDet` một-lớp tùy chỉnh ("vehicle"), không phải COCO; footprint theo lớp (car/truck/bus) và khởi phát hiện diện người đi bộ (person, SC-12) của ta cần hoặc mô hình COCO `yolov8n` hoặc một phép ánh xạ lớp.
  2. **Bất đối xứng dwell** — `main.py` của họ chạy `PRESENCE_THRESHOLD = 0` (không có dwell xác nhận) → dễ báo động giả (cry-wolf); dwell xác nhận `T_dwell` cấu hình được của ta phải chi phối khi tích hợp.
  3. **Hình học ROI** — của họ là bbox∩polygon trong mặt phẳng ảnh (overlap ≥ 0.2); của ta là footprint-chiếu-mặt-đất ∩ ROI-mặt-đất (đúng phối cảnh, PC-11). Của ta thay thế; của họ là phương án dự phòng khi gần thẳng đứng (near-nadir).
  4. **ShakingFilter là no-op dưới MicroPython** (cần cv2) — không phải biện pháp giảm nhiễu thật trên thiết bị; không được tính là một.
  5. **Phụ thuộc đám mây** — MQTT CoreIoT phải nằm ngoài đường an toàn (ADR-0002); chỉ telemetry.
  6. **Bí mật** — mã ESP32 / Wi-Fi đã đưa vào chứa mật khẩu Wi-Fi + access token CoreIoT hardcode (vốn đã công khai trong kho của họ) → xoay vòng + chuyển vào config.
  7. **Nhị phân mô hình** — hai `kmodel` ~7 MB; một quyết định git-LFS-hay-commit (tạm để ngoài git; xem `models/README.md`).
- **Không đổi:** radar vắng mặt ở **cả hai** kho (RQ-H1); quyết định này không chạm vào khoảng trống phương thức cảm biến.
- **Xem lại khi:** adapter tri giác hoàn thành và vòng kín (bộ nhận diện → `perception` → `state_machine` → IF-4) chạy trên K230; hoặc nếu hai nhóm chọn cấu trúc hai-kho-cộng-ICD.

## Hạng mục hành động

1. [ ] **Adapter tri giác** — ánh xạ đầu ra `collect_vehicle_detections` của họ sang định dạng detections của `Perception.step()`; test tích hợp trên host cho vòng kín; giải quyết backlog #1 (tập lớp).
2. [ ] **Hòa giải điểm giáp ranh trong ICD / [tài liệu 09](../09-software-hardware-handoff.vi.md)** — ghi rằng IF-4 thay thế chốt `LED:ON/OFF` và MQTT CoreIoT chỉ là telemetry IF-6.
3. [ ] **Thu hoạch các bộ lọc nhiễu** vào đường tri giác — ánh xạ `OverVehiclesFilter` sang chống ùn tắc (R14 / SC-11); nối `LightFilter`; loại `ShakingFilter` khỏi danh sách biện pháp giảm nhiễu trên thiết bị.
4. [ ] **Bí mật** — xoay vòng mật khẩu Wi-Fi + token CoreIoT đã lộ; chuyển vào `config.json` (backlog #6).
5. [ ] **Lưu trữ mô hình** — quyết định git-LFS hay kho lưu trữ vật phẩm bên ngoài cho các `kmodel` ngày/đêm (backlog #7).
6. [ ] **Nhóm phần cứng ký duyệt (Đề xuất → Chấp nhận)** — ACLAB ELMS áp dụng IF-4 trên ESP32 và loại chốt MQTT khỏi đường an toàn.
