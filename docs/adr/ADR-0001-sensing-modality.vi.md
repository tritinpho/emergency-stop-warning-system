# ADR-0001: Phương thức cảm biến — hợp nhất camera + radar

> 🇬🇧 Bản gốc tiếng Anh: [ADR-0001-sensing-modality.md](ADR-0001-sensing-modality.md)

**Trạng thái:** Đề xuất
**Ngày:** 2026-06-26
**Người quyết định:** Chủ nhiệm đề tài (ThS. Phó Trí Tín), trưởng nhóm kỹ thuật, cố vấn an toàn giao thông

## Bối cảnh

Hệ thống phải phát hiện một xe đang dừng trong làn dừng xe khẩn cấp và làm được điều đó **cụ thể trong
những điều kiện mà đề xuất nêu là nguy hiểm nhất: ban đêm, mưa, sương mù, lóa sáng và mật độ giao
thông cao**. Chỉ dùng một camera là rẻ nhất và cho khả năng phân loại phong phú, nhưng nó lại yếu nhất
chính trong những điều kiện đó — thiếu sáng, lóa đèn pha, nước đọng trên ống kính và bị che khuất bởi
các xe tải chạy qua. Đặt một cảnh báo *an toàn* dựa trên cảm biến vốn thất bại đúng lúc cần đến nó nhất
chính là rủi ro trung tâm của cách định hình ban đầu theo kiểu "camera AI".

Các yếu tố tác động: độ vững chắc của phát hiện trong điều kiện bất lợi (chi phối), chi phí và nguồn
điện (ngân sách năng lượng mặt trời), tải tính toán tại biên, hiệu năng ban đêm/thời tiết, khả năng
phân loại (xe ô tô vs người vs mảnh vỡ) và khả năng bảo trì.

## Quyết định

Sử dụng một **cặp cảm biến camera + radar có hợp nhất** làm phương thức cảm biến cốt lõi. Camera cung
cấp khả năng phân loại và hình học ROI; radar cung cấp **cự ly, sự hiện diện và tốc độ — những thông
tin tồn tại được qua bóng tối, mưa và sương mù**, đồng thời xác nhận "đang hiện diện và đứng yên" một
cách độc lập với điểm ảnh. Ảnh nhiệt được giữ lại như một bổ sung tùy chọn cho các vị trí có điều kiện
ban đêm/sương mù khắc nghiệt khi ngân sách cho phép.

> **Lưu ý — đây là giả định chịu tải, nên nó là một cổng kiểm chứng, không phải điều mặc nhiên.** Phát
> hiện một xe **đứng yên** trong nhiễu nền (clutter) bên đường là trường hợp *khó* đối với radar: một
> xe đang đỗ có Doppler gần bằng không và phải cạnh tranh với các phản hồi tĩnh từ hộ lan, biển báo và
> mặt đường, còn một radar bên đường nhìn dọc theo lề đường thì bản thân nó cũng bị che khuất một phần
> bởi các xe tải chạy trong làn xuyên suốt. Điều này cần một **radar có khả năng phát hiện xe đứng yên**
> (ví dụ một thiết bị imaging radar / FMCW có độ phân giải cự ly cao kèm bản đồ nhiễu nền), **chứ
> không** phải một mô-đun "hiện diện" thông thường, và nó phải được **kiểm chứng tại hình học lướt sát
> (grazing) của lề đường** trước khi tuyên bố về điều kiện bất lợi được chứng cứ hỗ trợ (go/no-go Giai
> đoạn 3, [tài liệu 03 §5](../03-roadmap-and-phasing.vi.md#5-per-phase-risk-gates)). Bởi vì toàn bộ lập
> luận về độ vững chắc ban đêm/mưa/sương mù đều dựa trên điều này, nó cũng là **mức phơi nhiễm rủi ro
> cao nhất** của hệ thống ([tài liệu 04 R5](../04-risk-and-safety.vi.md#1-risk-register)).

## Các phương án đã xét

### Phương án A: Chỉ dùng camera
| Khía cạnh | Đánh giá |
|-----------|------------|
| Độ phức tạp | Thấp |
| Chi phí | Thấp |
| Độ vững chắc (đêm/mưa/sương mù/lóa sáng) | **Kém** — các điều kiện gây thất bại trùng với các điều kiện nguy hiểm |
| Phân loại | Tốt |
| Nguồn điện | Thấp–trung bình |

**Ưu điểm:** rẻ nhất; đơn giản nhất; ngữ nghĩa phong phú; khớp với hình ảnh "camera AI" của đề xuất.
**Nhược điểm:** yếu nhất đúng lúc cần nhất; âm tính giả do lóa sáng/che khuất; một hệ thống an toàn
suy giảm âm thầm vào ban đêm.

### Phương án B: Hợp nhất camera + radar *(được chọn)*
| Khía cạnh | Đánh giá |
|-----------|------------|
| Độ phức tạp | Trung bình (hợp nhất + đồng bộ thời gian) |
| Chi phí | Trung bình (+ một radar/vị trí) |
| Độ vững chắc | **Tốt** — radar bù đắp cho các điều kiện mù của camera |
| Phân loại | Tốt (camera) + hiện diện/tốc độ đáng tin cậy (radar) |
| Nguồn điện | Trung bình (radar tiêu thụ ít điện) |

**Ưu điểm:** vững chắc ngày/đêm/thời tiết; xác nhận độc lập làm giảm cả bỏ sót lẫn báo động giả; radar
cho tốc độ trực tiếp (tín hiệu "đứng yên" sạch); suy giảm có kiểm soát (một cảm biến hỏng → vẫn còn
phạm vi giám sát một phần + một cảnh báo về tình trạng).
**Nhược điểm:** chi phí và tích hợp nhiều hơn; việc hợp nhất và đồng bộ thời gian giữa các cảm biến
làm tăng công sức kỹ thuật.

### Phương án C: Đa cảm biến đầy đủ (camera + radar + nhiệt + lidar)
| Khía cạnh | Đánh giá |
|-----------|------------|
| Độ phức tạp | Cao |
| Chi phí | Cao |
| Độ vững chắc | Xuất sắc |
| Nguồn điện | Cao |

**Ưu điểm:** độ vững chắc tốt nhất có thể.
**Nhược điểm:** vượt ngân sách và quá phạm vi đối với một nguyên mẫu cấp trường; điện năng cao làm
suy yếu việc bố trí dùng năng lượng mặt trời; lợi ích giảm dần so với phương án B cho trường hợp sử
dụng này.

## Phân tích đánh đổi

Yếu tố quyết định là **độ vững chắc theo điều kiện**: giá trị của hệ thống là cao nhất vào ban đêm và
trong thời tiết xấu, nên khả năng cảm biến không được sụp đổ ở đó. Phương án A tối ưu chi phí nhưng
đánh đổi lời hứa an toàn cốt lõi. Phương án C mua độ vững chắc mà ngân sách và giới hạn nguồn điện
không thể duy trì. Phương án B bù đắp cho các kiểu lỗi cụ thể của camera bằng một bổ trợ rẻ, tiêu thụ
ít điện, chịu được thời tiết, đồng thời tạo ra một tín hiệu "đứng yên" độc lập mà còn **cắt giảm báo
động giả** — phục vụ cả hai yêu cầu về tỉ lệ lỗi cùng một lúc.

Đối với phạm vi mô phỏng/bench, radar có thể được biểu diễn bằng một kênh hiện diện/tốc độ tổng hợp,
nên việc chọn phương án B ngay bây giờ tốn ít chi phí và giữ mở lối đi cho triển khai hiện trường.
**Nhưng một radar tổng hợp giả định phát hiện đứng yên hoàn hảo thì không thể được dùng để _chứng cứ
hóa_ mục tiêu recall trong điều kiện bất lợi** — tuyên bố đó được hoãn sang giai đoạn hiện trường trừ
khi một radar có khả năng phát hiện xe đứng yên thực sự được đặt trên bàn thử (bench) và vượt qua cổng
kiểm chứng nêu trên ([ADR-0007](ADR-0007-validation-and-data-strategy.vi.md),
[tài liệu 01 §5](../01-requirements.vi.md#5-evaluation-metrics--acceptance-criteria)). Hãy giữ radar là
một ưu tiên ngân sách đúng vì lý do này; nếu ngân sách phần cứng buộc phải loại nó ra, **hãy thu hẹp
phạm vi tuyên bố về ban đêm/điều kiện bất lợi, đừng âm thầm đặt nó dựa trên dữ liệu tổng hợp**.

## Hệ quả

- **Dễ hơn (nếu cổng kiểm chứng được vượt qua):** phát hiện ban đêm/thời tiết đáng tin cậy; phát hiện
  đứng yên sạch hơn; suy giảm có kiểm soát; tỉ lệ báo động giả thấp hơn.
- **Khó hơn:** **đồng bộ thời gian và hiệu chuẩn ngoại tại (extrinsic calibration)** giữa camera và
  radar; một mô-đun hợp nhất cần thiết kế và kiểm thử; chi phí và điện năng mỗi vị trí cao hơn đôi chút;
  **và khả năng phát hiện xe đứng yên trong nhiễu nền của radar phải được kiểm chứng, chứ không phải
  mặc nhiên** (cổng kiểm chứng nêu trên).
- **Có điều kiện:** toàn bộ lợi ích trong điều kiện bất lợi đều **phụ thuộc vào cổng kiểm chứng radar**.
  Cho đến khi nó được vượt qua trên phần cứng thực, hãy coi độ vững chắc ban đêm/mưa/sương mù là một
  *giả thuyết được thiết kế*, chứ không phải một kết quả đã đo được
  ([ADR-0007](ADR-0007-validation-and-data-strategy.vi.md)).
- **Xem xét lại khi:** dữ liệu hiện trường cho thấy chỉ riêng camera đã đạt mục tiêu tại một vị trí ôn
  hòa nào đó (khi đó một biến thể chỉ-dùng-camera có thể là một phương án giảm chi phí được ghi nhận),
  hoặc khi ảnh nhiệt chứng tỏ là cần thiết tại các vị trí khó (nâng các thành phần của Phương án C theo
  từng vị trí).

## Hạng mục hành động

1. [ ] Chọn một radar **có khả năng phát hiện xe đứng yên** cụ thể (imaging / FMCW độ phân giải cự ly cao, 24/77 GHz, có lập bản đồ nhiễu nền) và một camera (WDR + IR tốt) — chứ không phải một mô-đun hiện diện thông thường.
2. [ ] **Cổng kiểm chứng (Giai đoạn 3):** chứng minh khả năng phát hiện đáng tin cậy một xe *đứng yên* trong nhiễu nền bên đường tại hình học lướt sát của lề đường, cả ngày lẫn đêm, trước khi tuyên bố về độ vững chắc trong điều kiện bất lợi.
3. [ ] Xác định hợp đồng hợp nhất và phương pháp đồng bộ thời gian (đồng hồ dùng chung / PTP / căn chỉnh dấu thời gian).
4. [ ] Xây dựng kênh radar tổng hợp cho khung mô phỏng — với một **mô hình cảm biến được ghi nhận, thận trọng** ([ADR-0007](ADR-0007-validation-and-data-strategy.vi.md)).
5. [ ] Bổ sung các kiểm tra tình trạng cho từng cảm biến vào bộ giám sát tình trạng (cung cấp đầu vào cho [ADR-0005](ADR-0005-fail-safe-and-system-safety.vi.md)).
