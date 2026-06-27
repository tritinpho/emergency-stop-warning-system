# ADR-0013: Hợp nhất trạng thái giữ-khi-suy-giảm — một cảnh báo khi camera không xác thực được thì bị giới hạn bất kể nguyên nhân, và ma trận trạng thái cảnh báo × chế độ cảm biến

> 🇬🇧 Bản gốc tiếng Anh: [ADR-0013-degraded-hold-unification.md](ADR-0013-degraded-hold-unification.md)

**Trạng thái:** Đề xuất
**Ngày:** 2026-06-27
**Người quyết định:** Chủ nhiệm đề tài (PI) (ThS. Phó Trí Tín), trưởng nhóm kỹ thuật, cố vấn an toàn giao thông đường bộ, kỹ sư thị giác máy tính (CV)

## Bối cảnh

[ADR-0009](ADR-0009-failsafe-placement-and-degraded-modes.vi.md) đã làm hai việc mà, khi đọc cùng nhau,
để lại một đường còn thiếu đặc tả:

- **§C** đã giới hạn trạng thái `CAMERA_OCCLUDED_DEGRADED` bằng **`T_degraded_max`** — bởi vì watchdog
  *cố ý bị vô hiệu hóa trong khi radar còn đối chứng*
  ([ADR-0008](ADR-0008-detection-persistence-and-multitrack.vi.md) §4), một cảnh báo được giữ BẬT chỉ
  nhờ radar (camera **bị che khuất**, tầm nhìn bị một xe tải ở làn thông xe chắn) không có giới hạn cuối
  nào, nên dưới một tiêu chí (b) yếu của [ADR-0001](ADR-0001-sensing-modality.vi.md), phát hiện "đối
  chứng" có thể chính là chiếc xe tải che khuất và biển báo sẽ BẬT mãi mãi. `T_degraded_max` buộc một
  **lần xóa độ-tin-cậy-thấp lớn tiếng + leo thang mức cao nhất** khi hết hạn.
- **§B** đã trao cho chế độ cảm biến **RADAR-ONLY** (camera **chết / đứng hình**) quy tắc: *không thể
  khởi tạo một cảnh báo mới (BLIND-TO-NEW), nhưng có thể **giữ một cảnh báo đã được xác nhận từ trước
  trong thời gian ngắn** trong khi radar còn đối chứng.* Cái "khoảng giữ ngắn có giới hạn" đó chưa bao
  giờ được cấp một **định thời có tên hay một định đoạt cuối**.

Đây là **cùng một mối nguy mang hai cái nhãn.** Ở cả hai, *cảnh báo bị giữ BẬT trong khi camera không
thể xác thực vết bên trong ROI và chỉ có radar đối chứng* — nên cả hai đều thừa hưởng đúng cái lỗi mà §C
được viết ra để khép lại: nếu tiêu chí (b) yếu, phát hiện đối chứng có thể là một **xe ở làn thông xe**,
không phải chiếc xe trên lề, và cảnh báo trở thành một **kẹt-BẬT khóa vào dòng xe thông xe không bao giờ
xóa**. Thế nhưng chỉ cái nhãn che khuất mới có giới hạn. Cái nhãn **lỗi** camera — vốn *tệ hơn*, vì một
camera chết **không có triển vọng bắt lại** vết bằng phần mềm, nên thậm chí không có cả một lối thoát tự
phục hồi — lại bị để mặc với một chữ "trong thời gian ngắn" vô hạn.

Một khoảng trống thứ hai, có liên quan, nằm ngay bên dưới nó. Máy trạng thái ra quyết định
([tài liệu 02 §4](../02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo)) được mô hình hóa
như một vùng (region) duy nhất trên vòng đời của **cảnh báo** (IDLE → … →
WARN_ON/WARN_HOLD/CAMERA_OCCLUDED_DEGRADED → CLEARING → SAFE_STATE). Nhưng **tình trạng cảm biến** (FULL
/ CAMERA-ONLY / RADAR-ONLY / NEITHER,
[ADR-0009 §B](ADR-0009-failsafe-placement-and-degraded-modes.vi.md)) lại là một chiều **trực giao**: một
đơn vị có thể đang ở WARN_ON *và* mất camera. Hành vi nằm trong **tích (product)** của hai vùng, và cái
tích đó chỉ được đặc tả rải rác bằng văn xuôi trong
[ADR-0009 §B](ADR-0009-failsafe-placement-and-degraded-modes.vi.md), bảng chế độ suy giảm ở
[tài liệu 02 §4](../02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo), và bản FMEA ở
[tài liệu 04 §2](../04-risk-and-safety.vi.md#2-fmea-lite-kiểu-lỗi--tác-động--phát-hiện--phản-ứng) —
chưa bao giờ được liệt kê đầy đủ. Ô có hệ quả lớn nhất (camera chết *trong khi một cảnh báo đang hoạt
động*) chính là đường vô hạn nói ở trên. Một người xây dựng hệ thống khi hiện thực máy trạng thái không
thể suy ra hành vi đúng từ sơ đồ vùng-đơn; họ sẽ đoán, và cái đoán đó là một tham số an toàn.

Các yếu tố tác động: tránh bỏ sót thầm lặng và tránh kẹt-BẬT (cả hai đều chi phối), việc cố ý vô hiệu hóa
watchdog khi đang đối chứng, khả năng hiện thực (mô hình phải xây dựng được mà không cần suy diễn), và
khả năng kiểm thử (mọi ô đều phải tiếp cận được bằng tiêm lỗi).

## Quyết định

### A. Một giới hạn duy nhất cho "camera không xác thực được, radar đối chứng" — bất kể nguyên nhân

**Bất kỳ trạng thái nào trong đó cảnh báo bị giữ BẬT khi (i) camera không thể xác thực vết bên trong ROI
và (ii) chỉ có radar đối chứng thì đều bị giới hạn bởi `T_degraded_max`** và, khi hết hạn mà camera chưa
xác thực lại, sẽ phân giải về **cùng một lần buộc xóa độ-tin-cậy-thấp lớn tiếng + leo thang mức cao nhất
tới người trực** ([ADR-0009 §C](ADR-0009-failsafe-placement-and-degraded-modes.vi.md),
[ADR-0011](ADR-0011-operator-concept-and-alarm-management.vi.md)). Nguyên nhân khiến camera không xác
thực được — **che khuất** kéo dài (camera còn sống, tầm nhìn bị chắn) **hoặc** **lỗi** camera (đứng hình
/ chết / RADAR-ONLY) — **không** làm thay đổi giới hạn. Điều này tổng quát hóa quy tắc của §C sang trường
hợp lỗi-camera mà §B đã để vô hạn, và là sự khép lại có nguyên tắc đối với khoảng giữ thiếu-đặc-tả *cuối
cùng* (NFR-04, được mở rộng ở lần rà soát số 4 để bao quát kẹt-BẬT do phân biệt-cảm-biến, nay áp dụng cho
kẹt-BẬT do camera-không-xác-thực-được bất kể nguyên nhân).

Hai nguyên nhân chỉ khác nhau ở **đúng một** điểm — **triển vọng bắt lại (vết)** — và máy trạng thái chỉ
mã hóa duy nhất sự khác biệt đó:

| Nguyên nhân | Lối thoát tự phục hồi | Rời trạng thái giữ có giới hạn qua |
|-------------|-----------------------|------------------------------------|
| **Che khuất** (camera còn sống, bị chắn) | **Có** — `→ WARN_ON` khi camera bắt lại được vết | camera bắt lại (vết) · lần thoát ra đã xác nhận (nếu nó quan sát được) · mất toàn bộ đối chứng → `T_hold` → xóa lớn tiếng · **`T_degraded_max`** buộc xóa |
| **Lỗi camera** (chết / đứng hình) | **Không** — một camera chết không thể bắt lại bằng phần mềm | mất toàn bộ đối chứng → xóa lớn tiếng · **`T_degraded_max`** buộc xóa · → SAFE_STATE nếu radar cũng rớt (NEITHER) |

Bởi vì biến thể lỗi-camera **không có lối thoát tự phục hồi và không có lần thoát ra đã xác nhận quan sát
được** (một camera chết không thể nhìn một diện tích tiếp xúc vượt qua biên thoát ra), `T_degraded_max`
trên thực tế là **lối kết thúc tự động duy nhất** của nó — đó chính là lý do để nó vô hạn lại là cái lỗ
sắc bén hơn. Đơn vị vận hành **có thể** cấu hình một **trần thời gian ngắn hơn** cho biến thể lỗi so với
che khuất (chẳng có lý do gì giữ một cảnh báo chỉ-radar trong trọn ngân sách che khuất khi camera sẽ
không trở lại nếu không có người ra hiện trường xử lý), nhưng mặc định là một `T_degraded_max` duy nhất;
cả hai đều nằm trong bề mặt giới hạn của FR-20 ([tài liệu 01 FR-20](../01-requirements.vi.md#2-yêu-cầu-chức-năng),
[tài liệu 02 §7a](../02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu)).

Tên trạng thái `CAMERA_OCCLUDED_DEGRADED` được **giữ lại để bảo đảm tính liên tục** nhưng nay được định
nghĩa là *"camera không thể xác thực vết bên trong ROI (do che khuất **hoặc** lỗi) trong khi radar đối
chứng"* — cái tên đọc là "bị che khuất", nhưng ngữ nghĩa là "camera-không-xác-thực-được". Ở nơi sự phân
biệt có ý nghĩa (triển vọng bắt lại, mức độ leo thang) thì tài liệu nêu rõ nguyên nhân.

### B. Ma trận tương tác cảnh báo × chế độ cảm biến (hai vùng, được làm tường minh)

Vòng đời cảnh báo và chế độ tình-trạng-cảm-biến là **hai vùng đồng thời (concurrent regions)**. Tương tác
của chúng được **liệt kê đầy đủ**, không để mặc cho văn xuôi:

| Chế độ cảm biến → | **FULL** (cam+radar) | **CAMERA-ONLY** (radar chết) | **RADAR-ONLY** (camera chết) | **NEITHER** |
|---|---|---|---|---|
| **IDLE / TRACKING** | bình thường | khởi tạo OK; không có đối chiếu chéo radar; suy giảm + cảnh báo | **BLIND-TO-NEW** — không thể khởi tạo (không có lớp, không có cổng ROI trên ảnh); **cảnh báo nghiêm trọng** | **SAFE STATE** + cảnh báo nghiêm trọng |
| **CONFIRMED → WARN_ON** | bình thường | khởi tạo bình thường; không có khoảng giữ-khi-che-khuất | cảnh báo **đã** được khẳng định, nay camera chết → bước vào **trạng thái giữ khi camera không xác thực được (vết)** (§A): giữ trong khi radar đối chứng, **`T_degraded_max`**, **cảnh báo nghiêm trọng** | **SAFE STATE** (để trống) + cảnh báo nghiêm trọng |
| **WARN_HOLD** (mất vết, không thoát ra) | giữ trong khi còn đối chứng; → `CAMERA_OCCLUDED_DEGRADED` quá `T_occlusion` | chỉ có độ trễ (hysteresis) `T_hold` ngắn (không có radar để đối chứng) → xóa độ-tin-cậy-thấp lớn tiếng | **trạng thái giữ khi camera không xác thực được (vết)** (§A), `T_degraded_max`, **cảnh báo nghiêm trọng** | **SAFE STATE** + cảnh báo nghiêm trọng |
| **CAMERA_OCCLUDED_DEGRADED** | (nguyên nhân che khuất) bị giới hạn bởi `T_degraded_max`; `→ WARN_ON` khi bắt lại | tương tự, kèm lưu ý không có đối chiếu chéo radar | (nguyên nhân lỗi) bị giới hạn bởi `T_degraded_max`; **không** có lối thoát bắt lại | **SAFE STATE** + cảnh báo nghiêm trọng |
| **CLEARING** | xóa; xác nhận biển báo tắt | xóa; xác nhận biển báo tắt | xóa; xác nhận biển báo tắt | **SAFE STATE** + cảnh báo nghiêm trọng |

Cách đọc: **RADAR-ONLY là BLIND-TO-NEW khi rảnh và là một trạng thái giữ khi camera không xác thực được
(vết) khi đã có một cảnh báo dựng lên** — không bao giờ là một trạng thái vô hạn hay thầm lặng ở bất kỳ ô
nào. **NEITHER luôn luôn là SAFE STATE.** CAMERA-ONLY giữ được khả năng *khởi tạo* (chỉ riêng camera vẫn
có thể phân lớp + đặt cổng + theo vết) nhưng mất đi khoảng giữ-khi-che-khuất của radar và phép đối chiếu
chéo độc lập về vật thể đứng yên, nên một vết bị mất mà không còn đối chứng sẽ rơi xuống `T_hold` ngắn rồi
đến một lần xóa độ-tin-cậy-thấp lớn tiếng — không bao giờ là một lần xóa thầm lặng.

### C. Các thay đổi của máy trạng thái (Mermaid có thẩm quyền nằm ở tài liệu 02 §4)

1. Thêm các chuyển tiếp **`WARN_ON → CAMERA_OCCLUDED_DEGRADED`** và
   **`CONFIRMED → CAMERA_OCCLUDED_DEGRADED`** khi *lỗi camera xảy ra trong khi radar đối chứng* (hôm nay
   chỉ tồn tại `WARN_HOLD → CAMERA_OCCLUDED_DEGRADED` qua thời gian chờ che khuất). Trạng thái đích và
   giới hạn `T_degraded_max` của nó không đổi — việc này chỉ thêm **đường vào** do lỗi-camera để cái
   "khoảng giữ ngắn" vô hạn của §B được định tuyến vào trạng thái có giới hạn.
2. Cạnh `CAMERA_OCCLUDED_DEGRADED → WARN_ON` (camera bắt lại được vết) chỉ áp dụng cho nguyên nhân **che
   khuất**; nguyên nhân lỗi không có cạnh như vậy (theo §A).
3. Độc lập với §A/§B, thêm **`CLEARING → SAFE_STATE`** khi *trạng thái biển báo ≠ tắt sau lệnh CLEAR* (một
   biển báo bị kẹt-BẬT vật lý — lỗi duy nhất mà cơ chế tự ngắt an toàn không sửa được, vì biển báo sẽ
   không để trống): máy trạng thái rời CLEARING để sang SAFE STATE và phát một **leo thang bảo trì
   biển-báo-bị-kẹt** ([ADR-0011](ADR-0011-operator-concept-and-alarm-management.vi.md)) thay vì lặp vòng
   trong CLEARING. Điều này khép lại trạng thái duy nhất không có lối thoát được mô hình hóa trên nhánh
   sự cố của nó.

## Các phương án đã xét

### Phương án A: Để "khoảng giữ ngắn" của §B dưới dạng văn xuôi, tinh chỉnh một con số ma thuật trong mã
| Khía cạnh | Đánh giá |
|-----------|------------|
| Công sức bây giờ | **Không có** |
| Tính toàn vẹn của luận cứ an toàn | **Bị phá vỡ** — đường duy nhất watchdog không giới hạn được lại vô hạn đối với nguyên nhân lỗi-camera |
| Khả năng hiện thực | **Kém** — "trong thời gian ngắn" là một định thời an toàn không có giá trị lẫn định đoạt |

**Ưu điểm:** không phải viết gì.
**Nhược điểm:** mở lại, dưới cái nhãn "camera chết", đúng cái kẹt-BẬT vô hạn mà `T_degraded_max` được tạo
ra để khép lại; trao cho người xây dựng một tham số an toàn không xác định. Không thể chấp nhận đối với
một chức năng an toàn.

### Phương án B: Hợp nhất giới hạn (bất-kể-nguyên-nhân) + liệt kê ma trận cảnh báo × chế độ cảm biến *(được chọn)*
| Khía cạnh | Đánh giá |
|-----------|------------|
| Công sức bây giờ | Thấp–trung bình (một lần tổng quát hóa + một ma trận + hai cạnh Mermaid) |
| Tính toàn vẹn của luận cứ an toàn | **Khép kín** — không trạng thái giữ khi camera không xác thực được nào là vô hạn, bất kể nguyên nhân |
| Khả năng hiện thực | **Cao** — tích của hai vùng là một bảng, không phải một phép suy diễn |

**Ưu điểm:** một quy tắc cho một mối nguy; các vùng trực giao được làm tường minh nên việc xây dựng mang
tính tất định; mọi ô đều là một mục tiêu tiêm lỗi; tái sử dụng `T_degraded_max` (không có tham số lõi
mới, chỉ thêm một trần ngắn hơn tùy chọn cho biến thể lỗi).
**Nhược điểm:** tên trạng thái `CAMERA_OCCLUDED_DEGRADED` mô tả hơi thiếu so với ý nghĩa (nay đã rộng hơn)
của nó — được giảm nhẹ bằng cách nêu rõ định nghĩa ở mọi nơi nó xuất hiện lần đầu.

### Phương án C: Đổi tên trạng thái và tách thành hai trạng thái suy giảm riêng biệt
| Khía cạnh | Đánh giá |
|-----------|------------|
| Độ rõ ràng của tên gọi | **Cao** |
| Rủi ro xáo trộn / hồi quy | **Cao** — cái tên xuyên suốt ~10 tài liệu EN + các bản VI + sơ đồ |
| Lợi ích về hành vi so với B | **Không có** — giới hạn và định đoạt là y hệt |

**Ưu điểm:** cái tên sẽ khớp chính xác với ý nghĩa.
**Nhược điểm:** một lần đổi tên xuyên-tài-liệu lớn để đổi lấy số không lợi ích về hành vi, và hai trạng
thái ở nơi chỉ cần một sẽ mời gọi đúng cái lỗi xử-lý-phân-kỳ mà ADR này tồn tại để loại bỏ. Bị loại để
chọn trạng thái có giới hạn duy nhất của B kèm một định nghĩa được nêu rõ.

## Phân tích đánh đổi

Quan sát mang tính quyết định là **"camera bị che khuất, radar đối chứng" và "camera chết, radar đối
chứng" là cùng một mối nguy cảnh-báo-bị-giữ-mà-không-xác-thực**, nên chúng phải chung một giới hạn; khác
biệt thực sự duy nhất — liệu camera có thể trở lại hay không — là một chuyển tiếp duy nhất, chứ không phải
một quy tắc an toàn khác. Chữ "trong thời gian ngắn" bằng văn xuôi của Phương án A chính là cách mà một
thiết kế đã được rà soát vẫn xuất xưởng với một kẹt-BẬT vô hạn: cái lỗ vô hình vì nó được mô tả bằng lời,
không phải bằng một định thời. Phương án C mua được sự rõ ràng về tên gọi với cái giá là sự xáo trộn và
một đường mã thứ hai. Phương án B khép lại cái lỗ bằng tham số đã được định nghĩa sẵn, biến tích hai-vùng
thành một bảng mà người xây dựng có thể hiện thực trực tiếp, và gộp nhánh CLEARING kẹt-BẬT mồ côi vào mô
hình — tất cả đều kiểm thử được bằng tiêm lỗi (giết camera khi một cảnh báo đang hoạt động; xác nhận
`T_degraded_max` buộc một lần xóa lớn tiếng; ra lệnh CLEAR đối với một biển báo bị kẹt-BẬT; xác nhận leo
thang sang SAFE STATE). Đó cũng chính là nước đi an-toàn-khi-sự-cố/báo-động-lớn-khi-sự-cố
([ADR-0005](ADR-0005-fail-safe-and-system-safety.vi.md)) áp dụng cho hai nhánh chưa-được-mô-hình-hóa cuối
cùng.

## Hệ quả

- **Dễ hơn:** không một cảnh báo khi camera không xác thực được nào có thể kẹt BẬT vô hạn, dù camera bị
  chắn hay chết; máy trạng thái có thể hiện thực được mà không cần suy diễn hành vi xuyên-vùng; nhánh
  CLEARING kẹt-BẬT có một lối thoát được xác định; chỉ một giới hạn để tinh chỉnh và tiêm lỗi, không phải
  hai.
- **Khó hơn:** tên `CAMERA_OCCLUDED_DEGRADED` nay cần được nêu rõ định nghĩa đã mở rộng của nó ở nơi nó
  xuất hiện; thêm một chuyển tiếp vào và cạnh CLEARING→SAFE_STATE để hiện thực và kiểm thử; một trần thứ
  hai (ngắn hơn) tùy chọn cho biến thể lỗi cần phơi ra qua cấu hình (trong các giới hạn của FR-20).
- **Phần còn lại (residual):** sau một lần buộc xóa `T_degraded_max` đối với một chiếc xe *thực sự còn
  hiện diện nhưng camera đã chết*, mối nguy là có thật, không được cảnh báo, và **không thể cảnh báo lại
  cho đến khi camera được sửa** (RADAR-ONLY không thể khởi tạo). Đây là một **phần còn lại được nêu rõ,
  do người trực sở hữu** — lần buộc xóa trao một mối nguy đang sống đã biết cho người trực (CCTV/tuần tra)
  kèm leo thang mức cao nhất; đó là định đoạt trung thực, không phải một định đoạt thầm lặng, và thời gian
  phản hồi của nó là mối quan tâm của NFR-15 /
  [ADR-0011](ADR-0011-operator-concept-and-alarm-management.vi.md). Được theo dõi tại
  [tài liệu 04 R18](../04-risk-and-safety.vi.md#1-bảng-đăng-ký-rủi-ro) (mở rộng sang nguyên nhân lỗi-camera).
- **Xem xét lại khi:** dữ liệu hiện trường lượng hóa được camera hỏng giữa-cảnh-báo xảy ra thường xuyên
  đến đâu và các lần che khuất thực-sự-còn-hiện-diện kéo dài bao lâu (tinh chỉnh riêng các trần che khuất
  và lỗi), hoặc một bộ giám sát tình trạng phong phú hơn có thể phân biệt một phát hiện đối chứng ở lề với
  một phát hiện ở làn thông xe ở cự ly xa (làm dịu toàn bộ mối quan tâm của §A — đó chính là phụ thuộc vào
  tiêu chí (b) của [ADR-0001](ADR-0001-sensing-modality.vi.md)).

## Hạng mục hành động

1. [ ] Tổng quát hóa `CAMERA_OCCLUDED_DEGRADED` thành *camera-không-xác-thực-được (che khuất **hoặc**
       lỗi)* và định tuyến **lỗi-camera-trong-khi-cảnh-báo** vào nó, bị giới hạn bởi `T_degraded_max`; cập
       nhật Mermaid ở [tài liệu 02 §4](../02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo)
       (hai chuyển tiếp vào + cạnh bắt lại được giới hạn vào nguyên nhân che khuất) và bảng chế độ suy
       giảm.
2. [ ] Thêm **ma trận tương tác cảnh báo × chế độ cảm biến** (§B) vào
       [tài liệu 02 §4](../02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo) như là bản
       liệt kê có thẩm quyền của hai vùng đồng thời; đối chiếu lại các hàng FMEA ở
       [tài liệu 04 §2](../04-risk-and-safety.vi.md#2-fmea-lite-kiểu-lỗi--tác-động--phát-hiện--phản-ứng)
       và bảng ở [ADR-0009 §B](ADR-0009-failsafe-placement-and-degraded-modes.vi.md) cho khớp với nó.
3. [ ] Hiện thực **`CLEARING → SAFE_STATE` khi biển-báo-kẹt-BẬT** (trạng thái ≠ tắt sau lệnh CLEAR) kèm
       một leo thang bảo trì biển-báo-bị-kẹt ([ADR-0011](ADR-0011-operator-concept-and-alarm-management.vi.md)).
4. [ ] Phơi ra **trần suy giảm cho lỗi-camera** (tùy chọn, ngắn hơn) như một tham số cấu hình có giới hạn
       (bề mặt FR-20, [tài liệu 02 §7a](../02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu));
       mặc định về một `T_degraded_max` duy nhất.
5. [ ] **Tiêm lỗi vào các ô mới:** giết camera trong khi một cảnh báo đang hoạt động (→ trạng thái giữ có
       giới hạn → xóa lớn tiếng `T_degraded_max`); giết camera ở WARN_HOLD; ra lệnh CLEAR đối với một biển
       báo bị kẹt-BẬT (→ SAFE STATE + leo thang biển-báo-bị-kẹt). Bổ sung vào bộ nghiệm thu
       ([tài liệu 01 §5](../01-requirements.vi.md#5-chỉ-số-đánh-giá--tiêu-chí-nghiệm-thu)).
