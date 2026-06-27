# ADR-0004: Cơ cấu cảnh báo dạng cắm-thay (pluggable) — tái sử dụng VMS sẵn có, nếu không thì dùng bảng LED năng lượng mặt trời chuyên dụng

> 🇬🇧 Bản gốc tiếng Anh: [ADR-0004-warning-actuator-integration.md](ADR-0004-warning-actuator-integration.md)

**Trạng thái:** Đề xuất
**Ngày:** 2026-06-26
**Người quyết định:** Chủ nhiệm đề tài (PI), trưởng nhóm kỹ thuật, đầu mối liên lạc đơn vị vận hành đường cao tốc

## Bối cảnh

Cảnh báo đến người lái là đầu ra duy nhất của hệ thống, nên *cách thức* hiển thị cảnh báo và *việc chúng ta tự xây dựng hay tái sử dụng* bảng cảnh báo có ý nghĩa quan trọng về mặt kiến trúc. Hình 1 cho thấy cả một **bảng thông báo điện tử (VMS) gắn trên giá long môn (gantry)** lẫn một **bảng LED bên đường**. Các tuyến đường cao tốc hiện đại thường đã có sẵn các giá long môn VMS do đơn vị vận hành điều khiển cùng một hạ tầng xương sống ITS; các đoạn khác (và bất kỳ mô hình thử nghiệm trên bàn (bench) nào) thì không có gì. Việc bổ sung biển báo dư thừa vừa tốn kém, vừa chậm cấp phép, vừa làm rối mặt đường.

Các yếu tố tác động: chi phí đầu tư, công sức lắp đặt/cấp phép, độ phức tạp tích hợp với hệ thống ITS của bên thứ ba, hình học bố trí bảng báo (phải đặt cách ≥ DSD về phía trước theo hướng xe tới — [tài liệu 01 §4](../01-requirements.vi.md#4--warning-placement--the-math-the-proposal-omits)), sự phù hợp với QCVN 41, và mức độ chấp nhận/quyền điều khiển của đơn vị vận hành.

## Quyết định

Định nghĩa **một lớp trừu tượng cơ cấu chấp hành duy nhất** (`SHOW(message) / CLEAR / STATUS`) với **hai backend có thể thay thế cho nhau**:

1. **Backend VMS sẵn có** — ở nơi tuyến đường đã có sẵn một VMS do đơn vị vận hành điều khiển nằm trong cửa sổ phía trước theo yêu cầu, điều khiển bảng đó qua giao thức của đơn vị vận hành (kiểu NTCIP / API của nhà cung cấp), với điều kiện được đơn vị vận hành ủy quyền và có cơ chế phân xử (arbitration).
2. **Backend bảng chuyên dụng** — một **bảng cảnh báo LED tuân thủ QCVN 41 chạy bằng năng lượng mặt trời** dành cho các đoạn chưa được trang bị thiết bị và cho mô hình thử nghiệm trên bàn (bench).

Máy trạng thái (state machine) không phụ thuộc vào việc backend nào đang được kết nối.

## Các phương án đã xét

### Phương án A: Luôn lắp một bảng chuyên dụng
| Khía cạnh | Đánh giá |
|-----------|------------|
| Chi phí | Cao (phần cứng + xây lắp cho mỗi vị trí) |
| Cấp phép | Chậm (công trình mới bên đường) |
| Mức rõ ràng về quyền điều khiển | Đơn giản (chúng ta sở hữu) |
| Tái sử dụng | Không có |

**Ưu điểm:** toàn quyền điều khiển; hành vi đồng nhất; hoạt động được ở nơi không có ITS.
**Nhược điểm:** tốn kém và chậm ở nơi đã có sẵn một VMS hoàn toàn tốt; biển báo dư thừa gây rối; trùng lặp.

### Phương án B: Luôn tái sử dụng VMS sẵn có
| Khía cạnh | Đánh giá |
|-----------|------------|
| Chi phí | Thấp (không có bảng mới) |
| Phạm vi bao phủ | Chỉ ở nơi đã có sẵn VMS đúng vị trí |
| Tích hợp | Giao thức của đơn vị vận hành + cơ chế phân xử |
| Quyền điều khiển | Chia sẻ với các ưu tiên của đơn vị vận hành |

**Ưu điểm:** rẻ nhất; không gây rối; tận dụng hạ tầng đã được phê duyệt sẵn có.
**Nhược điểm:** không khả dụng trên các đoạn chưa được trang bị thiết bị; VMS có thể không nằm ở khoảng cách phía trước theo yêu cầu; xung đột ưu tiên với các thông báo khác của đơn vị vận hành; không thể chạy một mô hình thử nghiệm trên bàn (bench) độc lập.

### Phương án C: Lớp trừu tượng dạng cắm-thay, chọn backend theo từng vị trí *(được chọn)*
| Khía cạnh | Đánh giá |
|-----------|------------|
| Chi phí | Tối ưu theo từng vị trí |
| Phạm vi bao phủ | Phổ quát (tái sử dụng hoặc lắp mới) |
| Tích hợp | Một giao diện nội bộ ổn định, hai bộ chuyển đổi (adapter) |
| Quyền điều khiển | Rõ ràng; việc phân xử được xử lý trong adapter VMS |

**Ưu điểm:** tái sử dụng ở nơi có thể, lắp mới ở nơi cần thiết; logic lõi không bao giờ thay đổi; có thể kiểm thử trên một bảng LED đặt bàn ngay hôm nay, và triển khai với VMS thực tế về sau.
**Nhược điểm:** phải xây dựng và bảo trì hai adapter; adapter VMS cần công sức tích hợp riêng cho từng đơn vị vận hành.

## Phân tích đánh đổi

Cam kết theo một chiến lược bảng báo vật lý duy nhất (A hoặc B) là một kiểu tiết kiệm sai lầm: A chi tiêu quá mức ở nơi đã có ITS; B có các lỗ hổng phạm vi bao phủ và sai lệch hình học. Chi phí thực sự đáng quan tâm là **việc gắn chặt logic ra quyết định vào một loại bảng báo cụ thể** — điều này được tránh hoàn toàn nhờ lớp trừu tượng của Phương án C. Tính biến thiên (giao thức của các nhà cung cấp, cơ chế phân xử của đơn vị vận hành, định dạng thông báo theo QCVN 41) được cô lập trong các adapter, giúp máy trạng thái trọng yếu an toàn luôn ổn định và có thể kiểm thử. Điều này cũng cho phép nguyên mẫu cấp trường của trường đại học sử dụng một bảng LED giá rẻ trong khi vẫn giữ một lộ trình sạch sẽ để chuyển sang VMS thực tế trong thử nghiệm hiện trường.

## Hệ quả

- **Dễ hơn:** tối ưu chi phí theo từng vị trí; kiểm thử trên bàn ngay hôm nay; tái sử dụng VMS hiện trường về sau; phần lõi ổn định.
- **Khó hơn:** hai adapter phải bảo trì; adapter VMS đòi hỏi tích hợp riêng theo từng đơn vị vận hành và một **chính sách phân xử** (cái gì thắng nếu đơn vị vận hành đang hiển thị sẵn một thông báo); nội dung thông báo phải tuân thủ QCVN 41 ở cả hai backend.
- **Xem xét lại khi:** một giao thức thông báo ITS tiêu chuẩn được đơn vị vận hành bắt buộc áp dụng (thu gọn về một adapter), hoặc khi bổ sung một kênh cảnh báo V2X/trên xe (một backend *thứ ba* nằm sau cùng giao diện đó).

## Hạng mục hành động

1. [ ] Đặc tả giao diện cơ cấu chấp hành `SHOW/CLEAR/STATUS` và ngữ nghĩa đọc lại trạng thái (status read-back).
2. [ ] Làm việc với một đơn vị vận hành đường cao tốc để tìm hiểu giao thức VMS và các quy tắc phân xử thông báo của họ.
3. [ ] Chọn một bảng LED năng lượng mặt trời tuân thủ QCVN 41 cho backend chuyên dụng / mô hình thử nghiệm trên bàn (bench).
4. [ ] Định nghĩa tập thông báo cảnh báo được phê duyệt và quy trình rà soát sự phù hợp của tập đó.
