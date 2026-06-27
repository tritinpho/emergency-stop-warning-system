# 05 — Đề cương đề tài cấp sở — Thử nghiệm hiện trường — bản nháp

> 🇬🇧 Bản gốc tiếng Anh: [05-field-pilot-proposal.md](05-field-pilot-proposal.md)

**Đề tài:** Hệ thống cảnh báo tự động làn dừng xe khẩn cấp (ESW) — thử nghiệm hiện trường
**Trạng thái:** Bản nháp (tiếp nối nhiệm vụ cấp trường)
**Cập nhật:** 2026-06-26
**Kế thừa từ:** [01 yêu cầu](01-requirements.vi.md) · [02 kiến trúc](02-system-architecture.vi.md) · [03 lộ trình](03-roadmap-and-phasing.vi.md) · [04 rủi ro & an toàn](04-risk-and-safety.vi.md) · [ADR](adr/README.vi.md)

> Đây là **khung sườn bản nháp** cho đề tài nghiên cứu và phát triển cấp sở mà bản mẫu (prototype)
> cấp trường được thiết kế để làm tiền đề. Đề tài chuyển nguyên lý đã được kiểm chứng thành một
> thử nghiệm hiện trường thực tế trên đường. Các con số (kinh phí, thời lượng, số lượng điểm) là
> giá trị dự kiến mang tính tạm thời, sẽ được chốt lại cùng với đơn vị vận hành đường cao tốc được
> lựa chọn và báo giá mua sắm.

---

## 1. Đề xuất tóm lược trong một đoạn

Lấy **bản mẫu ESW đã được kiểm chứng** từ nhiệm vụ cấp trường và triển khai một **thử nghiệm hiện
trường thực tế**: lắp đặt **2–3 thiết bị tại hiện trường (bên đường) đã được sản phẩm hóa tại các
điểm có nguy cơ cao trên đường cao tốc**, phối hợp với đơn vị vận hành đường, vận hành trên dòng
giao thông thực trong **≥ 6 tháng**, và **đo lường xem cảnh báo chủ động có thực sự làm giảm nguy cơ
sự cố trên làn dừng mà không gây báo động giả lặp lại hay không** — qua đó tạo ra một thiết kế tham
chiếu khả triển khai, tuân thủ QCVN, và một hồ sơ an toàn (safety case) đã được kiểm chứng mà các
đơn vị vận hành khác có thể áp dụng.

## 2. Xuất xứ & luận chứng (xuất xứ)

Nhiệm vụ cấp trường đã mang lại đúng những gì một khoản tài trợ hạt giống có thể tạo ra: một bản mẫu
vòng kín (chu trình khép kín) hoạt động được, các chỉ số đo được trên mô hình thử nghiệm trên bàn
(bench) / mô phỏng, một kiến trúc và bộ ADR đã được chấp nhận, và một khung sườn hồ sơ an toàn
([tài liệu 03 §6](03-roadmap-and-phasing.vi.md)). Nhiệm vụ này một cách có chủ đích **không thể**
trả lời những câu hỏi quyết định giá trị thực tế, bởi vì một mô hình thử nghiệm trên bàn và mô phỏng
không thể:

- đo **hiệu quả trên dòng giao thông thực** — liệu các lái xe phía sau có thực sự giảm tốc / chuyển
  làn không, và xung đột đâm sau với xe dừng trên làn dừng có giảm tại các điểm được lắp đặt thiết bị
  đo đạc không?
- đo **tỉ lệ báo động giả trong thực tế** qua các điều kiện thời tiết, ánh sáng và mật độ giao thông;
- chứng minh **tích hợp với đơn vị vận hành / ITS** (VMS thực, TMC thực, giấy phép thực);
- thiết lập **sự chấp nhận của công chúng** và việc hiệu chỉnh niềm tin mà toàn bộ thiết kế phụ thuộc
  vào ([tài liệu 04 R2/R7](04-risk-and-safety.vi.md)).

Chỉ một thử nghiệm hiện trường mới trả lời được những câu hỏi này. Thử nghiệm này cũng phù hợp với
các ưu tiên cấp tỉnh về **giao thông thông minh (ITS), an toàn giao thông và chuyển đổi số trong quản
lý hạ tầng**.

## 3. Mục tiêu

**Tổng quát.** Thiết kế, triển khai và kiểm chứng một ESW đã được sản phẩm hóa tại các điểm thực tế
trên đường cao tốc; định lượng hiệu quả an toàn của nó; cung cấp một thiết kế tham chiếu khả triển
khai, tuân thủ QCVN, và một hồ sơ an toàn đã được kiểm chứng; và tạo cơ sở cho việc tiêu chuẩn hóa và
thương mại hóa.

**Cụ thể.**

1. **Sản phẩm hóa** thiết bị tại hiện trường đạt cấp độ hiện trường — gia cố bền bỉ, dùng pin mặt
   trời, đa cảm biến, an toàn khi sự cố (fail-safe) ([ADR-0001](adr/ADR-0001-sensing-modality.vi.md),
   [ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.vi.md), [ADR-0006](adr/ADR-0006-connectivity-and-power.vi.md)).
2. Thiết lập một **phương pháp chọn vị trí theo từng điểm dựa trên DSD** và áp dụng tại các điểm thử
   nghiệm ([tài liệu 01 §4](01-requirements.vi.md)).
3. Tích hợp với **VMS/ITS hiện có** của đơn vị vận hành nếu có sẵn, hoặc lắp đặt một **bảng LED dùng
   pin mặt trời** tuân thủ QCVN nếu không có
   ([ADR-0004](adr/ADR-0004-warning-actuator-integration.vi.md)).
4. **Triển khai và vận hành** các thiết bị trong ≥ 6 tháng với dữ liệu đo từ xa (telemetry) gửi về
   TMC của đơn vị vận hành.
5. **Đo các KPI về sự chấp nhận trên hiện trường** ([tài liệu 01 §5](01-requirements.vi.md), cột hiện
   trường) cùng với một chỉ số an toàn trước/sau được thống nhất với đơn vị vận hành.
6. Thực hiện **xử lý an toàn chức năng** — phân tích mối nguy, hành vi trạng thái an toàn đã được kiểm
   chứng, độ phủ tiêm lỗi (fault-injection).
7. Đáp ứng các nghĩa vụ về **quyền riêng tư dữ liệu và an ninh** trên đường công cộng
   ([tài liệu 04 §4](04-risk-and-safety.vi.md)).
8. Tạo ra một **hồ sơ an toàn + hướng dẫn triển khai**, đóng góp vào **tiêu chuẩn hóa**, và theo đuổi
   **sở hữu trí tuệ / thương mại hóa** (giải pháp hữu ích / sáng chế) nếu tính mới có thể bảo vệ được.

## 4. Tính mới & đóng góp khoa học

Ngoài tính mới của bản mẫu, thử nghiệm này đóng góp **cảnh báo sự cố làn dừng chủ động được kiểm
chứng trên hiện trường** đầu tiên trong bối cảnh Việt Nam: một **phương pháp luận chọn vị trí dựa
trên DSD**, một **thiết kế tham chiếu đa cảm biến an toàn khi sự cố (fail-safe)**, và — quan trọng
nhất — **dữ liệu hiệu quả trên đường và báo động giả đo được trên thực tế**, những thứ hiện chưa tồn
tại tại địa phương. Đầu ra là một thiết kế tham chiếu + hồ sơ an toàn mà các cơ quan quản lý đường bộ
và đơn vị vận hành có thể áp dụng, và có thể làm tiền đề cho một **hướng dẫn hoặc tiêu chuẩn kỹ thuật
cấp quốc gia**.

## 5. Phạm vi & các điểm thử nghiệm

- **2–3 điểm có nguy cơ cao mang tính đại diện** được lựa chọn cùng đơn vị vận hành, ví dụ một **đoạn
  tiếp cận hầm/cầu**, một **đoạn cong/đỉnh dốc hạn chế tầm nhìn**, và một **điểm nóng đã biết về sự cố
  làn dừng** ([tài liệu 02 §6](02-system-architecture.vi.md), mô hình phạm vi giám sát).
- Theo từng điểm: chọn vị trí dựa trên DSD, bố trí cảm biến, bảng cảnh báo (tái sử dụng VMS hoặc LED
  dùng pin mặt trời), giải pháp nguồn điện và kết nối.
- **Rõ ràng không phải** là phủ giám sát liên tục toàn tuyến — thử nghiệm kiểm chứng các **vùng giám
  sát rời rạc**, vốn là mô hình khả triển khai.

## 6. Cách tiếp cận kỹ thuật — từ bản mẫu đến hiện trường

**Kiến trúc logic không thay đổi** ([tài liệu 02](02-system-architecture.vi.md)); thử nghiệm sản
phẩm hóa từng lớp và bổ sung mức độ chặt chẽ mà một triển khai trên đường công cộng đòi hỏi.

| Lớp | Bản mẫu (cấp trường) | Thử nghiệm hiện trường (cấp sở) |
|-------|------------------------|----------------------|
| Cảm biến | camera trên bàn (+ radar tùy chọn) | **camera + radar** gia cố bền bỉ, mọi thời tiết, hiệu chuẩn theo từng điểm |
| Tính toán | bo mạch phát triển trên bàn | **thiết bị biên** hiện trường (IP65, có quản lý nhiệt, ngân sách nguồn pin mặt trời) |
| Bảng cảnh báo | tấm LED tạm thay thế | **tích hợp VMS thực** hoặc **LED dùng pin mặt trời** theo QCVN-41 ở khoảng cách ≥ DSD về phía trước (theo hướng xe tới) |
| Nguồn điện / kết nối | điện lưới phòng thí nghiệm | **pin mặt trời + ắc quy ≥ 72 h**, LTE lưu và chuyển về TMC |
| An toàn | *thiết kế* an toàn khi sự cố (fail-safe) | **phân tích mối nguy + trạng thái an toàn đã kiểm chứng + giám sát/cảnh báo qua TMC** |
| Đánh giá | kịch bản theo từng giai đoạn + lỗi tiêm vào | **giao thông thực** + lỗi tiêm vào + phân tích **trước/sau** |
| Tuân thủ | chỉ nguyên lý | tuân thủ **QCVN 41**, quản trị **quyền riêng tư dữ liệu**, gia cố an ninh |

Các [ADR](adr/README.vi.md) là cơ sở thiết kế và được kế thừa nguyên vẹn; thử nghiệm là nơi các điều
khoản "xem xét lại khi…" của chúng có được dữ liệu thực.

## 7. Kế hoạch công việc (mang tính chỉ dẫn, ~18–24 tháng)

| Giai đoạn | Thời lượng | Nội dung | Tiêu chí hoàn thành |
|------:|----------|---------|---------------|
| **P1** | 3–4 tháng | MOU với đơn vị vận hành; lựa chọn điểm; giấy phép; **khảo sát DSD** theo từng điểm; chốt thông số kỹ thuật | Đã đảm bảo điểm + giấy phép; đã phê duyệt việc chọn vị trí |
| **P2** | 4–5 tháng | **Sản phẩm hóa** thiết bị hiện trường; **phân tích mối nguy**; thiết kế tích hợp bảng cảnh báo/VMS; mua sắm | Thiết bị đã chế tạo & nghiệm thu trên bàn; phân tích an toàn hoàn tất |
| **P3** | 2–3 tháng | **Lắp đặt & chạy thử nghiệm thu** tại các điểm thử nghiệm; tích hợp dữ liệu đo từ xa với TMC | Thiết bị đã vận hành; tự kiểm tra + tiêm lỗi đạt yêu cầu tại hiện trường |
| **P4** | 6 tháng | **Vận hành hiện trường & thu thập dữ liệu** qua các mùa/thời tiết | Vận hành liên tục; tập dữ liệu tích lũy dần |
| **P5** | 2–3 tháng | **Đánh giá**: KPI, phân tích trước/sau, tiêm lỗi; **hồ sơ an toàn** | KPI đo được so với mục tiêu; hồ sơ an toàn hoàn tất |
| **P6** | 2 tháng | Sản phẩm bàn giao, **hướng dẫn triển khai**, đầu vào cho tiêu chuẩn hóa, sở hữu trí tuệ / thương mại hóa | Báo cáo cuối cùng & thiết kế tham chiếu đã nộp |

## 8. Sản phẩm bàn giao

- **2–3 thiết bị hiện trường đã nghiệm thu vận hành** tại các điểm thử nghiệm.
- **Báo cáo đánh giá hiện trường** với các KPI đo được và một **phân tích an toàn trước/sau**.
- **Hồ sơ an toàn đã được kiểm chứng** (phân tích mối nguy, kiểm chứng trạng thái an toàn, độ phủ
  tiêm lỗi).
- **Phương pháp luận chọn vị trí theo từng điểm dựa trên DSD** (có thể tái sử dụng).
- **Thiết kế tham chiếu khả triển khai** — danh mục vật tư (bill of materials), bản vẽ, thông số kỹ
  thuật tích hợp.
- **Hướng dẫn triển khai / đầu vào cho tiêu chuẩn hóa** (hướng tới một khuyến nghị phù hợp với
  QCVN/TCVN).
- **Hồ sơ tuân thủ quyền riêng tư dữ liệu & an ninh**.
- **Kế hoạch thương mại hóa** và, nếu có cơ sở, một **đơn đăng ký sở hữu trí tuệ** (giải pháp hữu ích
  / sáng chế).
- **Phổ biến khoa học** (báo cáo hội nghị/tạp chí).

## 9. Kinh phí (mang tính chỉ dẫn, theo bậc độ lớn)

Một thử nghiệm hiện trường **lớn hơn rất nhiều** so với khoản tài trợ hạt giống 20.000.000 VND cho
bản mẫu. Khung kinh phí mang tính chỉ dẫn (sẽ được chốt lại cùng với đồng tài trợ của đơn vị vận hành
và báo giá mua sắm):

| Hạng mục | Tỉ trọng chỉ dẫn | Ghi chú |
|----------|------------------|-------|
| Phần cứng hiện trường (2–3 điểm: đa cảm biến, biên, pin mặt trời+ắc quy, tích hợp bảng cảnh báo/VMS, IP65) | ~35–45% | Hạng mục lớn nhất; giảm đi nếu đơn vị vận hành cung cấp VMS/nguồn điện dưới dạng hiện vật |
| Lắp đặt, xây dựng cơ bản, giấy phép | ~10–15% | Theo yêu cầu của đơn vị vận hành |
| Nhân sự (nhóm nghiên cứu, kỹ thuật, vận hành hiện trường) | ~20–25% | Trong suốt 18–24 tháng |
| Sản phẩm hóa phần mềm + phân tích an toàn/mối nguy | ~10% | Công việc an toàn chức năng |
| Thu thập dữ liệu, đánh giá, đi lại | ~5–10% | Phủ theo mùa |
| Phổ biến, sở hữu trí tuệ, dự phòng | ~5–10% | — |

> Tổng chỉ dẫn theo bậc độ lớn nằm trong khoảng **hàng trăm triệu đến ~1,5 tỉ VND**, phụ thuộc nhiều
> vào số lượng điểm và mức độ đóng góp bằng hiện vật của đơn vị vận hành (điểm lắp đặt, VMS, nguồn
> điện, quyền truy cập TMC). **Đồng tài trợ** được tìm kiếm một cách rõ ràng
> ([tài liệu 03 §1](03-roadmap-and-phasing.vi.md), nguồn tài trợ bên ngoài): hiện vật của đơn vị vận
> hành, các đối tác trong ngành ITS, và các chương trình cấp tỉnh khác.

## 10. Hợp tác

| Đối tác | Vai trò (thiết yếu trừ khi có ghi chú khác) |
|---------|-------------------------------|
| **Đơn vị vận hành đường cao tốc** | Điểm lắp đặt, VMS/TMC hiện có, giấy phép, dữ liệu giao thông & sự cố, đồng tài trợ bằng hiện vật — **thiết yếu** |
| Nhà cung cấp trong ngành ITS | Camera/AI, radar, VMS/LED, IoT, phần cứng biên |
| Cơ quan quản lý / điều tiết đường bộ | Tuân thủ QCVN 41, phê duyệt, lộ trình tiêu chuẩn hóa |
| Trường đại học (chủ nhiệm + nhóm + sinh viên) | Thiết kế, tích hợp, đánh giá, phổ biến |

## 11. KPI nghiệm thu (hiện trường)

Từ [tài liệu 01 §5](01-requirements.vi.md) (cột hiện trường), cùng với các chỉ số an toàn riêng cho
thử nghiệm:

| KPI | Mục tiêu |
|-----|--------|
| Tỉ lệ phát hiện (recall) — xe (ban ngày · ban đêm/bất lợi) | ≥ 98% · ≥ 95% |
| Tỉ lệ phát hiện (recall) — người đi bộ (ban ngày · ban đêm) | ≥ 90% · nỗ lực tối đa |
| Tỉ lệ kích hoạt sai | tạm thời ≤ 1 lần mỗi điểm mỗi tuần, **hiệu chỉnh theo đơn vị vận hành** theo ngưỡng tin cậy ([tài liệu 04 §5](04-risk-and-safety.vi.md#5-open-safety-questions-for-the-team)) |
| Độ trễ phát hiện / xóa cảnh báo | ≤ dwell + 2 s · ≤ hold + 2 s (khi thoát ra đã xác nhận) |
| Cự ly cảnh báo trước hiệu quả | ≥ DSD tại hiện trường (đã khảo sát) |
| Độ sẵn sàng **chức năng** | ≥ 99% |
| Độ phủ phát hiện lỗi | ≥ 95% danh mục FMEA |
| **Chỉ số an toàn trước/sau** | giảm đo được về xung đột / suýt va chạm liên quan đến sự cố làn dừng tại các điểm được lắp đặt thiết bị đo đạc (với dữ liệu của đơn vị vận hành) |

## 12. Quản lý rủi ro

Kế thừa từ [tài liệu 04](04-risk-and-safety.vi.md), với trọng tâm riêng cho hiện trường:

| Rủi ro | Biện pháp giảm thiểu |
|------|-----------|
| Hợp tác / giấy phép của đơn vị vận hành chậm hoặc thất bại | **MOU** sớm; cùng thiết kế; bắt đầu P1 với cổng kiểm soát này |
| Thiếu hụt nguồn điện / kết nối tại điểm lắp đặt | **Pin mặt trời + ắc quy + LTE** lưu và chuyển ([ADR-0006](adr/ADR-0006-connectivity-and-power.vi.md)) |
| Hiệu năng trong điều kiện bất lợi | **Camera + radar** + các bài kiểm tra nghiệm thu theo từng điều kiện cụ thể |
| Báo động giả lặp lại làm xói mòn niềm tin | Dwell/trễ (hysteresis)/watchdog; trần báo động giả đã thống nhất với đơn vị vận hành; rà soát hiệu chỉnh niềm tin |
| Phụ thuộc quá mức / sự chấp nhận của công chúng | Định khung như một **công cụ hỗ trợ, không phải sự bảo đảm**; truyền thông công chúng; hành vi nhất quán |
| Mơ hồ về trách nhiệm pháp lý | Định khung mang tính **khuyến cáo**; nhật ký sự kiện (nhật ký kiểm toán); vai trò rõ ràng trong thỏa thuận với đơn vị vận hành |
| Kinh phí / mua sắm | Chi tiêu theo giai đoạn; đồng tài trợ; giảm số lượng điểm nếu cần (nêu rõ sự đánh đổi, không cắt giảm âm thầm) |

## 13. Tác động kỳ vọng

- **An toàn:** cảnh báo sớm hơn và giảm xung đột đâm sau với xe dừng trên làn dừng tại các điểm có
  nguy cơ cao được lắp đặt thiết bị đo đạc; bảo vệ tốt hơn cho người trong xe gặp nạn và đội cứu hộ.
- **Khoa học:** **phương pháp được kiểm chứng trên hiện trường và tập dữ liệu hiệu quả** đầu tiên tại
  địa phương; cơ sở cho một hướng dẫn/tiêu chuẩn.
- **Kinh tế:** một sản phẩm khả triển khai và một lộ trình thương mại hóa cùng ngành ITS Việt Nam.
- **Chính sách:** đầu vào cụ thể cho các chương trình hạ tầng giao thông thông minh và an toàn giao
  thông.

## 14. Lộ trình sau thử nghiệm

Một thử nghiệm thành công hỗ trợ cho một **luận chứng kinh doanh triển khai quy mô toàn tuyến**, một
**hướng dẫn hoặc tiêu chuẩn kỹ thuật cấp quốc gia**, và **sản phẩm hóa/thương mại hóa** được tích hợp
vào ITS của các đơn vị vận hành — đúng quỹ đạo mà đề cương ban đầu đã dự kiến khi định khung giai đoạn
cấp sở và xa hơn.
