# 09 — Yêu cầu phần mềm → phần cứng & bàn giao giao diện

> 🇬🇧 Bản gốc tiếng Anh: [09-software-hardware-handoff.md](09-software-hardware-handoff.md)

**Dự án:** Hệ thống cảnh báo tự động làn dừng khẩn cấp (ESW)
**Trạng thái:** Đề xuất / Bản nháp — bàn giao từ **đội phần mềm** (ThS. Phó Trí Tín) sang đội **phần cứng/firmware** và **vận hành/kinh doanh**
**Cập nhật lần cuối:** 2026-06-27
**Liên quan:** [08 ICD](08-interface-control-document.vi.md) · [02 kiến trúc](02-system-architecture.vi.md) · [ADR-0001](adr/ADR-0001-sensing-modality.vi.md) · [ADR-0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md) · [ADR-0012](adr/ADR-0012-security-and-threat-model.vi.md)

**Mục đích.** Thiết kế phần mềm đã đủ ổn định để bắt tay xây dựng (các tài liệu [02](02-system-architecture.vi.md)/[07](07-simulation-methodology.vi.md)/[08](08-interface-control-document.vi.md); các ADR thuộc quyền sở hữu của phần mềm đã được chấp nhận). Trang này là **danh sách một-cửa về những gì phần mềm cần từ đội phần cứng/firmware** — và các **quyết định liên-đội** đang chốt cửa cho những ADR vẫn còn ở trạng thái *Đề xuất*. Mỗi yêu cầu dưới đây là một chỗ mà việc chọn linh kiện **âm thầm làm nên hoặc phá vỡ một bảo đảm an toàn của phần mềm**, vì vậy hãy đáp ứng nó hoặc phản hồi lại **trước khi mua sắm**. Toàn bộ lược đồ thông điệp (message schema) nằm trong [ICD (tài liệu 08)](08-interface-control-document.vi.md).

---

## 1. Các yêu cầu phần cứng/firmware mà thiết kế an toàn của phần mềm phụ thuộc vào

| ID | Phần mềm cần gì | Nguồn | Nếu không đáp ứng → hệ quả với phần mềm | Kiểm chứng thế nào |
|----|---------------------|--------|---------------------------------|-------------------|
| **RQ-H1** | **Radar phát hiện được một phương tiện *đứng yên* trong nhiễu nền ven đường (a) _và_ phân giải được làn dừng khẩn cấp với làn thông hành liền kề ở cự ly giám sát (b)** — một mô-đun đánh giá radar tạo ảnh / HRR FMCW, **chứ không phải** một thiết bị báo hiện diện thông thường. | [ADR-0001](adr/ADR-0001-sensing-modality.vi.md) | Logic giữ-khi-che-khuất và `CAMERA_OCCLUDED_DEGRADED` **đảo ngược thành kẹt-BẬT** (R12); khả năng phát hiện ban đêm/điều kiện bất lợi trở nên không chứng minh được → **hoãn lại cho hiện trường**. | Thử nghiệm radar giai đoạn 1; cổng giai đoạn 3 (a)+(b) |
| **RQ-H2** | **Bộ điều khiển biển báo = một *điểm cuối thông minh*:** nó phải **xóa trắng biển báo** nếu không có lệnh `SHOW` mới, **được xác thực** đến trong vòng `T_signhold`, và tôn trọng nhịp tim SHOW làm mới (IF-4). | [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md), [ADR-0012](adr/ADR-0012-security-and-threat-model.vi.md) | **Cơ chế tự ngắt an toàn không thể hoạt động** — một biển báo chốt trạng thái sẽ kẹt-BẬT khi hộp/liên kết chết. (Một VMS chốt trạng thái buộc phải dùng phương án dự phòng yếu hơn là watchdog+CLEAR.) | Tiêm lỗi: tắt-hộp / cắt-liên-kết → biển báo xóa trắng ≤ `T_signhold` |
| **RQ-H3** | **Camera:** màn trập toàn cục (global-shutter) / WDR mạnh + **chiếu sáng IR** cho ban đêm. | [ADR-0001](adr/ADR-0001-sensing-modality.vi.md), NFR-05 | Khả năng phát hiện ban đêm kém hơn; nhiều phát hiện sai hơn nạp vào vòng lặp. | Bộ kịch bản ngày/đêm trên bàn |
| **RQ-H4** | **Tính toán biên (edge compute)** với đủ TOPS để chạy bộ phát hiện **trong ngân sách độ trễ NFR-01** *và* trong phạm vi nguồn điện mặt trời. | ADR-0002/0003/[0006](adr/ADR-0006-connectivity-and-power.vi.md) | Độ trễ dừng→cảnh báo hoặc ngân sách điện mặt trời bị phá vỡ. | Đo độ trễ trên bàn với bo mạch mục tiêu |
| **RQ-H5** | **Nguồn thời gian:** thời gian **tuyệt đối** được hiệu chỉnh bằng GNSS/PPS + đồng bộ **tương đối dưới-mức-khung-hình (sub-frame)** giữa các cảm biến, duy trì được qua các lần mất tín hiệu. | NFR-16 | Hợp nhất camera↔radar suy giảm; **dấu thời gian phục vụ kiểm toán trở nên không có giá trị pháp lý** (trách nhiệm pháp lý R10). | Đo đồng bộ trên bàn; duy trì qua mất tín hiệu (hiện trường) |
| **RQ-H6** | **Liên kết biên↔biển báo** được đặc tả về **tổn hao / độ trễ / năng lượng** ở khoảng cách ≥ DSD, và có khả năng tải một kênh **được xác thực**. | [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md), IF-4 | Không thể tinh chỉnh `T_signhold`/`T_assert_refresh` một cách an toàn → nhấp nháy (cry-wolf) hoặc kẹt-BẬT. | Thử nghiệm liên kết qua khoảng cách (hoãn lại cho hiện trường) |
| **RQ-H7** | **Ngân sách điện phải bao gồm mức tiêu thụ của radar đạt-chuẩn-cổng** (cao hơn một thiết bị báo hiện diện thông thường). | [ADR-0006](adr/ADR-0006-connectivity-and-power.vi.md), [ADR-0001](adr/ADR-0001-sensing-modality.vi.md) | Không đạt mức tự chủ điện mặt trời ≥ 72 giờ (NFR-07). | Tính lại ngân sách năng lượng sau khi chọn radar |

> Cặp có rủi ro cao nhất là **RQ-H1** (năng lực radar) và **RQ-H2** (bộ điều khiển biển báo thông minh): cả hai đều là nền tảng cho các bảo đảm an toàn cốt lõi của hệ thống, và cả hai đều là **lựa chọn phần cứng**, không phải lựa chọn phần mềm.

---

## 2. Các giao diện được đóng băng *chung* (phần mềm đề xuất, phần cứng cùng ký)

Phần mềm đã đơn phương đóng băng các giao diện **nội bộ** — **IF-2** (tri giác → máy trạng thái) và **IF-3** (máy trạng thái ↔ lớp trừu tượng cơ cấu chấp hành). Các giao diện sau đây là **chia sẻ** và phải được thống nhất với phần cứng trước khi đóng băng; lược đồ nằm trong [ICD (tài liệu 08)](08-interface-control-document.vi.md):

- **IF-1** — trình điều khiển cảm biến (khung hình camera, tín hiệu phản hồi radar) kèm dấu thời gian.
- **IF-4** — biên → bộ điều khiển biển báo **SHOW làm mới + xác thực** (liên kết tối-quan-trọng-về-an-toàn; RQ-H2/H6).
- **Phân phối thời gian** (RQ-H5).

---

## 3. Phần mềm cung cấp gì ↔ cần nhận lại gì

- **Phần mềm cung cấp:** các giao kèo `SHOW / CLEAR / STATUS` và SHOW làm mới (IF-3/IF-4); ngữ nghĩa cấu hình / OTA / ghi đè kèm cưỡng chế giới hạn ngay trên thiết bị; lược đồ nhịp tim và sự kiện.
- **Phần mềm cần nhận lại từ phần cứng:** **đọc-lại trạng thái** biển báo (trạng thái đèn được-lệnh so với thực-tế); các tín hiệu **tình trạng từng cảm biến** (độ cũ của khung hình, độ sống của radar); các ngưỡng **đo từ xa pin/nguồn điện**; và **tổn hao/độ trễ đo được** của liên kết biên↔biển báo.

---

## 4. Các quyết định liên-đội đang chốt cửa cho những ADR vẫn còn *Đề xuất*

Các ADR này vẫn ở trạng thái **Đề xuất** cho đến khi đội sở hữu ký duyệt (rà soát phía phần mềm đã xong):

| ADR | Quyết định mà đội sở hữu phải đưa ra | Đội sở hữu |
|-----|------------------------------------|-------|
| [ADR-0001](adr/ADR-0001-sensing-modality.vi.md) | Lựa chọn mô-đun radar **+ tái cơ cấu ngân sách** (~6–8 triệu đạt-chuẩn-cổng so với loại thông thường) | **Phần cứng + kinh doanh** |
| [ADR-0004](adr/ADR-0004-warning-actuator-integration.vi.md) | Hậu phương biển báo (LED tự làm so với VMS của đơn vị vận hành) **+ bộ thông điệp QCVN 41** | **Phần cứng + vận hành/cơ quan quản lý** |
| [ADR-0006](adr/ADR-0006-connectivity-and-power.vi.md) | Nguồn điện (định cỡ pin mặt trời/ắc quy), kết nối, vỏ bọc IP65 | **Phần cứng** |
| [ADR-0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md) | Bố trí bộ-điều-khiển-biển-báo-như-điểm-cuối-thông-minh (**RQ-H2**) | **Phần cứng/firmware** |
| [ADR-0011](adr/ADR-0011-operator-concept-and-alarm-management.vi.md) | Quy trình vận hành (ConOps) của người trực: bố trí nhân sự, thời gian phản hồi, thỏa thuận vận hành | **Vận hành/kinh doanh** |
| [ADR-0012](adr/ADR-0012-security-and-threat-model.vi.md) | An ninh vật lý + quản lý khóa cho đội thiết bị (phần **xác thực phần mềm** đã được đặc tả xong) | **Phần cứng/vận hành** |

> **Các ADR thuộc quyền sở hữu của phần mềm được chấp nhận ngày 2026-06-27:** [0002](adr/ADR-0002-edge-vs-cloud-processing.vi.md), [0003](adr/ADR-0003-detection-algorithm.vi.md), [0005](adr/ADR-0005-fail-safe-and-system-safety.vi.md), [0007](adr/ADR-0007-validation-and-data-strategy.vi.md), [0008](adr/ADR-0008-detection-persistence-and-multitrack.vi.md), [0010](adr/ADR-0010-operator-override-and-manual-control.vi.md) (cơ chế), [0013](adr/ADR-0013-degraded-hold-unification.vi.md).

---

## 5. Hai mục dành cho đội kinh doanh/vận hành (không phải phần mềm, nhưng phần mềm cần câu trả lời)

- **Phạm vi SXTN (R19) — xác nhận với bên cấp kinh phí trước.** Sản phẩm giao nộp cấp-trường là một **mẫu nguyên lý** (điều mà tất cả các tài liệu này giả định) hay là một **đơn vị sản xuất thử nghiệm** được kỳ vọng theo hợp đồng? Điều đó thay đổi những gì mọi người xây dựng.
- **Thời gian chờ giao hàng mua sắm.** Bộ kit đánh giá mmWave còn **8–12 tuần** nữa mới về; việc đặt nó chốt cửa cho thử nghiệm RQ-H1 và toàn bộ tuyên bố về ban đêm/điều kiện bất lợi — hãy đặt hàng ngay khi khởi động dự án.
