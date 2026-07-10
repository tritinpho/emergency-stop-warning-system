# 06 — Ma trận truy vết kiểm chứng

> 🇬🇧 Bản gốc tiếng Anh: [06-traceability-matrix.md](06-traceability-matrix.md)

**Dự án:** Hệ thống cảnh báo tự động cho làn dừng xe khẩn cấp (ESW)
**Trạng thái:** Đề xuất
**Cập nhật lần cuối:** 2026-06-27
**Liên quan:** [01 yêu cầu](01-requirements.vi.md) · [02 kiến trúc](02-system-architecture.vi.md) · [04 rủi ro & an toàn](04-risk-and-safety.vi.md) · [các ADR](adr/README.vi.md)

Ma trận này là **cổng tiền-xây-dựng**: mỗi yêu cầu một dòng kiểm toán được, gắn nó với quyết định chi
phối, **tầng** kiểm chứng có thể chứng minh nó, **kịch bản/phép thử được đặt tên** thực hiện việc đó, và
**tiêu chí đạt**. Nó tập hợp những gì trước đây rải rác qua các bảng yêu cầu
[tài liệu 01 §2/§3](01-requirements.vi.md#2-yêu-cầu-chức-năng), các nhãn B/S/F/D ở
[§3a](01-requirements.vi.md#3a-phạm-vi-kiểm-chứng--giai-đoạn-được-tài-trợ-bàn-thửmô-phỏng-thực-sự-có-thể-chứng-minh-điều-gì),
các chỉ số & tập kịch bản ở [§5](01-requirements.vi.md#5-chỉ-số-đánh-giá--tiêu-chí-nghiệm-thu), và bộ
FMEA-làm-tập-tiêm-lỗi ở [tài liệu 04 §2](04-risk-and-safety.vi.md#2-fmea-lite-kiểu-lỗi--tác-động--phát-hiện--phản-ứng)
— để **không một "Phải" nào bị bỏ mồ côi** và không tuyên bố nào vượt quá tầng bằng chứng của nó.

**Các tầng** (theo [ADR-0007](adr/ADR-0007-validation-and-data-strategy.vi.md)): **B** = bàn thử · **S** =
mô phỏng · **F** = hoãn-cho-hiện-trường (cấp sở) · **D** = chỉ thiết kế/rà soát. Một dòng có **F** trong
tầng của nó **không được báo cáo như một kết quả nguyên mẫu đã đo** — nó được chuyển sang nghiệm thu thử
nghiệm hiện trường ([tài liệu 05 §11](05-field-pilot-proposal.vi.md#11-kpi-nghiệm-thu-hiện-trường)).

---

> ## ⚠ LƯU Ý GIAI ĐOẠN — bản dựng này CHỈ DÙNG CAMERA
>
> [ADR-0001](adr/ADR-0001-sensing-modality.vi.md) (hợp nhất camera + radar) đã bị **Bác bỏ ngày 2026-07-10**. Nguyên mẫu trên bàn
> (cấp trường) **chỉ dùng camera**. Mọi hành vi phụ thuộc radar được mô tả bên dưới — radar chứng thực,
> khoảng giữ-khi-che-khuất (`WARN_HOLD` / `CAMERA_OCCLUDED_DEGRADED`), `T_degraded_max`, và các chế độ
> cảm biến `FULL` / `RADAR-ONLY` — đều **đang tạm ngưng: mã nguồn vẫn giữ, nhưng không bao giờ chạy**,
> vì `corr` không bao giờ đúng khi không có kênh radar.
>
> Hệ quả được chấp nhận: **R5** (mù ban đêm/mưa/sương mù) **không còn biện pháp giảm thiểu** và khả năng
> phát hiện ban đêm/bất lợi **không được tuyên bố**; **R20** — xe bị che khuất bị xóa sau `T_hold`
> (~10 giây), biển báo tắt trong khi mối nguy vẫn còn; **R21** — thiết bị nằm vĩnh viễn ở `CAMERA_ONLY`,
> do đó vĩnh viễn `DEGRADED`. Xem [tài liệu 04](04-risk-and-safety.vi.md).
>
> Nội dung radar bên dưới là **thiết kế mục tiêu cấp sở**, không phải bản dựng của giai đoạn này.

## 1. Yêu cầu chức năng

| ID | Yêu cầu (rút gọn) | Ưu tiên | ADR chi phối | Tầng | Kịch bản / phép thử kiểm chứng | Tiêu chí đạt |
|----|-------------------|---------|--------------|------|--------------------------------|--------------|
| FR-01 | Giám sát ROI cấu hình được | M | [0003](adr/ADR-0003-detection-algorithm.vi.md) | B·S | Mọi kịch bản; kiểm thử đơn vị giới hạn-ROI (chồng lấn ≥ 50 %) | Phát hiện ngoài ROI bị loại; tư thế nằm vắt ranh giới xác định |
| FR-02 | Phát hiện xe trong ROI | M | [0001](adr/ADR-0001-sensing-modality.vi.md) *(Bác bỏ)* /[0003](adr/ADR-0003-detection-algorithm.vi.md) | B·S (ngày) · **—** (đêm/bất lợi) | Tập ngày; chỉ số recall (§5) trên các lượt thu **thật** | Recall ≥ 95 % ban ngày. Đêm/bất lợi **bị rút lại** — không radar, không cổng, không tuyên bố (R5 không còn giảm thiểu) |
| FR-03 | Phân biệt dừng vs. đi ngang | M | [0003](adr/ADR-0003-detection-algorithm.vi.md)/[0008](adr/ADR-0008-detection-persistence-and-multitrack.vi.md) | B·S | Đi-ngang thoáng qua; bò dọc lề | Đi-ngang **không** kích hoạt (kích hoạt sai §5) |
| FR-04 | Xác nhận bằng dwell | M | [0008](adr/ADR-0008-detection-persistence-and-multitrack.vi.md) | B·S | Dừng-và-giữ; quét dwell 3–10 s | Chỉ xác nhận sau `T_dwell`; cân theo ngân sách phơi-nhiễm |
| FR-05 | Kích hoạt biển khi xác nhận | M | [0004](adr/ADR-0004-warning-actuator-integration.vi.md) | B·S | Vòng kín đường thuận lợi | Biển BẬT ≤ dwell + 2 s (NFR-01) |
| FR-06 | Theo dõi khi đang BẬT | M | [0008](adr/ADR-0008-detection-persistence-and-multitrack.vi.md) | B·S | Hiện diện kéo dài; đa phương tiện | Cảnh báo giữ khi tập khác rỗng |
| FR-07 | Xóa + hysteresis | M | [0008](adr/ADR-0008-detection-persistence-and-multitrack.vi.md) | B·S | Rời đi; che khuất ngắn | Xóa ≤ hold + 2 s khi thoát ra xác nhận; rớt ngắn không nhấp nháy |
| FR-08 | Cảnh báo người đi bộ (**khởi-phát-theo-hiện-diện**) | S | [0003](adr/ADR-0003-detection-algorithm.vi.md)/[0008](adr/ADR-0008-detection-persistence-and-multitrack.vi.md) | S(xấp xỉ)·**F** | **Người mắc kẹt di chuyển** (đi bộ, không bao giờ đứng yên); người trong/cạnh ROI | Kích hoạt theo hiện-diện-khử-dội; recall theo dõi **riêng** (§5), đêm best-effort |
| ~~FR-09~~ | Ngày/đêm/mưa/sương mù | ~~M~~ **đã giảm phạm vi** | [0001](adr/ADR-0001-sensing-modality.vi.md) *(Bác bỏ 2026-07-10)* | **—** | *(không có — giai đoạn này không nghiệm thu điều kiện bất lợi)* | **Rút lại.** Chỉ ban ngày. Đêm/mưa/sương mù cần cảm biến thứ hai vốn không được cấp kinh phí; R5 không còn giảm thiểu, khôi phục ở cấp sở |
| FR-10 | Tự giám sát + nhịp tín hiệu (**gồm cả bộ giám sát trôi hiệu chuẩn**) | M | [0005](adr/ADR-0005-fail-safe-and-system-safety.vi.md) | B·S · **F** (trôi thực) | Sức khỏe từng hệ con; nhịp định kỳ; **bộ giám sát trôi** — tiêm một phép dịch homography tổng hợp | Nhịp mang sức khỏe + vân tay phiên bản; lỗi được phát hiện; dịch trôi → suy giảm + cảnh báo (trôi thực hoãn-hiện-trường, R15) |
| FR-11 | Trạng thái an toàn + báo khi lỗi | M | [0005](adr/ADR-0005-fail-safe-and-system-safety.vi.md)/[0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md)/[0013](adr/ADR-0013-degraded-hold-unification.vi.md) | B·S | **Tiêm lỗi** (giết SM, giết hộp, cắt liên kết; **giết camera khi đang cảnh báo**; **CLEAR đối với bảng kẹt-BẬT**) | Biển trống trong `T_signhold` (SM/hộp/liên kết); giết-camera → trạng thái giữ có giới hạn → buộc xóa lớn tiếng `T_degraded_max`; kẹt-BẬT → TRẠNG THÁI AN TOÀN + leo thang biển-báo-bị-kẹt; báo người trực ở mọi trường hợp |
| FR-12 | Sự kiện tới TMC + audit | S | [0002](adr/ADR-0002-edge-vs-cloud-processing.vi.md) | B·S | Sự kiện kích hoạt/xóa/lỗi; xếp hàng khi mất liên kết | Sự kiện kèm vân tay phiên bản tới audit; lưu-và-chuyển sống sót outage |
| FR-13 | Ghi đè người trực (có giới hạn) | S | [0010](adr/ADR-0010-operator-override-and-manual-control.vi.md) | B·S | **Hết hạn ghi đè**; **từ chối** ghi đè ngoài chính sách; ép-bật khi giết-hộp | Tắt tiếng tự hết hạn; ép-bật trống khi giết-hộp/cắt-liên-kết; không-xác-thực bị từ chối |
| FR-14 | Cấu hình từ xa | S | [0010](adr/ADR-0010-operator-override-and-manual-control.vi.md)/[0012](adr/ADR-0012-security-and-threat-model.vi.md) | B·S | Đẩy cấu hình có ký; cấu hình xấu (→ FR-20) | Cấu hình ký hợp lệ áp dụng; không hợp lệ bị từ chối |
| FR-15 | OTA + khôi phục | C | [0007](adr/ADR-0007-validation-and-data-strategy.vi.md)/[0012](adr/ADR-0012-security-and-threat-model.vi.md) | B·S | Mô hình thoái lui → **canary** → khôi phục | Mô hình thoái lui được khôi phục về bản ký trước |
| FR-16 | Ghi bằng chứng (không video thô) | S | [0007](adr/ADR-0007-validation-and-data-strategy.vi.md) | B·S·D | Chụp ảnh-sự-kiện; lưu giữ/hết hạn | Chỉ siêu dữ liệu/ảnh tối thiểu; tự-hết-hạn có giới hạn; rà soát quyền riêng tư (NFR-10) |
| FR-17 | Tái dùng VMS sẵn có | S | [0004](adr/ADR-0004-warning-actuator-integration.vi.md) | **F** | VMS vận hành thực (bàn thử dùng LED thay thế) | NFR-01 **được định mức**; lưu ý phân xử + chốt-trạng-thái được ghi |
| FR-18 | Vật cản chung / đi ngược chiều | W | [0003](adr/ADR-0003-detection-algorithm.vi.md) | — | *Tương lai* — không kiểm chứng giai đoạn này | n/a (lập luận khả năng mở rộng, NFR-14) |
| FR-19 | Báo dịch vụ khẩn cấp | W | — | — | *Tương lai* — không kiểm chứng giai đoạn này | n/a |
| FR-20 | Ràng buộc biên cấu hình (**toàn bộ bề mặt tham số an toàn**, [doc 02 §7a](02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu)) | M | [0010](adr/ADR-0010-operator-override-and-manual-control.vi.md)/[0012](adr/ADR-0012-security-and-threat-model.vi.md)/[0013](adr/ADR-0013-degraded-hold-unification.vi.md) | B·S | **Giá trị ngoài biên** cho bất kỳ tham số bề mặt nào — ROI / `T_dwell=900 s` / **`T_signhold` đủ lớn để vô hiệu hóa cơ chế tự ngắt an toàn** / **`T_degraded_max`→"không bao giờ"** — bị từ chối/ghim | Tham số ngoài-tầm (gồm cả các chốt-chặn an toàn) bị từ chối hoặc ghim; giữ tốt-cuối; có báo |
| FR-21 | Hoãn OTA khi đang cảnh báo | S | [0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md) | B·S | **OTA yêu cầu khi tập-vết khác rỗng** | Cập nhật được hoãn, hoặc trống *lớn tiếng cho người trực* — không bao giờ rớt âm thầm |

## 2. Yêu cầu phi chức năng

| ID | Yêu cầu (rút gọn) | ADR chi phối | Tầng | Kịch bản / phép thử | Tiêu chí đạt |
|----|-------------------|--------------|------|---------------------|--------------|
| NFR-01 | Dừng→cảnh ≤ 2 s | [0004](adr/ADR-0004-warning-actuator-integration.vi.md)/[0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md) | B·S (LED) · **F** (VMS) | Đo độ trễ, phụ trợ LED | ≤ dwell + 2 s trên LED; phụ trợ VMS **được định mức** với ngân sách riêng |
| NFR-02 | Xe-đi→tắt ≤ hold + 2 s | [0008](adr/ADR-0008-detection-persistence-and-multitrack.vi.md) | B·S | Độ trễ xóa khi thoát ra xác nhận | ≤ hold + 2 s; che khuất được giữ **không** phải lỗi độ trễ xóa |
| NFR-03 | Khả dụng chức năng ≥ 99 % | [0005](adr/ADR-0005-fail-safe-and-system-safety.vi.md) | **F** | Đo hiện trường; bàn thử = MTBF vòng phần mềm dưới tiêm lỗi | **Tạm thời** ≥ 99 %, **chờ ngân sách MTBF/MTTR** ([tài liệu 04 Q6](04-risk-and-safety.vi.md#5-các-câu-hỏi-an-toàn-còn-mở-cho-nhóm)) |
| NFR-04 | Không kẹt-BẬT (mọi lỗi) | [0005](adr/ADR-0005-fail-safe-and-system-safety.vi.md)/[0008](adr/ADR-0008-detection-persistence-and-multitrack.vi.md)/[0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md)/[0013](adr/ADR-0013-degraded-hold-unification.vi.md) | B·S | Hết hạn watchdog; **buộc-xóa `T_degraded_max` (nguyên nhân che khuất _và_ lỗi-camera)**; logic kẹt | Không trạng thái nào — và không chế độ cảm-biến-suy-giảm nào — giữ bảng BẬT mà thiếu xác nhận được-camera-xác-thực, quy-được-về-làn; xóa có giới hạn trong mọi trường hợp |
| ~~NFR-05~~ | Bền vững mưa/đêm | [0001](adr/ADR-0001-sensing-modality.vi.md) *(Bác bỏ 2026-07-10)* | **—** | *(cổng đã gỡ — hoãn sang cấp sở)* | **Giảm phạm vi, không phải hoãn.** Không radar → không cổng → **không tuyên bố**; không bao giờ dựa lên radar tổng hợp (R5 không còn giảm thiểu) |
| NFR-06 | Tự chủ tại biên (WAN offline) | [0002](adr/ADR-0002-edge-vs-cloud-processing.vi.md) | B·S | Tiêm outage WAN | Vòng phát-hiện→cảnh-báo không bị ảnh hưởng; sự kiện xếp hàng |
| NFR-07 | Pin mặt trời ≥ 72 h | [0006](adr/ADR-0006-connectivity-and-power.vi.md) | **F** (D ở bàn thử) | Ngân sách năng lượng gồm radar đạt-chuẩn-cổng | Chỉ thiết kế ở bàn thử; đo hiện trường ở thử nghiệm |
| NFR-08 | Khả năng bảo trì | [0002](adr/ADR-0002-edge-vs-cloud-processing.vi.md) | B·D | Sức khỏe/cấu hình/OTA từ xa | Mô-đun hóa; bảo trì được từ xa |
| NFR-09 | An ninh (có phạm vi) | [0012](adr/ADR-0012-security-and-threat-model.vi.md) | D · **F** | Rà soát mô hình mối đe dọa; xác thực liên kết/ghi đè; thử phát lại | Xác thực chống giả mạo/phát lại trên bề mặt liệt kê; từ chối → an-toàn-trống-và-báo; gia cố sâu **hiện trường** |
| NFR-10 | Quyền riêng tư (trên-thiết-bị, không lưu thô) | [0007](adr/ADR-0007-validation-and-data-strategy.vi.md) | B·D | Rà soát xử lý dữ liệu; thử lưu giữ/hết hạn | Suy luận trên thiết bị; không video thô liên tục; bằng chứng có giới hạn |
| NFR-11 | Tiêu chuẩn (QCVN 41 / TCVN 5729) | [0004](adr/ADR-0004-warning-actuator-integration.vi.md) | D | Rà soát tuân thủ; rà soát tập thông điệp | Tập thông điệp tuân thủ **hoặc** xin ngoại lệ có quản lý (ADR-0004 AI#4) |
| NFR-12 | Chi phí (giới hạn 20M / BoM hiện trường) | — ([tài liệu 03](03-roadmap-and-phasing.vi.md)) | D | Theo dõi ngân sách | Bản dựng cấp trường trong 20M; BoM hiện trường được theo dõi |
| NFR-13 | Môi trường IP65+ | [0006](adr/ADR-0006-connectivity-and-power.vi.md) | **F** | Vỏ bảo vệ cấp hiện trường | Không vỏ hiện trường ở bàn thử; hoãn-hiện-trường |
| NFR-14 | Khả năng mở rộng | [0003](adr/ADR-0003-detection-algorithm.vi.md)/[0004](adr/ADR-0004-warning-actuator-integration.vi.md) | D | Lập luận kiến trúc | Thêm lớp cảm biến/sự kiện / phụ trợ mới không thiết kế lại |
| NFR-15 | Phản hồi người trực / quản lý cảnh báo | [0011](adr/ADR-0011-operator-concept-and-alarm-management.vi.md) | D · **F** | Trình diễn gộp trùng/ưu tiên; **leo-thang-lại khi không xác nhận**; rà soát ConOps | Gộp trùng/ưu tiên/leo-thang-lại được trình diễn; giới hạn thời gian phản hồi **tinh chỉnh hiện trường** |
| NFR-16 | Toàn vẹn thời gian (tương đối + tuyệt đối) | [0001](adr/ADR-0001-sensing-modality.vi.md) | B · **F** | Đo đồng bộ giữa cảm biến; duy trì qua outage | Đồng bộ tương đối dưới-khung-hình ở bàn thử; duy trì tuyệt đối **hiện trường** (hầm không GNSS) |

## 3. Yêu cầu bố trí

| ID | Yêu cầu (rút gọn) | Chi phối | Tầng | Kiểm chứng | Tiêu chí đạt |
|----|-------------------|----------|------|------------|--------------|
| PL-01 | Biển ≥ DSD phía trước biên gần ROI | [tài liệu 01 §4](01-requirements.vi.md#4-bố-trí-cảnh-báo--phép-tính-mà-đề-xuất-bỏ-sót) | D · **F** | Nghiên cứu chọn vị trí (hiệu chỉnh độ dốc + tốc độ 85%); khảo sát tại chỗ | ≥ DSD-C cho tốc độ chi phối, từ biên trên ROI; đối chiếu TCVN 5729 |
| PL-02 | Cự ly đọc được | [tài liệu 01 §4](01-requirements.vi.md#4-bố-trí-cảnh-báo--phép-tính-mà-đề-xuất-bỏ-sót) | D · **F** | Tính chiều cao ký tự; đọc được tại chỗ | Đọc được khi tài xế còn cách DSD |
| PL-03 | Tính độ trễ kích hoạt | [tài liệu 01 §4](01-requirements.vi.md#4-bố-trí-cảnh-báo--phép-tính-mà-đề-xuất-bỏ-sót) | B·S | Mô hình phơi-nhiễm-không-cảnh-báo | `N_unwarned` trong trần đơn-vị-vận-hành-thống-nhất tại giãn cách của vị trí |
| PL-04 | Quy tắc biển lặp / vị trí không phù hợp | [tài liệu 01 §4](01-requirements.vi.md#4-bố-trí-cảnh-báo--phép-tính-mà-đề-xuất-bỏ-sót) | D | Rà soát hình học từng vị trí | Biển lặp khi tầm nhìn bị chặn; nếu không, ghi vị trí không phù hợp (A4) |

---

## 4. Ghi chú bao phủ — ma trận này làm rõ điều gì

- **Không "Phải" nào mồ côi.** Mọi yêu cầu **M** nay có một kịch bản và tiêu chí đạt được đặt tên. Các yêu
  cầu chức năng trước đây ngầm — **FR-12** (sự kiện/audit), **FR-13** (ghi đè), **FR-14** (cấu hình),
  **FR-16** (bằng chứng), **FR-20** (ràng buộc cấu hình), **FR-21** (hoãn OTA) — nay là **kịch bản nghiệm
  thu tường minh** ([tài liệu 01 §5](01-requirements.vi.md#5-chỉ-số-đánh-giá--tiêu-chí-nghiệm-thu)), không
  bị hấp thụ âm thầm vào "các lỗi được tiêm".
- **Hai kịch bản là *được-thiết-kế*, không phải *vững-ở-hiện-trường*.** Không-kích-hoạt-sai khi ùn tắc và
  giữ-khi-che-khuất kéo dài dựa vào tiêu chí (b) radar hoãn-hiện-trường — báo cáo chúng **được kiểm chứng
  về logic như đã đặc tả**, không phải đã chứng minh ở hiện trường
  ([ADR-0001](adr/ADR-0001-sensing-modality.vi.md)/[ADR-0007](adr/ADR-0007-validation-and-data-strategy.vi.md)).
- **Bao phủ lỗi là một phần của các chế độ *tiêm-được-trên-bàn-thử*.** Trôi hiệu chuẩn, hộp-biên/liên-kết
  chết ở cự ly ≥ DSD, và cạn pin mặt trời là **chỉ-hiện-trường**; chỉ tiêu ≥ 95 % phát-hiện-lỗi được báo
  cáo trên những gì bàn thử có thể tiêm ([tài liệu 04 §2](04-risk-and-safety.vi.md#2-fmea-lite-kiểu-lỗi--tác-động--phát-hiện--phản-ứng)).
- **Phương tiện mang liên kết biển báo IF-4 nay đã được quyết** — LoRa điểm-điểm
  ([ADR-0014](adr/ADR-0014-sign-link-bearer.vi.md)) — và thêm một hạng mục **hoãn-hiện-trường**: ngân sách
  **chu-kỳ-làm-việc / mất-gói / độ-trễ qua khoảng cách vốn đặt ra `T_signhold`** (giới hạn chu kỳ 433 MHz có
  thể ràng buộc tốc độ làm mới của cơ chế tự ngắt an toàn). Nó chi phối FR-11 / NFR-01 / NFR-04 ở lớp liên kết
  và gia nhập việc kiểm chứng liên kết ≥ DSD vốn đã hoãn-hiện-trường bởi [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md).
- **Mọi thứ gắn nhãn F được chuyển sang nghiệm thu thử nghiệm hiện trường**
  ([tài liệu 05 §11](05-field-pilot-proposal.vi.md#11-kpi-nghiệm-thu-hiện-trường)); không gì gắn nhãn F là
  một kết quả nguyên mẫu đã đo.
