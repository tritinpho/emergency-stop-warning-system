# ADR-0011: Quy trình vận hành & quản lý cảnh báo của người trực

> 🇬🇧 Bản gốc tiếng Anh: [ADR-0011-operator-concept-and-alarm-management.md](ADR-0011-operator-concept-and-alarm-management.md)

**Trạng thái:** Đề xuất
**Ngày:** 2026-06-27
**Người quyết định:** Chủ nhiệm (ThS. Phó Trí Tín), trưởng nhóm kỹ thuật, cố vấn an toàn giao thông, đầu mối liên hệ đơn vị vận hành cao tốc

## Bối cảnh

Toàn bộ thiết kế an toàn theo nguyên tắc **an toàn khi sự cố + báo động lớn khi sự cố**
([ADR-0005](ADR-0005-fail-safe-and-system-safety.vi.md)): khi có bất kỳ lỗi nào, biển báo về **trống** và
đơn vị **leo thang đến người trực**. Điều đó khiến **người trực trở thành điểm cuối của gần như mọi đường
dẫn phần dư rủi ro** trong hệ thống:

- một **lần bỏ sót âm thầm** / một đơn vị bị mù không trống-và-báo → người trực được kỳ vọng điều xe tuần
  tra / CCTV;
- một đơn vị **BLIND-TO-NEW** (camera chết) hoặc **CAMERA-OCCLUDED-DEGRADED** leo thang ở mức trọng yếu →
  người trực được kỳ vọng điều tra và, qua CCTV, định đoạt nó
  ([ADR-0009 §B/§C](ADR-0009-failsafe-placement-and-degraded-modes.vi.md));
- lần buộc-xóa **`T_degraded_max`** bàn giao tường minh một quyết định che-khuất-kéo-dài cho người trực;
- **ức chế khi ùn tắc** mở ra một khoảng trống phạm vi có chủ đích trong một điều kiện nguy-hiểm-có-tên,
  "được mang sang quy trình vận hành" ([tài liệu 04 §0](../04-risk-and-safety.vi.md#0-giới-hạn-bảo-vệ-mối-nguy-còn-lại));
- một lần **ghi đè của người trực** phải được theo dõi để một lần tắt tiếng không âm thầm vượt quá cửa sổ
  của nó ([ADR-0010](ADR-0010-operator-override-and-manual-control.vi.md));
- tương tác **an-toàn-trống × phụ-thuộc-quá-mức** được kiểm soát bằng cách báo *lớn tiếng cho người trực*
  ([tài liệu 04 §0](../04-risk-and-safety.vi.md#0-giới-hạn-bảo-vệ-mối-nguy-còn-lại)).

Vậy mà bản phác đầu chỉ nêu "leo thang đến TMC" như một động từ và không bao giờ đặc tả đường dẫn đó.
**"Báo động lớn" chỉ là một biện pháp kiểm soát nếu có người lắng nghe và hành động trong một thời gian có
giới hạn** — nếu không, mọi lần leo thang ở trên đều quy về số không. Một bảng điều khiển bị ngập (mệt mỏi
vì cảnh báo), một ca đêm không người, hoặc một cảnh báo trọng yếu không được xác nhận sẽ âm thầm vô hiệu
hóa biện pháp bù trừ mà hồ sơ an toàn dựa vào. Đây là **nửa con người** còn thiếu của báo-động-lớn, và nó
quyết định liệu các phần dư của thiết kế tự động có thực sự được bao phủ hay không.

Các lực: sự phụ thuộc của hồ sơ an toàn vào sự bù trừ của người trực (chủ đạo), mệt-mỏi-vì-cảnh-báo / quá
tải bảng điều khiển, thực tế nhân sự (đơn vị vận hành sở hữu TMC, không phải dự án), trách nhiệm pháp lý
(R10), và nhu cầu giữ các con số tinh-chỉnh-được-ở-hiện-trường mà không để chúng vô định ngay bây giờ.

## Quyết định

Đặc tả một **quy trình vận hành (ConOps) của người trực + kỷ luật quản lý cảnh báo** như một phần hạng
nhất của thiết kế an toàn (yêu cầu **NFR-15**), không phải một thứ nghĩ sau để mặc cho người tích hợp TMC.

1. **Mỗi lần leo thang có một phản hồi được đặt tên của người trực.** Với mỗi điều kiện leo thang —
   `BLIND-TO-NEW`, `CAMERA-OCCLUDED-DEGRADED`, buộc-xóa `T_degraded_max`, xóa độ-tin-cậy-thấp,
   `OVERRIDDEN`-quá-hạn, kẹt-bảng / lệch-trạng-thái, nguồn-thấp, mất-liên-kết — ConOps phát biểu **người
   trực được kỳ vọng làm gì** (xác nhận, kiểm chứng qua CCTV, điều xe tuần tra, ép-tắt / ép-bật trong
   chính sách, lên lịch bảo trì) và **thời gian mục tiêu** để làm.
2. **Mức nghiêm trọng + thời gian phản hồi mục tiêu + leo thang lại.** Mỗi điều kiện mang một **mức nghiêm
   trọng** và một **thời gian xác nhận/phản hồi mục tiêu**; một lần leo thang **không được xác nhận** sẽ
   **leo thang lại** (lớn hơn, hoặc lên một tầng cao hơn / cấp trên), nên một cảnh báo bị bỏ lỡ tự nó là
   một điều kiện được báo. Không lần leo thang liên quan an toàn nào có thể nằm im không được thấy.
3. **Tải cảnh báo được giới hạn bằng thiết kế.** Cảnh báo được **gộp trùng** (một sự cố ≠ một cơn bão
   dòng), **xếp ưu tiên** (leo thang an toàn xếp trên telemetry thông tin), và **giới hạn tốc độ / nhóm
   lại**, nên một lỗi đơn lẻ hay một vị trí nhiễu không thể chôn vùi một cảnh báo trọng yếu. Các điều kiện
   dao động được khử dội trước khi báo.
4. **Máy không bao giờ chờ người trực mãi.** Ở đâu có một giới hạn tự động thì nó kích hoạt bất kể hành
   động của người trực — sắc nét nhất, **`T_degraded_max`** định đoạt một che-khuất-camera kéo dài
   ([ADR-0009 §C](ADR-0009-failsafe-placement-and-degraded-modes.vi.md)) thay vì giữ bảng BẬT cho đến khi
   một con người tình cờ nhìn vào. ConOps **bù trừ** cho các phần dư; nó **không** phải một mắt xích trong
   vòng lặp an toàn thời gian thực ([ADR-0002](ADR-0002-edge-vs-cloud-processing.vi.md) giữ vòng lặp đó tại
   biên).
5. **Nhân sự & phạm vi trực là một cam kết tường minh của đơn vị vận hành.** Vì dự án không sở hữu TMC,
   **nhân sự, giờ trực, và các tầng leo thang** của đường phản hồi được thống nhất trong **thỏa thuận vận
   hành** (anh em với điều khoản trách nhiệm/vai trò, R10). Thiết kế phát biểu *yêu cầu*; đơn vị vận hành
   cam kết *nguồn lực*. Một vị trí mà đơn vị vận hành không thể bố trí đường phản hồi là một **ràng buộc
   chọn vị trí**, được nêu rõ, không mặc nhiên bỏ qua.
6. **Con số tạm thời, tinh chỉnh ở hiện trường.** Thời gian phản hồi mục tiêu và trần tốc độ cảnh báo cụ
   thể được đặt tạm thời ngay bây giờ và **hiệu chỉnh ở thử nghiệm hiện trường**
   ([tài liệu 05](../05-field-pilot-proposal.vi.md)) với khối lượng cảnh báo thực và bảng điều khiển của
   đơn vị vận hành — cùng với hiệu chỉnh-niềm-tin về báo động giả (R2) và ngân sách MTBF/MTTR (NFR-03,
   [tài liệu 04 §5 Q6](../04-risk-and-safety.vi.md#5-các-câu-hỏi-an-toàn-còn-mở-cho-nhóm)).

## Các phương án đã xét

### Phương án A: Để đường người trực ngầm định ("leo thang đến TMC") *(khoảng trống của bản phác đầu)*
| Khía cạnh | Đánh giá |
|-----------|------------|
| Công sức bây giờ | **Không** |
| Tính toàn vẹn hồ sơ an toàn | **Vỡ** — mọi phần dư quy về một người phản hồi không được đặc tả, có thể vắng mặt |
| Mệt mỏi vì cảnh báo | Không quản lý — một vị trí nhiễu có thể chôn vùi cảnh báo duy nhất quan trọng |

**Ưu:** không có gì để viết bây giờ.
**Nhược:** biện pháp bù trừ mà tư thế an-toàn-khi-sự-cố dựa vào thì không được định nghĩa, nên các tuyên bố
phần dư rủi ro (bỏ-sót-âm-thầm, chế-độ-suy-giảm, khoảng trống ùn tắc, ghi đè) không có cơ sở. Không chấp
nhận được cho một hệ thống liên quan an toàn.

### Phương án B: ConOps + quản lý cảnh báo như một yêu cầu được đặc tả *(được chọn)*
| Khía cạnh | Đánh giá |
|-----------|------------|
| Công sức bây giờ | Trung bình (bảng ConOps, mức nghiêm trọng, quy tắc gộp trùng/ưu tiên; con số tạm thời) |
| Tính toàn vẹn hồ sơ an toàn | **Khép kín** — mỗi lần leo thang có một phản hồi được đặt tên, có giới hạn, leo thang lại |
| Mệt mỏi vì cảnh báo | **Có giới hạn** — gộp trùng + ưu tiên + giới hạn tốc độ bằng thiết kế |

**Ưu:** biến "báo động lớn" thành một biện pháp kiểm soát thực; giới hạn tải người trực trước khi nó thành
mệt mỏi; cho thỏa thuận vận hành một yêu cầu nguồn lực cụ thể; tinh chỉnh được ở hiện trường mà không vô
định.
**Nhược:** thêm thiết kế + một sự phụ thuộc vào đơn vị vận hành cần đàm phán; thêm một yêu cầu (NFR-15) và
một lớp bộ định thời (`T_override_max`, hết-hạn-xác-nhận) để tinh chỉnh và tiêm-lỗi.

### Phương án C: Tự động hóa hoàn toàn — loại con người khỏi vòng lặp
| Khía cạnh | Đánh giá |
|-----------|------------|
| Khả năng vận hành | **Kém** — không ai điều xe tuần tra, kiểm chứng một đơn vị suy giảm, hay ức chế một báo động giả đã biết |
| Tính khả thi | Ngoài phạm vi — xử lý/điều phối sự cố tự động là một mục tiêu-ngoài tường minh ([tài liệu 00 §2](../00-context-and-glossary.vi.md#2-mục-tiêu--ngoài-phạm-vi)) |

**Ưu:** không có phụ thuộc nhân sự.
**Nhược:** các phần dư mà an-toàn-trống tạo ra (một đơn vị mù trên một con đường sống) *đòi hỏi* một người
bù trừ ở mức trưởng thành này; tự động hóa điều phối là một hệ thống khác, lớn hơn. Bị từ chối.

## Phân tích đánh đổi

Lựa chọn thực là **A so với B — người trực là một hệ thống được đặc tả hay một động từ đầy hy vọng?**
Thiết kế tự động đã dồn công sức để loại bỏ các đầu ra âm thầm và kẹt cứng; tất cả những thứ đó, khi gặp
lỗi, quy về một con người phải nhận ra và hành động. Để con người đó vô định (A) lặng lẽ tái lập sự cố âm
thầm ở tầng *kỹ-thuật-xã-hội*: một lần leo thang trọng yếu không ai xác nhận, về bản chất, là một lần bỏ
sót âm thầm với vài bước phụ. B tốn một bảng ConOps và một điều khoản thỏa thuận vận hành, và đổi lại mỗi
"leo thang đến người trực" trong các ADR khác có được một phản hồi được định nghĩa, có giới hạn, leo thang
lại — và máy vẫn không bao giờ *chờ* con người, vì các giới hạn tự động (watchdog, `T_degraded_max`,
hết-hạn-ghi-đè) tự kích hoạt. Chi phí vừa phải và **kiểm thử được** (tiêm một lỗi trọng yếu; xác nhận cảnh
báo phát ra, gộp trùng, và leo thang lại khi không xác nhận).

## Hệ quả

- **Dễ hơn:** các tuyên bố phần dư rủi ro trong [tài liệu 04](../04-risk-and-safety.vi.md) thực sự có cơ
  sở; tải cảnh báo có giới hạn trước khi mệt mỏi; thỏa thuận vận hành có một yêu cầu nguồn lực cụ thể; một
  mục tiêu hiệu chỉnh hiện trường sạch sẽ.
- **Khó hơn:** một bảng ConOps và mô hình mức nghiêm trọng để soạn; gộp trùng/ưu tiên/giới hạn tốc độ cảnh
  báo để xây và tiêm-lỗi (NFR-15); một **sự phụ thuộc nhân sự thực** với đơn vị vận hành để đàm phán (R17),
  có thể thành một **ràng buộc chọn vị trí**; con số thời gian phản hồi là tạm thời cho đến thử nghiệm hiện
  trường.
- **Xem xét lại khi:** khối lượng cảnh báo hiện trường cho thấy các quy tắc gộp trùng/ưu tiên hay thời gian
  phản hồi cần tinh chỉnh lại, hoặc một hệ cảnh báo TMC sẵn có của đơn vị vận hành bắt buộc một tích hợp cụ
  thể (ánh xạ ConOps này lên nó thay vì nhân đôi).

## Hạng mục hành động

1. [ ] Soạn **bảng ConOps**: theo từng điều kiện leo thang (`BLIND-TO-NEW`, `CAMERA-OCCLUDED-DEGRADED`,
       xóa `T_degraded_max`, xóa độ-tin-cậy-thấp, `OVERRIDDEN`-quá-hạn, kẹt-bảng, nguồn-thấp, mất-liên-kết)
       → hành động kỳ vọng của người trực + mức nghiêm trọng + thời gian xác nhận/phản hồi mục tiêu.
2. [ ] Đặc tả **gộp trùng, ưu tiên, giới hạn tốc độ, và leo-thang-lại-khi-không-xác-nhận** cho cảnh báo;
       bổ sung tư thế OVERRIDDEN/suy-giảm vào việc hiển thị nhịp tín hiệu
       ([tài liệu 02 §7](../02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu)).
3. [ ] Bổ sung **không-xác-nhận-cảnh-báo / ngập-cảnh-báo** vào FMEA + bộ tiêm lỗi
       ([tài liệu 04 §2](../04-risk-and-safety.vi.md#2-fmea-lite-kiểu-lỗi--tác-động--phát-hiện--phản-ứng), R17)
       và xác nhận một lần leo thang trọng yếu sẽ leo thang lại nếu không được xác nhận.
4. [ ] Đưa **nhân sự, giờ trực, và tầng leo thang** của đường phản hồi vào **thỏa thuận vận hành** (cùng
       điều khoản vai trò/trách nhiệm R10); đánh dấu các vị trí không thể bố trí nó là một ràng buộc chọn
       vị trí.
5. [ ] Đặt con số **tạm thời** về thời gian phản hồi và tốc độ cảnh báo; lên lịch **hiệu chỉnh hiện
       trường** của chúng ([tài liệu 05](../05-field-pilot-proposal.vi.md)) cùng với hiệu chỉnh-niềm-tin R2
       và ngân sách MTBF/MTTR NFR-03.
