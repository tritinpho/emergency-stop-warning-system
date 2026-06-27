# ADR-0004: Cơ cấu cảnh báo dạng cắm-thay (pluggable) — tái sử dụng VMS sẵn có, nếu không thì dùng bảng LED năng lượng mặt trời chuyên dụng

> 🇬🇧 Bản gốc tiếng Anh: [ADR-0004-warning-actuator-integration.md](ADR-0004-warning-actuator-integration.md)

**Trạng thái:** Đề xuất
**Ngày:** 2026-06-26
**Người quyết định:** Chủ nhiệm đề tài (PI), trưởng nhóm kỹ thuật, đầu mối liên lạc đơn vị vận hành đường cao tốc

## Bối cảnh

Cảnh báo đến người lái là đầu ra duy nhất của hệ thống, nên *cách thức* hiển thị cảnh báo và *việc chúng ta tự xây dựng hay tái sử dụng* bảng cảnh báo có ý nghĩa quan trọng về mặt kiến trúc. Hình 1 cho thấy cả một **bảng thông báo điện tử (VMS) gắn trên giá long môn (gantry)** lẫn một **bảng LED bên đường**. Các tuyến đường cao tốc hiện đại thường đã có sẵn các giá long môn VMS do đơn vị vận hành điều khiển cùng một hạ tầng xương sống ITS; các đoạn khác (và bất kỳ mô hình thử nghiệm trên bàn (bench) nào) thì không có gì. Việc bổ sung biển báo dư thừa vừa tốn kém, vừa chậm cấp phép, vừa làm rối mặt đường.

Các yếu tố tác động: chi phí đầu tư, công sức lắp đặt/cấp phép, độ phức tạp tích hợp với hệ thống ITS của bên thứ ba, hình học bố trí bảng báo (phải đặt cách ≥ DSD về phía trước theo hướng xe tới — [tài liệu 01 §4](../01-requirements.vi.md#4-bố-trí-cảnh-báo--phép-tính-mà-đề-xuất-bỏ-sót)), sự phù hợp với QCVN 41, và mức độ chấp nhận/quyền điều khiển của đơn vị vận hành.

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
- **Độ trễ & fail-safe có điều kiện theo backend.** Hai backend **không** đưa ra cùng những bảo đảm như nhau, và tài liệu phải nêu rõ điều này theo từng vị trí:
  - *Bảng LED chuyên dụng* — một điểm cuối thông minh tuân theo nhịp khẳng định (heartbeat) tín hiệu SHOW làm mới liên tục, nên nó đáp ứng trực tiếp độ trễ NFR-01 và được trang bị cơ chế tự ngắt an toàn của bộ điều khiển biển báo theo [ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.vi.md) (xóa bảng khi mất kết nối).
  - *VMS sẵn có* — được tiếp cận qua giao thức của đơn vị vận hành với các chu kỳ lệnh/làm mới và cơ chế phân xử thông báo có thể **vượt quá ngân sách ≤2 s của NFR-01** và có thể **chốt trạng thái (latch)** (không có cam kết heartbeat). Do đó NFR-01 là **có điều kiện** đối với backend này, và fail-safe quay về cơ chế *watchdog + chủ động CLEAR + đọc lại trạng thái* với một cửa sổ kẹt-BẬT (stale-ON) tồn dư bằng đúng chu kỳ lệnh của đơn vị vận hành (ADR-0009 §A). Hãy cấp cho adapter VMS ngân sách độ trễ + ưu tiên phân xử riêng của nó, và ưu tiên chế độ khẳng định-làm-mới / khóa liên động phần cứng (hardware interlock) ở nơi đơn vị vận hành có cung cấp.
- **Xem xét lại khi:** một giao thức thông báo ITS tiêu chuẩn được đơn vị vận hành bắt buộc áp dụng (thu gọn về một adapter), hoặc khi bổ sung một kênh cảnh báo V2X/trên xe (một backend *thứ ba* nằm sau cùng giao diện đó).

## Hạng mục hành động

1. [ ] Đặc tả giao diện cơ cấu chấp hành `SHOW/CLEAR/STATUS` và ngữ nghĩa đọc lại trạng thái (status read-back).
2. [ ] Làm việc với một đơn vị vận hành đường cao tốc để tìm hiểu giao thức VMS và các quy tắc phân xử thông báo của họ.
3. [ ] Chọn một bảng LED năng lượng mặt trời tuân thủ QCVN 41 cho backend chuyên dụng / mô hình thử nghiệm trên bàn (bench).
4. [ ] Định nghĩa tập thông báo cảnh báo được phê duyệt và quy trình rà soát sự phù hợp của tập đó — **xác nhận rằng QCVN 41 thực sự cung cấp một phần tử tuân thủ** cho tình huống "có xe dừng trên lề đường phía trước"; nếu không có, hãy theo đuổi một ngoại lệ được quản lý hoặc một biểu tượng (pictogram) mới với cơ quan quản lý đường bộ thay vì mặc nhiên cho rằng đã tuân thủ. Việc rà soát phải bao trùm **mọi thông báo mà máy trạng thái có thể muốn hiển thị** — thông báo chính "có xe dừng phía trước", **bất kỳ cảnh báo/đổi-thông-điệp khi tắc nghẽn nào** ([tài liệu 02 §4](../02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo)), và bất kỳ chỉ báo trạng-thái-suy-giảm nào — bởi vì **thiết kế ức chế khi tắc nghẽn giả định tồn tại một thông báo hợp pháp _thứ hai_**; nếu QCVN 41 chỉ cung cấp một phần tử dùng được, thì việc đổi-thông-điệp là không khả dụng và thiết kế lùi về **chỉ-ức-chế, một khoảng trống phạm vi bao phủ đã được nêu** ([tài liệu 04 §0](../04-risk-and-safety.vi.md#0-giới-hạn-bảo-vệ-mối-nguy-còn-lại)). **Đây là một cổng đạt/không-đạt (go/no-go) của Giai đoạn 1** ([tài liệu 03 §5](../03-roadmap-and-phasing.vi.md#5-cổng-kiểm-soát-rủi-ro-theo-từng-giai-đoạn)), không phải một lần kiểm tra ở cuối khâu thiết kế: một phần tử bị thiếu sẽ buộc một quy trình xin ngoại-lệ-được-quản-lý có thời gian chuẩn bị dài, vốn chặn đầu ra duy nhất của hệ thống, nên hãy xác nhận nó (hoặc khởi động quy trình ngoại lệ) ngay từ đầu dự án, song song với mũi nhọn (spike) radar.
5. [ ] Đặc tả **ngân sách độ trễ + ưu tiên phân xử của adapter VMS** và ghi nhận NFR-01 có điều kiện cùng phương án fail-safe dự phòng cho VMS chốt trạng thái (latching) ([ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.vi.md)).
