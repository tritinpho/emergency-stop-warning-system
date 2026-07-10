# ADR-0005: Tư thế an toàn khi sự cố (fail-safe), trạng thái an toàn, và leo thang theo tình trạng

> 🇬🇧 Bản gốc tiếng Anh: [ADR-0005-fail-safe-and-system-safety.md](ADR-0005-fail-safe-and-system-safety.md)

**Trạng thái:** Đã chấp nhận (phía phần mềm) — 2026-06-27
**Ngày:** 2026-06-26
**Người quyết định:** Chủ nhiệm đề tài (PI), trưởng nhóm kỹ thuật, cố vấn an toàn giao thông đường bộ

> ## ⚠ LƯU Ý GIAI ĐOẠN — bản dựng này CHỈ DÙNG CAMERA
>
> [ADR-0001](ADR-0001-sensing-modality.vi.md) (hợp nhất camera + radar) đã bị **Bác bỏ ngày 2026-07-10**. Nguyên mẫu trên bàn
> (cấp trường) **chỉ dùng camera**. Mọi hành vi phụ thuộc radar được mô tả bên dưới — radar chứng thực,
> khoảng giữ-khi-che-khuất (`WARN_HOLD` / `CAMERA_OCCLUDED_DEGRADED`), `T_degraded_max`, và các chế độ
> cảm biến `FULL` / `RADAR-ONLY` — đều **đang tạm ngưng: mã nguồn vẫn giữ, nhưng không bao giờ chạy**,
> vì `corr` không bao giờ đúng khi không có kênh radar.
>
> Hệ quả được chấp nhận: **R5** (mù ban đêm/mưa/sương mù) **không còn biện pháp giảm thiểu** và khả năng
> phát hiện ban đêm/bất lợi **không được tuyên bố**; **R20** — xe bị che khuất bị xóa sau `T_hold`
> (~10 giây), biển báo tắt trong khi mối nguy vẫn còn; **R21** — thiết bị nằm vĩnh viễn ở `CAMERA_ONLY`,
> do đó vĩnh viễn `DEGRADED`. Xem [tài liệu 04](../04-risk-and-safety.vi.md).
>
> Nội dung radar bên dưới là **thiết kế mục tiêu cấp sở**, không phải bản dựng của giai đoạn này.

## Bối cảnh

Đây là quyết định phi chức năng quan trọng nhất. Hệ thống tác động đến dòng xe di chuyển nhanh ở gần một chướng ngại vật đứng yên, nên **hành vi của nó khi có sự cố** quan trọng ngang với hành vi khi nó hoạt động bình thường. Hai kiểu lỗi kéo hệ thống về hai hướng ngược nhau ([tài liệu 01 §1](../01-requirements.vi.md#1-tái-định-khung-an-toàn-đọc-phần-này-trước)):

- một **trường hợp bỏ sót thầm lặng (silent miss)** (cảm biến bị mù, tiến trình bị treo) — cảnh báo đáng lẽ phải xuất hiện thì lại không bao giờ xuất hiện, nhưng thiết bị trông vẫn "ổn";
- một **trạng thái BẬT cũ/sai (stale / false ON)** — một cảnh báo được hiển thị mà không có nguy hiểm, làm cho người lái quen với việc phớt lờ nó ("báo động giả lặp lại" — hiệu ứng cừu giả).

Một hệ thống ngây thơ thì không có khả năng tự nhận biết lẫn một hành vi được định nghĩa cho cả hai trường hợp. Chúng ta phải quyết định tư thế an toàn khi sự cố (fail-safe) một cách tường minh.

## Quyết định

Áp dụng **an toàn khi sự cố (fail-safe) + báo lỗi rõ ràng (fail-loud)**:

1. Một **bộ giám sát tình trạng độc lập với đường nhận diện (perception path)** liên tục tự kiểm tra các cảm biến, khối tính toán, tiến trình ra quyết định, đường liên kết tới bảng báo, và phần đọc lại trạng thái của chính bảng báo; nó phát ra một **nhịp tín hiệu (heartbeat)** tới TMC.
2. Khi xảy ra bất kỳ **lỗi trọng yếu (critical fault)** nào, hệ thống chuyển vào một **TRẠNG THÁI AN TOÀN** đã được định nghĩa: bảng báo được **lái** về một **điều kiện đã biết, không gây nhầm lẫn** (mặc định: **CLEAR/để trống** — không bao giờ là một thông báo *cụ thể* kiểu "có xe phía trước" mà nó không thể chứng thực), và lỗi được **leo thang đến đơn vị vận hành ngay lập tức**.
3. **Kích hoạt trạng thái an toàn một cách độc lập (cơ chế an toàn tự kích hoạt khi mất tín hiệu — dead-man's switch).** Cơ cấu chấp hành **mặc định về trạng thái an toàn (để trống) khi mất một nhịp tín hiệu "khẳng định" (assertion) còn mới** từ máy trạng thái, và bộ giám sát tình trạng nắm giữ một **đường trực tiếp để buộc cơ cấu chấp hành về trạng thái an toàn mà không đi qua máy trạng thái**. Do đó, một máy trạng thái bị treo hoặc bị kẹt **không thể** để lại một cảnh báo đang được khẳng định — bảng báo tự nó rơi về trạng thái để trống. Điều này dung hòa bất biến của [tài liệu 02](../02-system-architecture.vi.md) ("chỉ máy trạng thái mới được *khẳng định* một cảnh báo") với an toàn khi sự cố: máy trạng thái là thành phần duy nhất được phép *khẳng định*, nhưng **không bắt buộc phải có nó để xóa cảnh báo**. Nếu không có cơ chế này, thành phần phát hiện máy trạng thái bị kẹt sẽ phải ra lệnh chuyển sang trạng thái an toàn *thông qua* chính máy trạng thái đang bị kẹt — một bộ giám sát phụ thuộc vào chính đối tượng nó canh chừng. **Việc kích hoạt trạng thái an toàn phải nằm về mặt vật lý trong _bộ điều khiển biển báo_, ở phía hạ lưu của đường liên kết cục bộ — chứ không phải trong hộp biên (edge box)** — nếu không, một hộp biên đã chết, một hệ điều hành bị kẹt, hoặc một đường liên kết bị cắt/nghẽn sẽ làm mắc kẹt một biển báo đã chốt trạng thái (latched) ở trạng thái cuối cùng (có thể đang BẬT) của nó. Vị trí đặt, giao thức khẳng-định-được-làm-mới (refreshed-assertion), sự đánh đổi về định thời `T_signhold` của nó, và lưu ý về VMS chốt trạng thái (latching) được đặc tả trong [ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.vi.md), tài liệu này cũng khắc phục ngữ nghĩa **chế độ suy giảm** bất đối xứng (một thiết bị có camera đã chết thì *mù với sự cố mới (không thể khởi tạo cảnh báo mới)*, chứ không phải "suy giảm nhưng vẫn chạy").
4. Một **watchdog (bộ canh chừng)** giới hạn thời gian cho mọi lần kích hoạt: không cảnh báo nào được phép giữ ở trạng thái BẬT mà không có xác nhận mới hoặc một lần làm mới của watchdog (`T_watchdog`, NFR-04), qua đó loại bỏ tình trạng BẬT-cũ kéo dài vô thời hạn. Sự tương tác của nó với cơ chế giữ khi che khuất (occlusion hold) được đặc tả trong [ADR-0008](ADR-0008-detection-persistence-and-multitrack.vi.md) — watchdog xóa cảnh báo **và phát sinh một lỗi**, nên một lần xóa trong điều kiện bất định không bao giờ là im lặng. Trạng thái duy nhất mà watchdog *cố ý* không giới hạn (camera bị che, radar vẫn còn đối chứng) được giới hạn thay vào đó bởi **`T_degraded_max`** ([ADR-0009 §C](ADR-0009-failsafe-placement-and-degraded-modes.vi.md)), nên không trạng thái nào giữ bảng BẬT vô hạn.
5. Thiết bị **không bao giờ báo cáo là khỏe mạnh khi nó đang suy giảm**; "bị mù" là một điều kiện cảnh báo, không phải sự im lặng.
6. Việc leo thang báo-lỗi-rõ-ràng giả định một **đường phản hồi của người trực có giới hạn** — gộp trùng/ưu tiên cảnh báo, mức nghiêm trọng, thời gian phản hồi mục tiêu, leo thang lại — được đặc tả trong [ADR-0011](ADR-0011-operator-concept-and-alarm-management.vi.md); và bề mặt tấn công của điều khiển / telemetry / ghi đè được liệt kê trong mô hình mối đe dọa ([ADR-0012](ADR-0012-security-and-threat-model.vi.md)). Cả hai đều bị bỏ ngầm trong bản phác đầu: "báo động lớn" chỉ là biện pháp kiểm soát nếu có người lắng nghe, và "không thể bị giả mạo" cần một bề mặt đã phát biểu.

> Tại sao để trống khi có sự cố thay vì một cảnh báo chung chung kéo dài? Một bảng báo *luôn luôn* cảnh báo sẽ trở thành thứ "giấy dán tường" và làm xói mòn niềm tin vào cảnh báo thực, cụ thể (lỗi báo động giả lặp lại). Hành vi suy giảm trung thực là: ngừng khẳng định một mối nguy mà bạn không còn phát hiện được nữa, và **làm cho sự cố trở nên rõ ràng (loud) với những người có thể khắc phục hoặc bù đắp cho nó** (TMC, đội tuần tra) — chứ không phải với người lái thông qua một bảng báo đứng yên mơ hồ. Những vị trí thực sự cần một cách xử lý kiểu "khu vực phát hiện sự cố" đứng yên có thể cấu hình theo từng vị trí, nhưng đó không phải là mặc định.

## Các phương án đã xét

### Phương án A: Không có an toàn khi sự cố tường minh (nỗ lực tốt nhất - best-effort)
**Ưu điểm:** ít công sức nhất.
**Nhược điểm:** bỏ sót thầm lặng; có thể kẹt ở trạng thái BẬT; không có khả năng quan sát cho đơn vị vận hành. Không thể chấp nhận đối với một chức năng an toàn.

### Phương án B: An toàn khi sự cố về trạng thái **để trống** + leo thang theo tình trạng + watchdog *(được chọn)*
**Ưu điểm:** không có đầu ra gây nhầm lẫn; không có BẬT-cũ; sự cố là quan sát được và có thể hành động; bảo vệ niềm tin.
**Nhược điểm:** đòi hỏi một bộ giám sát tình trạng độc lập, một watchdog, phần đọc lại trạng thái bảng báo, và cảnh báo tới TMC — đây là công việc kỹ thuật thực sự, nhưng là cốt lõi của một hệ thống đáng tin cậy.

### Phương án C: An toàn khi sự cố về một bảng báo **cảnh báo chung chung kéo dài**
**Ưu điểm:** "luôn có thứ gì đó đang cảnh báo" tạo cảm giác thận trọng.
**Nhược điểm:** kiểu báo động giả lặp lại điển hình — các cảnh báo mơ hồ đứng yên bị phớt lờ, làm mất giá trị của cảnh báo cụ thể; bản thân nó có thể gây phanh không cần thiết. Bị loại làm mặc định; chỉ cho phép như một tùy chọn theo từng vị trí.

## Phân tích đánh đổi

Phương án A tối ưu hóa công sức nhưng đánh đổi bằng chính lý do tồn tại của hệ thống. Quyết định thực sự là giữa B và C — *một bảng báo bị lỗi sẽ hiển thị gì?* C đánh đổi một cảm giác an toàn để lấy sự xói mòn niềm tin mà rốt cuộc làm cho cảnh báo **đang hoạt động** kém hiệu quả hơn. B giữ cho kênh cảnh báo **đáng tin cậy**: bảng báo chỉ khẳng định một mối nguy mà nó có thể chứng thực, và các sự cố được định tuyến đến những người có thể hành động. Niềm tin chính là sản phẩm (nguyên tắc định hướng 3), nên B thắng.

## Hệ quả

- **Dễ hơn:** suy giảm trung thực; không kẹt BẬT; đơn vị vận hành thấy được sự cố và có thể điều động đội tuần tra; kênh cảnh báo vẫn đáng tin cậy.
- **Khó hơn:** phải xây dựng bộ giám sát tình trạng độc lập, watchdog, phần đọc lại trạng thái bảng báo, hệ phân loại lỗi (fault taxonomy), và cảnh báo tới TMC; phải định nghĩa và kiểm thử quá trình chuyển sang TRẠNG THÁI AN TOÀN (tiêm lỗi là một phần của nghiệm thu, [tài liệu 01 §5](../01-requirements.vi.md#5-chỉ-số-đánh-giá--tiêu-chí-nghiệm-thu)).
- **Xem xét lại khi:** một hệ thống hiện trường được sản phẩm hóa theo đuổi cách xử lý an toàn chức năng (functional-safety) chính thức (ví dụ: một phân tích mối nguy / mục tiêu SIL) — ADR này là nền tảng mà nỗ lực đó sẽ xây dựng trên đó.

## Hạng mục hành động

1. [ ] Liệt kê đầy đủ **hệ phân loại lỗi (fault taxonomy)** (cảm biến chết, đóng băng khung hình, sập mô hình, mất liên kết, bảng báo không phản hồi, nguồn yếu, lệch đồng hồ) và phản ứng cho từng trường hợp.
2. [ ] Hiện thực watchdog và quá trình chuyển sang TRẠNG THÁI AN TOÀN trong máy trạng thái.
3. [ ] Hiện thực **cơ chế an toàn tự kích hoạt khi mất tín hiệu (dead-man's switch)** trong **bộ điều khiển biển báo** (ở phía hạ lưu của đường liên kết) theo [ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.vi.md), cộng với một đường buộc-về-an-toàn độc lập từ bộ giám sát tình trạng → cơ cấu chấp hành (kiểm chứng bằng cách giết tiến trình máy trạng thái (SM), **giết hộp biên (edge box), và cắt đường liên kết** trong các bài kiểm thử tiêm lỗi và xác nhận bảng báo chuyển về để trống trong vòng `T_signhold` ở mọi trường hợp).
4. [ ] Hiện thực phần **đọc lại trạng thái (status read-back)** của bảng báo để "đã ra lệnh BẬT" được kiểm chứng đối chiếu với "thực sự đang BẬT".
5. [ ] Định nghĩa các mức nghiêm trọng của cảnh báo TMC và luồng xác nhận (acknowledgement).
6. [ ] Bổ sung **các bài kiểm thử tiêm lỗi (fault-injection)** vào bộ nghiệm thu (mục tiêu phạm vi phát hiện lỗi ≥95%).
