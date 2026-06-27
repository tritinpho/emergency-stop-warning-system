# ADR-0007: Chiến lược kiểm chứng & dữ liệu — mô phỏng chứng minh được điều gì, và dữ liệu đến từ đâu

> 🇬🇧 Bản gốc tiếng Anh: [ADR-0007-validation-and-data-strategy.md](ADR-0007-validation-and-data-strategy.md)

**Trạng thái:** Đề xuất
**Ngày:** 2026-06-27
**Người quyết định:** Chủ nhiệm đề tài (PI) (ThS. Phó Trí Tín), trưởng nhóm kỹ thuật, kỹ sư thị giác máy tính (CV)

## Bối cảnh

Sản phẩm bàn giao được tài trợ (cấp trường) là một **giàn thử nghiệm (bench rig) + mô phỏng**, chứ không phải một lần triển khai hiện trường ([tài liệu 03](../03-roadmap-and-phasing.vi.md)). Điều đó khiến cho câu hỏi *"làm sao chúng ta kiểm chứng một tuyên bố về an toàn mà không có đường thực?"* tự thân trở thành một quyết định chịu lực — thế nhưng bản phác thảo đầu tiên của các tài liệu lại giả định rằng các kết quả mô phỏng tự nó đã có ý nghĩa hiển nhiên, và để ngỏ phần **dữ liệu huấn luyện/đánh giá** của bộ phát hiện. Cả hai khoảng trống này quyết định liệu báo cáo cuối cùng có thể bảo vệ được các tuyên bố của nó hay không.

Hai câu hỏi gắn kết với nhau:

1. **Giàn thử nghiệm/mô phỏng thực sự chứng minh được điều gì, và điều gì phải hoãn sang giai đoạn thử nghiệm hiện trường (field pilot)?** Một bộ mô phỏng và một giàn thử trong phòng thí nghiệm có thể vận hành logic và định thời một cách triệt để, nhưng không thể tái tạo mưa, lóa sáng, sương mù thật, hay nhiễu radar (radar clutter) thật.
2. **Dữ liệu mang tính đại diện đến từ đâu?** Lựa chọn nhận diện ([ADR-0003](ADR-0003-detection-algorithm.vi.md)) cần các đoạn clip ngày/đêm/mưa của lề đường cao tốc Việt Nam để tinh chỉnh và đánh giá — và việc thu thập video bên đường làm phát sinh chính những nghĩa vụ về quyền riêng tư ([tài liệu 04 §4](../04-risk-and-safety.vi.md#4-privacy-data--legal-compliance)) ngay ở giai đoạn **nguyên mẫu (prototype)**, chứ không chỉ ở hiện trường.

Các yếu tố tác động: tính trung thực của tuyên bố (giá trị đã nêu của dự án), độ trung thực của mô phỏng so với công sức bỏ ra, tính sẵn có của dữ liệu và quyền riêng tư, và một sự bàn giao gọn gàng sang giai đoạn thử nghiệm cấp sở.

## Quyết định

Áp dụng một **cách phân tách kiểm chứng hai tầng với các ranh giới chứng minh được (provability boundaries) tường minh**, cộng với một **kế hoạch dữ liệu phân tầng**:

**Các tầng kiểm chứng.**
- **Mô phỏng** kiểm chứng phần *logic*: máy trạng thái, chính sách dwell/độ trễ (hysteresis)/che khuất/đa vết (multi-track) ([ADR-0008](ADR-0008-detection-persistence-and-multitrack.vi.md)), và **phạm vi tiêm lỗi (fault-injection coverage)** đối chiếu với danh mục kịch bản.
- **Giàn thử nghiệm** kiểm chứng phần *nhận diện + tác động (actuation)*: một camera thật (và radar nếu được tài trợ) điều khiển vòng lặp thật để ra lệnh cho một bảng báo thay thế (stand-in sign) trên các kịch bản vật lý được dàn dựng.

**Ranh giới chứng minh được (nêu rõ trong báo cáo).** Giàn thử/mô phỏng *có thể* tuyên bố: tính đúng đắn của logic, định thời/độ trễ (latency), xử lý lỗi, và khả năng kháng kích hoạt sai đối với các nhiễu (nuisance) *đã được mô hình hóa*. Chúng **không thể** tuyên bố: độ nhạy phát hiện (recall) trong điều kiện thực khi mưa/lóa sáng/sương mù, tỷ lệ báo động giả thực, hay hiệu năng trước nhiễu radar thực — những điều này được **hoãn sang giai đoạn hiện trường (field-deferred)** cho lần thử nghiệm cấp sở ([tài liệu 05](../05-field-pilot-proposal.vi.md)).

**Các kênh cảm biến tổng hợp (synthetic sensor channels)** được phép sử dụng nhưng phải dùng một **mô hình cảm biến được lập tài liệu, thận trọng (conservative)** với các giả định được nêu rõ; một radar tổng hợp *giả định* khả năng phát hiện xe đứng yên hoàn hảo thì không thể được dùng để làm bằng chứng cho độ nhạy phát hiện trong điều kiện bất lợi (xem [ADR-0001](ADR-0001-sensing-modality.vi.md) và cách phân tách nghiệm thu ở [tài liệu 01 §5](../01-requirements.vi.md#5-evaluation-metrics--acceptance-criteria)).

**Kế hoạch dữ liệu**, theo thứ tự ưu tiên: (1) các tập dữ liệu ITS/giao thông công khai; (2) dữ liệu CCTV lịch sử do đơn vị vận hành cung cấp theo một thỏa thuận dữ liệu; (3) một lần thu thập cục bộ nhỏ, giới hạn mục đích, **có sự đồng thuận (consented)**, chỉ khi (1)–(2) không đủ — tuân theo các quy tắc giảm thiểu dữ liệu (data-minimization) ngay từ ngày đầu (xử lý ngay trên thiết bị, thời gian lưu trữ có giới hạn, kiểm soát truy cập). Việc thu thập dữ liệu là một nhiệm vụ tường minh của Giai đoạn 1/Giai đoạn 3 với các bước về xin phép và quyền riêng tư, **không phải** một đầu vào miễn phí.

**Tiêu chí đạt (mô phỏng).** Vòng lặp kín đáp ứng các mục tiêu ở *cột nguyên mẫu (prototype-column)* của tài liệu 01 §5 trên toàn bộ danh mục kịch bản, việc tiêm lỗi bắt được ≥ 95 % danh sách FMEA ([tài liệu 04 §2](../04-risk-and-safety.vi.md#2-fmea-lite-failure-mode--effect--detection--response)), và **không có lỗi nào được tiêm vào tạo ra một đầu ra gây nhầm lẫn hoặc bị kẹt**.

## Các phương án đã xét

### Phương án A: "Kiểm chứng trong mô phỏng" để ngỏ không định nghĩa *(khoảng trống của bản phác thảo đầu tiên)*
**Ưu điểm:** ít việc lập kế hoạch nhất ngay lúc này.
**Nhược điểm:** không có tiêu chí đạt, không có ranh giới chứng minh được, không có nguồn dữ liệu — dẫn đến một báo cáo cuối cùng tuyên bố nhiều hơn những gì nó đã kiểm thử. Không thể chấp nhận đối với một hệ thống liên quan đến an toàn.

### Phương án B: Phân tách hai tầng với ranh giới chứng minh được tường minh + kế hoạch dữ liệu phân tầng *(được chọn)*
**Ưu điểm:** các tuyên bố trung thực, có thể bảo vệ được; thiết lập sẵn cho lần thử nghiệm hiện trường một cách gọn gàng; buộc công việc về dữ liệu/quyền riêng tư phải nổi lên sớm, nơi nó rẻ và chưa có dữ liệu công khai nào bị đặt vào rủi ro.
**Nhược điểm:** nhiều phương pháp luận phải làm trước; phải xây dựng một mô hình cảm biến tổng hợp đáng tin cậy và lập tài liệu các điểm cần lưu ý (caveat) của nó; việc thu thập dữ liệu trở thành một phụ thuộc được theo dõi.

### Phương án C: Cố gắng kiểm chứng mang tính đại diện cho hiện trường ngay bây giờ
**Ưu điểm:** các tuyên bố mạnh hơn nếu nó thành công.
**Nhược điểm:** bất khả thi trong phạm vi 20 triệu VND / giàn thử nghiệm; sẽ hứa hẹn quá mức và bàn giao dưới mức. Đây **chính là** dự án cấp sở, không phải dự án này.

## Phân tích đánh đổi

Uy tín của dự án dựa trên việc tuyên bố chính xác những gì nó đã chứng minh — không hơn. Sự im lặng của Phương án A chính là cách mà các nguyên mẫu tốt rốt cuộc lại có những báo cáo cuối cùng không thể bảo vệ được. Phương án B tốn một ít công viết phương pháp luận và một mô hình cảm biến được lập tài liệu, và đổi lại mọi tuyên bố trong báo cáo cuối cùng đều mang một nhãn rõ ràng *"được kiểm chứng bởi mô phỏng / giàn thử / hoãn sang hiện trường"*, và công việc về quyền riêng tư của dữ liệu đáp xuống ở giai đoạn nguyên mẫu, nơi nó rẻ. Nó cũng cho tuyên bố về độ bền của radar trong [ADR-0001](ADR-0001-sensing-modality.vi.md) và phần giữ-khi-che-khuất (occlusion-hold) của [ADR-0008](ADR-0008-detection-persistence-and-multitrack.vi.md) một mục tiêu kiểm chứng cụ thể thay vì một giả định.

## Hệ quả

- **Dễ hơn:** một câu chuyện nghiệm thu trung thực, chịu được sự soi xét của người phản biện; một sự bàn giao cấp sở gọn gàng; tuân thủ quyền riêng tư sớm và rẻ.
- **Khó hơn:** phải soạn phương pháp luận mô phỏng và một mô hình cảm biến tổng hợp được lập tài liệu; việc thu thập dữ liệu (kèm xin phép) trở thành một nhiệm vụ thực sự; một số tuyên bố nổi bật bị hoãn lại một cách tường minh, điều này phải được truyền đạt như một **điểm mạnh** (sự trung thực về phạm vi), chứ không phải một thiếu hụt.
- **Xem xét lại khi:** lần thử nghiệm hiện trường cung cấp dữ liệu thực và hiệu năng thực, lúc đó các tuyên bố bị hoãn lại sẽ được đo lường một cách thực sự.

## Hạng mục hành động

1. [ ] Viết **phương pháp luận mô phỏng**: danh mục kịch bản, mô hình cảm biến tổng hợp + các giả định, và tiêu chí đạt.
2. [ ] Gắn nhãn cho mọi yêu cầu của tài liệu 01 và mọi chỉ số ở §5 là **giàn thử / mô phỏng / hoãn sang hiện trường** (cung cấp đầu vào cho cổng kiểm chứng tính kiểm chứng được của yêu cầu).
3. [ ] Thiết lập **kế hoạch dữ liệu**: xác định các tập dữ liệu công khai; khởi động cuộc trao đổi về thỏa thuận dữ liệu CCTV với đơn vị vận hành; định nghĩa một quy trình thu thập cục bộ có sự đồng thuận với các giới hạn về thời gian lưu trữ/truy cập như một phương án dự phòng.
4. [ ] Bảo đảm các giả định của mô hình radar tổng hợp là **thận trọng** và rằng các tuyên bố về điều kiện bất lợi được kiểm soát (gated) dựa trên bằng chứng từ radar thật ([ADR-0001](ADR-0001-sensing-modality.vi.md)).
