# Bản ghi quyết định kiến trúc (ADR)

> 🇬🇧 Bản gốc tiếng Anh: [README.md](README.md)

Mỗi ADR ghi lại một quyết định có tính chịu lực: bối cảnh, các phương án đã cân nhắc, lựa chọn và các
hệ quả. Chúng tuân theo định dạng ADR tiêu chuẩn. Các quyết định **thuộc quyền sở hữu của phần mềm**
đã được **chấp nhận (phía phần mềm) ngày 2026-06-27 — "Đã chấp nhận (phía phần mềm) ngày 2026-06-27"**;
phần còn lại vẫn ở trạng thái **Đề xuất**, chờ đội sở hữu ký duyệt (phần cứng / firmware / vận hành /
cơ quan quản lý) — cột Trạng thái nêu rõ đội nào.

| ADR | Quyết định | Trạng thái |
|-----|----------|--------|
| [ADR-0001](ADR-0001-sensing-modality.vi.md) | Phương thức cảm biến — hợp nhất camera + radar (không chỉ dùng camera) | Đề xuất — **phần cứng + kinh doanh** |
| [ADR-0002](ADR-0002-edge-vs-cloud-processing.vi.md) | Chạy vòng lặp an toàn tại biên; đám mây chỉ để giám sát | **Đã chấp nhận (pm)** 2026-06-27 |
| [ADR-0003](ADR-0003-detection-algorithm.vi.md) | Bộ phát hiện nhẹ + giới hạn theo ROI + logic thời gian chờ (không dùng DL đầu-cuối nặng, không dùng trừ nền thuần túy) | **Đã chấp nhận (pm)** 2026-06-27 |
| [ADR-0004](ADR-0004-warning-actuator-integration.vi.md) | Cơ cấu chấp hành cắm-ghép — tái sử dụng VMS sẵn có nếu có, nếu không thì dùng bảng LED năng lượng mặt trời chuyên dụng | Đề xuất — **phần cứng + vận hành/cơ quan quản lý** |
| [ADR-0005](ADR-0005-fail-safe-and-system-safety.vi.md) | Tư thế an toàn khi sự cố (fail-safe), trạng thái an toàn, leo thang theo tình trạng, và đường dẫn trạng thái an toàn theo cơ chế an toàn tự kích hoạt khi mất tín hiệu (dead-man's switch) | **Đã chấp nhận (pm)** 2026-06-27 |
| [ADR-0006](ADR-0006-connectivity-and-power.vi.md) | Kết nối & nguồn điện — phương án pin mặt trời + ắc quy, đo từ xa kiểu lưu và chuyển | Đề xuất — **phần cứng** |
| [ADR-0007](ADR-0007-validation-and-data-strategy.vi.md) | Chiến lược kiểm chứng & dữ liệu — những gì thử nghiệm trên bàn (bench)/mô phỏng chứng minh được so với những gì hoãn lại cho hiện trường; kế hoạch thu thập dữ liệu | **Đã chấp nhận (pm)** 2026-06-27 |
| [ADR-0008](ADR-0008-detection-persistence-and-multitrack.vi.md) | Tính bền vững của phát hiện — che khuất so với rời đi, giữ trạng thái có radar chứng thực, ngữ nghĩa tập hợp đa vết (track) | **Đã chấp nhận (pm)** 2026-06-27 |
| [ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.vi.md) | Bố trí cơ cấu chấp hành an toàn khi sự cố (cơ chế tự ngắt an toàn trong bộ điều khiển biển báo), các chế độ suy giảm bất đối xứng, giữ-khi-che-khuất có thể gia hạn | Đề xuất — **phần cứng/firmware** (logic đã được phê duyệt qua 0013) |
| [ADR-0010](ADR-0010-operator-override-and-manual-control.vi.md) | Chính sách ghi đè & điều khiển thủ công của người vận hành — có giới hạn, báo động lớn khi sự cố, tôn trọng nhịp tim (không bao giờ chốt, không bao giờ tồn tại âm thầm) | **Đã chấp nhận (pm)** 2026-06-27 · phạm vi vận hành còn chờ |
| [ADR-0011](ADR-0011-operator-concept-and-alarm-management.vi.md) | Quy trình vận hành & quản lý cảnh báo của người trực — đường phản hồi có nhân sự, có giới hạn mà "báo động lớn" phụ thuộc vào (gộp trùng, mức ưu tiên, leo thang lại) | Đề xuất — **vận hành/kinh doanh** |
| [ADR-0012](ADR-0012-security-and-threat-model.vi.md) | Tư thế an ninh & mô hình mối đe dọa hợp nhất — giới hạn phạm vi tuyên bố NFR-09 vào một bề mặt được liệt kê (liên kết biển báo, ghi đè, cấu hình/OTA, vô hiệu hóa cảm biến) | Đề xuất — **phần cứng/vận hành** (xác thực pm đã xong) |
| [ADR-0013](ADR-0013-degraded-hold-unification.vi.md) | Hợp nhất trạng thái giữ-khi-suy-giảm — một cảnh báo khi camera không xác thực được (che khuất *hoặc* lỗi) được giới hạn bởi T_degraded_max; đóng lỗ giữ-vô-hạn của RADAR-ONLY + liệt kê ma trận trạng thái cảnh báo × chế độ cảm biến | **Đã chấp nhận (pm)** 2026-06-27 |
| [ADR-0014](ADR-0014-sign-link-bearer.vi.md) | Phương tiện mang tín hiệu cho liên kết biển báo IF-4 — LoRa điểm-điểm, và ràng buộc chu kỳ làm việc 433 MHz lên cơ chế tự ngắt an toàn | Đề xuất — **phần cứng/firmware + phần mềm** (phân tích pm đã xong; chờ đo bench + pháp lý) |
| [ADR-0015](ADR-0015-state-machine-implementation-strategy.vi.md) | Chiến lược hiện thực máy trạng thái — bộ oracle SC-01..30 làm đặc tả thực thi, tick cố định nhịp, runtime MicroPython | **Đã chấp nhận (pm)** 2026-07-03 · D3 runtime chờ spike |
| [ADR-0016](ADR-0016-repo-consolidation-and-perception-source.vi.md) | Hợp nhất kho mã — kho này là gốc; đưa bộ nhận diện K230 của ACLAB ELMS vào sau điểm giáp ranh tri giác của ta; IF-4 thay chốt biển báo MQTT của họ | **Đã chấp nhận (pm)** 2026-07-09 · chờ phần cứng áp dụng IF-4 |

**Ghi chú phạm vi (thay cho một ADR riêng):** **mô hình phạm vi giám sát** khi triển khai là **các
vùng giám sát rời rạc tại những vị trí có giá trị cao**, không phải giám sát liên tục, và phạm vi được
cấp kinh phí là **một vùng thử nghiệm / mô phỏng của nó**. Lý do và chi tiết nằm trong
[tài liệu 02 §6](../02-system-architecture.vi.md#6-mô-hình-phạm-vi-giám-sát) và
[tài liệu 03](../03-roadmap-and-phasing.vi.md).

## Quy ước

- Mỗi tệp một quyết định, đánh số `ADR-NNNN`.
- Vòng đời trạng thái: **Đề xuất → Chấp nhận → (Ngưng dùng | Bị thay thế bởi ADR-XXXX)**.
- Thay thế thay vì viết lại lịch sử: một quyết định bị đảo ngược sẽ nhận một ADR mới thay thế cho ADR cũ.
