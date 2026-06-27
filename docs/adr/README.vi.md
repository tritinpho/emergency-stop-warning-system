# Bản ghi quyết định kiến trúc (ADR)

> 🇬🇧 Bản gốc tiếng Anh: [README.md](README.md)

Mỗi ADR ghi lại một quyết định có tính chịu lực: bối cảnh, các phương án đã cân nhắc, lựa chọn và các
hệ quả. Chúng tuân theo định dạng ADR tiêu chuẩn. Tất cả đều ở trạng thái **Đề xuất** cho đến khi
nhóm dự án chấp nhận.

| ADR | Quyết định | Trạng thái |
|-----|----------|--------|
| [ADR-0001](ADR-0001-sensing-modality.vi.md) | Phương thức cảm biến — hợp nhất camera + radar (không chỉ dùng camera) | Đề xuất |
| [ADR-0002](ADR-0002-edge-vs-cloud-processing.vi.md) | Chạy vòng lặp an toàn tại biên; đám mây chỉ để giám sát | Đề xuất |
| [ADR-0003](ADR-0003-detection-algorithm.vi.md) | Bộ phát hiện nhẹ + giới hạn theo ROI + logic thời gian chờ (không dùng DL đầu-cuối nặng, không dùng trừ nền thuần túy) | Đề xuất |
| [ADR-0004](ADR-0004-warning-actuator-integration.vi.md) | Cơ cấu chấp hành cắm-ghép — tái sử dụng VMS sẵn có nếu có, nếu không thì dùng bảng LED năng lượng mặt trời chuyên dụng | Đề xuất |
| [ADR-0005](ADR-0005-fail-safe-and-system-safety.vi.md) | Tư thế an toàn khi sự cố (fail-safe), trạng thái an toàn, leo thang theo tình trạng, và đường dẫn trạng thái an toàn theo cơ chế an toàn tự kích hoạt khi mất tín hiệu (dead-man's switch) | Đề xuất |
| [ADR-0006](ADR-0006-connectivity-and-power.vi.md) | Kết nối & nguồn điện — phương án pin mặt trời + ắc quy, đo từ xa kiểu lưu và chuyển | Đề xuất |
| [ADR-0007](ADR-0007-validation-and-data-strategy.vi.md) | Chiến lược kiểm chứng & dữ liệu — những gì thử nghiệm trên bàn (bench)/mô phỏng chứng minh được so với những gì hoãn lại cho hiện trường; kế hoạch thu thập dữ liệu | Đề xuất |
| [ADR-0008](ADR-0008-detection-persistence-and-multitrack.vi.md) | Tính bền vững của phát hiện — che khuất so với rời đi, giữ trạng thái có radar chứng thực, ngữ nghĩa tập hợp đa vết (track) | Đề xuất |
| [ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.vi.md) | Bố trí cơ cấu chấp hành an toàn khi sự cố (cơ chế tự ngắt an toàn trong bộ điều khiển biển báo), các chế độ suy giảm bất đối xứng, giữ-khi-che-khuất có thể gia hạn | Đề xuất |

**Ghi chú phạm vi (thay cho một ADR riêng):** **mô hình phạm vi giám sát** khi triển khai là **các
vùng giám sát rời rạc tại những vị trí có giá trị cao**, không phải giám sát liên tục, và phạm vi được
cấp kinh phí là **một vùng thử nghiệm / mô phỏng của nó**. Lý do và chi tiết nằm trong
[tài liệu 02 §6](../02-system-architecture.vi.md#6-mô-hình-phạm-vi-giám-sát) và
[tài liệu 03](../03-roadmap-and-phasing.vi.md).

## Quy ước

- Mỗi tệp một quyết định, đánh số `ADR-NNNN`.
- Vòng đời trạng thái: **Đề xuất → Chấp nhận → (Ngưng dùng | Bị thay thế bởi ADR-XXXX)**.
- Thay thế thay vì viết lại lịch sử: một quyết định bị đảo ngược sẽ nhận một ADR mới thay thế cho ADR cũ.
