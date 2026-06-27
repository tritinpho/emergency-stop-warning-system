# 04 — Rủi ro, An toàn & Tuân thủ

> 🇬🇧 Bản gốc tiếng Anh: [04-risk-and-safety.md](04-risk-and-safety.md)

**Dự án:** Hệ thống cảnh báo tự động làn dừng xe khẩn cấp (ESW)
**Trạng thái:** Đề xuất
**Cập nhật:** 2026-06-26
**Liên quan:** [ADR-0005 an toàn khi sự cố](adr/ADR-0005-fail-safe-and-system-safety.vi.md) · [yêu cầu §1](01-requirements.vi.md#1-the-safety-reframe-read-first)

Vì hệ thống đưa ra khuyến cáo cho các tài xế di chuyển nhanh ở gần một chướng ngại vật đứng yên, rủi ro và an toàn được
xử lý như một phần hạng nhất của kiến trúc, không phải là một phụ lục. Tài liệu này chứa **bảng đăng ký
rủi ro**, một **phân tích kiểu lỗi (FMEA-lite)**, **bản tóm tắt an toàn khi sự cố**, và các nghĩa vụ về **quyền riêng tư /
pháp lý**.

---

## 1. Bảng đăng ký rủi ro

Khả năng xảy ra (L) và Mức tác động (I): 1 = thấp, 5 = cao. Mức phơi nhiễm (Exp) = L × I.

| ID | Rủi ro | L | I | Exp | Biện pháp giảm thiểu |
|----|------|--:|--:|----:|-----------|
| R1 | **Bỏ sót thầm lặng** — xe đang dừng không được phát hiện; không hiển thị cảnh báo | 3 | 5 | 15 | Hợp nhất đa cảm biến ([ADR-0001](adr/ADR-0001-sensing-modality.vi.md)); bộ giám sát tình trạng; mục tiêu recall đã đo (doc 01 §5). |
| R2 | **Báo động giả lặp lại (cry wolf)** — các lần kích hoạt sai lặp lại làm xói mòn niềm tin của tài xế | 3 | 4 | 12 | Dwell + hysteresis + cổng lọc ROI + đối chiếu chéo radar; mục tiêu tỉ lệ báo động giả; rà soát hiệu chỉnh niềm tin. |
| R3 | **Kẹt-BẬT (Stale-ON)** — cảnh báo bị kẹt ở trạng thái bật sau khi xe đã rời đi | 2 | 4 | 8 | Watchdog giới hạn thời gian kích hoạt (NFR-04); đọc lại trạng thái bảng cảnh báo; hysteresis với thời gian giữ có giới hạn. |
| R4 | **Cảnh báo đặt quá gần** — quá muộn để tài xế kịp hành động | 3 | 5 | 15 | **Yêu cầu bố trí dựa trên DSD** (doc 01 §4); nghiên cứu chọn vị trí theo từng địa điểm; bảng lặp lại (PL-04). |
| R5 | **Mù trong điều kiện bất lợi** — đêm/mưa/sương mù vô hiệu hóa camera | 4 | 4 | 16 | Radar (+ nhiệt ảnh tùy chọn); các bài kiểm tra nghiệm thu theo điều kiện cụ thể; cảnh báo chế độ suy giảm. |
| R6 | **Mất nguồn/kết nối** tại hiện trường | 3 | 3 | 9 | Pin mặt trời + ắc quy ≥72 h; tự chủ tại biên ([ADR-0002](adr/ADR-0002-edge-vs-cloud-processing.vi.md)); lưu và chuyển; cảnh báo nhịp tín hiệu (heartbeat). |
| R7 | **Tài xế phụ thuộc/chủ quan quá mức** — tài xế ngừng quan sát, tin tưởng vào hệ thống | 3 | 4 | 12 | Định hình như một *công cụ hỗ trợ*, không phải một bảo đảm; hành vi nhất quán, đáng tin cậy; không hứa hẹn phủ sóng toàn bộ. |
| R8 | **Giả mạo / can thiệp trái phép (spoofing/tampering)** — bảng cảnh báo bị ép hiển thị thông điệp sai | 2 | 4 | 8 | Điều khiển có xác thực, mã hóa; firmware được ký; an ninh vật lý; đọc lại trạng thái (NFR-09). |
| R9 | **Quyền riêng tư / pháp lý** — thu thập PII (biển số, khuôn mặt) và lưu giữ | 3 | 3 | 9 | Suy luận trên thiết bị; **không lưu giữ video thô**; tối thiểu hóa bằng chứng sự kiện; kiểm soát truy cập (§4). |
| R10 | **Mơ hồ về trách nhiệm pháp lý** — ai chịu trách nhiệm nếu một cảnh báo bị lỗi | 2 | 4 | 8 | Khái niệm vận hành rõ ràng; nhật ký sự kiện (audit log); định hình rõ ràng "khuyến cáo, tài xế chịu trách nhiệm"; thỏa thuận với đơn vị vận hành. |
| R11 | **Vượt ngân sách / vượt phạm vi** — cố gắng triển khai hiện trường trên một nguồn tài trợ nguyên mẫu | 4 | 3 | 12 | MVP và giới hạn ngân sách được giới hạn phạm vi ([doc 03](03-roadmap-and-phasing.vi.md)); thử nghiệm hiện trường được hoãn sang cấp sở. |
| R12 | **Che khuất** — xe tải đi ngang che mất xe đang dừng | 3 | 3 | 9 | Thời gian giữ hysteresis hấp thụ che khuất ngắn; radar (hình học khác); vị trí/độ cao đặt cảm biến. |
| R13 | **Lớp đối tượng giả** — mảnh vỡ/bóng đổ/động vật kích hoạt hoặc gây nhầm lẫn | 2 | 3 | 6 | Bộ phát hiện học máy có phân lớp; cổng lọc ROI; dwell; chứng thực bằng radar. |

**Các mức phơi nhiễm cao nhất cần thiết kế đối phó trước tiên:** R5 (mù trong điều kiện bất lợi), R1 (bỏ sót thầm lặng), R4
(đặt quá gần) — cả ba đều được xử lý bằng các quyết định mang tính chịu lực đã được đưa ra (ADR-0001,
ADR-0005, doc 01 §4).

## 2. FMEA-lite (kiểu lỗi → tác động → phát hiện → phản ứng)

| Kiểu lỗi | Tác động | Cách phát hiện | Phản ứng của hệ thống |
|--------------|--------|--------------|-----------------|
| Camera chết / khung hình đóng băng | Mất khả năng phát hiện bằng hình ảnh | Watchdog phát hiện khung hình cũ; kiểm tra tình trạng theo từng cảm biến | Nếu radar vẫn tốt → chạy chế độ suy giảm + cảnh báo; nếu không → TRẠNG THÁI AN TOÀN + cảnh báo |
| Radar chết | Mất khả năng xác nhận bền vững với thời tiết | Nhịp tín hiệu cảm biến (heartbeat) | Chỉ camera ở chế độ suy giảm + cảnh báo (gắn cờ rủi ro ban đêm/thời tiết) |
| Tiến trình nhận diện sập | Không có phát hiện nào được tạo ra | Bộ giám sát tiến trình / nhịp tín hiệu watchdog | Tự khởi động lại; nếu lặp lại → TRẠNG THÁI AN TOÀN + cảnh báo |
| Logic quyết định bị kẹt với bảng cảnh báo BẬT | Cảnh báo kẹt-BẬT (Stale-ON) | Bộ định thời xác nhận lại `T_watchdog` | Buộc đánh giá lại → GIẢI TỎA nếu không được xác nhận |
| Đứt liên kết bảng cảnh báo / bảng không phản hồi | Cảnh báo được lệnh nhưng không thực sự hiển thị | Sai lệch khi **đọc lại trạng thái** bảng cảnh báo | Cảnh báo ngay lập tức; đánh dấu vị trí ở chế độ suy giảm |
| Bảng cảnh báo bị kẹt BẬT về mặt vật lý | Báo động giả lặp lại (cry wolf) | Đọc lại trạng thái so với lệnh | Cảnh báo; điều động nhân viên vận hành/bảo trì |
| Nguồn yếu (cạn pin mặt trời) | Sắp tắt máy | Ngưỡng telemetry ắc quy | Cảnh báo sớm nguồn yếu; tắt máy có trật tự về TRẠNG THÁI AN TOÀN |
| Gián đoạn WAN | Không có telemetry/giám sát | Khoảng trống nhịp tín hiệu tại TMC | Vòng an toàn vẫn tiếp tục (tự chủ tại biên); sự kiện xếp hàng đợi; cảnh báo khi có khoảng trống |
| Lệch đồng hồ giữa các cảm biến | Hợp nhất sai | Bộ giám sát đồng bộ thời gian | Gắn cờ; chuyển về dùng cảm biến đơn; cảnh báo |
| Suy giảm mô hình sau OTA | Giảm độ chính xác | Số liệu canary sau cập nhật | **Khôi phục về** (rollback) phiên bản đã ký trước đó |

Danh sách FMEA này cũng là **tập kiểm thử tiêm lỗi** cho nghiệm thu (doc 01 §5 — mục tiêu ≥95%
độ phủ phát hiện).

## 3. Bản tóm tắt an toàn khi sự cố

Hành vi an toàn được đặc tả trong [ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.vi.md). Tóm lại:

- **An toàn khi sự cố (fail-safe):** khi có lỗi trọng yếu, bảng cảnh báo về một **trạng thái đã biết, không gây hiểu nhầm** (mặc định để trống —
  nó không bao giờ khẳng định một mối nguy mà nó không thể chứng thực).
- **Báo lỗi rõ ràng (fail-loud):** thiết bị **leo thang sự suy giảm tới nhân viên vận hành**; "mù" là một báo động, không bao giờ là sự im lặng.
- **Không kẹt-BẬT (No stale-ON):** một **watchdog** giới hạn mọi lần kích hoạt; **đọc lại trạng thái** xác minh bảng cảnh báo
  thực sự phản ánh đúng lệnh.
- **Giữ gìn niềm tin:** dwell + hysteresis ngăn dao động (flapping) và kích hoạt sai, giữ cho cảnh báo
  đáng tin cậy (chống báo động giả lặp lại).

## 4. Quyền riêng tư, dữ liệu & tuân thủ pháp lý

Đề xuất không đề cập đến những điều này; đối với một hệ thống camera trên đường công cộng thì chúng là bắt buộc.

| Lĩnh vực | Nghĩa vụ | Phản ứng thiết kế |
|------|-----------|-----------------|
| **Tối thiểu hóa PII** | Camera thu biển số/khuôn mặt (dữ liệu cá nhân) | **Suy luận trên thiết bị**; không tải lên hay lưu giữ video thô liên tục. |
| **Lưu giữ bằng chứng** | Việc kiểm toán một quyết định cần *một số* bằng chứng | Chỉ lưu **ảnh chụp/siêu dữ liệu sự kiện tối thiểu**, thời gian lưu giữ có giới hạn, được kiểm soát truy cập (FR-16, NFR-10). |
| **Giới hạn mục đích** | Hệ thống dùng để **cảnh báo an toàn, không phải cưỡng chế** | Không có quy trình xử phạt/định danh; cách định hình và phạm vi dữ liệu phản ánh điều này (nguyên tắc định hướng 2). |
| **Tuân thủ về biển báo** | Biển báo/thông điệp đường bộ được quản lý theo quy định | Nội dung cảnh báo và bảng cảnh báo tuân thủ **QCVN 41** (quy chuẩn kỹ thuật quốc gia về báo hiệu đường bộ); tập thông điệp được rà soát. |
| **Tiêu chuẩn đường bộ/hình học** | Việc bố trí & lắp đặt được quản lý theo quy định | Tuân theo tiêu chuẩn hình học đường cao tốc (ví dụ **TCVN 5729**) và yêu cầu của đơn vị vận hành; bố trí dựa trên DSD (doc 01 §4). |
| **An ninh** | Ngăn chặn cảnh báo bị giả mạo/can thiệp | Kênh có xác thực, mã hóa; firmware được ký; an ninh vật lý (NFR-09, R8). |
| **Trách nhiệm pháp lý / khái niệm vận hành** | Làm rõ trách nhiệm | Ghi chép hệ thống là **khuyến cáo** (tài xế vẫn chịu trách nhiệm); duy trì một **nhật ký sự kiện**; thống nhất vai trò với đơn vị vận hành (R10). |
| **Phê duyệt** | Triển khai hiện trường cần sự phê duyệt của cơ quan có thẩm quyền | Phối hợp với cơ quan quản lý đường bộ/đơn vị vận hành từ sớm; coi việc phê duyệt là một điều kiện tiên quyết của thử nghiệm hiện trường (cấp sở). |

> Các nghĩa vụ này nhẹ nhàng để tuân thủ ở giai đoạn cấp trường/trên bàn (không thu thập dữ liệu công cộng), nhưng
> **các lựa chọn thiết kế giúp chúng dễ dàng về sau — suy luận trên thiết bị, không lưu giữ dữ liệu thô, nhật ký sự kiện —
> phải được đưa ra ngay bây giờ**, đó là lý do chúng được tích hợp sẵn vào yêu cầu và kiến trúc thay vì
> lắp thêm vào lúc triển khai hiện trường.

## 5. Các câu hỏi an toàn còn mở cho nhóm

1. **Tỉ lệ báo động giả chấp nhận được** với đơn vị vận hành là bao nhiêu trước khi tài xế bắt đầu mất tin tưởng vào
   bảng cảnh báo? (Hiệu chỉnh mục tiêu của R2 cùng với đơn vị vận hành.)
2. Đối với các vị trí mà bố trí DSD là bất khả thi, một **bảng lặp lại** có chấp nhận được không, hay vị trí đó
   đơn giản là bị loại? (PL-04.)
3. Một thiết bị ở chế độ suy giảm có bao giờ nên hiển thị một **cảnh báo thường trực theo từng vị trí** (ADR-0005 Phương án C) không, và dưới
   cơ chế quản trị nào?
4. **Thời hạn lưu giữ và chính sách truy cập** nào đối với bằng chứng sự kiện thỏa mãn được cả nhu cầu kiểm toán lẫn
   nghĩa vụ về quyền riêng tư?
