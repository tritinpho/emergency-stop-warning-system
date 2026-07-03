# ADR-0006: Kết nối & nguồn điện — tùy chọn pin mặt trời + ắc quy, đo lường từ xa theo cơ chế lưu và chuyển

> 🇬🇧 Bản gốc tiếng Anh: [ADR-0006-connectivity-and-power.md](ADR-0006-connectivity-and-power.md)

**Trạng thái:** Đề xuất
**Ngày:** 2026-06-26
**Người quyết định:** Chủ nhiệm đề tài (PI), trưởng nhóm kỹ thuật, kỹ sư hiện trường/lắp đặt

## Bối cảnh

Đề xuất không đề cập đến hai thực tế hiện trường vốn quyết định việc một thiết bị bên đường có thể được đặt vị trí hay không: **nguồn điện đến từ đâu** và **nó giao tiếp với TMC bằng cách nào**. Các điểm nóng trên làn dừng xe khẩn cấp (đường dẫn vào hầm, cầu, các đoạn đường cao tốc ở xa) thường thiếu nguồn điện lưới thuận tiện và có vùng phủ sóng di động chập chờn. Những ràng buộc này tương tác với các quyết định trước đó: xử lý cục bộ tại biên ([ADR-0002](ADR-0002-edge-vs-cloud-processing.vi.md)) đã loại bỏ sự phụ thuộc về mặt *an toàn* vào mạng, và lựa chọn nhận diện ([ADR-0003](ADR-0003-detection-algorithm.vi.md)) đã được giữ trong một ngân sách nguồn điện thân thiện với năng lượng mặt trời. ADR này ấn định chiến lược nguồn điện và kết nối nhất quán với cả hai.

Các yếu tố tác động: tự do chọn vị trí so với mức sẵn có của điện lưới, ngân sách nguồn điện (dẫn dắt các lựa chọn cảm biến/khối tính toán), nhu cầu đo lường từ xa so với các đường liên kết gián đoạn, chi phí, và bảo trì.

## Quyết định

- **Nguồn điện:** hỗ trợ **điện lưới ở nơi có sẵn, và pin mặt trời + ắc quy ở những nơi khác**, được tính toán kích cỡ cho **≥ 72 h tự chủ khi không có nắng** (NFR-07). Điều này biến ngân sách nguồn điện thành một ràng buộc thiết kế hạng nhất, giới hạn việc lựa chọn cảm biến và khối tính toán.
- **Kết nối:** **4G/LTE (hoặc cáp quang ở nơi có sẵn) cho đo lường từ xa/OTA**, được sử dụng theo cơ chế **lưu và chuyển (store-and-forward)** — các sự kiện và nhịp tín hiệu xếp hàng cục bộ và đồng bộ khi có cơ hội. Tùy chọn dùng **LoRaWAN** làm kênh phụ công suất thấp cho nhịp tín hiệu ở nơi sóng di động kém. Vòng lặp an toàn **không bao giờ** phụ thuộc vào bất kỳ thứ nào trong số này.

> **Không phải liên kết biển báo.** LoRa/LoRaWAN nêu ở đây là kênh phụ đo lường từ xa biên→TMC
> **không-trọng-yếu-an-toàn**. Liên kết biên→**biển báo** (IF-4) là trọng yếu an toàn và được đặc tả
> riêng trong [ADR-0014](ADR-0014-sign-link-bearer.vi.md) — đừng lẫn lộn hai thứ: phương tiện mang IF-4
> thừa hưởng xác thực, chống phát lại, và định thời khẳng-định-làm-mới mà một kênh phụ đo lường từ xa không có.

## Các phương án đã xét

### Phương án A: Giả định có điện lưới + sóng di động luôn bật
| Khía cạnh | Đánh giá |
|-----------|------------|
| Tự do chọn vị trí | **Thấp** — chỉ những vị trí có điện, phủ sóng tốt |
| Chi phí | Thấp (không có pin mặt trời/ắc quy) |
| Tính thực tế hiện trường | Kém đối với các điểm nóng đã nêu |

**Ưu điểm:** đơn giản nhất.
**Nhược điểm:** loại trừ chính những vị trí hầm/cầu/đường xa mà hệ thống nhắm tới; gắn chặt hoạt động vào mức sẵn có của đường liên kết nếu không đi kèm khả năng tự chủ tại biên.

### Phương án B: Tùy chọn pin mặt trời + ắc quy + đo lường từ xa theo cơ chế lưu và chuyển, tự chủ tại biên *(được chọn)*
| Khía cạnh | Đánh giá |
|-----------|------------|
| Tự do chọn vị trí | **Cao** — có điện hoặc ngoài lưới |
| Chi phí | Vừa phải (pin mặt trời/ắc quy ở nơi cần) |
| Tính thực tế hiện trường | Tốt; chịu được các khoảng đứt liên kết |
| Kỷ luật về nguồn điện | Bắt buộc một ngân sách cảm biến/khối tính toán hiệu quả (một ưu điểm) |

**Ưu điểm:** có thể đặt vị trí gần như ở bất cứ đâu; bền bỉ trước các sự cố mất điện; lượng dữ liệu xuất ra bị giới hạn (quyền riêng tư/chi phí); trần công suất giữ cho thiết kế gọn nhẹ.
**Nhược điểm:** việc tính kích cỡ/bảo trì pin mặt trời; các lựa chọn khối tính toán/cảm biến phải tôn trọng giới hạn công suất.

### Phương án C: Ngoài lưới + truyền dẫn vệ tinh/đắt tiền (backhaul), đo lường từ xa phong phú hơn
**Ưu điểm:** kết nối ở bất cứ đâu.
**Nhược điểm:** chi phí và công suất vượt ngân sách; không cần thiết vì khả năng tự chủ tại biên đã loại bỏ nhu cầu an toàn đối với kết nối.

## Phân tích đánh đổi

Phương án A âm thầm giả định bỏ qua bài toán triển khai và sẽ khiến dự án mắc kẹt ở các vị trí phòng thí nghiệm. Vì vòng lặp an toàn vốn đã tự chủ tại biên, **kết nối có thể ở mức nỗ lực tốt nhất (best-effort)**, điều này làm cho cơ chế lưu và chuyển qua sóng di động thông thường là đủ và rẻ — không cần đến truyền dẫn (backhaul) cao cấp của Phương án C. Pin mặt trời + ắc quy mua được **sự tự do chọn vị trí** mà tình huống sử dụng đòi hỏi; trần công suất phát sinh từ đó là một hàm ép buộc hữu ích giúp giữ cho phần cảm biến/tính toán hiệu quả (và nhất quán với ADR-0001/0003). Phương án B là lựa chọn cân bằng.

## Hệ quả

- **Dễ hơn:** triển khai tại các điểm nóng ngoài lưới có giá trị cao; bền bỉ trước các gián đoạn nguồn điện/liên kết; lượng dữ liệu xuất ra thấp, riêng tư.
- **Khó hơn:** tính kích cỡ pin mặt trời/ắc quy, thiết kế nhiệt cho vỏ bảo vệ, và bảo trì hiện trường; một ngân sách nguồn điện cứng mà các lựa chọn cảm biến/tính toán phải tuân thủ; logic đồng bộ lưu và chuyển (thứ tự, lưu giữ, kiểm soát áp lực ngược - backpressure). **Radar đạt-chuẩn-cổng** ([ADR-0001](ADR-0001-sensing-modality.vi.md)) tiêu thụ nhiều hơn một mô-đun hiện diện thông thường — công suất của nó là một **đầu vào hạng nhất cho ngân sách này**, được dung hòa như chi phí của nó đã được ([tài liệu 03 §1](../03-roadmap-and-phasing.vi.md#1-rà-soát-thực-tế-phạm-vi--ngân-sách-đọc-trước)).
- **Xem xét lại khi:** một hành lang tuyến cung cấp điện lưới + cáp quang đáng tin cậy (đơn giản hóa về Phương án A tại chỗ), hoặc khi phân tích trung tâm theo thời gian thực phong phú hơn biện minh cho truyền dẫn (backhaul) cao cấp.

## Hạng mục hành động

1. [ ] Tính ngân sách năng lượng tại vị trí (cảm biến + khối tính toán + tín hiệu cho bảng báo) và tính kích cỡ tấm pin + ắc quy cho ≥72 h tự chủ — **bao gồm cả công suất tiêu thụ của radar đạt-chuẩn-cổng**, vốn vượt giả định mô-đun-hiện-diện-thông-thường trong [ADR-0001](ADR-0001-sensing-modality.vi.md); đưa vào tính toán khi mô-đun được chọn.
2. [ ] Chọn mô-đun/gói cước di động; thiết kế hộp thư gửi đi (outbox) theo cơ chế lưu và chuyển (lưu giữ, thứ tự).
3. [ ] Đánh giá LoRaWAN làm kênh phụ cho nhịp tín hiệu ở các vị trí phủ sóng kém.
4. [ ] Đặc tả vỏ bảo vệ ngoài trời (IP65+, nhiệt) cho cảm biến, khối tính toán, và ắc quy.
