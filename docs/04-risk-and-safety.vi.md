# 04 — Rủi ro, An toàn & Tuân thủ

> 🇬🇧 Bản gốc tiếng Anh: [04-risk-and-safety.md](04-risk-and-safety.md)

**Dự án:** Hệ thống cảnh báo tự động làn dừng xe khẩn cấp (ESW)
**Trạng thái:** Đề xuất
**Cập nhật:** 2026-06-26
**Liên quan:** [ADR-0005 an toàn khi sự cố](adr/ADR-0005-fail-safe-and-system-safety.vi.md) · [ADR-0009 bố trí an toàn khi sự cố & chế độ suy giảm](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md) · [yêu cầu §1](01-requirements.vi.md#1-tái-định-khung-an-toàn-đọc-phần-này-trước)

Vì hệ thống đưa ra khuyến cáo cho các tài xế di chuyển nhanh ở gần một chướng ngại vật đứng yên, rủi ro và an toàn được
xử lý như một phần hạng nhất của kiến trúc, không phải là một phụ lục. Tài liệu này chứa **giới hạn bảo
vệ**, **bảng đăng ký rủi ro**, một **phân tích kiểu lỗi (FMEA-lite)**, **bản tóm tắt an toàn khi sự
cố**, và các nghĩa vụ về **quyền riêng tư / pháp lý**.

---

## 0. Giới hạn bảo vệ (mối nguy còn lại)

Những gì hệ thống bao phủ chính là thước đo của những gì nó **không** làm — phát biểu rõ ranh giới vừa
là sự trung thực, vừa là biện pháp kiểm soát chính đối với sự phụ thuộc quá mức (R7). ESW **không**:

- cảnh báo về một xe vẫn **đang giảm tốc tiến vào** lề đường — thời điểm động nhất, năng lượng cao nhất;
  chỉ một xe *đã xác nhận dừng* (≥ thời gian dwell) mới làm dấy lên một cảnh báo;
- bảo vệ phần **giữa** các vùng được giám sát — phạm vi phủ là các vùng giá trị cao rời rạc, không phải
  toàn bộ một hành lang ([doc 02 §6](02-system-architecture.vi.md#6-mô-hình-phạm-vi-giám-sát));
- **khẳng định cảnh báo lề đường trong lúc ùn tắc nặng / dừng-chạy (stop-and-go)** — khi chính làn lưu
  thông sát ROI cũng đứng yên, cảnh báo bị **ngăn chặn hoặc đổi thông điệp** một cách có chủ đích để tránh
  kích hoạt giả vào giữa một đám kẹt xe ([doc 02 §4](02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo),
  R14). Lưu ý sự sắc bén: *mật độ giao thông cao* là một điều kiện nguy-hiểm-hàng-đầu **có tên gọi**
  ([doc 00 §1](00-context-and-glossary.vi.md)), nên biện pháp chống báo-động-giả mở ra một khoảng trống
  phạm vi phủ **đúng trong một điều kiện rủi ro cao** — được mang vào khái niệm vận hành và xem xét lại
  với dữ liệu ùn tắc thực tại thử nghiệm hiện trường;
- buộc bất kỳ tài xế nào phải hành động — nó mang tính **khuyến cáo**; một tài xế phớt lờ bảng cảnh báo
  thì không được bảo vệ;
- cảnh báo trong **cửa sổ xác nhận** — trong khoảng ~`T_dwell + T_activate` (≈ 7 s) sau khi một xe vừa
  dừng, chưa có cảnh báo nào được hiển thị (chính là *ngân sách phơi nhiễm chưa-cảnh-báo*,
  [doc 01 §4](01-requirements.vi.md#4-bố-trí-cảnh-báo--phép-tính-mà-đề-xuất-bỏ-sót));
- phát hiện đáng tin cậy một **người đi bộ vào ban đêm** — tiết diện radar nhỏ trong khi camera ở trạng
  thái yếu nhất, nên FR-08 chỉ đặt một mục tiêu ban đêm *nỗ lực tốt nhất*
  ([doc 01 §5](01-requirements.vi.md#5-chỉ-số-đánh-giá--tiêu-chí-nghiệm-thu)); một người bị mắc kẹt
  trên lề đường trong bóng tối là một **rủi ro còn lại đã được phát biểu** (mối nguy H-C), không phải
  một trường hợp được bao phủ;
- phát hiện nguyên nhân, điều động cứu hộ, hay điều khiển bất kỳ phương tiện nào (các phi-mục-tiêu rõ ràng,
  [doc 00 §2](00-context-and-glossary.vi.md#2-mục-tiêu--ngoài-phạm-vi));
- bảo đảm phát hiện vượt ra ngoài phạm vi đã kiểm chứng (ví dụ đêm/bất lợi trước khi cổng radar
  [ADR-0001](adr/ADR-0001-sensing-modality.vi.md) được thông qua — đã thiết kế, chưa chứng minh).

Mỗi mục là một ranh giới phạm vi có chủ đích, được mang vào khái niệm vận hành và biện pháp giảm thiểu
sự phụ thuộc quá mức (R7), và được xem xét lại tại thử nghiệm hiện trường.

Một tương tác sắc bén hơn cả, nên hãy phát biểu thẳng: **fail-safe-blank × phụ thuộc quá mức.**
Khi thiết bị gặp sự cố nó chuyển sang **để trống** (không cảnh báo) — lựa chọn đúng để chống báo động
giả lặp lại ([ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.vi.md)) — nhưng một tài xế đã *học cách
phụ thuộc* vào bảng cảnh báo khi đó **còn tệ hơn so với khi không có hệ thống nào** (họ đã ngừng quan sát
*và* lại không có cảnh báo). Biện pháp kiểm soát là **báo lỗi rõ ràng tới đơn vị vận hành** (điều động
tuần tra / CCTV) và không bao giờ để niềm tin vượt quá phạm vi phủ (R7); rủi ro còn lại mang tính hành vi
và không thể loại bỏ hoàn toàn bằng kỹ thuật.

**Phạm vi bảo vệ thực tế tích lũy (hãy phát biểu một lần, rõ ràng).** Mỗi giới hạn ở trên được nêu riêng
lẻ, nhưng *tích* của chúng hẹp hơn "phát hiện xe đang dừng." Hệ thống chủ động bảo vệ trước một xe **đã
dừng hẳn trong ≳ `T_dwell` + `T_activate` (~7 s)**, **trong dòng xe lưu thông tự do (không ùn tắc)**,
**bên trong một vùng được giám sát**, **trong các điều kiện đã kiểm chứng** (ban ngày bây giờ; ban
đêm/bất lợi chỉ khi cổng radar [ADR-0001](adr/ADR-0001-sensing-modality.vi.md) được thông qua), được nhìn
bởi một thiết bị **khỏe mạnh hoặc còn-camera**. Ngoài phạm vi đó hệ thống **im lặng theo thiết kế** — chỉ
chấp nhận được vì nó *được phát biểu* và khái niệm vận hành (tuần tra / CCTV) bao phủ phần còn lại. Câu
tổng hợp này chính là tiêu đề trung thực mà các gạch đầu dòng theo từng mục cộng lại thành.

---

## 1. Bảng đăng ký rủi ro

**Mối nguy an toàn so với rủi ro dự án.** Bảng đăng ký được chấm điểm phơi nhiễm dưới đây cố ý chứa cả
hai. Đối với một hệ thống liên quan đến an toàn, các *mối nguy an toàn* — những cách hệ thống có thể góp
phần gây hại trên đường — xứng đáng có tầm nhìn riêng, nên chúng được tách ra ở đây trước tiên và truy
vết tới yêu cầu/ADR kiểm soát. Đây là một **bộ khung nhật ký mối nguy (hazard-log skeleton)**; một phân
tích mối nguy đầy đủ là một sản phẩm bàn giao ở cấp sở
([doc 05 §3](05-field-pilot-proposal.vi.md#3-mục-tiêu)).

| Mối nguy (gây hại trên đường) | Nguyên nhân chính | Biện pháp kiểm soát chính | Còn lại sau kiểm soát | Truy vết tới |
|-------------------------------|-------------------|---------------------------|-----------------------|--------------|
| **H-A** Va chạm từ phía sau / va chạm thứ cấp với một xe đang dừng — dòng xe phía sau không được cảnh báo kịp thời | Bỏ sót thầm lặng (cảm biến mù, che khuất, sập) **hoặc** cảnh báo đặt quá gần | Đa cảm biến + bộ giám sát tình trạng + trạng thái an toàn dead-man's; bố trí theo DSD | Bỏ sót trong điều kiện thuận lợi; khoảng trống giữa các vùng; cửa sổ dwell trước khi xác nhận | R1, R4, R5, R12; ADR-[0001](adr/ADR-0001-sensing-modality.vi.md)/[0005](adr/ADR-0005-fail-safe-and-system-safety.vi.md)/[0008](adr/ADR-0008-detection-persistence-and-multitrack.vi.md); [doc 01 §4](01-requirements.vi.md#4-bố-trí-cảnh-báo--phép-tính-mà-đề-xuất-bỏ-sót) |
| **H-B** Phanh gấp / đánh lái không cần thiết do một cảnh báo giả hoặc cũ | Kích hoạt giả hoặc kẹt-BẬT ("cry wolf") | Dwell + hysteresis + cổng lọc ROI + đối chiếu chéo radar; watchdog + đọc lại trạng thái | Tỉ lệ báo động giả còn lại (được hiệu chỉnh bởi đơn vị vận hành) | R2, R3; [ADR-0008](adr/ADR-0008-detection-persistence-and-multitrack.vi.md); [doc 01 §5](01-requirements.vi.md#5-chỉ-số-đánh-giá--tiêu-chí-nghiệm-thu) |
| **H-C** Người đi bộ trên lề đường bị tông | Người không được phát hiện (đặc biệt vào ban đêm) | Lớp người trong bộ phát hiện; cảnh báo khi có người trong/cạnh ROI | Phát hiện người đi bộ ban đêm chỉ là nỗ lực tốt nhất (doc 01 §5) | FR-08; [ADR-0003](adr/ADR-0003-detection-algorithm.vi.md) |
| **H-D** Phụ thuộc quá mức — tài xế ngừng quan sát, tin tưởng vào hệ thống | Niềm tin bị hiệu chỉnh sai so với phạm vi phủ thực tế | Định hình như một công cụ hỗ trợ; phát biểu giới hạn bảo vệ (§0); hành vi nhất quán | Mang tính hành vi; không thể loại bỏ hoàn toàn bằng kỹ thuật | R7; [doc 01 §1](01-requirements.vi.md#1-tái-định-khung-an-toàn-đọc-phần-này-trước) |
| **H-E** Sóng phanh (giảm tốc dây chuyền) — ngay cả một cảnh báo *đúng* cũng khiến dòng xe phía sau dày đặc phanh/giảm tốc, gây nguy cơ va chạm từ phía sau *bên trong* dòng xe lưu thông | Một lần kích hoạt đúng trong điều kiện mật độ cao gây ra một sóng giảm tốc đột ngột | Bố trí theo **DSD** cho thời gian phản ứng mượt mà (không phải một cú dừng khẩn cấp); thông điệp QCVN 41 súc tích, rõ nghĩa; (hiện trường) phối hợp với thực hành VMS của đơn vị vận hành | Nguy cơ giảm tốc còn lại trong dòng xe đông đúc | Liền kề R2; [doc 01 §4](01-requirements.vi.md#4-bố-trí-cảnh-báo--phép-tính-mà-đề-xuất-bỏ-sót) |

Bảng đăng ký được chấm điểm phơi nhiễm sau đó bao phủ **tất cả** rủi ro (an toàn + dự án + vận hành) để phục vụ lập kế hoạch.

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
| R10 | **Trách nhiệm pháp lý của sự phụ thuộc** — một hệ thống an toàn được triển khai nhưng có thể mắc lỗi có thể *làm tăng* mức phơi nhiễm của đơn vị vận hành so với khi không có hệ thống nào (sự phụ thuộc được tạo ra), cộng thêm sự mơ hồ về việc ai chịu trách nhiệm nếu một cảnh báo bị lỗi | 2 | 4 | 8 | Khái niệm vận hành rõ ràng; nhật ký sự kiện (audit log) chứng minh hành vi đúng đặc tả; định hình rõ ràng "khuyến cáo, tài xế chịu trách nhiệm"; **thỏa thuận với đơn vị vận hành giải quyết minh thị câu hỏi về sự phụ thuộc**; phát biểu giới hạn bảo vệ (§0). |
| R11 | **Vượt ngân sách / vượt phạm vi** — cố gắng triển khai hiện trường trên một nguồn tài trợ nguyên mẫu | 4 | 3 | 12 | MVP và giới hạn ngân sách được giới hạn phạm vi ([doc 03](03-roadmap-and-phasing.vi.md)); thử nghiệm hiện trường được hoãn sang cấp sở. |
| R12 | **Che khuất** — xe tải đi ngang che mất xe đang dừng | 3 | 3 | 9 | Thời gian giữ hysteresis hấp thụ che khuất ngắn; radar (hình học khác); vị trí/độ cao đặt cảm biến. **Phụ thuộc vào việc radar phân biệt làn ([ADR-0001](adr/ADR-0001-sensing-modality.vi.md) cổng b); nếu yếu, khoảng giữ-khi-che-khuất có thể _đảo_ thành một lần giữ-giả (kẹt-BẬT) trên chính chiếc xe tải che khuất — kiểm chứng tại hiện trường, không khép lại được trên bàn thử.** |
| R13 | **Lớp đối tượng giả** — mảnh vỡ/bóng đổ/động vật kích hoạt hoặc gây nhầm lẫn | 2 | 3 | 6 | Bộ phát hiện học máy có phân lớp; cổng lọc ROI; dwell; chứng thực bằng radar. |
| R14 | **Kích hoạt giả do ùn tắc** — dòng xe lưu thông đang dừng cạnh ROI bị đọc nhầm thành một xe dừng trên lề; điều kiện "mật độ cao" là tệ nhất cho việc phân biệt ROI | 3 | 3 | 9 | Phát hiện ùn tắc (các vết đứng yên trải dài qua các làn lưu thông) → ngăn chặn/đổi thông điệp; hình học ROI + phân biệt làn bằng radar; kịch bản nghiệm thu minh thị ([doc 02 §4](02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo)). |
| R15 | **Lỗi hiệu chuẩn / trôi hiệu chuẩn** — homography sai hoặc thông số ngoại lai camera↔radar sai, hoặc trôi do cột rung lắc / chấn động / nhiệt, làm dịch chuyển ROI một cách thầm lặng → bỏ sót hoặc báo động giả có hệ thống | 3 | 4 | 12 | Quy trình hiệu chuẩn theo từng vị trí; kiểm tra lại định kỳ; **bộ giám sát trôi** trong bộ giám sát tình trạng; cảnh báo khi vượt dung sai ([doc 02 §4](02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo)). |
| R16 | **Cấu hình không an toàn / đẩy OTA** — một ROI/bộ định thời sai hoặc một mô hình bị thoái lui phá vỡ chức năng an toàn từ xa; việc ký chặn *can thiệp trái phép*, chứ không chặn *lỗi của người vận hành* | 2 | 4 | 8 | **Ràng buộc biên tham số tại thiết bị** (FR-20); triển khai theo từng giai đoạn/được kiểm chứng + số liệu canary; **hoãn OTA khi một cảnh báo đang hoạt động** (FR-21); khôi phục có ký (§2). |

**Các mức phơi nhiễm cao nhất cần thiết kế đối phó trước tiên:** R5 (mù trong điều kiện bất lợi), R1 (bỏ sót thầm lặng), R4
(đặt quá gần) — cả ba đều được xử lý bằng các quyết định mang tính chịu lực đã được đưa ra (ADR-0001,
ADR-0005, doc 01 §4).

## 2. FMEA-lite (kiểu lỗi → tác động → phát hiện → phản ứng)

| Kiểu lỗi | Tác động | Cách phát hiện | Phản ứng của hệ thống |
|--------------|--------|--------------|-----------------|
| Camera chết / khung hình đóng băng | Mất lớp phân loại + hình học ROI ảnh → **không thể xác nhận một xe dừng _mới_** | Watchdog phát hiện khung hình cũ; kiểm tra tình trạng theo từng cảm biến | **CHỈ-RADAR = MÙ VỚI SỰ CỐ MỚI** ([ADR-0009 §B](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md)): có thể *giữ* một vết đã được xác nhận trong thời gian ngắn qua radar, nhưng **không thể khởi tạo cảnh báo mới** → **cảnh báo trọng yếu (critical)**, *không phải* một "lần chạy suy giảm" lành tính; cả hai cảm biến đều hỏng → TRẠNG THÁI AN TOÀN |
| Radar chết | Mất khả năng xác nhận bền vững với thời tiết + giữ khi che khuất | Nhịp tín hiệu cảm biến (heartbeat) | **CHỈ-CAMERA**: vẫn có thể *khởi tạo* (lớp phân loại camera + ROI + tốc độ vết) nhưng mất phần giữ khi che khuất của radar → chế độ suy giảm + cảnh báo, gắn cờ rủi ro bỏ sót ban đêm/thời tiết |
| Tiến trình nhận diện sập | Không có phát hiện nào được tạo ra | Bộ giám sát tiến trình / nhịp tín hiệu watchdog | Tự khởi động lại; nếu lặp lại → TRẠNG THÁI AN TOÀN + cảnh báo |
| **Tiến trình máy trạng thái chết / treo cứng** | Cảnh báo không thể được logic cập nhật hoặc giải tỏa | Mất **nhịp tín hiệu khẳng định (assertion heartbeat)** của máy trạng thái; bộ giám sát | **Cơ chế tự ngắt an toàn (dead-man's switch) nằm trong bộ điều khiển biển báo** xóa trống biển báo khi mất nhịp tín hiệu; bộ giám sát tình trạng cưỡng bức về trạng thái an toàn **độc lập với máy trạng thái** ([ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md), [ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.vi.md)) |
| **Edge box chết / OS treo cứng / mất nguồn thiết bị khi một cảnh báo đang BẬT** | Edge box không thể ra lệnh cho bất cứ thứ gì; một biển báo chốt trạng thái sẽ kẹt-BẬT | Bộ điều khiển biển báo thấy **nhịp tín hiệu SHOW-được-làm-mới ngừng lại** | Bộ điều khiển biển báo **tự xóa trống trong vòng `T_signhold`** (đây *chính là lý do* cơ chế tự ngắt an toàn phải nằm ở hạ nguồn của liên kết — [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md)); khoảng trống nhịp tín hiệu tại TMC làm dấy lên cảnh báo |
| Logic quyết định bị kẹt với bảng cảnh báo BẬT | Cảnh báo kẹt-BẬT (Stale-ON) | Bộ định thời xác nhận lại `T_watchdog` | Buộc đánh giá lại → GIẢI TỎA nếu không được xác nhận |
| Đứt liên kết bảng cảnh báo / bảng không phản hồi | Một lệnh mới không thể tới được biển báo; **một cảnh báo đang BẬT không được phép bị bỏ kẹt ở trạng thái cũ** | Sai lệch khi **đọc lại trạng thái** biển báo; mất nhịp tín hiệu tại bộ điều khiển biển báo | Nếu một cảnh báo đang BẬT, **cơ chế tự ngắt an toàn của bộ điều khiển biển báo xóa trống nó** khi mất nhịp tín hiệu (backend LED riêng, [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md)); một **VMS chốt trạng thái (latching)** không thể tuân thủ điều này → kẹt-BẬT còn lại = chu kỳ lệnh của đơn vị vận hành (lưu ý đã phát biểu). Cảnh báo ngay lập tức; đánh dấu ở chế độ suy giảm |
| Bảng cảnh báo bị kẹt BẬT về mặt vật lý | Báo động giả lặp lại (cry wolf) | Đọc lại trạng thái so với lệnh | Cảnh báo; điều động nhân viên vận hành/bảo trì |
| Nguồn yếu (cạn pin mặt trời) | Sắp tắt máy | Ngưỡng telemetry ắc quy | Cảnh báo sớm nguồn yếu; tắt máy có trật tự về TRẠNG THÁI AN TOÀN |
| Gián đoạn WAN | Không có telemetry/giám sát | Khoảng trống nhịp tín hiệu tại TMC | Vòng an toàn vẫn tiếp tục (tự chủ tại biên); sự kiện xếp hàng đợi; cảnh báo khi có khoảng trống |
| Lệch đồng hồ giữa các cảm biến | Hợp nhất sai | Bộ giám sát đồng bộ thời gian | Gắn cờ; chuyển về dùng cảm biến đơn; cảnh báo |
| Suy giảm mô hình sau OTA | Giảm độ chính xác | Số liệu canary sau cập nhật | **Khôi phục về** (rollback) phiên bản đã ký trước đó |
| **Đẩy cấu hình sai (bad config push)** (ROI sai / bộ định thời ngoài dải) | Chức năng an toàn bị phá vỡ thầm lặng — bỏ sót hoặc báo động giả | **Kiểm tra biên tại thiết bị**; triển khai theo từng giai đoạn; canary sau thay đổi | Từ chối/kẹp cấu hình ngoài biên (FR-20); cảnh báo; giữ bản tốt gần nhất; khôi phục có ký (R16) |
| **OTA / khởi động lại khi một cảnh báo đang hoạt động** | Một cảnh báo đang sống bị rớt trong cửa sổ cập nhật | Tập vết khác rỗng tại thời điểm cập nhật | **Hoãn** việc cập nhật, hoặc để trống *báo lỗi rõ ràng tới đơn vị vận hành* trong cửa sổ (FR-21) — không bao giờ rớt thầm lặng |
| **Lỗi hiệu chuẩn / trôi hiệu chuẩn** (homography hoặc thông số ngoại lai camera↔radar) | ROI dịch chuyển → bỏ sót hoặc báo động giả có hệ thống, không có triệu chứng rõ ràng | **Bộ giám sát trôi** so với các mốc tham chiếu; kiểm tra lại định kỳ | Cảnh báo khi vượt dung sai; hiệu chuẩn lại; coi như chế độ suy giảm cho tới khi được khắc phục (R15) |
| **Người vận hành ép tắt / tắt tạm trong khi có mối nguy thật** | Bỏ sót thầm lặng do người vận hành gây ra | Ghi đè được ghi nhật ký + tư thế nhịp tim **OVERRIDDEN**; tự hết hiệu lực bắt buộc; leo thang qua TMC | Có giới hạn, báo động lớn khi sự cố, giới hạn thời gian; tự tiếp tục khi hết hạn ([ADR-0010](adr/ADR-0010-operator-override-and-manual-control.vi.md)) |
| **Lệnh ép bật bị chốt / ghi đè bị giả mạo** | Kẹt-BẬT hoặc báo động giả; ngăn-hoặc-khẳng-định trái phép | Ép bật do hộp biên trung chuyển, **được làm mới (không chốt)**; kênh ghi đè đã xác thực; đọc lại trạng thái | Cơ chế tự ngắt an toàn vẫn xóa trống khi giết-hộp / cắt-liên-kết / hết hạn; từ chối ghi đè không xác thực / ngoài chính sách (ADR-0010, NFR-09) |

Danh sách FMEA này cũng là **tập kiểm thử tiêm lỗi** cho nghiệm thu (doc 01 §5 — mục tiêu ≥95%
độ phủ phát hiện). **Lưu ý:** mục tiêu đó kiểm chứng các bộ phát hiện mà bạn *đã xây dựng* đối với các
lỗi mà bạn *đã liệt kê*; nó không giới hạn các lỗi *chưa được liệt kê*. Hãy xem 95% là độ phủ của các
kiểu lỗi đã biết và tiếp tục bổ sung các kiểu lỗi khi chúng lộ ra — những lỗi bạn không nghĩ tới mới là
những lỗi quan trọng nhất. **Hãy phân tầng danh sách này nữa:** một số kiểu lỗi ở đây là
**chỉ-hiện-trường** — trôi hiệu chuẩn (R15, cần cột rung lắc / nhiệt), **hộp biên / liên kết chết ở cự ly
≥ DSD** (liên kết qua khoảng cách, [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md)),
và **cạn pin mặt trời** — nên bàn thử không thể tiêm chúng. Hãy báo cáo độ phủ phát hiện lỗi như một phần
của các chế độ **tiêm-được-trên-bàn-thử** và mang các chế độ chỉ-hiện-trường sang giai đoạn thử nghiệm,
nếu không con số 95% âm thầm loại trừ đúng các chế độ cần đến hiện trường mới xuất hiện.

## 3. Bản tóm tắt an toàn khi sự cố

Hành vi an toàn được đặc tả trong [ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.vi.md) và
[ADR-0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md). Tóm lại:

- **An toàn khi sự cố (fail-safe):** khi có lỗi trọng yếu, bảng cảnh báo về một **trạng thái đã biết, không gây hiểu nhầm** (mặc định để trống —
  nó không bao giờ khẳng định một mối nguy mà nó không thể chứng thực).
- **Báo lỗi rõ ràng (fail-loud):** thiết bị **leo thang sự suy giảm tới nhân viên vận hành**; "mù" là một báo động, không bao giờ là sự im lặng.
- **Không kẹt-BẬT (No stale-ON):** một **watchdog** giới hạn mọi lần kích hoạt; **đọc lại trạng thái** xác minh bảng cảnh báo
  thực sự phản ánh đúng lệnh.
- **Trạng thái an toàn độc lập, ở hạ nguồn của liên kết:** **cơ chế tự ngắt an toàn (dead-man's switch)
  nằm trong bộ điều khiển biển báo**, nên một máy trạng thái bị sập, một **edge box chết**, hay một
  **liên kết bị đứt** đều xóa trống biển báo; một đường cưỡng bức về an toàn của bộ giám sát tình trạng là
  lớp bên trong. Trạng thái an toàn không bao giờ nằm ở thượng nguồn của — cũng không phụ thuộc vào —
  chính thành phần mà nó giám sát ([ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md)).
- **Các chế độ suy giảm trung thực:** một thiết bị có camera chết là **mù với sự cố mới** (chỉ riêng
  radar không thể khởi tạo một lần xác nhận trong-ROI mới) và leo thang ở mức **trọng yếu (critical)** —
  nó không bao giờ quảng cáo phạm vi phủ mà nó đã đánh mất ([ADR-0009 §B](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md)).
- **Giữ gìn niềm tin:** dwell + hysteresis ngăn dao động (flapping) và kích hoạt sai, giữ cho cảnh báo
  đáng tin cậy (chống báo động giả lặp lại).

## 4. Quyền riêng tư, dữ liệu & tuân thủ pháp lý

Đề xuất không đề cập đến những điều này; đối với một hệ thống camera trên đường công cộng thì chúng là bắt buộc.

| Lĩnh vực | Nghĩa vụ | Phản ứng thiết kế |
|------|-----------|-----------------|
| **Tối thiểu hóa PII** | Camera thu biển số/khuôn mặt (dữ liệu cá nhân) | **Suy luận trên thiết bị**; không tải lên hay lưu giữ video thô liên tục. |
| **Lưu giữ bằng chứng** | Việc kiểm toán một quyết định cần *một số* bằng chứng | Chỉ lưu **ảnh chụp/siêu dữ liệu sự kiện tối thiểu**, thời gian lưu giữ có giới hạn, được kiểm soát truy cập (FR-16, NFR-10). |
| **Khả năng kiểm toán việc bỏ sót** | Việc kiểm toán mối nguy *chủ đạo* — một lần **bỏ sót** thầm lặng — cần bằng chứng về những khoảng thời gian hệ thống **không** kích hoạt, nhưng việc lưu giữ dữ liệu thô lại bị cấm | Một **bộ đệm cuộn tự hết hạn (auto-expiring rolling buffer)** ngắn, được kiểm soát truy cập (vài giây–vài phút) chỉ được giải phóng khi có một tình huống suýt va chạm/sự cố được gắn cờ, cộng với việc đối chiếu chéo với nhật ký CCTV/sự cố của đơn vị vận hành; **không bao giờ** lưu giữ dữ liệu thô dài hạn. Chốt cửa sổ thời gian chính xác cùng với chính sách quyền riêng tư (câu hỏi còn mở 4). |
| **Giới hạn mục đích** | Hệ thống dùng để **cảnh báo an toàn, không phải cưỡng chế** | Không có quy trình xử phạt/định danh; cách định hình và phạm vi dữ liệu phản ánh điều này (nguyên tắc định hướng 2). |
| **Tuân thủ về biển báo** | Biển báo/thông điệp đường bộ được quản lý theo quy định | Nội dung cảnh báo và bảng cảnh báo tuân thủ **QCVN 41** (quy chuẩn kỹ thuật quốc gia về báo hiệu đường bộ); tập thông điệp được rà soát. |
| **Tiêu chuẩn đường bộ/hình học** | Việc bố trí & lắp đặt được quản lý theo quy định | Tuân theo tiêu chuẩn hình học đường cao tốc (ví dụ **TCVN 5729**) và yêu cầu của đơn vị vận hành; bố trí dựa trên DSD (doc 01 §4). |
| **An ninh** | Ngăn chặn cảnh báo bị giả mạo/can thiệp | Kênh có xác thực, mã hóa; firmware được ký; an ninh vật lý (NFR-09, R8). Tuyên bố "không thể bị giả mạo" được **giới hạn trong một mô hình mối đe dọa đã phát biểu** — bao gồm liên kết edge↔biển báo cục bộ và việc từ chối cảm biến — cần làm rõ trước khi triển khai (§5 Q5). |
| **Trách nhiệm pháp lý / khái niệm vận hành** | Làm rõ trách nhiệm | Ghi chép hệ thống là **khuyến cáo** (tài xế vẫn chịu trách nhiệm); duy trì một **nhật ký sự kiện**; thống nhất vai trò với đơn vị vận hành; **giải quyết minh thị việc liệu triển khai một bộ phát hiện có thể mắc lỗi có làm tăng mức phơi nhiễm của đơn vị vận hành so với khi không có hay không** — cố vấn pháp lý của đơn vị vận hành sẽ hỏi, nên hãy nêu nó lên ở giai đoạn cấp sở (R10). |
| **Phê duyệt** | Triển khai hiện trường cần sự phê duyệt của cơ quan có thẩm quyền | Phối hợp với cơ quan quản lý đường bộ/đơn vị vận hành từ sớm; coi việc phê duyệt là một điều kiện tiên quyết của thử nghiệm hiện trường (cấp sở). |

> Các nghĩa vụ này nhẹ nhàng để tuân thủ ở giai đoạn cấp trường/trên bàn (ít dữ liệu công cộng được thu thập) —
> nhưng lưu ý rằng **kế hoạch dữ liệu** huấn luyện/đánh giá của bộ phát hiện ([ADR-0007](adr/ADR-0007-validation-and-data-strategy.vi.md))
> bản thân nó cũng có thể bao gồm các đoạn clip ven đường, nên cùng các quy tắc tối thiểu hóa đó được áp dụng **ngay từ ngày đầu**. Các
> **lựa chọn thiết kế giúp việc tuân thủ dễ dàng về sau — suy luận trên thiết bị, không lưu giữ dữ liệu thô, nhật ký sự kiện —
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
5. **Mô hình mối đe dọa** cho liên kết edge↔biển báo và các cảm biến là gì? Tuyên bố "không thể bị giả
   mạo" (NFR-09) cần được liệt kê các bề mặt tấn công của nó — lệnh `SHOW`/`CLEAR` bị giả mạo/phát lại
   hoặc một **nhịp tín hiệu bị nhiễu (jammed heartbeat)** trên liên kết cục bộ (lưu ý: nhiễu nhịp tín hiệu
   buộc về một trạng thái *để trống*, vốn an toàn khi sự cố nhưng là một sự từ-chối-cảnh-báo), **nhiễu
   radar**, **làm chói camera / dội đèn IR**, và cấu hình/OTA — và **nhịp tín hiệu SHOW-được-làm-mới của
   liên kết biển báo phải được xác thực**, chứ không chỉ telemetry. Việc gia cố sâu là một nhiệm vụ ở giai
   đoạn hiện trường; hãy giới hạn tuyên bố NFR-09 trong phạm vi phân tích thực sự đã thực hiện.
6. **Ngân sách độ tin cậy MTBF/MTTR** nào đứng sau mục tiêu khả dụng chức năng ≥ 99% (NFR-03)? Đối với một
   thiết bị đơn lẻ ở xa, một lần sửa chữa hiện trường kéo dài nhiều ngày (~0,5% của một năm *cho mỗi lần*)
   gần như làm cạn kiệt ngân sách, nên mức 99% cần một MTBF minh thị tương ứng với MTTR hiện trường khả thi
   — hoặc nên được nới lỏng. Hãy phát biểu ngân sách này ở giai đoạn thử nghiệm hiện trường thay vì khẳng
   định 99% mà không có cơ sở.
