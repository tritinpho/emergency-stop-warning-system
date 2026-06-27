# ADR-0009: Vị trí cơ chế an toàn khi sự cố & ngữ nghĩa chế độ suy giảm

> 🇬🇧 Bản gốc tiếng Anh: [ADR-0009-failsafe-placement-and-degraded-modes.md](ADR-0009-failsafe-placement-and-degraded-modes.md)

**Trạng thái:** Đề xuất
**Ngày:** 2026-06-27
**Người quyết định:** Chủ nhiệm đề tài (PI) (ThS. Phó Trí Tín), trưởng nhóm kỹ thuật, cố vấn an toàn giao thông đường bộ, kỹ sư hiện trường/lắp đặt

## Bối cảnh

[ADR-0005](ADR-0005-fail-safe-and-system-safety.vi.md) đã thiết lập nguyên tắc **an toàn khi sự cố + báo lỗi rõ ràng (fail-safe + fail-loud)** và đặt tên cho một **cơ chế tự ngắt an toàn (dead-man's switch)** để một máy trạng thái bị sập không thể để lại một cảnh báo đang được khẳng định. [ADR-0008](ADR-0008-detection-persistence-and-multitrack.vi.md) đã thiết lập **tính bền vững dựa trên tập hợp (set-based persistence)** với một **khoảng giữ-khi-che-khuất được radar đối chứng (corroborate)**. Ba câu hỏi tiếp nối đã bị để lại ngầm định — và mỗi câu đều mang tính quyết định về an toàn một khi ta nhìn vào topology *vật lý* và các chế độ *một-cảm-biến-hỏng* thay vì sơ đồ khối logic.

1. **Cơ chế tự ngắt an toàn nằm ở đâu về mặt vật lý?** [Tài liệu 02 §2](../02-system-architecture.vi.md#2-kiến-trúc-logic-các-thành-phần--trách-nhiệm) đã đặt phần "mặc định về để trống khi mất nhịp khẳng định (heartbeat) của SM" vào trong **lớp trừu tượng cơ cấu chấp hành (actuator abstraction)**, vốn chạy trên **khối biên (edge box)**. Nhưng biển báo lại được điều khiển bởi một **bộ điều khiển biển báo riêng biệt** thông qua một liên kết cục bộ ([tài liệu 02 §3](../02-system-architecture.vi.md#3-kiến-trúc-vật-lý--triển-khai)). Một bộ ngắt nằm trên khối biên bảo vệ được trước một lần sập SM *trong khi khối còn sống* — nhưng một **khối biên chết**, một **liên kết bị cắt hoặc bị nghẽn**, hay một OS bị kẹt sẽ để lại một biển báo chốt trạng thái (latching) riêng biệt **đang giữ trạng thái cuối của nó**. Nếu trạng thái đó là BẬT, thì đây chính xác là tình huống **BẬT-cũ (stale-ON)** mà thiết kế ra đời để ngăn chặn. Một watchdog nằm ở thượng nguồn (upstream) của liên kết không thể bảo đảm rằng một biển báo ở hạ nguồn (downstream) sẽ tắt đèn.

2. **Hệ thống thực sự có thể làm được gì khi một cảm biến hỏng?** Bản FMEA ([tài liệu 04 §2](../04-risk-and-safety.vi.md#2-fmea-lite-kiểu-lỗi--tác-động--phát-hiện--phản-ứng)) đã xử lý "camera chết → chạy suy giảm chỉ-radar" và "radar chết → chạy suy giảm chỉ-camera" như thể chúng đối xứng. Chúng **không** đối xứng. Theo [ADR-0001](ADR-0001-sensing-modality.vi.md)/[ADR-0003](ADR-0003-detection-algorithm.vi.md)/[ADR-0008](ADR-0008-detection-persistence-and-multitrack.vi.md), **camera sở hữu việc phân loại, hình học ROI trên ảnh, và vết (track) mà thời gian lưu lại (dwell) chạy trên đó**; radar chỉ *đối chứng* cho một vết đã được xác nhận từ trước. Vì vậy **chỉ-radar không thể _khởi tạo_ một lần xác nhận mới bên trong ROI** — nó mù với các mối nguy mới, chứ không đơn thuần là suy giảm.

3. **Điều gì xảy ra ở thời điểm kết thúc khoảng giữ-khi-che-khuất trong khi radar vẫn còn nhìn thấy chiếc xe?** ADR-0008 giữ một vết đã mất "trong tối đa `T_occlusion` (60 giây)" nhưng chưa bao giờ nói điều gì xảy ra tại mốc 60 giây **trong khi radar vẫn còn đối chứng**. Việc xóa ngay lúc đó sẽ tạo ra đúng cái trường hợp bỏ sót thầm lặng (silent miss) mà ADR-0008 được viết ra để ngăn chặn.

Các yếu tố tác động: tránh bỏ sót thầm lặng (yếu tố chi phối), tránh BẬT-cũ, topology vật lý biên↔biển báo, hành vi chốt trạng thái (latching) của VMS bên thứ ba, sự đơn giản của khối tính toán biên (edge-compute), và khả năng kiểm thử (mọi tuyên bố ở đây đều phải chứng minh được bằng tiêm lỗi).

## Quyết định

### A. Cơ chế tự ngắt an toàn nằm trong bộ điều khiển biển báo, ở hạ nguồn của liên kết

Cảnh báo được khẳng định bằng một **nhịp khẳng định SHOW làm mới liên tục (continuously refreshed SHOW heartbeat), không phải một lệnh chốt trạng thái (latching)**:

- khối biên làm mới một **tín hiệu khẳng định SHOW đã được xác thực (authenticated)** tới bộ điều khiển biển báo sau mỗi `T_assert_refresh` (mặc định **0,5 giây**);
- **bộ điều khiển biển báo để trống biển báo nếu không có một tín hiệu SHOW mới, hợp lệ nào đến trong vòng `T_signhold` (mặc định 2 giây)** — một cách độc lập với khối biên, với liên kết, và với máy trạng thái. **Đây mới là tuyến phòng vệ cuối cùng (backstop) thật sự.**
- lớp trừu tượng cơ cấu chấp hành trên khối biên vẫn giữ một cơ chế tự ngắt an toàn *bên trong* dựa trên nhịp khẳng định (heartbeat) của SM (phản ứng cục bộ nhanh hơn), và bộ giám sát tình trạng (health monitor) vẫn giữ đường ép-về-an-toàn (force-safe) độc lập của nó ([ADR-0005](ADR-0005-fail-safe-and-system-safety.vi.md)). **Ba lớp, mỗi lớp đều nằm nghiêm ngặt ở hạ nguồn của thứ mà nó canh giữ.**

Mọi đường lỗi cứng (hard-failure) giờ đây đều phân giải về để trống: **SM sập** → biên ngừng làm mới → cả lớp trừu tượng bên trong lẫn bộ điều khiển biển báo đều để trống; **khối biên chết** → bộ điều khiển để trống; **liên kết bị cắt/nghẽn** → bộ điều khiển để trống; **bộ điều khiển biển báo chết** → một biển báo LED đơn giản là tắt đèn (an toàn). Thẩm quyền về trạng thái an toàn không bao giờ nằm ở thượng nguồn của, hay phụ thuộc vào, chính cái thứ mà nó bảo vệ.

**`T_signhold` là một sự đánh đổi thật sự, không phải một bảo đảm miễn phí.** Nó *đồng thời* vừa là **cửa sổ BẬT-cũ tối đa sau một lỗi cứng** vừa là **khoảng trống nhịp khẳng định (heartbeat) tối thiểu sẽ làm để trống một cảnh báo đang sống và đúng đắn**. Quá ngắn → một lần khựng bình thường của khối biên (tạm dừng GC, đỉnh tải suy luận) sẽ để trống một cảnh báo hợp lệ và biển báo chập chờn tắt/bật (một lần bỏ sót thầm lặng ngắn + một lần nhấp nháy kiểu báo-động-giả); quá dài → BẬT-cũ nán lại sau một lần sập thật. Giá trị mặc định **2 giây ≈ 4× `T_assert_refresh`** là một điểm khởi đầu để tinh chỉnh ở Giai đoạn 3; rủi ro chập chờn được giới hạn bằng cách giữ `T_assert_refresh` thấp hơn hẳn `T_signhold` và bằng cách làm mượt độ trễ nhất thời của khối biên xuống dưới chu kỳ làm mới.

**Kẻ thù tệ nhất của nhịp khẳng định là _liên kết_, không phải khối biên — và bàn thử không nhìn thấy nó.** Biển báo nằm **cách ≥ DSD về phía thượng nguồn** (≈ 315 m ở 100 km/h, [tài liệu 02 §3](../02-system-architecture.vi.md#3-kiến-trúc-vật-lý--triển-khai)), nên tín hiệu SHOW làm mới chạy qua một **liên kết cáp hoặc RF dài 300 m+**, chứ không phải đoạn cáp 1 m trên bàn thử. Một liên kết hiện trường mất gói hoặc nghẽn là một nguồn gây ra các khoảng trống dài bằng `T_signhold` còn nhiều khả năng hơn một lần tạm dừng GC của khối biên — và mỗi khoảng trống như vậy đều để trống một cảnh báo hợp lệ (một bỏ sót thầm lặng ngắn + một nhấp nháy báo-động-giả), còn một liên kết bị *nghẽn (jammed)* là một sự từ-chối-cảnh-báo có chủ đích ([tài liệu 04 §5 Q5](../04-risk-and-safety.vi.md#5-các-câu-hỏi-an-toàn-còn-mở-cho-nhóm)). Vì vậy `T_signhold` / `T_assert_refresh` phải được tinh chỉnh theo phân bố mất gói và độ trễ của **liên kết hiện trường**, liên kết cần **ngân sách độ tin cậy / độ trễ / năng lượng / xác thực riêng** như một giao diện hạng nhất ([tài liệu 02 §7](../02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu)), và — vì bàn thử chạy việc này qua một mét cáp — **chính nhịp khẳng định qua khoảng cách xa là phần kiểm chứng bị hoãn sang hiện trường**, không phải thứ mà một lần đạt trên bàn thử có thể khép lại.

**Lưu ý về backend — một VMS bên thứ ba chốt trạng thái (latching) không thể đem lại sự bảo đảm ở mức phần cứng.** Một VMS của đơn vị vận hành được kết nối qua giao thức riêng của nó ([ADR-0004](ADR-0004-warning-actuator-integration.vi.md)) có thể *chốt* một thông điệp và có thể không tôn trọng một hợp đồng làm-mới-nhịp-khẳng-định (heartbeat-refresh). Đối với backend đó, sự bảo đảm mạnh ở trên **không** thành lập; hệ thống lùi về dùng **watchdog + lệnh CLEAR chủ động + đọc-ngược (read-back) trạng thái**, và cửa sổ BẬT-cũ còn lại bằng đúng chu kỳ lệnh của giao thức vận hành. Điều này phải được nêu rõ theo từng vị trí, và đây là thêm một lý do nữa khiến độ trễ và hành vi của backend VMS được phân định riêng (ADR-0004, [NFR-01](../01-requirements.vi.md#3-yêu-cầu-phi-chức-năng)). Ở nơi nào đơn vị vận hành cho phép, hãy ưu tiên một chế độ khẳng-định-làm-mới hoặc khóa-liên-động phần cứng (hardware-interlock) trên VMS.

### B. Ngữ nghĩa chế độ suy giảm — *khởi tạo* và *duy trì* không đối xứng

| Chế độ | Trạng thái cảm biến | KHỞI TẠO một cảnh báo mới? | DUY TRÌ một cảnh báo hiện có? | Tư thế |
|--------|---------------------|----------------------------|-------------------------------|--------|
| **FULL** | camera + radar khỏe | Có | Có (gồm cả khoảng giữ-khi-che-khuất bằng radar) | Bình thường |
| **CAMERA-ONLY** | radar chết | **Có** (lớp camera + ROI + tốc-độ-vết) | Có, nhưng **không có khoảng giữ-khi-che-khuất bằng radar** và không có phép đối chiếu chéo độc lập về vật thể đứng yên | Suy giảm + cảnh báo; gắn cờ rủi ro bỏ sót ban đêm/thời tiết |
| **RADAR-ONLY** | camera chết | **Không** — không có lớp, không có cổng ROI trên ảnh; phương vị radar có thể không phân giải được lề so với làn thông (through-lane) | Chỉ trong thời gian ngắn, đối với các vết **đã** được xác nhận, trong khi radar còn đối chứng | **BLIND-TO-NEW: cảnh báo nghiêm trọng** — *không phải* một lần chạy lành tính |
| **NEITHER** | cả hai hỏng | Không | Không | **SAFE STATE** (để trống) + cảnh báo nghiêm trọng |

Phần chỉnh sửa chịu lực là **RADAR-ONLY**: nó **mù với các mối nguy mới (blind to new hazards)** và phải leo thang như một suy giảm **nghiêm trọng (critical)**, trong khi các vết đã được xác nhận có thể được duy trì trong một khoảng giữ **có giới hạn** để một cảnh báo đang diễn ra không bị rớt ngay khoảnh khắc camera hỏng. Một đơn vị không thể xác nhận một lần dừng mới **không bao giờ được tự thể hiện mình như đang giám sát**. (CAMERA-ONLY vẫn là một lần-chạy-suy-giảm đích thực, vì chỉ riêng camera vẫn có thể khởi tạo; nó chỉ đơn thuần mất đi tính bền vững trước thời tiết và khoảng giữ-khi-che-khuất của radar.)

### C. Che khuất kéo dài với đối chứng còn sống thì không bao giờ xóa thầm lặng — và có giới hạn thời gian

Tinh chỉnh khoảng giữ của ADR-0008: **`T_occlusion` giới hạn sự đối chứng *không được làm mới (un-renewed)*.** Chừng nào radar còn tiếp tục trả về một phát hiện mang tính đối chứng, khoảng giữ **được làm mới** và cảnh báo vẫn duy trì. Nếu che khuất camera kéo dài **vượt quá `T_occlusion` trong khi radar vẫn còn đối chứng**, đơn vị bước vào trạng thái **CAMERA-OCCLUDED-DEGRADED**: cảnh báo **vẫn BẬT** (mối nguy vẫn đang được đối chứng) **và** đơn vị vận hành được báo để điều tra — che khuất kéo dài thường là một sự cố *phức hợp (compound)* (một chiếc xe dừng thứ hai) hoặc một lỗi camera.

**Bản thân trạng thái này phải có giới hạn thời gian — đây là nơi duy nhất watchdog không chạm tới.** Watchdog ([ADR-0008](ADR-0008-detection-persistence-and-multitrack.vi.md) §4) *cố ý* bị vô hiệu hóa trong khi bất kỳ kênh nào còn đối chứng, nên ở CAMERA-OCCLUDED-DEGRADED — camera bị che, chỉ radar giữ cảnh báo BẬT — không có gì tự động giới hạn khoảng giữ. Hai dạng lỗi khiến điều đó nguy hiểm: một chiếc xe **bị che khuất vĩnh viễn nhưng thực sự còn hiện diện** (giữ cảnh báo là đúng, nhưng một lần giữ kéo dài hàng giờ nên *do người trực sở hữu*, không phải do máy duy trì thầm lặng), và — tệ hơn — một **tiêu chí (b) yếu** ([ADR-0001](ADR-0001-sensing-modality.vi.md)) khi tín hiệu "đối chứng" là **chiếc xe tải che khuất ở làn thông xe**, không phải một xe ở lề đã rời đi, biến cảnh báo thành một **kẹt-BẬT khóa vào dòng xe thông xe** không bao giờ xóa. Một lần thoát ra đã xác nhận không cứu được cả hai trường hợp: một đơn vị *bị che camera* không thể quan sát một diện tích tiếp xúc vượt qua biên thoát ra.

Do đó **`T_degraded_max` (mặc định ~5 phút, tinh chỉnh được) giới hạn thời gian ở CAMERA-OCCLUDED-DEGRADED.** Khi hết hạn mà camera chưa thu nhận lại, đơn vị buộc một định đoạt **lớn tiếng**, rõ ràng — một **lần xóa độ-tin-cậy-thấp + leo thang mức cao nhất tới người trực** ([ADR-0011](ADR-0011-operator-concept-and-alarm-management.vi.md)) — trao quyết định cho một con người có CCTV/tuần tra thay vì tin tưởng mãi vào một tín hiệu radar không kiểm chứng được. Đây cũng chính là sự đánh đổi mà ADR-0008 thực hiện khi cạn bằng chứng (báo động lớn, bàn giao), áp dụng cho trạng thái duy nhất watchdog không thấy. Các đường có thể xóa một cảnh báo nay là **bốn**: một **lần thoát ra đã xác nhận** (nhanh), **mất toàn bộ đối chứng mà không có lần thoát ra** (→ `T_hold` → xóa độ-tin-cậy-thấp rõ ràng), một **lần hết hạn watchdog do logic bị kẹt** (→ xóa + lỗi), và **lần hết hạn `T_degraded_max`** (→ buộc xóa lớn tiếng + leo thang). **Không đường nào thầm lặng, và không đường nào vô hạn** (NFR-04, được mở rộng để bao quát kẹt-BẬT do phân biệt-cảm-biến).

## Các phương án đã xét

### Phương án A: Cơ chế tự ngắt an toàn chỉ nằm trên khối biên *(vị trí đặt theo bản phác thảo đầu tiên)*
| Khía cạnh | Đánh giá |
|-----------|------------|
| Bảo vệ trước lần sập SM (khối còn sống) | Có |
| Bảo vệ trước khối chết / mất liên kết | **Không** — biển báo chốt trạng thái giữ trạng thái cuối |
| Độ phức tạp | Thấp |

**Ưu điểm:** đơn giản nhất; không cần một điểm cuối biển báo thông minh.
**Nhược điểm:** thẩm quyền về trạng thái an toàn nằm ở *thượng nguồn* của liên kết và của biển báo, nên hai sự cố dễ làm mắc kẹt một biển báo đang sáng nhất (khối chết, liên kết cắt) lại chính là những sự cố nó không thể bao trùm. Bị loại.

### Phương án B: Bộ ngắt trong bộ điều khiển biển báo + các chế độ suy giảm bất đối xứng + khoảng giữ có thể làm mới *(được chọn)*
| Khía cạnh | Đánh giá |
|-----------|------------|
| Mức bao phủ an toàn khi sự cố | **Trọn vẹn** — lỗi khối, liên kết, SM, cảm biến đều phân giải về để trống |
| Tính trung thực của các chế độ suy giảm | **Cao** — chỉ-radar được nêu đúng là "mù với cái mới" |
| Độ phức tạp | Trung bình — điểm cuối biển báo thông minh + hai chế độ suy giảm + một trạng thái suy giảm |

**Ưu điểm:** trạng thái an toàn nằm nghiêm ngặt ở hạ nguồn của mọi thành phần mà nó canh giữ; các chế độ suy giảm khớp với năng lực cảm biến thực tế; không có xóa thầm lặng khi đang còn đối chứng.
**Nhược điểm:** bộ điều khiển biển báo phải là một điểm cuối thông minh (nhịp khẳng định + logic để trống); một VMS chốt trạng thái không thể đem lại sự bảo đảm phần cứng và phải được ghi nhận là một backend yếu hơn.

### Phương án C: Biển báo chốt trạng thái + watchdog thuần phần mềm
| Khía cạnh | Đánh giá |
|-----------|------------|
| Mức bao phủ an toàn khi sự cố | **Yếu** — phụ thuộc vào việc thành phần được canh giữ phải còn sống |
| Độ phức tạp | Thấp |

**Ưu điểm:** tầm thường; hoạt động với các biển báo câm/chốt trạng thái.
**Nhược điểm:** một watchdog lại phụ thuộc vào chính đối tượng của nó. Chỉ chấp nhận được **duy nhất** trong vai trò phương án lùi không thể tránh khỏi cho một VMS bên thứ ba chốt trạng thái (lưu ý ở mục A), không bao giờ làm thiết kế chính.

## Phân tích đánh đổi

Nguyên tắc duy nhất quyết định mục A là **thẩm quyền về trạng thái an toàn phải nằm nghiêm ngặt ở hạ nguồn của — và độc lập với — mọi thành phần mà nó bảo vệ.** Một bộ ngắt trên khối biên vi phạm điều này đối với liên kết và biển báo; dời nó vào bộ điều khiển biển báo thì thỏa mãn được điều đó cho toàn bộ chuỗi, với cái giá là một điểm cuối thông minh — thứ mà cả mô hình LED thay thế trên bàn thử lẫn một biển báo LED hiện trường đều đã có sẵn. Tính bất đối xứng của chế độ suy giảm ở mục B không phải là một sự tinh chỉnh mà là một sự sửa lỗi tính đúng đắn: gọi chỉ-radar là một "lần chạy suy giảm" sẽ cho phép một đơn vị đã mù camera tiếp tục *quảng cáo* phạm vi bao phủ mà nó không còn nữa — trường hợp bỏ sót thầm lặng khoác lên mình cái nhãn "suy giảm nhưng vẫn OK". Quy tắc khoảng-giữ-có-thể-làm-mới ở mục C khép lại đường xóa-thầm-lặng cuối cùng còn sót trong ADR-0008, và giới hạn **`T_degraded_max`** của nó khép lại đường *giữ-vô-hạn* cuối cùng — trạng thái duy nhất mà watchdog cố ý không chạm tới được. Cả ba đều mua đứt các chế độ bỏ sót thầm lặng (và kẹt-BẬT vô hạn) bằng một lượng kỹ thuật vừa phải và kiểm thử được, nhất quán với nguyên tắc dẫn đường số 1 (an toàn khi sự cố, báo lỗi rõ ràng).

## Hệ quả

- **Dễ hơn:** an toàn khi sự cố đích thực trước lỗi toàn-khối và lỗi liên kết; các chế độ suy giảm trung thực, khớp-với-năng-lực; không có xóa thầm lặng khi một mối nguy đang được đối chứng; mọi đường lỗi đều là một bài kiểm thử tiêm lỗi cụ thể.
- **Khó hơn:** bộ điều khiển biển báo trở thành một **điểm cuối thông minh** (nhịp khẳng định + logic để trống) — ổn đối với LED bàn thử (vi điều khiển) và một biển báo LED hiện trường, nhưng một **VMS bên thứ ba chốt trạng thái thì không thể** đem lại sự bảo đảm phần cứng và phải được ghi nhận là một backend yếu hơn với một phần còn lại (residual) được nêu rõ; hai chế độ suy giảm có tên và một trạng thái suy giảm phải hiện thực và tiêm lỗi; `T_signhold` / `T_assert_refresh` trở thành các tham số định thời có liên quan đến an toàn cần tinh chỉnh.
- **Xem xét lại khi:** một nhà cung cấp VMS phơi bày một chế độ khóa-liên-động phần cứng hoặc khẳng-định-làm-mới (thu gọn lưu ý về chốt trạng thái), hoặc dữ liệu hiện trường lượng hóa được các phân bố khựng thật của khối biên **và mất gói của liên kết hiện trường** (tinh chỉnh `T_signhold`).

## Hạng mục hành động

1. [ ] Đặc tả **giao thức khẳng định SHOW làm mới (refreshed-SHOW)** (chu kỳ `T_assert_refresh`, xác thực, `T_signhold`) giữa khối biên và bộ điều khiển biển báo; hiện thực **để-trống-khi-mất-tín-hiệu trong bộ điều khiển biển báo** (và trong bộ điều khiển LED bàn thử).
2. [ ] **Tiêm cả ba lỗi cứng** — giết khối biên, cắt liên kết, giết tiến trình SM — và xác nhận biển báo **để trống trong vòng `T_signhold`** trong mọi trường hợp (mở rộng [ADR-0005](ADR-0005-fail-safe-and-system-safety.vi.md) AI#3).
3. [ ] Hiện thực các **chế độ suy giảm** (CAMERA-ONLY, RADAR-ONLY/BLIND-TO-NEW, NEITHER) với năng lực *khởi tạo/duy trì* đúng đắn và mức độ leo thang nghiêm trọng tương ứng; bổ sung mỗi chế độ vào bộ nghiệm thu tiêm lỗi và đối chiếu lại các hàng FMEA ở [tài liệu 04 §2](../04-risk-and-safety.vi.md#2-fmea-lite-kiểu-lỗi--tác-động--phát-hiện--phản-ứng).
4. [ ] Hiện thực **CAMERA-OCCLUDED-DEGRADED** (cảnh báo duy trì + báo cho đơn vị vận hành) tại thời điểm `T_occlusion` hết hạn khi đang còn đối chứng sống, **được giới hạn bởi `T_degraded_max`** → buộc xóa lớn-tiếng độ-tin-cậy-thấp + leo thang mức cao nhất ([ADR-0011](ADR-0011-operator-concept-and-alarm-management.vi.md)); bổ sung kịch bản **che-khuất-kéo-dài-có-radar** *và lần buộc-xóa `T_degraded_max`* vào bộ nghiệm thu (gắn với [ADR-0008](ADR-0008-detection-persistence-and-multitrack.vi.md) AI#5).
5. [ ] Ghi nhận **lưu ý về backend VMS chốt trạng thái** và cửa sổ BẬT-cũ còn lại của nó trong bản đặc tả bộ chuyển đổi (adapter) VMS của [ADR-0004](ADR-0004-warning-actuator-integration.vi.md).
6. [ ] Đặc trưng hóa **liên kết biên↔biển báo** (cáp / RF) về ngân sách mất gói + độ trễ ở cự ly triển khai ≥ DSD; tinh chỉnh `T_signhold` / `T_assert_refresh` theo nó; gắn nhãn nhịp khẳng định qua khoảng cách xa là kiểm chứng **bị hoãn sang hiện trường** (bàn thử chỉ vận hành một đoạn cáp ngắn) và cấp cho liên kết một mục riêng trong các hợp đồng [tài liệu 02 §7](../02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu).
