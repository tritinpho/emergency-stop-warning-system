# ADR-0012: Tư thế an ninh & mô hình mối đe dọa hợp nhất

> 🇬🇧 Bản gốc tiếng Anh: [ADR-0012-security-and-threat-model.md](ADR-0012-security-and-threat-model.md)

**Trạng thái:** Đề xuất
**Ngày:** 2026-06-27
**Người quyết định:** Chủ nhiệm (ThS. Phó Trí Tín), trưởng nhóm kỹ thuật, cố vấn an toàn giao thông, đầu mối liên hệ đơn vị vận hành cao tốc

## Bối cảnh

NFR-09 đưa ra một **tuyên bố cứng** — *"việc kích hoạt biển báo không thể bị một bên ngoài giả mạo"* — và
một số quyết định về sau đã lặng lẽ **mở rộng bề mặt tấn công** mà không có một nơi duy nhất để lập luận về
nó:

- **nhịp tín hiệu SHOW-được-làm-mới của liên kết biển báo** nay mang tính chịu lực về an toàn
  ([ADR-0009 §A](ADR-0009-failsafe-placement-and-degraded-modes.vi.md)) — một `SHOW` bị giả mạo/phát lại là
  một cảnh báo giả mạo, một nhịp tín hiệu **bị nhiễu** buộc về *trống* (an toàn khi sự cố, nhưng là một
  **sự từ-chối-cảnh-báo**);
- **ghi đè của người trực** là một lệnh từ xa đã xác thực có thể ngăn hoặc khẳng định biển báo
  ([ADR-0010](ADR-0010-operator-override-and-manual-control.vi.md)) — một ép-tắt giả mạo là một
  từ-chối-cảnh-báo, một ép-bật giả mạo là báo-động-giả;
- **cấu hình (FR-20) và OTA (FR-21)** có thể phá vỡ chức năng an toàn từ xa; việc ký chặn *can thiệp trái
  phép*, không chặn *lỗi của người vận hành*;
- **vô hiệu hóa cảm biến** là đặc thù của lớp hệ thống này — **gây nhiễu radar**, **làm chói camera /
  dội đèn IR** — tạo ra một lần bỏ sót âm thầm mà không một gói tin nào bị giả mạo.

An ninh bị để trong một **câu hỏi còn mở** ([tài liệu 04 §5 Q5](../04-risk-and-safety.vi.md#5-các-câu-hỏi-an-toàn-còn-mở-cho-nhóm))
trong khi mọi mối quan tâm chịu lực *khác* đều có một ADR. Đó là hình dạng sai: tuyên bố của NFR-09 không
có phạm vi phát biểu, nên nó hoặc quá rộng (không thể bảo vệ) hoặc không xác định. ADR này cho an ninh một
mái nhà, **giới hạn tuyên bố NFR-09 vào một bề mặt được liệt kê**, và phân tầng độ sâu của việc gia cố theo
các giai đoạn của dự án — gia cố đầy đủ là một nhiệm vụ hiện trường/sản-phẩm-hóa, nhưng *phân tích* và các
biện pháp **rẻ-bây-giờ, đắt-về-sau** (xác thực trên liên kết biển báo, cấu hình/OTA có ký, audit) thuộc về
giai đoạn nguyên mẫu.

Các lực: tính trung thực của tuyên bố (NFR-09 phải có nghĩa cụ thể), chi phí an toàn của mỗi bề mặt (một
cảnh báo bị giả mạo hay bị nhiễu là một hiểm họa đường bộ, không chỉ một vụ rò rỉ dữ liệu), cấu trúc tự-chủ
tại biên ([ADR-0002](ADR-0002-edge-vs-cloud-processing.vi.md)), chi phí/công sức ở một nguyên mẫu 20M VND,
và một sự bàn giao sạch sẽ cho thử nghiệm cấp sở.

## Quyết định

Áp dụng một **mô hình mối đe dọa hợp nhất, phân tầng theo giai đoạn** làm mái nhà cho NFR-09 và các hàng
liên-quan-an-ninh của [tài liệu 04](../04-risk-and-safety.vi.md).

1. **Liệt kê tài sản, tác nhân, và bề mặt.** Tài sản: **đầu ra biển báo** (thứ không được khẳng định sai
   hay bị ngăn sai), **tính toàn vẹn phát hiện** (cảm biến), **cấu hình/mô hình/hiệu chuẩn**, và **nhật ký
   audit**. Tác nhân: kẻ tấn công bên ngoài, người trong cuộc ác ý/bị xâm phạm, và một **lỗi không-ác-ý của
   người vận hành** (xem như một mối đe dọa với chức năng an toàn, theo FR-20). Bề mặt: **liên kết
   SHOW-được-làm-mới edge↔biển báo**, **telemetry**, **cấu hình/OTA**, **kênh ghi đè**, và **cảm biến** (vô
   hiệu hóa RF + quang).
2. **Xác thực kênh cục bộ liên-quan-an-toàn, không chỉ telemetry.** **Nhịp tín hiệu SHOW-được-làm-mới của
   liên kết biển báo phải được xác thực** (chống giả mạo, chống phát lại) — một mặt phẳng điều khiển có thể
   bật một biển báo bên đường không thể yếu hơn mặt phẳng telemetry. Ghi đè đi trên **cùng kênh đã gia cố,
   không-thể-chối-bỏ** như cấu hình/OTA (ADR-0010); cấu hình/OTA được **ký** kèm khôi phục.
3. **Ánh xạ mỗi bề mặt tới một biện pháp và một phần dư.** ví dụ `SHOW` giả mạo/phát lại → khẳng định có
   xác thực, có nonce; **nhịp tín hiệu bị nhiễu** → an-toàn-trống **nhưng** một phần dư từ-chối-cảnh-báo đã
   phát biểu (phát hiện như một khoảng hở nhịp → báo cho người trực, ADR-0011); **gây nhiễu radar / làm chói
   camera** → sức khỏe theo từng cảm biến + leo thang chế độ suy giảm
   ([ADR-0009 §B](ADR-0009-failsafe-placement-and-degraded-modes.vi.md)) khiến sự từ chối **lớn tiếng**,
   không bao giờ âm thầm; **cấu hình sai** → ràng buộc biên tại thiết bị (FR-20) + canary + khôi phục có ký.
4. **Giới hạn tuyên bố NFR-09 vào phân tích thực sự đã thực hiện.** "Không thể bị giả mạo" được viết lại
   thành *"việc khẳng định biển báo được xác thực chống giả mạo/phát lại trên các bề mặt được liệt kê; sự
   **từ chối** của cảm biến và liên kết được giảm thiểu về an-toàn-trống-và-báo, chứ không phải ngăn
   chặn"* — một tuyên bố trung thực có ranh giới, không phải một khẩu hiệu.
5. **Phân tầng độ sâu.** Giai đoạn nguyên mẫu: **tài liệu** mô hình mối đe dọa, **xác thực** liên kết biển
   báo + ghi đè + telemetry, cấu hình/OTA có ký, và nhật ký audit — những biện pháp **rẻ bây giờ và đắt để
   lắp về sau**. Giai đoạn hiện trường/sản-phẩm-hóa: kiểm thử xâm nhập, quản lý khóa ở quy mô đội thiết bị,
   gia cố chống-nhiễu/chống-chói, an ninh vật lý — **được hoãn lại tường minh cho hiện trường**, với nguyên
   mẫu giới hạn tuyên bố của mình cho phù hợp ([ADR-0007](ADR-0007-validation-and-data-strategy.vi.md)).

## Các phương án đã xét

### Phương án A: Để nó là câu-hỏi-mở Q5 *(trạng thái của bản phác đầu)*
| Khía cạnh | Đánh giá |
|-----------|------------|
| Công sức bây giờ | **Không** |
| Tính toàn vẹn NFR-09 | **Không xác định** — một tuyên bố cứng không có phạm vi |
| Bao phủ bề mặt | Rải rác qua R8 / R16 / ADR-0009 / ADR-0010 mà không có một góc nhìn duy nhất |

**Ưu:** không có gì để viết bây giờ.
**Nhược:** các bề mặt *giả-mạo/nhiễu* liên-quan-an-toàn (liên kết biển báo, ghi đè, cảm biến) không có phân
tích hợp nhất, và NFR-09 không thể chứng sai. Không chấp nhận được cho một hệ thống mà đầu ra là một tín
hiệu an toàn bên đường.

### Phương án B: ADR mô hình mối đe dọa hợp nhất, phân tầng theo giai đoạn *(được chọn)*
| Khía cạnh | Đánh giá |
|-----------|------------|
| Công sức bây giờ | Trung bình (liệt kê bề mặt + biện pháp; xác thực liên kết biển báo; tài liệu hóa) |
| Tính toàn vẹn NFR-09 | **Có phạm vi** — tuyên bố được giới hạn vào một bề mặt được liệt kê |
| Bao phủ bề mặt | **Góc nhìn duy nhất** — liên kết biển báo, ghi đè, cấu hình/OTA, vô hiệu hóa cảm biến, audit |

**Ưu:** NFR-09 có nghĩa cụ thể; các biện pháp rẻ-bây-giờ rơi vào giai đoạn nguyên mẫu nơi chúng rẻ; một sự
bàn giao gia cố hoãn lại sạch sẽ cho thử nghiệm.
**Nhược:** thêm phân tích trả trước; một số biện pháp (quản lý khóa, chống-nhiễu) được hoãn tường minh và
phải được truyền đạt là **có phạm vi**, không phải đã làm.

### Phương án C: Gia cố / chứng nhận an ninh đầy đủ ngay bây giờ
| Khía cạnh | Đánh giá |
|-----------|------------|
| Công sức | **Cao** — kiểm thử xâm nhập, quản lý khóa đội thiết bị, công việc RF chống-nhiễu |
| Phù hợp phạm vi | Ngoài ngân sách/phạm vi cho một nguyên mẫu bàn thử 20M VND |

**Ưu:** tư thế mạnh nhất có thể.
**Nhược:** đây **là** workstream an ninh cấp sở / sản-phẩm-hóa, không phải của nguyên mẫu; cố làm bây giờ là
hứa quá. Bị từ chối cho giai đoạn này, giữ lại làm mục tiêu hiện trường.

## Phân tích đánh đổi

Điểm quyết định là với hệ thống này một sự cố an ninh là một **sự cố an toàn đường bộ**: một `SHOW` giả mạo
là một hiểm họa ảo, một nhịp tín hiệu bị nhiễu hay một cảm biến bị làm chói là một sự từ-chối-cảnh-báo. Nên
các bề mặt quan trọng là các bề mặt **liên-quan-an-toàn** (liên kết biển báo, ghi đè, cảm biến), và nước đi
đúng không phải là gia cố tối đa (C, ngoài ngân sách) cũng không phải im lặng (A, không thể bảo vệ) mà là
một **mô hình có phạm vi (B)** xác thực kênh bật biển báo, khiến sự từ chối của cảm biến/liên kết **lớn
tiếng** qua bộ máy chế-độ-suy-giảm và nhịp tín hiệu đã xây, và **phát biểu ranh giới** của tuyên bố. Các
biện pháp rẻ-bây-giờ (xác thực liên kết biển báo, cấu hình/OTA có ký, audit) chính là những thứ đắt để lắp
về sau, nên chúng thuộc về giai đoạn nguyên mẫu; phần còn lại được hoãn một cách trung thực.

## Hệ quả

- **Dễ hơn:** NFR-09 thành một tuyên bố có phạm vi, có thể bảo vệ; các bề mặt giả-mạo/nhiễu có một phân
  tích duy nhất; nhật ký audit (R10) và cấu hình/OTA có ký (R16) có một cơ sở an ninh; bàn giao cấp sở sạch.
- **Khó hơn:** xác thực trên **liên kết biển báo cục bộ** (không chỉ telemetry) để thiết kế và quản lý khóa
  ở quy mô bàn thử; một tài liệu mô hình mối đe dọa để duy trì khi các bề mặt thay đổi; các mục hoãn lại
  (kiểm thử xâm nhập, chống-nhiễu, khóa đội thiết bị) phải được theo dõi, không quên.
- **Xem xét lại khi:** thử nghiệm hiện trường thêm khóa thực/quy mô đội thiết bị, một đơn vị vận hành bắt
  buộc một hồ sơ an ninh cụ thể, hoặc một bề mặt mới xuất hiện (ví dụ một phụ trợ V2X —
  [ADR-0004](ADR-0004-warning-actuator-integration.vi.md)).

## Hạng mục hành động

1. [ ] Viết **tài liệu mô hình mối đe dọa**: tài sản, tác nhân (gồm lỗi người vận hành), bề mặt, biện
       pháp + phần dư theo từng bề mặt; thay thế câu-hỏi-mở
       [tài liệu 04 §5 Q5](../04-risk-and-safety.vi.md#5-các-câu-hỏi-an-toàn-còn-mở-cho-nhóm).
2. [ ] Đặc tả và hiện thực **xác thực cho nhịp tín hiệu SHOW-được-làm-mới của liên kết biển báo** (chống
       giả mạo, chống phát lại) — mở rộng [ADR-0009 §A](ADR-0009-failsafe-placement-and-degraded-modes.vi.md) AI#1.
3. [ ] Đưa **ghi đè lên cùng kênh đã gia cố** như cấu hình/OTA; ký cấu hình/OTA kèm khôi phục (gộp
       [ADR-0010](ADR-0010-operator-override-and-manual-control.vi.md) AI#5, R16).
4. [ ] **Viết lại NFR-09** thành dạng có phạm vi của nó (xác thực chống giả mạo/phát lại trên các bề mặt
       được liệt kê; sự từ chối được giảm thiểu về an-toàn-trống-và-báo) trong
       [tài liệu 01 §3](../01-requirements.vi.md#3-yêu-cầu-phi-chức-năng).
5. [ ] Bổ sung **gây-nhiễu-radar / làm-chói-camera / IR-flood** và **liên-kết-biển-báo giả-mạo/phát-lại/​bị-nhiễu**
       vào FMEA + bộ tiêm lỗi ở đâu có thể tiêm trên bàn thử; gắn nhãn gia cố chống-RF/quang **hoãn lại cho hiện trường**.
