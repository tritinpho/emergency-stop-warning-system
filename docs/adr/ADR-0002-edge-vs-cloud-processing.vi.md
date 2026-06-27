# ADR-0002: Chạy vòng lặp an toàn tại biên; đám mây chỉ để giám sát

> 🇬🇧 Bản gốc tiếng Anh: [ADR-0002-edge-vs-cloud-processing.md](ADR-0002-edge-vs-cloud-processing.md)

**Trạng thái:** Đã chấp nhận (phía phần mềm) — 2026-06-27
**Ngày:** 2026-06-26
**Người quyết định:** Chủ nhiệm đề tài, trưởng nhóm kỹ thuật

## Bối cảnh

Đề xuất gọi tên một "bộ xử lý trung tâm" mà không xác định vị trí của nó. Việc vòng lặp
phát hiện→quyết định→cảnh báo chạy ở đâu là một quyết định có tính chịu lực vì vòng lặp này **liên quan
đến an toàn và bị ràng buộc về độ trễ** (bật cảnh báo trong khoảng ≈ thời gian chờ + 2 giây, NFR-01) và
môi trường hiện trường có **kết nối chập chờn** (sóng di động bên đường, đường hầm, các đoạn cao tốc xa
xôi).

Các yếu tố tác động: độ trễ, độ sẵn sàng khi WAN ngừng hoạt động, băng thông/chi phí truyền video,
quyền riêng tư (video thô rời khỏi hiện trường) và nhu cầu vận hành về giám sát và cập nhật tập trung.

## Quyết định

**Vòng lặp trọng yếu an toàn chạy hoàn toàn trên một thiết bị biên tại hiện trường bên đường** (cảm
biến → nhận diện → hợp nhất → máy trạng thái → lệnh điều khiển bảng). **Đám mây / TMC là không trọng
yếu**: nó nhận dữ liệu đo từ xa và các sự kiện (lưu và chuyển), cung cấp giám sát, kiểm toán, cấu hình
và OTA — nhưng thiết bị tại hiện trường phải vận hành đúng đắn ngay cả khi WAN mất kết nối hoàn toàn.

## Các phương án đã xét

### Phương án A: Vòng lặp cục bộ tại biên, đám mây để giám sát *(được chọn)*
| Khía cạnh | Đánh giá |
|-----------|------------|
| Độ trễ | **Thấp & xác định** (không có vòng đi-về qua WAN) |
| Độ sẵn sàng | **Cao** — sống sót qua sự cố mất WAN |
| Băng thông/chi phí | Thấp — chỉ có sự kiện/nhịp tín hiệu rời đi |
| Quyền riêng tư | Mạnh — suy luận ngay trên thiết bị, không tải video thô lên |
| Chi phí tính toán | Một hộp biên đủ năng lực cho mỗi vị trí |

**Ưu điểm:** đáp ứng yêu cầu về độ trễ và hoạt động ngoại tuyến; lượng dữ liệu ra ngoài tối thiểu
(quyền riêng tư + chi phí); vững chắc.
**Nhược điểm:** phần cứng biên cho mỗi vị trí; quản lý OTA/mô hình trên các thiết bị phân tán.

### Phương án B: Xử lý tại đám mây/trung tâm (truyền dòng cảm biến tới một máy chủ)
| Khía cạnh | Đánh giá |
|-----------|------------|
| Độ trễ | **Cao & biến thiên** — bị ràng buộc bởi WAN |
| Độ sẵn sàng | **Kém** — sự cố mất WAN làm vô hiệu hóa cảnh báo |
| Băng thông/chi phí | Cao — truyền video lên liên tục |
| Quyền riêng tư | Yếu — video thô ra khỏi hiện trường |
| Chi phí tính toán | Tập trung (rẻ hơn trên mỗi đơn vị, nhưng…) |

**Ưu điểm:** tính toán tập trung; cập nhật mô hình dễ hơn; phần cứng tại hiện trường mỏng hơn.
**Nhược điểm:** một sự cố mạng trở thành một **sự cố an toàn**; độ trễ không phù hợp cho một vòng lặp
cảnh báo; truyền lên liên tục tốn kém; phơi bày quyền riêng tư của video thô. Bị loại đối với một chức
năng an toàn.

### Phương án C: Lai — biên chạy vòng lặp, đám mây hỗ trợ phân tích nặng/thứ cấp
| Khía cạnh | Đánh giá |
|-----------|------------|
| Độ trễ | Thấp cho vòng lặp an toàn |
| Độ sẵn sàng | Cao cho vòng lặp an toàn |
| Độ phức tạp | Cao hơn (hai tầng tính toán) |

**Ưu điểm:** giữ vòng lặp an toàn cục bộ trong khi cho phép phân tích phong phú hơn ở trung tâm theo
kiểu ngoại tuyến.
**Nhược điểm:** nhiều bộ phận chuyển động hơn mức cần thiết hiện nay; phần phân tích trên đám mây nằm
ngoài phạm vi hiện tại.

## Phân tích đánh đổi

Đối với một cảnh báo an toàn, **độ sẵn sàng và độ trễ chi phối**. Phương án B gắn tính đúng đắn của
cảnh báo vào mạng di động — điều không thể chấp nhận. Phương án A thỏa mãn độ trễ, hoạt động ngoại
tuyến, quyền riêng tư và chi phí, đổi lại là việc quản lý biên phân tán — một mối quan tâm vận hành
thông thường đã được giải quyết (được xử lý bằng OTA trong [ADR-0005](ADR-0005-fail-safe-and-system-safety.vi.md)
và lớp TMC). Phương án C là Phương án A cộng thêm phân tích trong tương lai; ta áp dụng ranh giới của A
ngay bây giờ và để mở cánh cửa cho phương án lai (nó là một tập cha, không phải một mâu thuẫn).

## Hệ quả

- **Dễ hơn:** độ trễ xác định; hoạt động được trong đường hầm/khi mất kết nối; rẻ, riêng tư (không có
  dữ liệu thô ra ngoài).
- **Khó hơn:** quản lý đội thiết bị biên (cấu hình, OTA, lệch phiên bản) — được xử lý bằng dịch vụ
  cấu hình/OTA của TMC và các bản cập nhật có ký số.
- **Xem xét lại khi:** một khối lượng công việc phân tích không liên quan đến an toàn trong tương lai
  (phân tích sự cố trên toàn hành lang) biện minh cho việc nâng lên phương án lai C.

## Hạng mục hành động

1. [ ] Cố định ranh giới biên/đám mây trong các hợp đồng giao diện ([tài liệu 02 §7](../02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu)).
2. [ ] Đặc tả ngữ nghĩa lưu-và-chuyển cho hộp thư gửi đi của dữ liệu đo từ xa (thứ tự, lưu giữ, phản áp).
3. [ ] Xác nhận thiết bị biên đã chọn đáp ứng được ngân sách độ trễ nhận diện ngay trên thiết bị.
