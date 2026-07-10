# 08 — Tài liệu Kiểm soát Giao diện (ICD v1)

> 🇬🇧 Bản gốc tiếng Anh: [08-interface-control-document.md](08-interface-control-document.md)

**Dự án:** Hệ thống cảnh báo tự động làn dừng xe khẩn cấp (ESW)
**Trạng thái:** Đề xuất / Bản nháp — **Tạo phẩm Giai đoạn 2** (đóng băng các ranh giới + lược đồ trước khi xây dựng song song)
**Cập nhật:** 2026-06-27
**Liên quan:** [02 kiến trúc §7](02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu) · [02 §7a mặt phẳng tham số](02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu) · [ADR-0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md) · [ADR-0010](adr/ADR-0010-operator-override-and-manual-control.vi.md) · [ADR-0012](adr/ADR-0012-security-and-threat-model.vi.md) · [ADR-0013](adr/ADR-0013-degraded-hold-unification.vi.md)

Tài liệu này cụ thể hóa các hợp đồng mà [tài liệu 02 §7](02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu)
để ở mức "mang tính chỉ dẫn." Đây là **ICD v1**: các **ranh giới giao diện, hình dạng thông điệp, trường,
đơn vị, và ngữ nghĩa phân phối/xác thực đều được cố định** để nhận diện, máy trạng thái, bộ chuyển đổi cơ
cấu chấp hành, bộ điều khiển biển báo, và TMC có thể được xây dựng song song mà không bị trôi lệch khi tích
hợp. **Mã hóa truyền** (protobuf so với JSON), các topic MQTT chính xác, và hồ sơ giao thức VMS cụ thể được
chủ ý **hoãn lại sang lần tích hợp đầu tiên** (Giai đoạn 4) — xem [§7](#7-cố-định-ở-v1-so-với-hoãn-lại-sang-tích-hợp).

> **Quản lý phiên bản.** ICD được đánh phiên bản theo SemVer; mỗi lược đồ thông điệp mang một `schema_ver`. Một
> thay đổi gây vỡ tương thích trên một trường đã cố định là một lần tăng phiên bản lớn (major) và là một quyết
> định cấp ADR. Các trường tùy chọn bổ sung là lần tăng phiên bản nhỏ (minor).

---

> ## ⚠ LƯU Ý GIAI ĐOẠN — bản dựng này CHỈ DÙNG CAMERA
>
> [ADR-0001](adr/ADR-0001-sensing-modality.vi.md) (hợp nhất camera + radar) đã bị **Bác bỏ ngày 2026-07-10**. Nguyên mẫu trên bàn
> (cấp trường) **chỉ dùng camera**. Mọi hành vi phụ thuộc radar được mô tả bên dưới — radar chứng thực,
> khoảng giữ-khi-che-khuất (`WARN_HOLD` / `CAMERA_OCCLUDED_DEGRADED`), `T_degraded_max`, và các chế độ
> cảm biến `FULL` / `RADAR-ONLY` — đều **đang tạm ngưng: mã nguồn vẫn giữ, nhưng không bao giờ chạy**,
> vì `corr` không bao giờ đúng khi không có kênh radar.
>
> Hệ quả được chấp nhận: **R5** (mù ban đêm/mưa/sương mù) **không còn biện pháp giảm thiểu** và khả năng
> phát hiện ban đêm/bất lợi **không được tuyên bố**; **R20** — xe bị che khuất bị xóa sau `T_hold`
> (~10 giây), biển báo tắt trong khi mối nguy vẫn còn; **R21** — thiết bị nằm vĩnh viễn ở `CAMERA_ONLY`,
> do đó vĩnh viễn `DEGRADED`. Xem [tài liệu 04](04-risk-and-safety.vi.md).
>
> Nội dung radar bên dưới là **thiết kế mục tiêu cấp sở**, không phải bản dựng của giai đoạn này.

## 1. Danh mục giao diện

```
        IF-1            IF-2              IF-3                 IF-4 (auth, ≥DSD link)
 sensors ───▶ perception ───▶ state machine ───▶ actuator abstraction ═══▶ sign controller ──▶ sign
                                  ▲  │                  ▲                         ▲
                          health  │  │ IF-3            IF-5 force-safe ───────────┘
                          monitor ┘  │ (status read-back)
                                     │
        ┌────────────────────────────┴───── edge box ─────────────────────────────┐
        │  IF-6 heartbeat · IF-7 events (store-and-forward) ──▶ TMC                 │
        │  TMC ──▶ IF-8 config (signed) · IF-9 OTA (signed) · IF-10 override (auth) │
        └──────────────────────────────────────────────────────────────────────────┘
```

| IF | Giữa | Hướng | Trọng yếu an toàn? | Truyền tải (mang tính chỉ dẫn) | Phân phối |
|----|---------|-----------|------------------|------------------------|----------|
| **IF-1** | Cảm biến → Nhận diện | vào | có (vòng lặp) | trong tiến trình / driver SDK | streaming |
| **IF-2** | Nhận diện → Máy trạng thái | vào | có (vòng lặp) | trong tiến trình / IPC | streaming |
| **IF-3** | Máy trạng thái ↔ Trừu tượng hóa cơ cấu chấp hành | vào/ra | có (vòng lặp) | trong tiến trình / IPC | yêu cầu + đọc-lại trạng thái |
| **IF-4** | Thiết bị biên → **Bộ điều khiển biển báo** | ra | **có — mang an toàn khi sự cố** | liên kết hiện trường (cáp / RF), **được xác thực** | **khẳng định làm mới** mỗi `T_assert_refresh`; làm trống khi mất trong `T_signhold` |
| **IF-5** | Bộ giám sát tình trạng → Bộ điều khiển biển báo / cơ cấu chấp hành | ra | **có** | đường ép-về-an-toàn độc lập | lệnh (ép-về-an-toàn) |
| **IF-6** | Biên → TMC | ra | không | MQTT/TLS | định kỳ, lưu-và-chuyển |
| **IF-7** | Biên → TMC / kiểm toán | ra | không | MQTT/TLS | **lưu-và-chuyển, có thứ tự, bền bỉ** |
| **IF-8** | TMC → Biên (cấu hình) | vào | có (nội dung) | HTTPS / MQTT, **được ký** | yêu cầu + xác nhận; **thiết bị thực thi giới hạn §7a** |
| **IF-9** | TMC → Biên (OTA) | vào | có (nội dung) | HTTPS, **được ký** | theo giai đoạn; **hoãn lại khi cảnh báo đang hoạt động** |
| **IF-10** | TMC → Biên (override) | vào | **có** | **cùng kênh được gia cố như IF-8/9**, được xác thực | biên trung chuyển, **làm mới (không chốt)**, tự hết hạn |

**Vòng lặp an toàn là IF-1→IF-2→IF-3→IF-4** và chạy cục bộ tại biên; IF-6..IF-10 là giám sát và **không bao
giờ nằm trong đường an toàn** (NFR-06, [ADR-0002](adr/ADR-0002-edge-vs-cloud-processing.vi.md)). Một sự cố
TMC không thể làm vòng lặp mất an toàn.

---

## 2. Các giao diện vòng lặp nội bộ (IF-1 … IF-3, IF-5)

### IF-2 — Sự kiện phát hiện / vết (Nhận diện → Máy trạng thái)
Là hợp đồng mà **mô phỏng cấp-sự-kiện** ([doc 07 §2](07-simulation-methodology.vi.md)) cấp dữ liệu vào. Một thông điệp cho mỗi đối tượng được theo dõi trên mỗi chu kỳ:

| Trường | Kiểu | Đơn vị / ghi chú |
|-------|------|---------------|
| `track_id` | string/uint | ổn định trong suốt vòng đời của bộ theo dõi |
| `class` | enum | `car·truck·bus·motorcycle·person` |
| `footprint` | polygon / bbox | vùng tiếp xúc mặt đất (ưu tiên) hoặc bbox trên ảnh |
| `in_roi` | float | **mức chồng lấn theo tỷ lệ** của footprint với đa giác ROI (cổng ≥ 0.5, [doc 02 §4](02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo)) |
| `range_m` | float | mét (radar) — **luôn vắng mặt trong giai đoạn này** ([ADR-0001](adr/ADR-0001-sensing-modality.vi.md) bị Bác bỏ) |
| `speed_kph` | float | km/h; có dấu theo hướng tới/rời |
| `sensor_source` | enum/flags | `camera·radar·fused` — cho máy trạng thái biết nguồn đối chứng. **Giai đoạn này chỉ phát ra `camera`**; `radar`/`fused` là các giá trị cấp sở, nên `corr` không bao giờ đúng và khoảng giữ-khi-che-khuất không bao giờ kích hoạt (R20) |
| `ts` | timestamp | **tuyệt đối**, được kỷ luật bằng GNSS/PPS (NFR-16) |

### IF-3 — Lệnh biển báo + đọc-lại trạng thái (Máy trạng thái ↔ Trừu tượng hóa cơ cấu chấp hành)
- Lệnh: `SHOW(message_id)` | `CLEAR` | `STATUS?`
- `STATUS?` trả về `{ state: ON|OFF|FAULT, lamp_ok: bool, message_id?, ts }`
- Trừu tượng hóa cơ cấu chấp hành là **bộ khẳng định duy nhất** của một cảnh báo; **sự vắng mặt** của một khẳng định đang hoạt động tự thân đã là an toàn khi sự cố theo kiến tạo. Nó dịch IF-3 thành khẳng định làm mới IF-4 và đọc lại trạng thái. Hoán đổi được phần phụ trợ (bảng LED riêng / VMS, [ADR-0004](adr/ADR-0004-warning-actuator-integration.vi.md)).

### IF-5 — Ép-về-an-toàn độc lập (Bộ giám sát tình trạng → bộ điều khiển/cơ cấu chấp hành)
Một đường đưa biển báo về **trống** **mà không định tuyến qua máy trạng thái** ([ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.vi.md)) — dùng khi máy trạng thái bị kẹt cứng. Nằm nghiêm ngặt ở phía hạ lưu của máy trạng thái.

---

## 3. IF-4 — giao thức `SHOW` làm mới của liên kết biển báo (giao diện mang an toàn khi sự cố)

Đây là giao diện chịu lực an toàn nhiều nhất: biển báo nằm **cách ≥ DSD về phía thượng lưu** qua một liên kết
300 m+, và **cơ chế tự ngắt an toàn nằm trong bộ điều khiển biển báo** ([ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md)).

**Thông điệp khẳng định** (thiết bị biên → bộ điều khiển biển báo, mỗi `T_assert_refresh`):

| Trường | Kiểu | Ghi chú |
|-------|------|-------|
| `assertion` | enum | `SHOW(message_id)` \| `NONE` |
| `seq` | uint | đơn điệu — **chống phát lại** |
| `nonce` | bytes | **chống phát lại** |
| `cfg_ver` | hash | dấu vân tay cấu hình đang hoạt động |
| `ts` | timestamp | tuyệt đối |
| `auth_tag` | bytes | **HMAC/chữ ký trên toàn thông điệp** ([ADR-0012](adr/ADR-0012-security-and-threat-model.vi.md)) |

**Quy tắc của bộ điều khiển (cơ chế tự ngắt an toàn):** hiển thị `SHOW(message_id)` **chỉ** trong khi một khẳng
định *mới, hợp lệ, được xác thực* đến trong vòng `T_signhold`; ngược lại thì **làm trống**. "Hợp lệ" = `auth_tag`
tốt **và** `seq`/`nonce`/`ts` nằm trong cửa sổ chống phát lại. Do đó: máy trạng thái sập → biên ngừng làm mới →
làm trống; thiết bị biên chết → làm trống; liên kết bị cắt/nghẽn → làm trống; `SHOW` bị giả mạo/phát lại → bị từ
chối (xác thực/phát lại) → làm trống.

**Định thời** được chi phối bởi [doc 02 §7a](02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu): `T_assert_refresh`
≤ ¼·`T_signhold`; `T_signhold` đồng thời là thời gian BẬT-cũ tối đa sau một lỗi cứng và là khoảng hở tối thiểu
làm trống một cảnh báo hợp lệ, nên nó được tinh chỉnh theo độ mất gói/độ trễ của **liên kết hiện trường** (việc
kiểm chứng qua khoảng cách xa là **bị hoãn sang hiện trường**, [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md)).

**Lưu ý về VMS chốt trạng thái.** Một VMS bên thứ ba không thể tuân theo hợp đồng làm mới sẽ lùi về *watchdog +
CLEAR chủ động + đọc-lại trạng thái*, với một BẬT-cũ dư = chu kỳ lệnh của người vận hành; NFR-01 được **định mức**
cho phần phụ trợ đó ([ADR-0004](adr/ADR-0004-warning-actuator-integration.vi.md), [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md)).

**Hòa giải baseline ACLAB ELMS ([ADR-0016](adr/ADR-0016-repo-consolidation-and-perception-source.vi.md)).**
Đường biển báo hiện tại của đội phần cứng — một lệnh `LED:ON`/`LED:OFF` bị ESP32 **chốt** qua Wi-Fi/TCP và một
broker MQTT CoreIoT ([`firmware/k230-detector/esp32-legacy/`](../firmware/k230-detector/README.md)) — **không
tuân thủ IF-4**: không làm mới, không làm trống theo `T_signhold`, không xác thực, và định tuyến tín hiệu
an-toàn-tới-hạn qua một **broker đám mây** (vi phạm quy tắc cục bộ tại biên,
[ADR-0002](adr/ADR-0002-edge-vs-cloud-processing.vi.md)). Nó **bị thay thế** bởi cơ chế tự ngắt an toàn
[`firmware/sign-controller`](../firmware/sign-controller/README.md). ESP32 vốn đã nằm đúng chỗ đặt cơ chế này,
nên đây là thay đổi hành-vi-firmware, không phải thiết kế lại (RQ-H2, [tài liệu 09 §1a](09-software-hardware-handoff.vi.md)).

---

## 4. Các giao diện Biên → TMC (IF-6, IF-7) — không trọng yếu, lưu-và-chuyển

> Liên kết **CoreIoT MQTT** của ACLAB ELMS (ThingsBoard) là kênh mang cụ thể cho **IF-6/IF-7 ở đây** — chỉ
> telemetry giám sát, và bị **hạ cấp khỏi đường điều-khiển-biển-báo** ([ADR-0016](adr/ADR-0016-repo-consolidation-and-perception-source.vi.md)):
> một nhịp tim bị thiếu là cách TMC phát hiện sự cố, nhưng MQTT **không bao giờ** mang lệnh `SHOW`/`CLEAR`
> (đó là IF-4). Việc chuyển chế độ Ngày/Đêm của họ chấp nhận được như một gợi ý từ telemetry, nhưng **thời gian
> tuyệt đối cho kiểm toán vẫn là GNSS/PPS** (RQ-H5 / NFR-16), không đồng bộ từ đám mây.

### IF-6 — Nhịp tim
Nhịp cố định; mang theo tình trạng **và tư thế** để một thiết bị suy giảm không bao giờ có thể trông như khỏe mạnh:

| Trường | Kiểu | Ghi chú |
|-------|------|-------|
| `site_id` | string | |
| `fw_ver` `cfg_ver` `model_ver` `calib_ver` | hash | **dấu vân tay phiên bản** (R10 kiểm toán, [doc 02 §7](02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu)) |
| `subsystem_health[]` | danh sách | theo từng camera/radar/tính toán/liên kết/biển báo — **không có hệ con radar trong giai đoạn này** |
| `sensor_mode` | enum | `FULL·CAMERA-ONLY·RADAR-ONLY·NEITHER` ([ADR-0009 §B](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md), ma trận [ADR-0013](adr/ADR-0013-degraded-hold-unification.vi.md)). **Chỉ `CAMERA-ONLY` và `NEITHER` là đạt tới được trong giai đoạn này** — do đó thiết bị báo trạng thái `DEGRADED` vĩnh viễn (R21) |
| `posture` | enum | `NORMAL·OVERRIDDEN·BLIND-TO-NEW·CAMERA_OCCLUDED_DEGRADED·SAFE_STATE` |
| `drift_status` | enum | phán quyết của bộ giám sát trôi (FR-10, R15) |
| `state` | enum | trạng thái cảnh báo hiện thời |
| `ts` | timestamp | tuyệt đối |

### IF-7 — Sự kiện kích hoạt / xóa / lỗi (kiểm toán)
Lưu-và-chuyển, **có thứ tự và bền bỉ** (sống sót qua sự cố, đồng bộ một cách cơ hội):

| Trường | Kiểu | Ghi chú |
|-------|------|-------|
| `site_id` | string | |
| `type` | enum | `activation·clear·low_confidence_clear·forced_clear(T_degraded_max)·fault·override·sign_stuck` |
| `severity` | enum | dẫn động phản ứng theo ConOps ([ADR-0011](adr/ADR-0011-operator-concept-and-alarm-management.vi.md)) |
| `evidence_ref?` | id | con trỏ tới một ảnh chụp sự kiện đã tối giản (không có video thô, NFR-10) |
| `cfg_ver` `model_ver` `calib_ver` | hash | dấu vân tay ràng buộc với sự kiện |
| `ts` | timestamp | tuyệt đối |

---

## 5. Các giao diện TMC → Biên (IF-8 cấu hình, IF-9 OTA, IF-10 override)

### IF-8 — Cấu hình (được ký)
Tải trọng = **tập con tinh chỉnh được theo từng địa điểm**; thiết bị **thực thi toàn bộ giới hạn §7a** trên mỗi trường (FR-20):

```
{ schema_ver, roi_polygon, T_dwell, T_hold, T_occlusion, T_person_debounce,
  speed_gate, message_set, T_override_max, sig }
```
- **Được ký**; thiết bị xác minh chữ ký, rồi **kiểm tra dải giá trị từng tham số so với [doc 02 §7a](02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu)** — ngoài giới hạn → **từ chối/kẹp, giữ giá-trị-tốt-cuối-cùng, cảnh báo** (FR-20, R16). Việc ký chặn được giả mạo; việc kiểm tra giới hạn chặn được lỗi của người vận hành.
- Được triển khai theo giai đoạn/kiểm định như một bản cập nhật; các **chốt chặn** an toàn (`T_watchdog`/`T_signhold`/`T_assert_refresh`/`T_degraded_max`/`T_activate`) là các hằng số có giới hạn với trần cứng theo §7a và **không** được tự do đẩy tới các giá trị làm vô hiệu hóa bất biến của chúng.

### IF-9 — OTA (được ký + quay lui)
```
{ image, version, rollback_token, sig }
```
- **Hoãn lại khi một cảnh báo đang hoạt động** (tập vết không rỗng) hoặc biển báo được đưa về một trạng thái trống đã biết **lớn tiếng với người vận hành** — không bao giờ là một lần bỏ âm thầm (FR-21). Các chỉ số **canary** sau cập nhật → **quay lui** về phiên bản đã ký cuối cùng khi có suy thoái.

### IF-10 — Override của người vận hành (được xác thực, không chốt)
Đi trên **cùng kênh được gia cố** như IF-8/9 ([ADR-0010](adr/ADR-0010-operator-override-and-manual-control.vi.md), [ADR-0012](adr/ADR-0012-security-and-threat-model.vi.md)):

```
{ command: force_on|force_off|mute, message_id?, reason_code, operator_id,
  expiry (≤ T_override_max), auth }
```
- **Force-on** được khẳng định bằng **chính nhịp tim `SHOW` làm mới**, được làm mới **bởi thiết bị biên tại chỗ** — không bao giờ chốt qua WAN; cơ chế tự ngắt an toàn vẫn làm trống nó khi giết-hộp / cắt-liên-kết / hết hạn.
- **Force-off / mute** mang theo một **cơ chế tự hết hạn bắt buộc**; khi đang hoạt động, tư thế nhịp tim là **OVERRIDDEN** (không phải "khỏe mạnh"), và nó **leo thang lại** nếu sống lâu hơn cửa sổ của nó.
- Các lệnh override ngoài chính sách (expiry > trần, `message_id` lạ, không có `reason_code`) bị **từ chối/kẹp** tại thiết bị (cơ chế FR-20).
- Override chỉ tác động **lên đầu ra biển báo** — nhận diện, hợp nhất, máy trạng thái, và nhật ký kiểm toán đều tiếp tục chạy, nên một lệnh override luôn có thể tái dựng được.

---

## 6. Các hợp đồng xuyên suốt

- **Xác thực & toàn vẹn** ([ADR-0012](adr/ADR-0012-security-and-threat-model.vi.md)): **liên kết biển báo (IF-4)** được xác thực (chống giả mạo, chống phát lại) — một mặt phẳng điều khiển làm sáng một biển báo bên đường không thể yếu hơn dữ liệu đo lường từ xa; IF-8/9/10 được ký/được xác thực trên một kênh được gia cố. Tuyên bố có phạm vi của NFR-09: *được xác thực chống giả mạo/phát lại trên các bề mặt đã liệt kê; sự từ chối (nghẽn/làm mù) được giảm thiểu về **an-toàn-làm-trống-và-báo-động**, chứ không phải được ngăn chặn.*
- **Thời gian** (NFR-16): tất cả `ts` đều **tuyệt đối**, từ một nguồn được kỷ luật bằng GNSS/PPS, duy trì qua các lần mất kết nối; đồng bộ tương đối giữa các cảm biến (dưới khung hình) cho hợp nhất. Không nhãn thời gian nào được thừa hưởng từ một đồng hồ hệ điều hành chạy tự do.
- **Dấu vân tay phiên bản**: mọi thông điệp liên quan đến an toàn (IF-4/6/7) mang theo `cfg_ver`/`model_ver`/`calib_ver` để một cuộc kiểm toán có thể tái dựng *thiết bị đang chạy cái gì* tại thời điểm sự kiện ([doc 02 §7](02-system-architecture.vi.md#7-giao-diện--hợp-đồng-ban-đầu), R10).
- **Ngữ nghĩa sự cố**: mất IF-4 → bộ điều khiển làm trống (cơ chế tự ngắt an toàn); mất IF-6/7 → xếp hàng cục bộ, vòng lặp không bị ảnh hưởng; IF-8 xấu/ngoài giới hạn → từ chối, giữ giá-trị-tốt-cuối-cùng; IF-9 suy thoái → quay lui.

---

## 7. Cố định ở v1 so với hoãn lại sang tích hợp

**Cố định bây giờ** (để việc xây dựng song song có thể tiến hành): **danh mục và ranh giới** giao diện, các **tập
trường, kiểu, đơn vị, và trạng thái bắt buộc/tùy chọn** của thông điệp, **ngữ nghĩa khẳng định làm mới + xác thực
IF-4**, **thực thi giới hạn §7a** trên IF-8, ngữ nghĩa override **không-chốt/tự-hết-hạn**, và các quy tắc xuyên
suốt về **thời gian + dấu vân tay**.

**Hoãn lại sang lần tích hợp đầu tiên (Giai đoạn 4), được theo dõi như các hạng mục mở:**
- **Mã hóa truyền** cụ thể — protobuf so với JSON cho IF-2/3/6/7; cây topic MQTT chính xác.
- **Hồ sơ giao thức VMS** cụ thể (kiểu NTCIP / API của nhà cung cấp) cho phần phụ trợ VMS-hiện-có, và các quy tắc ưu tiên phân xử của nó ([ADR-0004](adr/ADR-0004-warning-actuator-integration.vi.md) AI#2/#5).
- **Liên kết hiện trường vật lý** cho IF-4: **phương tiện mang nay đã được chọn — LoRa điểm-điểm** ([ADR-0014](adr/ADR-0014-sign-link-bearer.vi.md)); ngân sách mất-gói/độ-trễ/năng-lượng/xác-thực **và chu kỳ làm việc** của nó ở cự ly ≥ DSD — vốn đồng-quyết-định `T_signhold` — vẫn **bị hoãn sang hiện trường** ([ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md)).
- **Quản lý khóa** chính xác cho xác thực IF-4/8/9/10 (nguyên mẫu: khóa được cấp phát lúc đưa vào vận hành; quản lý khóa ở quy mô đội thiết bị là việc của hiện trường/sản-phẩm-hóa, [ADR-0012](adr/ADR-0012-security-and-threat-model.vi.md)).
- Nội dung **`message_set`** đã duyệt — chờ cổng tuân thủ QCVN 41 ([ADR-0004](adr/ADR-0004-warning-actuator-integration.vi.md) AI#4); nếu chỉ tồn tại một phần tử hợp pháp duy nhất, việc **đổi-thông-điệp** khi ùn tắc là không khả dụng và thiết kế chỉ-ức-chế.
