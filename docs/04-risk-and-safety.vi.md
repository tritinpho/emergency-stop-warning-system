# 04 — Rủi ro, An toàn & Tuân thủ

> 🇬🇧 Bản gốc tiếng Anh: [04-risk-and-safety.md](04-risk-and-safety.md)

**Dự án:** Hệ thống cảnh báo tự động làn dừng xe khẩn cấp (ESW)
**Trạng thái:** Đề xuất
**Cập nhật:** 2026-06-26
**Liên quan:** [ADR-0005 an toàn khi sự cố](adr/ADR-0005-fail-safe-and-system-safety.vi.md) · [yêu cầu §1](01-requirements.vi.md#1-the-safety-reframe-read-first)

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
  toàn bộ một hành lang ([doc 02 §6](02-system-architecture.vi.md#6-coverage-model));
- buộc bất kỳ tài xế nào phải hành động — nó mang tính **khuyến cáo**; một tài xế phớt lờ bảng cảnh báo
  thì không được bảo vệ;
- phát hiện nguyên nhân, điều động cứu hộ, hay điều khiển bất kỳ phương tiện nào (các phi-mục-tiêu rõ ràng,
  [doc 00 §2](00-context-and-glossary.vi.md#2-goal--non-goals));
- bảo đảm phát hiện vượt ra ngoài phạm vi đã kiểm chứng (ví dụ đêm/bất lợi trước khi cổng radar
  [ADR-0001](adr/ADR-0001-sensing-modality.vi.md) được thông qua — đã thiết kế, chưa chứng minh).

Mỗi mục là một ranh giới phạm vi có chủ đích, được mang vào khái niệm vận hành và biện pháp giảm thiểu
sự phụ thuộc quá mức (R7), và được xem xét lại tại thử nghiệm hiện trường.

---

## 1. Bảng đăng ký rủi ro

**Mối nguy an toàn so với rủi ro dự án.** Bảng đăng ký được chấm điểm phơi nhiễm dưới đây cố ý chứa cả
hai. Đối với một hệ thống liên quan đến an toàn, các *mối nguy an toàn* — những cách hệ thống có thể góp
phần gây hại trên đường — xứng đáng có tầm nhìn riêng, nên chúng được tách ra ở đây trước tiên và truy
vết tới yêu cầu/ADR kiểm soát. Đây là một **bộ khung nhật ký mối nguy (hazard-log skeleton)**; một phân
tích mối nguy đầy đủ là một sản phẩm bàn giao ở cấp sở
([doc 05 §3](05-field-pilot-proposal.vi.md#3-objectives)).

| Mối nguy (gây hại trên đường) | Nguyên nhân chính | Biện pháp kiểm soát chính | Còn lại sau kiểm soát | Truy vết tới |
|-------------------------------|-------------------|---------------------------|-----------------------|--------------|
| **H-A** Va chạm từ phía sau / va chạm thứ cấp với một xe đang dừng — dòng xe phía sau không được cảnh báo kịp thời | Bỏ sót thầm lặng (cảm biến mù, che khuất, sập) **hoặc** cảnh báo đặt quá gần | Đa cảm biến + bộ giám sát tình trạng + trạng thái an toàn dead-man's; bố trí theo DSD | Bỏ sót trong điều kiện thuận lợi; khoảng trống giữa các vùng; cửa sổ dwell trước khi xác nhận | R1, R4, R5, R12; ADR-[0001](adr/ADR-0001-sensing-modality.vi.md)/[0005](adr/ADR-0005-fail-safe-and-system-safety.vi.md)/[0008](adr/ADR-0008-detection-persistence-and-multitrack.vi.md); [doc 01 §4](01-requirements.vi.md#4-warning-placement--the-math-the-proposal-omits) |
| **H-B** Phanh gấp / đánh lái không cần thiết do một cảnh báo giả hoặc cũ | Kích hoạt giả hoặc kẹt-BẬT ("cry wolf") | Dwell + hysteresis + cổng lọc ROI + đối chiếu chéo radar; watchdog + đọc lại trạng thái | Tỉ lệ báo động giả còn lại (được hiệu chỉnh bởi đơn vị vận hành) | R2, R3; [ADR-0008](adr/ADR-0008-detection-persistence-and-multitrack.vi.md); [doc 01 §5](01-requirements.vi.md#5-evaluation-metrics--acceptance-criteria) |
| **H-C** Người đi bộ trên lề đường bị tông | Người không được phát hiện (đặc biệt vào ban đêm) | Lớp người trong bộ phát hiện; cảnh báo khi có người trong/cạnh ROI | Phát hiện người đi bộ ban đêm chỉ là nỗ lực tốt nhất (doc 01 §5) | FR-08; [ADR-0003](adr/ADR-0003-detection-algorithm.vi.md) |
| **H-D** Phụ thuộc quá mức — tài xế ngừng quan sát, tin tưởng vào hệ thống | Niềm tin bị hiệu chỉnh sai so với phạm vi phủ thực tế | Định hình như một công cụ hỗ trợ; phát biểu giới hạn bảo vệ (§0); hành vi nhất quán | Mang tính hành vi; không thể loại bỏ hoàn toàn bằng kỹ thuật | R7; [doc 01 §1](01-requirements.vi.md#1-the-safety-reframe-read-this-first) |

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
| **Tiến trình máy trạng thái chết / treo cứng** | Cảnh báo không thể được logic cập nhật hoặc giải tỏa | Mất **nhịp tín hiệu khẳng định (assertion heartbeat)** của máy trạng thái tại cơ cấu chấp hành; bộ giám sát | **Cơ chế an toàn tự kích hoạt khi mất tín hiệu (dead-man's switch)**: cơ cấu chấp hành tự xóa trống; bộ giám sát tình trạng cưỡng bức về trạng thái an toàn **độc lập với máy trạng thái** (ADR-0005) |
| Logic quyết định bị kẹt với bảng cảnh báo BẬT | Cảnh báo kẹt-BẬT (Stale-ON) | Bộ định thời xác nhận lại `T_watchdog` | Buộc đánh giá lại → GIẢI TỎA nếu không được xác nhận |
| Đứt liên kết bảng cảnh báo / bảng không phản hồi | Cảnh báo được lệnh nhưng không thực sự hiển thị | Sai lệch khi **đọc lại trạng thái** bảng cảnh báo | Cảnh báo ngay lập tức; đánh dấu vị trí ở chế độ suy giảm |
| Bảng cảnh báo bị kẹt BẬT về mặt vật lý | Báo động giả lặp lại (cry wolf) | Đọc lại trạng thái so với lệnh | Cảnh báo; điều động nhân viên vận hành/bảo trì |
| Nguồn yếu (cạn pin mặt trời) | Sắp tắt máy | Ngưỡng telemetry ắc quy | Cảnh báo sớm nguồn yếu; tắt máy có trật tự về TRẠNG THÁI AN TOÀN |
| Gián đoạn WAN | Không có telemetry/giám sát | Khoảng trống nhịp tín hiệu tại TMC | Vòng an toàn vẫn tiếp tục (tự chủ tại biên); sự kiện xếp hàng đợi; cảnh báo khi có khoảng trống |
| Lệch đồng hồ giữa các cảm biến | Hợp nhất sai | Bộ giám sát đồng bộ thời gian | Gắn cờ; chuyển về dùng cảm biến đơn; cảnh báo |
| Suy giảm mô hình sau OTA | Giảm độ chính xác | Số liệu canary sau cập nhật | **Khôi phục về** (rollback) phiên bản đã ký trước đó |

Danh sách FMEA này cũng là **tập kiểm thử tiêm lỗi** cho nghiệm thu (doc 01 §5 — mục tiêu ≥95%
độ phủ phát hiện). **Lưu ý:** mục tiêu đó kiểm chứng các bộ phát hiện mà bạn *đã xây dựng* đối với các
lỗi mà bạn *đã liệt kê*; nó không giới hạn các lỗi *chưa được liệt kê*. Hãy xem 95% là độ phủ của các
kiểu lỗi đã biết và tiếp tục bổ sung các kiểu lỗi khi chúng lộ ra — những lỗi bạn không nghĩ tới mới là
những lỗi quan trọng nhất.

## 3. Bản tóm tắt an toàn khi sự cố

Hành vi an toàn được đặc tả trong [ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.vi.md). Tóm lại:

- **An toàn khi sự cố (fail-safe):** khi có lỗi trọng yếu, bảng cảnh báo về một **trạng thái đã biết, không gây hiểu nhầm** (mặc định để trống —
  nó không bao giờ khẳng định một mối nguy mà nó không thể chứng thực).
- **Báo lỗi rõ ràng (fail-loud):** thiết bị **leo thang sự suy giảm tới nhân viên vận hành**; "mù" là một báo động, không bao giờ là sự im lặng.
- **Không kẹt-BẬT (No stale-ON):** một **watchdog** giới hạn mọi lần kích hoạt; **đọc lại trạng thái** xác minh bảng cảnh báo
  thực sự phản ánh đúng lệnh.
- **Trạng thái an toàn độc lập:** một **cơ chế an toàn tự kích hoạt khi mất tín hiệu (dead-man's switch)** tại cơ cấu chấp hành cộng với một đường cưỡng bức về an toàn của bộ giám sát tình trạng
  xóa trống bảng cảnh báo ngay cả khi máy trạng thái sập — trạng thái an toàn không bao giờ phụ thuộc vào
  chính thành phần đang được giám sát ([ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.vi.md)).
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
| **An ninh** | Ngăn chặn cảnh báo bị giả mạo/can thiệp | Kênh có xác thực, mã hóa; firmware được ký; an ninh vật lý (NFR-09, R8). |
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
