# 10 — Đặc tả firmware bộ điều khiển biển báo IF-4 (hiện thực hóa RQ-H2)

> 🇬🇧 Bản gốc tiếng Anh: [10-if4-sign-controller-firmware-spec.md](10-if4-sign-controller-firmware-spec.md)

**Dự án:** Hệ thống cảnh báo tự động làn dừng khẩn cấp (ESW / ELMS)
**Trạng thái:** Đề xuất — bàn giao do phần mềm soạn thảo cho đội phần cứng/firmware (Nhóm ACLAB ELMS).
**Cập nhật lần cuối:** 2026-07-07
**Sở hữu:** hành vi firmware của bộ điều khiển biển báo ESP32. **Tiêu thụ:** [ICD §3](08-interface-control-document.vi.md), [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md), [ADR-0012](adr/ADR-0012-security-and-threat-model.vi.md), [ADR-0014](adr/ADR-0014-sign-link-bearer.vi.md), [RQ-H2](09-software-hardware-handoff.vi.md).

Tài liệu này là hiện thực hóa ở mức firmware của **RQ-H2** (bộ điều khiển biển báo như một *điểm cuối thông minh*). Nó tồn tại vì liên kết của mẫu nguyên lý Tuần-1 là **nguy hiểm khi sự cố**: một lệnh bắn-một-lần `$NODE01|ALERT|STOP|A3#` + checksum khiến LED **chốt trạng thái**. Đó chính là mặt trái của luận điểm an toàn — một biển báo chốt trạng thái sẽ mắc kẹt ở trạng thái BẬT-cũ khi thiết bị biên hoặc liên kết chết. Cách sửa là một **thay đổi hành vi firmware, không phải thiết kế lại**: ESP32 vốn đã nằm đúng chỗ mà cơ chế tự ngắt an toàn phải trú ngụ ([ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md)). **Bản hiện thực tham chiếu là mã chạy được và đã được kiểm thử** trong kho này — [`software/esw/if4.py`](../software/esw/if4.py) (bộ mã hóa khung trên đường truyền + `verify()`) và [`software/harness/sign.py`](../software/harness/sign.py) (mô hình bộ điều khiển), được chạy qua các kịch bản **SC-21/22/23** (làm trống khi lỗi cứng) và **SC-33/34** (từ chối giả mạo / phát lại) trên bo mạch Cấp-A.

---

## 1. Một quy tắc duy nhất (cơ chế tự ngắt an toàn)

> Biển báo hiển thị `SHOW(message_id)` **chỉ** trong khi một khẳng định **mới, hợp lệ, được xác thực** đã đến trong vòng `T_signhold`. Ngược lại nó **làm trống**.

Các hệ quả phải giữ được **theo kiến tạo**, chứ không phải nhờ một lệnh nào đó được gửi đi:

- Máy trạng thái sập, thiết bị biên chết, liên kết bị cắt hoặc bị nghẽn → việc làm mới ngừng đến → biển báo làm trống trong vòng `T_signhold`.
- Một `SHOW` bị giả mạo hoặc bị phát lại → xác thực thất bại → bị bỏ qua → biển báo làm trống.

**Không có thông điệp "tắt"/"làm trống" nào, và firmware tuyệt đối không được thêm một thông điệp như thế.** TẮT là *sự vắng mặt* của một lần làm mới hợp lệ. Bất kỳ thiết kế nào đòi hỏi phải có một thông điệp để tắt biển báo đều là nguy hiểm khi sự cố, vì chính lỗi cần làm trống biển báo nhất (một thiết bị biên đã chết) lại đúng là lỗi không thể gửi được thông điệp đó.

## 2. Định dạng khung (bản có thẩm quyền — 29 byte, big-endian)

Chỉ một loại thông điệp duy nhất: một **khẳng định SHOW được xác thực**. Bố trí byte (xem `esw/if4.py`):

| Offset | Field | Size | Ý nghĩa |
|-------:|-------|-----:|---------|
| 0 | `version` | 1 | phiên bản giao thức = `1` |
| 1 | `msg_type` | 1 | `MSG_SHOW` = `1` (loại duy nhất) |
| 2 | `message_id` | 1 | chỉ số thông điệp QCVN-41 ([ADR-0004](adr/ADR-0004-warning-actuator-integration.vi.md)); `1` = `STOPPED_VEHICLE_AHEAD` |
| 3–6 | `seq` | 4 | bộ đếm đơn điệu — **chống phát lại (trong phiên)** |
| 7–10 | `nonce` | 4 | ngẫu nhiên theo từng khung (biên dùng `os.urandom`) |
| 11–14 | `cfg_ver` | 4 | dấu vân tay cấu hình đang hoạt động (kiểm toán, [R10](04-risk-and-safety.vi.md)); được xác thực nhưng **mờ đục** với bộ điều khiển |
| 15–20 | `ts_ms` | 6 | dấu thời gian phát, ms tính từ mốc thời gian đã thống nhất — **chống phát lại (xuyên phiên)** |
| 21–28 | `auth_tag` | 8 | **HMAC-SHA256** cắt ngắn trên các byte 0–20 |

Khung được chủ ý làm nhỏ gọn: thời gian chiếm sóng LoRa tỉ lệ với số byte tải, và thời gian chiếm sóng của IF-4 bị ràng buộc bởi chu kỳ làm việc (§6). **Kích thước được cố định tại đây vì nó chính là đầu vào của thời gian chiếm sóng** — đổi một trường sẽ đổi `T_signhold` (§6), nên đây là một thay đổi cấp ADR, không phải một chỉnh sửa firmware.

## 3. Thuật toán verify của bộ điều khiển

Trên mỗi khung nhận được, theo đúng thứ tự (bản phản chiếu của `esw/if4.verify` + `harness/sign.py`):

```
receive(frame, now):
    if link_down or frame is None:            return            # nothing arrived
    if len(frame) != 29:                      reject("len")
    if frame[0] != 1 or frame[1] != 1:        reject("proto")   # version / type
    tag  = HMAC_SHA256(key, frame[0:21])[0:8]
    if not constant_time_equal(tag, frame[21:29]): reject("auth")
    seq  = u32(frame[3:7]);  ts = u48(frame[15:21])
    if session_open and seq <= last_seq:      reject("replay")  # in-session monotonicity
    if abs(now_ms - ts) > REPLAY_WINDOW_MS:   reject("stale")   # cross-session freshness
    # accept:
    last_show_ts = now;  last_seq = seq;  message_id = frame[2]

update(now):                                   # runs continuously (the dead-man's switch)
    if last_show_ts is not None and (now - last_show_ts) <= T_signhold:
        sign_on()                              # a fresh valid SHOW is holding it
    else:
        sign_off();  last_seq = None           # session ends -> a legit reconnect may re-assert
```

- **So sánh tag theo thời-gian-hằng-định** — không thoát sớm ngay ở byte lệch đầu tiên (không tạo kênh rò rỉ định thời).
- **Đóng-cửa-khi-sự-cố với mọi lỗi phân tích/xác thực** — một khung hỏng hoặc không kiểm chứng được là một *thao tác rỗng* (no-op), không bao giờ là một lần chấp nhận nửa vời.

## 4. Chống phát lại — hai lớp bảo vệ, mỗi lớp cho một mối đe dọa

1. **Trong phiên (`seq` tăng nghiêm ngặt).** Trong khi biển báo đang sáng, một khung bị chụp lại rồi gửi lại (phát lại) hoặc một khung sai-thứ-tự/trùng-lặp có `seq ≤ last_seq` → bị từ chối. Chặn kẻ tấn công (hoặc một bộ lặp lỗi) *kéo dài* một cảnh báo đang sống bằng các byte cũ.
2. **Xuyên phiên (cửa sổ mới của `ts`).** Khi biển báo đã ở trạng thái trống (cửa sổ tự-ngắt đã trôi qua), `last_seq` được đặt lại, nên một **thiết bị biên tái kết nối hợp lệ** — ví dụ một hộp vừa khởi động lại có bộ đếm `seq` trong RAM khởi động lại từ giá trị thấp ([SC-15](../software/scenarios/catalogue.py)) — có thể khẳng định lại. Một **khung cũ bị phát lại vẫn bị chặn** vì `ts` của nó nằm ngoài `REPLAY_WINDOW`. Không có lần đặt lại này, chống phát lại đơn điệu ngây thơ sẽ khóa vĩnh viễn một thiết bị biên vừa khởi động lại; không có kiểm tra độ mới, lần đặt lại lại mở ra một lỗ hổng hồi sinh. Cả hai đều bắt buộc.

`REPLAY_WINDOW` mặc định bằng `T_signhold` (một khung cũ hơn cửa sổ giữ là vô dụng và đáng ngờ). Độ trễ LoRa thực (~100 ms) ≪ `T_signhold`, nên các khung hợp lệ không bao giờ trượt kiểm tra độ mới.

## 5. Xác thực & khóa ([ADR-0012](adr/ADR-0012-security-and-threat-model.vi.md))

- **HMAC-SHA256**, tag **cắt ngắn còn 8 byte (64 bit)** — đây là đánh đổi giữa thời gian chiếm sóng và an ninh (một tag đầy đủ 32 byte sẽ gần như gấp ba tải trọng). Sức kháng giả mạo 64 bit là đủ cho một nhịp tim ven đường sống ngắn ngủi; xem xét lại nếu mô hình đe dọa được siết chặt.
- **Khóa** = một **bí mật chia sẻ theo từng đơn vị**, được cấp phát **ngoài băng tần** (không qua sóng), lưu trong bộ nhớ an toàn của ESP32 (NVS có mã hóa flash), và **có thể xoay vòng**. Thiết bị biên và bộ điều khiển bắt cặp với nó chia sẻ một khóa. *(Cơ chế cấp phát khóa là một hạng mục bàn giao còn để mở — §8.)*
- `cfg_ver` nằm trong vùng được xác thực nhưng **mờ đục** với bộ điều khiển (được lặp lại để kiểm toán, không bao giờ được diễn giải), nên các khác biệt về cách biểu diễn cấu hình giữa các môi trường chạy không thể làm thay đổi một quyết định an toàn.

## 6. Thời gian & ngân sách thời gian chiếm sóng LoRa — `T_signhold` được *xác định* như thế nào

**Thời gian.** Kiểm tra độ mới xuyên phiên đòi hỏi đồng hồ bộ điều khiển nằm trong phạm vi `REPLAY_WINDOW` so với đồng hồ thiết bị biên (NFR-16). Hãy cấp một nguồn thời gian: GNSS/PPS tại biển báo, hoặc một đồng hồ được đồng bộ định kỳ từ biên. **Nếu không tồn tại một đồng hồ đủ tốt**, bộ điều khiển phải lùi về một `seq` đơn điệu *bền bỉ* trong bộ nhớ an toàn (không đặt lại khi khởi động lại) và bỏ kiểm tra độ mới — một sự suy giảm có ghi nhận, vì nó tái xuất hiện tình trạng khóa-kết-nối-lại mà lớp bảo vệ độ mới vốn đang giải quyết.

**Thời gian chiếm sóng.** Theo **Thông tư 08/2021/TT-BTTTT**, LoRa 433 MHz được miễn giấy phép ở mức **≤ 25 mW ERP** với chu kỳ làm việc **≤ 10 %** (lớp dữ liệu/gateway) hoặc **≤ 1 %** (lớp terminal) — việc phân lớp có tính chịu lực và chưa được xác nhận ([ADR-0014](adr/ADR-0014-sign-link-bearer.vi.md)). Vì `T_assert_refresh ≤ ¼·T_signhold`, tốc độ làm mới đặt ra một **sàn** cho `T_signhold`:

> thời gian chiếm sóng tính toán của **khung thực 29 byte** (BW 125 kHz, CR 4/5, header tường minh, bật CRC):

| SF | ToA (ms) | max refresh @10% | `T_signhold` floor @10% | `T_signhold` floor @1% |
|---:|---------:|:----------------:|:-----------------------:|:----------------------:|
| 7 | 66.8 | 1.50 Hz | **2.7 s** | 26.7 s |
| 8 | 123.4 | 0.81 Hz | 4.9 s | 49.4 s |
| 9 | 226.3 | 0.44 Hz | 9.1 s | 90.5 s |
| 10 | 411.6 | 0.24 Hz | 16.5 s | 164.7 s |

**Cách đọc:** chỉ **SF7 ở lớp 10 %** cho một sàn `T_signhold` (~2.7 s) vừa khít với chốt chặn đã cố định (`T_signhold` ≤ **3.0 s**, [doc 02 §7a](02-system-architecture.vi.md) / `esw/params.py`). Bất kỳ SF nào cao hơn — điều mà trần 25 mW ERP có thể **buộc** phải dùng để khép liên kết ≥315 m trong mưa — hoặc lớp terminal 1 % đều đẩy sàn lên tới mức từ vài giây đến vài chục giây, và điều đó **vô hiệu hóa cơ chế tự ngắt an toàn**. Đây là một *dự đoán tính toán*; phép thử thời gian chiếm sóng trên bàn thử của [ADR-0014](adr/ADR-0014-sign-link-bearer.vi.md) phải xác nhận nó trên chip SX1276 thực, và **920–923 MHz phải được đánh giá song song** như phương án dự phòng Phương-án-C. Do đó `T_signhold` **không phải là một hằng số firmware tự do** — nó được đặt từ thời gian chiếm sóng đo được + biên liên kết + lớp chu kỳ làm việc đã xác nhận, rồi cố định thành hằng số có giới hạn theo §7a.

## 7. Kiểm thử nghiệm thu firmware (nghiệm thu)

Firmware là đạt-chuẩn-RQ-H2 khi, trên giàn thử trên bàn:

| # | Kích thích | Hành vi biển báo yêu cầu | Phản chiếu |
|--:|----------|-------------------------|---------|
| C1 | Làm mới hợp lệ ở `T_assert_refresh` | sáng, ổn định, không nhấp nháy | SC-01 |
| C2 | Giết tiến trình của thiết bị biên (SM) | làm trống ≤ `T_signhold` | SC-21 |
| C3 | Tắt nguồn thiết bị biên | làm trống ≤ `T_signhold` | SC-22 |
| C4 | Cắt / nghẽn liên kết RF | làm trống ≤ `T_signhold` | SC-23 |
| C5 | Tiêm các khung `SHOW` bằng khóa sai | **không bao giờ sáng**; số lượt từ chối tăng dần | SC-33 |
| C6 | Phát lại một khung hợp lệ đã chụp sau khi trống | **không bao giờ sáng lại** | SC-34 |
| C7 | Khởi động lại thiết bị biên (`seq` mới, thấp) | sáng lại sau khi một lần làm mới hợp lệ quay về | SC-15 |
| C8 | Lệnh CLEAR so với một bảng bị kẹt-BẬT | báo cáo vẫn-BẬT qua đọc-lại trạng thái IF-3 | SC-24 |

C2–C4 và C5–C6 là hai nửa của RQ-H2: **làm trống khi lỗi cứng** và **từ chối giả mạo/phát lại**. Cả hai phải vượt qua trước khi thiết kế an toàn khi sự cố sẵn sàng cho nghiệm thu ([doc 03 §5 "Sau P4"](03-roadmap-and-phasing.vi.md)).

## 8. Firmware Tuần-1 phải ngừng làm gì, và các hạng mục bàn giao còn mở

**Ngừng (những chỗ đang chệch sang nguy hiểm khi sự cố):** (a) **không chốt trạng thái** — trạng thái LED phải được tính lại mỗi lần `update()` từ độ mới của việc làm mới, không bao giờ đặt-rồi-giữ; (b) **không kích hoạt bắn-một-lần** — một khung đơn lẻ không được tạo ra một trạng thái BẬT bền bỉ; (c) **checksum ≠ xác thực** — một checksum CRC/XOR chặn được hỏng dữ liệu, chứ không chặn được giả mạo; hãy dùng HMAC; (d) **không có lệnh "tắt"** — xem §1.

**Các hạng mục bàn giao còn mở (không thuộc quyền quyết định của phần mềm):**
1. Các phép thử trên bàn thử của [ADR-0014](adr/ADR-0014-sign-link-bearer.vi.md) — thời gian chiếm sóng SX1276 cho khung này, **lớp chu kỳ làm việc** (10 % so với 1 %), và tầm xa ≥315 m ở ≤25 mW ERP — giải quyết liệu 433 MHz có thể chứa cơ chế tự ngắt ở `T_signhold` ≤ 3 s hay không (§6 dự đoán *chỉ vừa đủ*, ở SF7/10 %).
2. Đánh giá **920–923 MHz** như phương án dự phòng Phương-án-C nếu (1) thất bại.
3. **Cơ chế cấp phát khóa** — cách nạp và xoay vòng bí mật chia sẻ theo từng đơn vị (§5).
4. **Nguồn thời gian của bộ điều khiển** — GNSS/PPS so với đồng bộ từ biên so với phương án dự phòng `seq` bền bỉ (§6).
