# ADR-0010: Chính sách ghi đè & điều khiển thủ công của người vận hành

> 🇬🇧 Bản gốc tiếng Anh: [ADR-0010-operator-override-and-manual-control.md](ADR-0010-operator-override-and-manual-control.md)

**Trạng thái:** Đề xuất
**Ngày:** 2026-06-27
**Người quyết định:** Chủ nhiệm (ThS. Phó Trí Tín), trưởng nhóm kỹ thuật, cố vấn an toàn giao thông, đầu mối liên hệ đơn vị vận hành cao tốc

## Bối cảnh

[FR-13](../01-requirements.vi.md#2-yêu-cầu-chức-năng) cho phép người vận hành ghi đè thủ công — **ép bật, ép tắt, tắt tạm
(mute)** — và bảng điều khiển TMC bộc lộ chức năng này
([tài liệu 02 §2](../02-system-architecture.vi.md#2-kiến-trúc-logic-các-thành-phần--trách-nhiệm)). Bản đầu tiên chỉ nêu tên năng lực này trong một
dòng và không hề phân tích nó, thế nhưng ghi đè là một **đường điều khiển trọng yếu về an toàn, đi vòng
qua chính những bất biến mà toàn bộ phần còn lại của thiết kế an toàn dựa vào**:

- **Ép tắt / tắt tạm khi một mối nguy thật đang hiện diện chính là một _bỏ sót thầm lặng_ do người vận
  hành gây ra** — mối nguy chủ đạo ([tài liệu 01 §1](../01-requirements.vi.md#1-tái-định-khung-an-toàn-đọc-phần-này-trước)),
  nay được tạo ra một cách cố ý và từ xa. Một lệnh tắt tạm tồn tại âm thầm là không thể phân biệt với
  chính sự cố mà cả thiết kế tồn tại để ngăn chặn.
- **Ép bật xung đột với cơ chế tự ngắt an toàn không-chốt**
  ([ADR-0009 §A](ADR-0009-failsafe-placement-and-degraded-modes.vi.md)). Cảnh báo chỉ được khẳng định
  bằng một nhịp tim `SHOW` *được làm mới liên tục*, đúng để một hộp chết hay một liên kết bị cắt sẽ làm
  trống bảng. Một cảnh báo bị ép bật phải trả lời: *ai làm mới nhịp tim, và qua liên kết nào?* Nếu TMC
  **chốt (latch)** một thông điệp qua WAN, nó tái lập đúng cái kẹt-BẬT (stale-ON) mà kiến trúc đã loại
  bỏ — và gắn một đầu ra an toàn vào chính mạng lưới mà vòng lặp an toàn vốn phải độc lập với nó
  ([ADR-0002](ADR-0002-edge-vs-cloud-processing.vi.md)).
- Ghi đè là một **lệnh từ xa đã xác thực**, nên nó là một phần của bề mặt tấn công NFR-09 — một lệnh ép
  tắt giả mạo là *từ chối-cảnh-báo*, một lệnh ép bật giả mạo là *báo động giả (cry-wolf)* — và xứng đáng
  được xử lý ngang với config/OTA ([tài liệu 04 §5 Q5](../04-risk-and-safety.vi.md#5-các-câu-hỏi-an-toàn-còn-mở-cho-nhóm)).

Vì vậy ngữ nghĩa của ghi đè phải được quyết định **một cách tường minh**, không phó mặc cho khâu hiện
thực, bởi mỗi lựa chọn ngây thơ đều âm thầm mở lại một chế độ sự cố mà các ADR khác đã dồn công sức để
đóng lại.

## Quyết định

Áp dụng mô hình ghi đè **có giới hạn, báo động lớn khi sự cố, và tôn trọng nhịp tim**. Mọi lệnh ghi đè
đều được **xác thực, có mã lý do, ghi vào nhật ký kiểm toán bất biến, và bị giới hạn thời gian với cơ
chế tự hết hiệu lực bắt buộc** (`T_override_max`); **không lệnh nào được phép tồn tại âm thầm.**

1. **Phát hiện và ghi nhật ký không bao giờ dừng.** Ghi đè chỉ tác động lên *đầu ra biển báo* — không
   bao giờ lên tri giác, hợp nhất, sự đánh giá của máy trạng thái, hay nhật ký kiểm toán. Thiết bị vẫn
   tiếp tục phát hiện và ghi nhận xuyên suốt, nên một lệnh ghi đè luôn có thể tái dựng về sau, và một
   mối nguy thật hiện diện trong lúc tắt tạm sẽ được ghi lại như một **phơi nhiễm đã biết, được người
   vận hành chấp nhận** (cấp dữ liệu cho kiểm toán trách nhiệm pháp lý R10).
2. **Ép tắt / tắt tạm bị giới hạn thời gian và phải ồn ào.** Nó mang một hạn hết hiệu lực bắt buộc (mặc
   định **30 phút**, trần `T_override_max` ví dụ **8 giờ**) — đều có giới hạn và được triển khai theo
   giai đoạn/kiểm định như một thay đổi cấu hình (anh em với [FR-20](../01-requirements.vi.md#2-yêu-cầu-chức-năng)). Khi
   đang hiệu lực, thiết bị báo cáo tư thế **OVERRIDDEN** trong nhịp tim của nó (nó **không** "khỏe
   mạnh"), TMC hiển thị nổi bật, và tình trạng sẽ **leo thang** nếu lệnh ghi đè sống lâu hơn cửa sổ của
   nó. Khi hết hạn, logic bình thường tự động tiếp tục và đánh giá lại từ trạng thái cảm biến hiện thời.
3. **Ép bật tôn trọng hợp đồng `SHOW`-làm-mới — nó không bao giờ chốt.** Một cảnh báo do người vận hành
   ép bật được khẳng định bằng **chính nhịp tim `SHOW` làm mới** mà máy trạng thái dùng, được làm mới
   **bởi hộp biên (tại chỗ)**, dưới một lệnh đã xác thực và có giới hạn thời gian. Cơ chế tự ngắt an
   toàn do đó vẫn bảo vệ nó: một hộp biên chết, một liên kết bị cắt/nhiễu, hay sự hết hạn đều làm trống
   bảng. Một lệnh ép bật phát từ TMC được **hộp biên trung chuyển và làm mới, không chốt qua WAN**; nếu
   hộp hoặc liên kết hỏng, ép bật đơn giản là *không thể khẳng định* (giữ nguyên an-toàn-làm-trống) và
   người vận hành được báo điều đó.
4. **Thẩm quyền ghi đè được khoanh vùng và xác thực.** Định nghĩa các vai trò vận hành được phép ghi đè;
   yêu cầu lệnh đã xác thực, không thể chối bỏ, trên cùng kênh được gia cố như config/OTA (NFR-09). Một
   bên không xác thực thì không thể vừa ngăn vừa khẳng định một cảnh báo.
5. **Ghi đè bị ràng buộc như cấu hình.** Các lệnh ghi đè ngoài chính sách (hạn hết hiệu lực vượt trần,
   một mã thông điệp lạ, một lệnh ép bật không kèm lý do do người vận hành cung cấp) bị **từ chối hoặc
   kẹp tại thiết bị** (cơ chế FR-20), không tuân theo một cách mù quáng.

## Các phương án đã cân nhắc

### Phương án A: Không ghi đè (chỉ tự hành)
| Chiều | Đánh giá |
|-------|----------|
| Bề mặt tấn công | **Không thêm** |
| Tính vận hành được | **Kém** — không thể dập một báo động giả đã biết, tắt tạm một biển đang bảo trì, hay khẳng định một cảnh báo cho sự cố mà bộ phát hiện bỏ sót |
| Độ phức tạp | Thấp |

**Ưu:** không có gì phải bảo mật; không có đường đi vòng.
**Nhược:** bất khả thi về vận hành — người vận hành *sẽ* cần ngăn và cần khẳng định; chối bỏ điều đó đẩy
họ tới những cách lách tệ hơn ngoài luồng (rút nguồn biển báo, v.v.). Bị bác.

### Phương án B: Ghi đè chốt vô hạn (đặt trạng thái đến khi gỡ thủ công)
| Chiều | Đánh giá |
|-------|----------|
| Độ phức tạp | **Thấp** |
| Rủi ro bỏ sót thầm lặng | **Cao** — một lệnh tắt tạm bị quên là một bỏ sót thầm lặng vĩnh viễn |
| Rủi ro kẹt-BẬT | **Cao** — một lệnh ép bật bị chốt tái lập kẹt-BẬT, gắn vào WAN |
| An toàn khi sự cố | **Bị đi vòng** — cơ chế tự ngắt an toàn không còn chi phối biển báo |

**Ưu:** tầm thường.
**Nhược:** trả giá cho sự tiện lợi bằng đúng hai chế độ sự cố mà kiến trúc tồn tại để loại bỏ. Bị loại
đối với một chức năng an toàn.

### Phương án C: Ghi đè có giới hạn, báo động lớn, tôn trọng nhịp tim *(được chọn)*
| Chiều | Đánh giá |
|-------|----------|
| Độ phức tạp | Trung bình (bộ đếm hết hạn, tư thế OVERRIDDEN, ép bật do hộp biên trung chuyển, xác thực kênh) |
| Rủi ro bỏ sót thầm lặng | **Có giới hạn** — tắt tạm tự hết hiệu lực và ồn ào khi đang hiệu lực |
| Rủi ro kẹt-BẬT | **Có giới hạn** — ép bật được làm mới, không chốt; cơ chế tự ngắt an toàn vẫn làm trống |
| An toàn khi sự cố | **Được giữ nguyên** — ghi đè nằm trong cùng khung an toàn với logic tự hành |

**Ưu:** quyền điều khiển thực sự cho người vận hành mà không bao giờ tạo ra một đầu ra thầm lặng hay kẹt;
mọi lệnh ghi đè đều được xác thực, giới hạn, và kiểm toán.
**Nhược:** nhiều thứ phải xây và tiêm lỗi hơn; thêm một tham số trọng yếu về an toàn (`T_override_max`).

## Phân tích đánh đổi

Lựa chọn thực sự là **B so với C — một lệnh ghi đè tốn gì khi người vận hành bỏ đi?** Sự tiện lợi của B
được trả bằng đúng hai chế độ sự cố mà phần còn lại của kiến trúc dồn sức loại bỏ: một lệnh tắt tạm bị
quên là một *bỏ sót thầm lặng*, một lệnh ép bật bị chốt là *kẹt-BẬT* gắn vào mạng. C giữ ghi đè bên
trong cùng khung an toàn với logic tự hành — **có giới hạn, ồn ào, có thể làm-trống-từ-hạ-nguồn, được
kiểm toán** — nên một thao tác thủ công không bao giờ có thể âm thầm đánh bại chức năng an toàn. Chi phí
là khiêm tốn và **hoàn toàn kiểm thử được bằng tiêm lỗi** (để một lệnh tắt tạm hết hạn; giết hộp khi
đang ép bật; phát lại một lệnh ghi đè đã bắt được).

## Hệ quả

- **Dễ hơn:** người vận hành có thể dập báo động giả và khẳng định sự cố đã biết mà không bao giờ tạo ra
  một đầu ra thầm lặng hay kẹt; mọi thao tác thủ công đều kiểm toán được cho hồ sơ trách nhiệm pháp lý
  (R10).
- **Khó hơn:** bộ đếm hết hạn, tư thế nhịp tim OVERRIDDEN và việc bộc lộ nó lên TMC, ép bật do hộp biên
  trung chuyển (không chốt), và xác thực trên kênh ghi đè đều phải được xây và tiêm lỗi; `T_override_max`
  trở thành một tham số trọng yếu về an toàn cần tinh chỉnh.
- **Xem lại khi:** một tích hợp với đơn vị vận hành bắt buộc một giao thức ghi đè/phân xử cụ thể trên một
  VMS bên thứ ba — adapter VMS phải ánh xạ chính sách này lên các điều khiển của đơn vị vận hành, và một
  **VMS chốt (latching) cũng thừa hưởng phần dư của
  [ADR-0009 §A](ADR-0009-failsafe-placement-and-degraded-modes.vi.md) cho cả ép bật** (nó không thể cho
  bảo đảm khẳng định-làm-mới).

## Hạng mục hành động

1. [ ] Đặc tả các lệnh ghi đè (ép bật / ép tắt / tắt tạm) với xác thực, mã lý do, hạn hết hiệu lực, và
       tư thế nhịp tim **OVERRIDDEN**; thêm chúng vào các hợp đồng giao diện
       [tài liệu 02 §7](../02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu) và lược đồ kiểm toán.
2. [ ] Hiện thực **ép bật do hộp biên trung chuyển, được làm mới (không chốt)**; kiểm chứng cơ chế tự
       ngắt an toàn vẫn làm trống nó khi giết-hộp / cắt-liên-kết / hết hạn (mở rộng
       [ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.vi.md) AI#2).
3. [ ] Hiện thực **cơ chế tự hết hiệu lực bắt buộc + leo thang qua TMC** cho ép tắt/tắt tạm; kiểm chứng
       một lệnh tắt tạm không thể âm thầm sống lâu hơn cửa sổ của nó.
4. [ ] **Cưỡng chế giới hạn ghi đè tại thiết bị** (cơ chế FR-20); từ chối/kẹp các lệnh ghi đè ngoài
       chính sách.
5. [ ] Gộp ghi đè vào **mô hình mối đe dọa NFR-09** ([tài liệu 04 §5 Q5](../04-risk-and-safety.vi.md#5-các-câu-hỏi-an-toàn-còn-mở-cho-nhóm))
       và các **dòng FMEA về ghi đè** ([tài liệu 04 §2](../04-risk-and-safety.vi.md)).
