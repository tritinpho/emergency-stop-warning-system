# 07 — Phương pháp luận mô phỏng & kiểm chứng

> 🇬🇧 Bản gốc tiếng Anh: [07-simulation-methodology.md](07-simulation-methodology.md)

**Dự án:** Hệ thống cảnh báo tự động làn dừng xe khẩn cấp (ESW)
**Trạng thái:** Đề xuất / Bản nháp — **Tạo phẩm cố định Giai đoạn 2** (cố định trước khi bắt đầu xây dựng Giai đoạn 3)
**Cập nhật:** 2026-06-27
**Liên quan:** [yêu cầu 01 §5](01-requirements.vi.md#5-chỉ-số-đánh-giá--tiêu-chí-nghiệm-thu) · [kiến trúc 02 §4](02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo) · [rủi ro & an toàn 04](04-risk-and-safety.vi.md) · [truy vết 06](06-traceability-matrix.vi.md) · [ADR-0007](adr/ADR-0007-validation-and-data-strategy.vi.md) · [ADR-0001](adr/ADR-0001-sensing-modality.vi.md) · [ADR-0013](adr/ADR-0013-degraded-hold-unification.vi.md)

Tài liệu này hiện thực hóa [ADR-0007](adr/ADR-0007-validation-and-data-strategy.vi.md) AI#1. Nó là xương sống của
Giai đoạn 3: nó cố định **khung kiểm thử mô phỏng là gì, nó tiêm vào những gì, cái gì được tính là đạt, và nó
được phép và không được phép tuyên bố điều gì** — *trước khi* vòng lặp được xây dựng, để kết quả Giai đoạn 3 là
**bằng chứng**, chứ không phải một bản trình diễn. Các tiêu chí đạt và cỡ mẫu ở đây được **đăng ký trước**:
chúng được chốt trong tài liệu này và không được
điều chỉnh sau khi đã thấy kết quả.

> **Vì sao cố định ngay bây giờ.** Một tiêu chí đạt được định nghĩa *sau khi* nhìn vào đầu ra thì không phải là một
> tiêu chí. Độ tin cậy của toàn bộ giai đoạn được tài trợ phụ thuộc vào việc tuyên bố đúng những gì đã được kiểm
> thử — nên tập kịch bản, các giả định về cảm biến tổng hợp, và các ngưỡng được cố định như một tạo phẩm Giai đoạn 2
> và được quản lý theo phiên bản.

---

## 1. Ranh giới chứng minh được (mô phỏng được phép và không được phép tuyên bố điều gì)

Phát biểu lại ranh giới của [ADR-0007](adr/ADR-0007-validation-and-data-strategy.vi.md), vì mọi kết quả trong
tài liệu này đều thừa hưởng nó:

| Mô phỏng **được phép** tuyên bố | Mô phỏng **không được phép** tuyên bố (hoãn sang hiện trường) |
|--------------------------|-----------------------------------------------|
| Tính đúng đắn của logic máy trạng thái (dwell, hysteresis, ngữ nghĩa tập hợp, giữ khi che khuất/suy giảm, watchdog, `T_degraded_max`) | Độ nhạy (recall) trong thế giới thực khi mưa / chói / sương mù |
| Định thời/độ trễ (stop→warn, clear, `T_signhold`, watchdog) | Tỉ lệ báo động giả thực |
| Xử lý lỗi và hành vi an toàn khi sự cố dưới các lỗi được tiêm | Hiệu năng nhiễu loạn radar thực / tính vững của tiêu chí (b) |
| Khả năng kháng kích hoạt sai trước các nhiễu **được mô hình hóa** (đi-ngang-qua, ùn tắc, bóng đổ) | Liên kết biên↔biển báo qua cự ly, trôi hiệu chuẩn, năng lượng mặt trời, IP65 |

**Quy tắc cứng: các sự kiện tổng hợp không được tính vào recall.** Một biên Wilson trên *recall* được tính từ
các sự kiện tổng hợp mà chính vòng lặp tiêu thụ thì đo tính tất định của bộ mô phỏng, chứ không đo phát hiện
([tài liệu 01 §5](01-requirements.vi.md#5-chỉ-số-đánh-giá--tiêu-chí-nghiệm-thu)). Mô phỏng chứng thực
**logic / định thời / xử lý lỗi / kích hoạt sai trên nhiễu được mô hình hóa**; **N của recall là dữ liệu thu
thực** (bàn thử, rồi hiện trường) và được điều phối bởi kế hoạch bằng-chứng-nghiệm-thu, không phải khung kiểm thử này.

Mọi kết quả tạo ra theo phương pháp luận này đều được báo cáo kèm **bậc** của nó ([tài liệu 06](06-traceability-matrix.vi.md):
**S** mô phỏng, và nơi một kịch bản chỉ xấp xỉ thực tế, **S-approx**). Bất cứ thứ gì được gắn nhãn **F**
(hiện trường) đều không thể tuyên bố ở đây.

---

## 2. Kiến trúc khung kiểm thử — mô phỏng các cảm biến và biển báo, không bao giờ mô phỏng logic

**Hệ thống được kiểm thử (SUT) là mã thực**: cùng một hợp đồng đầu-ra-nhận-diện, hợp nhất, máy trạng thái
quyết định, trừu tượng hóa cơ cấu chấp hành, và bộ giám sát tình trạng đang chạy trên bàn thử và thiết bị
hiện trường. Khung kiểm thử **chỉ** thay thế các đầu vật lý — các cảm biến và biển báo — bằng các mô hình. Đây chính
là điều làm cho một lần đạt trong mô phỏng có ý nghĩa cho hiện trường: logic được vận hành chính là logic được xuất xưởng.

```
 scenario script ──▶ synthetic sensor model ──▶ [ REAL: perception · fusion · state machine ·
                                                   actuator abstraction · health monitor ]
                                                          │
                                                          ▼
                                              synthetic sign + status read-back
                                                          │
 ground-truth oracle ──────────────────────────────▶ comparator ──▶ metrics (tagged S / S-approx)
```

Hai cấp tiêm lỗi, với **năng lực tuyên bố khác nhau**:

| Cấp | Cái gì là tổng hợp | Cái gì là thực (SUT) | Chứng thực |
|-------|-------------------|--------------------|---------------|
| **A — cấp sự kiện** (chính yếu) | Các sự kiện phát hiện/vết Nhận diện→SM ([IF-2](08-interface-control-document.vi.md), [tài liệu 02 §7](02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu)) | Máy trạng thái, duy trì/bộ định thời, logic lỗi, trừu tượng hóa cơ cấu chấp hành, bộ giám sát tình trạng | Phần lớn của [tài liệu 01 §5](01-requirements.vi.md#5-chỉ-số-đánh-giá--tiêu-chí-nghiệm-thu) — logic, định thời, xử lý lỗi, chính sách tập hợp/che khuất/suy giảm |
| **B — cấp khung hình** (tùy chọn, nếu ngân sách cho phép) | Khung hình camera tổng hợp + tín hiệu phản hồi radar | Cả **nhận diện thực** (bộ phát hiện + cổng chặn ROI + bộ theo dõi) | *Đường ống* nhận diện (cổng chặn ROI, độ chồng lấn vết chân (footprint)) — **không phải** recall trong điều kiện thực |

**Bắt đầu với Cấp A** (một trình phát kịch bản 2-D tùy chỉnh là con đường rẻ nhất và vận hành máy trạng thái,
nơi logic an toàn và phần lớn §5 trú ngụ). Chỉ thêm Cấp B nếu nó xứng đáng với chi phí. Bất kể ở cấp nào,
SUT phải giống hệt từng byte với bản dựng bàn-thử/hiện-trường — không có nhánh "chỉ-dành-cho-mô-phỏng" nào trong
logic quyết định.

---

## 3. Mô hình cảm biến tổng hợp & các giả định (được ghi chép và thận trọng)

Mô hình chỉ trung thực ngang bằng các giả định của nó, nên mỗi giả định đều được **phát biểu và ghi lại cùng kết quả**.
Một giả định lạc quan tô vẽ cho SUT sẽ làm vô hiệu tuyên bố mà nó chống đỡ.

### 3.1 Kênh camera
Mô hình hóa một luồng phát hiện như một hàm của khung cảnh được viết kịch bản, với các **nhiễu được tiêm vào** sau đây
(không phải một nguồn cấp oracle sạch):
- **Rớt phát hiện** — theo xác suất và theo sự kiện (che khuất bởi một xe ở làn thông xe được viết kịch bản); dẫn động đường che khuất/mất-vết.
- **Phát hiện giả** — bóng đổ, quét đèn pha, mảnh vỡ, ở một tốc độ cấu hình được; kiểm thử cổng chặn ROI + dwell + kiểm tra chéo radar.
- **Nhiễu vết chân/khung** — rung lắc trên ước lượng vết chân mặt đất; kiểm thử quy tắc chồng lấn ROI ≥ 50 % và các tư thế vắt ngang.
- **Độ trễ & nhịp** — khoảng cách giữa các khung và độ trễ xử lý; kiểm thử các ngân sách `T_activate` / NFR-01.
- **Nhầm lớp** — gán nhầm nhãn ô tô/xe tải/xe buýt/xe máy/người ở một tốc độ cấu hình được.
- **Ban ngày vs ban đêm/bất lợi** — *được xấp xỉ* bằng cách nâng rớt phát hiện/nhiễu; rõ ràng là **S-approx**, không bao giờ là một tuyên bố recall thực (recall thực của FR-09 là **F**).

### 3.2 Kênh radar — mô hình hóa sự bất định, đừng giả định nó biến mất
Mô hình hóa các tín hiệu phản hồi về sự hiện diện/cự ly/tốc độ. Tham số **then chốt về mặt phương pháp luận**:
- **Lỗi gán làn (tiêu chí (b))** — một xác suất *cấu hình được* rằng một tín hiệu phản hồi bị gán cho sai làn (lề đường vs làn thông xe liền kề). Khung kiểm thử **phải** chạy các kịch bản dưới **cả** thiết lập *(b)-tốt* lẫn *(b)-yếu*, vì cổng (b) của [ADR-0001](adr/ADR-0001-sensing-modality.vi.md) bị hoãn sang hiện trường và **bất định**. Toàn bộ điểm mấu chốt của thiết kế giữ-khi-che-khuất / `CAMERA_OCCLUDED_DEGRADED` / `T_degraded_max` chính là hành vi của nó khi (b) yếu — nên mô phỏng cấp cho nó một radar *có thể* gán sai, và kiểm chứng rằng sự cố là có giới hạn (không có kẹt-BẬT cũ vô hạn), không bao giờ là một radar hoàn hảo theo giả định.
- Rớt sự hiện diện, nhiễu cự ly/tốc độ, và các tín hiệu phản hồi giả (radar) cũng cấu hình được.

### 3.3 Kênh thời gian
Tiêm **lệch/rung đồng hồ** giữa luồng camera và luồng radar để vận hành đồng bộ hợp nhất và việc xử lý
toàn-vẹn-thời-gian NFR-16; SUT phải suy giảm một cách nhẹ nhàng (gắn cờ, lùi về cảm biến đơn) thay vì
hợp nhất trên các nhãn thời gian xấu.

### 3.4 Kênh biển báo
Một bộ điều khiển biển báo được mô hình hóa, tuân theo (hoặc, theo cấu hình, **không tuân theo**) hợp đồng `SHOW`-được-làm-mới
([IF-4](08-interface-control-document.vi.md), [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md)):
làm trống trong `T_signhold` khi mất nhịp tín hiệu; có thể được lệnh **chốt** (để mô hình hóa một VMS bên thứ ba), **không tắt**
(kẹt-BẬT, ADR-0013), hoặc bỏ rơi việc đọc ngược lại trạng thái.

> **Sổ ghi tính thận trọng.** Mọi tham số ở trên (tỉ lệ rớt, nhiễu σ, xác suất lỗi-làn,
> độ trễ) đều được ghi lại theo từng lần chạy kịch bản, với một cờ trên bất kỳ thiết lập nào được chọn một cách *lạc quan*.
> Một tuyên bố dựa trên một thiết lập lạc quan sẽ bị hạ cấp hoặc bị giữ lại không công bố.

---

## 4. Bộ chuẩn đối chiếu (oracle) & tính toán chỉ số

Mỗi kịch bản mang theo một **oracle** đọc-được-bằng-máy được suy ra từ kịch bản, **độc lập với SUT**:
với mỗi bước thời gian nó phát biểu *tập hợp đúng* của các xe/người đã-xác-nhận-dừng trong-ROI và do đó liệu
cảnh báo **nên** ở trạng thái BẬT hay không, cộng với các sự kiện thoát ra / che khuất / lỗi đúng. Các chỉ số được tính
bởi bộ so sánh từ (trạng-thái-biển-báo-theo-thời-gian của SUT) so với (oracle):

- Các khoảng **đúng-BẬT / đúng-TẮT**; **kích hoạt nhầm** (BẬT khi oracle nói TẮT); **bỏ-sót-cảnh-báo** (TẮT khi oracle nói BẬT).
- **Độ trễ**: stop→warn, confirmed-exit→clear, fault→blank (`T_signhold`).
- **Tính đúng đắn của định đoạt**: `T_degraded_max` có buộc một lần xóa lớn tiếng không? một lần kẹt-BẬT có đi vào SAFE_STATE không? một ghi đè có tự hết hạn không?

Oracle phân biệt một **lần giữ khi che khuất** (cảnh báo được giữ lại đúng đắn) với một **lần kẹt-BẬT** (oracle
nói mối nguy đã rời đi) — nên một lần giữ-khi-che-khuất đúng đắn không bao giờ bị chấm là một lỗi độ-trễ-xóa
([NFR-02](01-requirements.vi.md#3-yêu-cầu-phi-chức-năng), [ADR-0008](adr/ADR-0008-detection-persistence-and-multitrack.vi.md)).

---

## 5. Danh mục kịch bản (dùng chung, được gắn ID — xương sống nghiệm thu)

Đây là danh mục chuẩn tắc; kế hoạch kiểm thử/nghiệm thu và [tài liệu 06](06-traceability-matrix.vi.md) tham chiếu
các ID này. Mỗi kịch bản cố định: các điều kiện tiên quyết, dòng thời gian được tiêm, **oracle**, yêu cầu/rủi ro
được vận hành, và **bậc**. *Được-kiểm-chứng-bằng-logic như đặc tả* ≠ *vững-tại-hiện-trường*: các kịch bản được đánh dấu **(b)-dep**
dựa trên tiêu chí radar (b) bị hoãn sang hiện trường và được báo cáo là được-thiết-kế-nhưng-chưa-chứng-minh-tại-hiện-trường
([ADR-0007](adr/ADR-0007-validation-and-data-strategy.vi.md)).

| ID | Kịch bản | Oracle (kỳ vọng) | Vận hành | Bậc |
|----|----------|-------------------|-----------|------|
| SC-01 | Dừng → dwell → warn → rời đi → clear (đường thuận lợi) | BẬT sau `T_dwell`+`T_activate`; TẮT sau khi thoát ra đã xác nhận + ≤2 s | FR-01..07, NFR-01/02 | S |
| SC-02 | Đi-ngang-qua thoáng chốc dọc lề đường | không bao giờ BẬT | FR-03 | S |
| SC-03 | Bò-dọc-lề-đường (< cổng tốc độ, không dừng hẳn) | theo quy tắc dwell | FR-03/04 | S |
| SC-04 | Quét dwell 3–10 s | chỉ xác nhận sau `T_dwell` | FR-04 | S |
| SC-05 | Che khuất ngắn (< `T_hold`) | giữ BẬT, không dao động | FR-07, NFR-02 | S |
| SC-06 | Che khuất kéo dài, radar đối chứng | BẬT → `CAMERA_OCCLUDED_DEGRADED` quá `T_occlusion`, + cảnh báo | ADR-0008/0009 | S **(b)-dep** |
| SC-07 | Che khuất kéo dài → đạt `T_degraded_max` | buộc **xóa độ-tin-cậy-thấp lớn tiếng** + leo thang mức cao nhất | NFR-04, ADR-0009 §C | S |
| SC-08 | **Lỗi camera trong khi cảnh báo đang hoạt động**, radar đối chứng | vào trạng thái giữ khi camera không xác thực được (vết) có giới hạn → `T_degraded_max` buộc xóa lớn tiếng; **không** thu nhận lại | **ADR-0013**, NFR-04 | S |
| SC-09 | **(b)-yếu**: radar đối chứng *chiếc xe tải ở làn thông xe đang che khuất*, xe ở lề đã rời đi | cảnh báo **không** duy trì vô hạn — `T_degraded_max` buộc một lần xóa lớn tiếng | đảo ngược R12, ADR-0001/0013 | S **(b)-dep** |
| SC-10 | Đan xen nhiều-xe tới/rời | BẬT khi tập hợp khác rỗng; không xóa sớm | FR-06, ADR-0008 | S |
| SC-11 | Ùn tắc / dừng-chạy cạnh ROI | **không** kích hoạt nhầm; ức chế hoặc đổi thông điệp | R14, [tài liệu 02 §4](02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo) | S **(b)-dep** |
| SC-12 | Người đi bộ xuất-hiện-hiện-diện gồm cả **người gặp nạn đang di chuyển** (không bao giờ < cổng tốc độ) | điều kiện kích hoạt khử-dội-theo-hiện-diện kích nổ (không phải đường tĩnh tại) | FR-08, ADR-0003 | S-approx |
| SC-13 | Xe máy đang dừng (RCS nhỏ) | duy trì cấp-độ-xe chỉ khi radar còn tín hiệu phản hồi, nếu không thì CAMERA-ONLY | ADR-0003/0008 | S |
| SC-14 | Xe có mặt lúc khởi động (khởi động nguội) | được xử lý như một vết mới; đủ dwell | [tài liệu 02 §4](02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo) | S |
| SC-15 | **Khởi động lại nóng trong khi cảnh báo đang hoạt động** | biển báo làm trống trong thời gian ngừng; xác nhận lại khi khởi động lại (tái-phơi-nhiễm được ghi nhận, Q7) | [tài liệu 04 Q7](04-risk-and-safety.vi.md#5-các-câu-hỏi-an-toàn-còn-mở-cho-nhóm) | S |
| SC-16 | Người vận hành ép-bật, rồi giết hộp biên / hết hạn | ép-bật được làm mới (không chốt) → làm trống khi giết-hộp / hết hạn | FR-13, ADR-0010 | S |
| SC-17 | Người vận hành ép-tắt / tắt tạm → tự hết hạn | tắt tạm hết hạn; tư thế OVERRIDDEN khi đang hoạt động; đánh giá lại | FR-13, ADR-0010 | S |
| SC-18 | Ghi đè ngoài chính sách (hết hạn > trần / thông điệp lạ / không lý do) | bị từ chối/kẹp tại thiết bị | FR-13/20, ADR-0010 | S |
| SC-19 | Đẩy cấu hình ngoài biên (ROI sai; `T_dwell=900 s`; **`T_signhold` khổng lồ**; **`T_degraded_max`→"không bao giờ"**) | bị từ chối/kẹp theo §7a; giữ bản tốt gần nhất; cảnh báo | FR-20, [tài liệu 02 §7a](02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu) | S |
| SC-20 | OTA / khởi động lại được yêu cầu trong khi cảnh báo đang hoạt động | hoãn, hoặc làm trống **lớn tiếng tới đơn vị vận hành** — không bao giờ rớt thầm lặng | FR-21, ADR-0009 | S |
| SC-21 | Tiêm lỗi: giết tiến trình SM | biển báo làm trống trong `T_signhold`; trạng thái an toàn + cảnh báo | FR-11, ADR-0005/0009 | S |
| SC-22 | Tiêm lỗi: giết hộp biên | bộ điều khiển biển báo làm trống trong `T_signhold` | FR-11, ADR-0009 §A | S |
| SC-23 | Tiêm lỗi: cắt liên kết biển báo | bộ điều khiển biển báo làm trống trong `T_signhold` | FR-11, ADR-0009 §A | S |
| SC-24 | **CLEAR vs biển báo kẹt-BẬT** (trạng thái không bao giờ tắt) | → SAFE_STATE + leo thang bảo trì biển-báo-kẹt | **ADR-0013** | S |
| SC-25 | Radar chết (CAMERA-ONLY) | vẫn có thể khởi tạo; không giữ khi che khuất; suy giảm + cảnh báo | ma trận ADR-0009 §B | S |
| SC-26 | Camera chết khi nhàn rỗi (RADAR-ONLY) | **BLIND-TO-NEW** — không thể khởi tạo; cảnh báo trọng yếu | ma trận ADR-0009 §B | S |
| SC-27 | Cả hai cảm biến chết | SAFE_STATE (làm trống) + cảnh báo trọng yếu | ADR-0009 §B | S |
| SC-28 | Watchdog: logic bị kẹt cứng, không có đối chứng | xóa + phát ra lỗi (`T_watchdog`) | NFR-04, ADR-0005/0008 | S |
| SC-29 | Trôi-hiệu-chuẩn: tiêm một dịch chuyển homography tổng hợp | bộ giám sát trôi → suy giảm + cảnh báo | FR-10, R15 | S (trôi thực **F**) |
| SC-30 | Gộp trùng/ưu tiên/leo-thang-lại-khi-không-xác-nhận cảnh báo | một sự cố ≠ một cơn bão; cảnh báo trọng yếu leo thang lại nếu không được xác nhận | NFR-15, ADR-0011 | S (thời-gian-phản-hồi **F**) |

> Hai kịch bản là *được-thiết-kế, chưa-vững-tại-hiện-trường*: **SC-11** (ùn tắc) và **SC-06** (giữ-khi-che-khuất
> kéo dài) đều dựa trên tiêu chí (b) và được báo cáo **được-kiểm-chứng-bằng-logic như đặc tả**, với **SC-09** là
> bộ canh gác (b)-yếu tường minh rằng sự cố vẫn nằm trong giới hạn.

---

## 6. Tiêu chí đạt & phương pháp thống kê (đăng ký trước)

Một lần chạy đạt **nghiệm thu cấp-nguyên-mẫu-đại-học** khi, trên toàn bộ danh mục:

1. **Logic/định đoạt** — đầu ra SUT của mỗi kịch bản khớp với định đoạt oracle của nó (BẬT/TẮT đúng, chuyển tiếp suy giảm/xóa/trạng-thái-an-toàn đúng). Đây là **đạt/không-đạt theo từng kịch bản**, không phải một tỉ lệ.
2. **Định thời** — các độ trễ đo được nằm trong ngân sách: stop→warn ≤ `T_dwell`+2 s; confirmed-exit→clear ≤ `T_hold`+2 s; fault→blank ≤ `T_signhold`; không cảnh báo nào BẬT quá `T_watchdog`/`T_degraded_max` mà không có định đoạt lớn tiếng đã đặc tả.
3. **Kích hoạt nhầm được mô hình hóa** — ≤ mục tiêu của [tài liệu 01 §5](01-requirements.vi.md#5-chỉ-số-đánh-giá--tiêu-chí-nghiệm-thu) trên các kịch bản nhiễu đã dàn dựng, được báo cáo **theo-100-kịch-bản và theo-giờ-mô-phỏng** kèm mẫu số phơi nhiễm của nó.
4. **Độ phủ phát hiện lỗi** — ≥ 95 % của danh sách FMEA **tiêm-được-trên-bàn-thử** ([tài liệu 04 §2](04-risk-and-safety.vi.md#2-fmea-lite-kiểu-lỗi--tác-động--phát-hiện--phản-ứng)); các chế độ chỉ-hiện-trường (trôi, liên kết qua cự ly, năng lượng mặt trời) bị loại trừ và được báo cáo như vậy, không bị tính âm thầm.
5. **Không có đầu ra lừa dối/kẹt** — dưới **không** lỗi được tiêm nào mà SUT để lại một lần kẹt-BẬT hay một lần xóa thầm lặng.

**Phương pháp thống kê.** Các chỉ số tỉ lệ mang theo một **N tối thiểu và một tuyên bố độ tin cậy** được cố định *ở đây* trước khi chạy
(ví dụ kích-hoạt-nhầm-được-mô-hình-hóa được báo cáo kèm phơi nhiễm và một khoảng tin cậy). **Recall bị loại trừ
khỏi mô phỏng** (§1) — N của nó là dữ liệu thu thực, được điều phối bởi kế hoạch bằng-chứng-nghiệm-thu. Mô phỏng *có thể*
sinh khối lượng một cách rẻ cho các chỉ số logic/định thời/kích-hoạt-sai-trên-nhiễu-được-mô-hình-hóa; nó **không được**
báo cáo một con số recall.

**Đăng ký trước.** Các ngưỡng, danh mục, các dải tham số cảm biến tổng hợp, và N cho mỗi chỉ số tỉ lệ
được cố định trong tài liệu này (và lịch sử phiên bản của nó) trước khi các lần chạy Giai đoạn 3 bắt đầu. Các thay đổi sau
khi chạy được ghi nhận như các bản sửa đổi kèm lý do, không bao giờ là chỉnh sửa thầm lặng.

---

## 7. Những gì mô phỏng không thể khép lại (mang sang bàn thử / hiện trường)

Theo bậc **F** của [tài liệu 06](06-traceability-matrix.vi.md) và [ADR-0007](adr/ADR-0007-validation-and-data-strategy.vi.md):
recall thực khi mưa/chói/sương mù, tỉ lệ báo động giả thực, **nhiễu loạn radar thực / tiêu chí (b)**, liên kết
biên↔biển báo qua cự ly, **trôi hiệu chuẩn thực**, năng lượng mặt trời cho ≥ 72 h tự chủ, và môi trường IP65.
*Sự-phụ-thuộc-(b)* của SC-06/09/11 là sắc bén nhất trong số này: logic được kiểm chứng, tính-vững-tại-hiện-trường thì không.

---

## 8. Khả năng tái lập, công cụ & tạo phẩm

- **Tính tất định** — khung kiểm thử dùng một RNG có **gieo mầm (seed)**; mầm được ghi lại để bất kỳ lần chạy nào cũng tái lập y hệt. (Chính tính tất định này là *lý do* N tổng hợp không thể làm bằng chứng cho recall — §1.)
- **Quản lý phiên bản** — các tệp kịch bản, các tham số cảm biến tổng hợp, và bản dựng SUT được quản lý phiên bản cùng nhau; mỗi bản ghi kết quả mang theo **dấu vân tay `cfg_ver` / `model_ver` / `calib_ver`** ([tài liệu 02 §7](02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu)) và **bậc** của nó.
- **Công cụ** — bắt đầu với một **trình phát kịch bản cấp-sự-kiện (Cấp A) tùy chỉnh** (rẻ nhất, kiểm chứng trực tiếp máy trạng thái và logic duy trì/lỗi vốn nắm giữ phần lớn §5). CARLA/SUMO hoặc một trình phát cấp-khung-hình ([tài liệu 02 §8](02-system-architecture.vi.md#8-ngăn-xếp-công-nghệ-khuyến-nghị-mang-tính-chỉ-dẫn-không-ràng-buộc)) là tùy chọn, chỉ thêm nếu Cấp B xứng đáng với chi phí. SUT vẫn giống hệt qua mô phỏng, bàn thử, và hiện trường.
- **Đầu ra** — một báo cáo theo từng lần chạy: các ID kịch bản, đạt/không-đạt, các độ trễ/tỉ lệ đo được kèm CI, các thiết lập cảm biến tổng hợp (kèm cờ lạc quan), và bậc của mọi tuyên bố — nguyên liệu thô cho báo cáo khả thi Giai đoạn 5, nơi mỗi kết quả được phát biểu *kèm bậc của nó* để không tuyên bố nào vượt quá bằng chứng của nó.
