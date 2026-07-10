# ADR-0008: Tính bền vững của phát hiện — che khuất, rời đi, và chính sách đa vết (multi-track)

> 🇬🇧 Bản gốc tiếng Anh: [ADR-0008-detection-persistence-and-multitrack.md](ADR-0008-detection-persistence-and-multitrack.md)

**Trạng thái:** Đã chấp nhận (phía phần mềm) — 2026-06-27
**Ngày:** 2026-06-27
**Người quyết định:** Chủ nhiệm đề tài (PI) (ThS. Phó Trí Tín), trưởng nhóm kỹ thuật, kỹ sư thị giác máy tính (CV), cố vấn an toàn giao thông đường bộ

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

Máy trạng thái ra quyết định ([tài liệu 02 §4](../02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo)) phải giữ một cảnh báo ở trạng thái BẬT chừng nào một mối nguy thực vẫn còn hiện diện, và xóa nó kịp thời khi mối nguy thực sự rời đi — dưới ba thực tế hiện trường mà bản phác thảo đầu tiên của vòng lặp đã không phân tách:

1. **Che khuất so với rời đi.** Một xe tải trên làn thông (through-lane) có thể che một chiếc xe dừng ở lề trong nhiều giây. Thiết kế đầu tiên gộp chung "xe đã rời đi" và "phát hiện bị rớt" thành một điều kiện duy nhất (*vắng mặt đối tượng ≥ T_hold → xóa*). Với một khoảng giữ 10 giây, một lần che khuất kéo dài trong dòng xe đông đúc — một điều kiện rủi ro cao **đã được nêu tên** — sẽ xóa một cảnh báo trong khi mối nguy vẫn còn hiện diện về mặt vật lý: một trường hợp bỏ sót thầm lặng (silent miss) do chính logic an toàn tạo ra. Việc kéo dài khoảng giữ để bao trùm che khuất thì ngược lại có nguy cơ gây ra BẬT-cũ sau một lần rời đi thực sự. Hai trường hợp này cần **bằng chứng khác nhau, không phải một bộ định thời đơn dài hơn**.
2. **Nhiều xe dừng đồng thời.** Một làn khẩn cấp có thể chứa hai xe dừng trở lên, hoặc một hàng xe nhỏ. Một chu trình vào/ra của một-đối-tượng-duy-nhất là không rõ ràng về thời điểm cảnh báo có thể được xóa.
3. **Rời đi là quan sát được.** Một chiếc xe thực sự rời đi sẽ băng qua biên của vùng phát hiện (ROI) dưới dạng một vết *đang chuyển động* (tốc độ tăng vượt ngưỡng đứng yên, dấu vết — footprint — đi ra khỏi đa giác). Một chiếc xe chỉ đơn thuần bị che khuất thì **không tạo ra lần thoát ra nào** — vết của nó chỉ đơn giản là ngừng cập nhật tại chỗ. Thiết kế đầu tiên đã loại bỏ sự phân biệt này.

Các yếu tố tác động: tránh bỏ sót thầm lặng (yếu tố chi phối), tránh BẬT-cũ (báo động giả lặp lại), tần suất che khuất trong dòng xe dày đặc, kênh hiện diện radar độc lập ([ADR-0001](ADR-0001-sensing-modality.vi.md)), và sự đơn giản của khối tính toán biên (edge-compute).

## Quyết định

Máy trạng thái vận hành trên **tập hợp các vết (track) đã-xác-nhận-đứng-yên bên trong ROI**, và xử lý *mất phát hiện* và *rời đi đã quan sát được* như những sự kiện riêng biệt được đối chứng (corroborate) chéo giữa các cảm biến:

1. **Ngữ nghĩa tập hợp (set semantics).** Cảnh báo ở trạng thái BẬT khi và chỉ khi tập hợp các vết đã-xác-nhận-đứng-yên trong ROI là khác rỗng. Việc gia nhập vào tập hợp đòi hỏi thời gian lưu lại (dwell) theo từng vết (`T_dwell`). Cảnh báo chỉ được xóa khi tập hợp trở nên rỗng theo các quy tắc bên dưới — **không phải** khi bất kỳ một vết đơn lẻ nào biến mất.
2. **Thoát ra đã xác nhận (xóa nhanh).** Một vết được quan sát thấy đang rời đi — tốc độ vượt lên trên ngưỡng đứng yên **và** dấu vết của nó đi ra khỏi đa giác ROI băng qua biên phía hạ lưu (downstream) — sẽ bị loại khỏi tập hợp ngay lập tức (tùy thuộc vào một khoảng chống dội — debounce — ngắn). Một lần rời đi thực sự sẽ xóa cảnh báo nhanh chóng.
3. **Mất vết (giữ, đừng xóa).** Một vết đã-xác-nhận-đứng-yên mà các phát hiện của nó ngừng lại *mà không có một lần thoát ra được quan sát* sẽ được giữ lại như **được-cho-là-hiện-diện (bị che khuất)**:
   - chừng nào **kênh hiện diện radar vẫn còn chứng thực (substantiate) một tín hiệu phản hồi (return)** ở tầm/vị trí đó, vết được giữ lại và cảnh báo vẫn duy trì — một chiếc xe bị-che-khuất-nhưng-hiện-diện thì vẫn tiếp tục cảnh báo. `T_occlusion` (mặc định 60 giây) chỉ giới hạn phần đối chứng **không được làm mới**: một tín hiệu phản hồi đối chứng còn sống sẽ **làm mới** khoảng giữ, và nếu che khuất kéo dài quá `T_occlusion` *trong khi radar vẫn còn đối chứng*, thiết bị chuyển vào **CAMERA-OCCLUDED-DEGRADED** (cảnh báo vẫn ở trạng thái BẬT **+ báo động cho người vận hành**) thay vì xóa — một lần camera mất tín hiệu kéo dài không bao giờ bị âm thầm biến thành một lần xóa — bản thân nó được **giới hạn bởi `T_degraded_max`** để lần giữ suy giảm không thể kéo dài vô hạn dựa trên một tín hiệu radar không kiểm chứng được ([ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.vi.md) §C);
   - khi **không có sự đối chứng từ bất kỳ cảm biến nào**, vết chỉ được giữ lại trong khoảng độ trễ (hysteresis) `T_hold` ngắn ngủi (mặc định 10 giây) rồi sau đó được chuyển sang trạng thái đang-xóa — nhưng việc xóa một mối nguy *có thể vẫn còn hiện diện* được ghi nhật ký (log) và leo thang như một sự kiện **xóa với độ tin cậy thấp (low-confidence clear)**, không bao giờ là một sự kiện thầm lặng.
   - **Chuyển tiếp trạng thái ùn tắc (tinh chỉnh 2026-07-07).** Ngoại lệ duy nhất đối với khoảng giữ `T_hold` ở trên là một vết đang chịu **chặn cảnh báo do ùn tắc** (R14, [tài liệu 02 §4](../02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo)) vào lần cuối cùng nó được nhìn thấy. Một vết chỉ được xác nhận *trong khi cảnh báo lề đang bị chặn* thì chưa bao giờ giành được một lần khẳng định không-bị-chặn, nên **không có cảnh báo đang hiển thị nào để giữ**: giữ nó lại sẽ **nháy sáng biển báo ở trạng thái `WARN_HOLD` ngay khoảnh khắc việc chặn được gỡ bỏ** — điều xảy ra đúng vào lúc một đám kẹt xe kết thúc bằng cách các vết *cùng biến mất mà không có lần thoát ra nào* — một báo động giả (cry-wolf) dựng trên đúng cái hình học ROI lề-so-với-làn-thông mà R14 vốn đã nghi ngờ. Do đó một vết như vậy, biến mất **không có thoát ra được xác nhận và không có đối chứng**, được **xóa lặng lẽ** (không giữ, không khẳng định; `WARN_ON → CLEARING → IDLE`): sự nghi ngờ vốn dẫn đến việc chặn được **mang vào quyết định xóa**. **Che khuất được-radar-đối-chứng thì không bị ảnh hưởng** — đó là gạch đầu dòng ở trên: bằng chứng hiện diện độc lập vẫn giữ cảnh báo và, khi đám kẹt xe tan, hiển thị nó một cách đúng đắn. Sự tan rã kẹt xe theo thực tế — mỗi xe **được nhìn thấy tăng tốc rời đi** (một thoát ra được xác nhận) — xóa nhanh và không bao giờ chạm tới đường dẫn này; chỉ một *lần mất toàn cảnh đồng thời mà không có thoát ra* (hiện tượng giả của bộ phát hiện / một lần chớp mất toàn cảnh) mới chạm tới. Chi phí còn lại: một xe hỏng thật sự chớp mất khỏi **cả hai** kênh đúng khoảnh khắc đó phải phục vụ lại `T_dwell` khi tái thu nhận — một độ trễ cảnh báo-lại **có giới hạn**, chỉ phát sinh bên trong khoảng trống phạm vi bao phủ mà R14 vốn đã chấp nhận ([tài liệu 04 §0](../04-risk-and-safety.vi.md)). Được ghim bởi **SC-38**.
4. **Watchdog thất bại theo hướng xóa, một cách rõ ràng.** `T_watchdog` giới hạn thời gian cho bất kỳ lần kích hoạt nào *không* có xác nhận hoặc đối chứng mới từ *bất kỳ* kênh nào; khi hết hạn, cảnh báo được xóa **và phát sinh một lỗi** (logic có thể đã bị kẹt — [ADR-0005](ADR-0005-fail-safe-and-system-safety.vi.md)). Hiện diện radar được tính là đối chứng, nên một chiếc xe thực-sự-hiện-diện, bị-camera-che-khuất thì **không** làm kích hoạt watchdog. Khoảng trống cố ý đó — một lần giữ được đối chứng mà watchdog sẽ không giới hạn — được khép lại thay vào đó bởi **`T_degraded_max`** ([ADR-0009 §C](ADR-0009-failsafe-placement-and-degraded-modes.vi.md)), nên lần giữ suy giảm được định đoạt lớn tiếng thay vì để BẬT mãi.

**Phạm vi: các bảo đảm bền vững là cấp-độ-xe, không phải cấp-độ-người-đi-bộ.** Khoảng giữ-khi-che-khuất và ngữ nghĩa tập hợp được-radar-đối-chứng ở trên đều dựa vào **kênh hiện diện radar**. Một người đi bộ có tiết diện phản xạ radar (RCS) không đáng kể ([tài liệu 04 H-C](../04-risk-and-safety.vi.md#1-bảng-đăng-ký-rủi-ro)), nên một **cảnh báo chỉ-do-người-đi-bộ** (một người trong/cạnh ROI mà không có xe đi kèm) **không có đối chứng radar và do đó không có khoảng giữ-khi-che-khuất** — nó chạy trên thực tế là chỉ-camera và lùi về khoảng độ trễ `T_hold` ngắn ngủi. Đây là một bảo đảm thực sự hẹp hơn cho FR-08 và phải được **nêu rõ, chứ không mặc nhiên coi là ngang với trường hợp xe** ([tài liệu 01 FR-08](../01-requirements.vi.md)). **Khởi phát** của nó cũng khác biệt — *hiện diện* trong/cạnh ROI (có khử dội), **không** theo cổng tĩnh tại mà một người đang di chuyển sẽ không thỏa ([ADR-0003](ADR-0003-detection-algorithm.vi.md), [tài liệu 02 §4](../02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo)).

Các bộ định thời cụ thể và sơ đồ trạng thái được bổ sung chi tiết nằm ở [tài liệu 02 §4](../02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo); ADR này cố định **chính sách** mà các bộ định thời đó hiện thực.

## Các phương án đã xét

### Phương án A: Một-đối-tượng-duy-nhất, một-ngưỡng-thời-gian-vắng-mặt-duy-nhất (thiết kế ngầm định của bản phác thảo đầu tiên)
| Khía cạnh | Đánh giá |
|-----------|------------|
| Độ phức tạp | Thấp |
| Xử lý che khuất | **Kém** — che khuất lâu sẽ xóa một cảnh báo còn sống |
| Đa xe | **Không hỗ trợ** |
| Rủi ro BẬT-cũ | Đánh đổi trực tiếp với che khuất (một bộ định thời không thể phục vụ cả hai) |

**Ưu điểm:** đơn giản tầm thường.
**Nhược điểm:** lẫn lộn rời đi với che khuất; đơn vết; buộc phải có một sự thỏa hiệp bộ định thời thiếu an toàn.

### Phương án B: Dựa trên tập hợp, phân biệt thoát-ra-so-với-mất-vết, giữ-được-radar-đối-chứng *(được chọn — ngữ nghĩa tập hợp và phân biệt thoát-ra/mất-vết vẫn chạy; **khoảng giữ có radar đối chứng đang tạm ngưng** trong giai đoạn chỉ-dùng-camera này, [ADR-0001](ADR-0001-sensing-modality.vi.md) bị Bác bỏ → xem R20)*
| Khía cạnh | Đánh giá |
|-----------|------------|
| Độ phức tạp | Trung bình (ghi sổ tập hợp vết + biên thoát ra) |
| Xử lý che khuất | **Tốt** — giữ khi còn được đối chứng, xóa nhanh khi thoát ra thực sự |
| Đa xe | Hỗ trợ nguyên bản (native) |
| Rủi ro BẬT-cũ | Được giới hạn bởi watchdog + xóa với độ tin cậy thấp một cách rõ ràng |

**Ưu điểm:** loại bỏ sự lẫn lộn che khuất/rời đi; hỗ trợ nhiều xe; tái sử dụng kênh radar đã được mua sẵn trong ADR-0001; không bao giờ xóa một mối nguy có-thể-vẫn-hiện-diện một cách thầm lặng.
**Nhược điểm:** nhiều trạng thái vết hơn; cần một biên thoát ra ROI đã được định nghĩa; phụ thuộc vào việc đối chứng radar là có thật (kiểm chứng theo [ADR-0001](ADR-0001-sensing-modality.vi.md) / [ADR-0007](ADR-0007-validation-and-data-strategy.vi.md)).

### Phương án C: Chỉ-dựa-trên-hiện-diện ("cảnh báo chừng nào còn bất kỳ chuyển động/tín hiệu phản hồi nào trong ROI", không có vết)
| Khía cạnh | Đánh giá |
|-----------|------------|
| Độ phức tạp | Thấp–trung bình |
| Kích hoạt sai | **Kém** — không thể tách một lần đi ngang qua thoáng qua khỏi một lần dừng nếu không có thời gian lưu lại (dwell) theo từng vết |

**Ưu điểm:** đơn giản; bền vững trước che khuất (hiện diện là hiện diện).
**Nhược điểm:** mất đi thời gian lưu lại theo từng đối tượng, nên một chiếc xe chỉ đơn thuần đi dọc theo lề cũng có thể kích hoạt; không có thông tin về lớp (class) cho trường hợp người đi bộ.

## Phân tích đánh đổi

Hiểu biết cốt lõi là **rời đi mang theo bằng chứng (một lần thoát ra) còn che khuất thì không** — nên thiết kế an toàn đặt điều kiện dựa trên việc đó *là cái nào* thay vì dựa trên một ngưỡng thời gian duy nhất. Đối chứng radar chính là thứ làm cho một khoảng giữ-khi-che-khuất lâu trở nên an toàn: nó cho phép hệ thống tiếp tục cảnh báo về một chiếc xe mà nó hiện không thể nhìn thấy **mà không** mở ra một cửa sổ BẬT-cũ không giới hạn, bởi vì ngay khoảnh khắc radar cũng mất tín hiệu phản hồi và không có lần thoát ra nào được quan sát, watchdog sẽ xóa một cách rõ ràng. Phương án B chi một lượng ghi sổ vừa phải để mua đứt trạng thái lỗi nguy hiểm nhất của máy trạng thái (bỏ sót thầm lặng do che khuất gây ra) và khoảng trống đa xe trong cùng một nước đi. Nó cũng làm cho kênh radar trở nên chịu lực cho **tính bền vững (persistence)**, chứ không chỉ cho phát hiện ban đầu — củng cố lập luận của ADR-0001 và cho ADR-0007 một thứ cụ thể để kiểm chứng.

## Hệ quả

- **Dễ hơn:** hành vi đúng đắn dưới che khuất và nhiều xe; xóa nhanh khi rời đi thực sự; không có xóa thầm lặng; và **không có nháy báo động giả** khi một vết bị-chặn-do-ùn-tắc bị mất do *biến mất* thay vì một lần thoát ra được xác nhận (chuyển tiếp trạng thái ùn tắc ở trên, SC-38).
- **Khó hơn:** một vòng đời tập hợp vết và một biên thoát ra ROI đã được định nghĩa để hiện thực và kiểm thử; một phụ thuộc cứng vào đối chứng radar thật — bao gồm việc radar có **phân biệt phương vị/làn (azimuth/lane discrimination)** đủ tốt để quy một tín hiệu phản hồi về ROI *trên lề* thay vì làn thông liền kề ở tầm được giám sát, chứ không chỉ đơn thuần phát hiện hiện diện (được gộp vào cổng kiểm soát của [ADR-0001](ADR-0001-sensing-modality.vi.md)). Nếu radar bị cắt giảm xuống thành một kênh tổng hợp, thì sự bảo đảm của khoảng giữ-khi-che-khuất chỉ tốt ngang với mô hình tổng hợp ([ADR-0007](ADR-0007-validation-and-data-strategy.vi.md)); nhiều kịch bản hơn trong bộ nghiệm thu (che khuất kéo dài có/không có radar, các đan xen vào/ra của nhiều xe).
- **Xem xét lại khi:** dữ liệu hiện trường cho thấy che khuất hiếm hơn/ngắn hơn so với giả định (đơn giản hóa `T_occlusion`), hoặc một bộ theo vết (tracker) phong phú hơn làm cho việc phát hiện thoát ra đủ đáng tin cậy để rút ngắn `T_hold`.

## Hạng mục hành động

1. [ ] Định nghĩa **biên thoát ra** của ROI và phép kiểm thoát-ra-đã-xác-nhận (ngưỡng tốc độ + băng qua đa giác + chống dội).
2. [ ] Hiện thực **tập hợp vết** với trạng thái theo từng vết (đang-theo-vết / đã-xác-nhận / được-cho-là-bị-che-khuất / đã-thoát-ra).
3. [ ] Nối **đối chứng hiện diện radar** vào khoảng giữ-khi-mất-vết; định nghĩa điều gì được tính là một tín hiệu phản hồi mang tính đối chứng.
4. [ ] Đặc tả sự tương tác giữa `T_occlusion` / `T_hold` / `T_watchdog` trong [tài liệu 02 §4](../02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo) và bổ sung sự kiện **xóa với độ tin cậy thấp** vào telemetry/nhật ký kiểm toán (audit).
5. [ ] Bổ sung các kịch bản che-khuất-kéo-dài (có và không có radar) và đan xen nhiều xe vào bộ nghiệm thu ([tài liệu 01 §5](../01-requirements.vi.md#5-chỉ-số-đánh-giá--tiêu-chí-nghiệm-thu)).
