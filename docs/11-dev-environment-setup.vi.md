# 11 — Sổ tay thiết lập môi trường lập trình (ba môi trường xây dựng)

**Dự án:** Hệ thống cảnh báo tự động cho làn dừng xe khẩn cấp (ESW / ELMS)
**Trạng thái:** Sổ tay sống — thực thi lần đầu trên máy của trưởng nhóm phần mềm ngày 09-07-2026 (§5).
**Cập nhật lần cuối:** 09-07-2026
**Sở hữu:** cách một thành viên nhóm có được bộ công cụ hoạt động cho từng module trong ba module xây dựng.
**Sử dụng:** [tài liệu 02 §8](02-system-architecture.vi.md#8-công-nghệ-đề-xuất-mang-tính-chỉ-dẫn-không-ràng-buộc) (công nghệ), [tài liệu 10](10-if4-sign-controller-firmware-spec.vi.md) (firmware IF-4), [sổ tay spike](../software/spikes/README.vi.md) (cổng D3), [ADR-0015](adr/ADR-0015-state-machine-implementation-strategy.vi.md).

> 🇬🇧 English version: [11-dev-environment-setup.md](11-dev-environment-setup.md).

Dự án có **ba module lập trình được**, mỗi module cần một môi trường riêng:

| Module | Vai trò trong kiến trúc | Môi trường |
|---|---|---|
| **Camera AI** | Bộ xử lý biên (edge) — Kendryte **K230** chạy CanMV/MicroPython; [`software/esw/`](../software/README.md) được triển khai lên đó **giống hệt từng byte** (ADR-0015 D3) | CanMV IDE + ảnh firmware + `mpremote` |
| **Server CoreIOT** | Tầng **giám sát** TMC — đo xa IF-6/7 chiều lên, lệnh IF-8/9/10 chiều xuống ([ICD §4–5](08-interface-control-document.vi.md)); **phi-an-toàn theo thiết kế** (ADR-0002) | Tài khoản CoreIOT + mã truy cập thiết bị + `paho-mqtt` |
| **ESP32 (YoloUno)** | **Bộ điều khiển biển báo** — cơ chế tự ngắt an toàn IF-4 đặc tả trong [tài liệu 10](10-if4-sign-controller-firmware-spec.vi.md) | PlatformIO + [`firmware/sign-controller/`](../firmware/sign-controller/README.md) |

Thứ tự dưới đây là có chủ đích: §1 (nền chung) mở khóa mọi thứ; §2–§4 độc lập với nhau
và có thể làm theo từng người khi phần cứng/tài khoản về đến.

---

## 1. Nền chung (mọi máy, ~10 phút)

1. **Git + Python ≥ 3.10** (khuyến nghị 3.12). Các bảng kiểm thử mô phỏng **chỉ dùng
   thư viện chuẩn một cách có chủ đích** (SUT phải giữ trong tập con an toàn cho
   MicroPython), nên phần lõi không có `requirements.txt` — các lệnh pip bên dưới chỉ
   dành cho công cụ *hướng phần cứng*.
2. Clone và chứng minh nhánh phần mềm chạy được:

   ```
   git clone https://github.com/tritinpho/emergency-stop-warning-system
   cd emergency-stop-warning-system
   python software/run_tests.py             # 43 kịch bản, exit 0
   python software/run_perception_tests.py  # và bốn bảng còn lại tương tự
   python software/tools/mp_safe_check.py software/esw
   ```

3. Cài các công cụ hướng phần cứng:

   ```
   python -m pip install --user esptool mpremote platformio paho-mqtt
   ```

   **Lưu ý PATH trên Windows:** script của pip `--user` nằm ở
   `%APPDATA%\Python\Python312\Scripts`, thường **không** có trong `PATH`. Hoặc thêm thư
   mục đó vào `PATH`, hoặc né hẳn vấn đề bằng cách gọi mọi công cụ dưới dạng module —
   `python -m esptool`, `python -m mpremote`, `python -m platformio` — như sổ tay này
   dùng xuyên suốt.

4. *(Tùy chọn, để chạy tập con MicroPython-unix tại máy)* **Docker** hoặc WSL. CI đã
   chạy các bảng Level-A/C + smoke dưới `micropython/unix:v1.28.0` trên mỗi lần push,
   nên bước này chỉ cần khi muốn tái hiện tại chỗ:

   ```
   docker run --rm -v "$PWD/software:/w" -w /w micropython/unix:v1.28.0 micropython run_tests.py
   ```

**Bạn biết §1 xong khi:** cả sáu bảng in dòng PASS và exit 0.

---

## 2. Module 1 — camera AI (K230, CanMV/MicroPython)

**Vì sao môi trường này quan trọng nhất:** K230 chạy *vòng lặp an toàn*. Tập con
[`software/esw/`](../software/README.md) đã được **chứng minh khả chuyển** (CI chạy nó
dưới cổng unix MicroPython thật), nhưng **ADR-0015 D3 vẫn là một giả định trên bo mạch
vật lý** — [phép đo thời gian K230](../software/spikes/README.vi.md) là cổng quyết định,
và nó đang *bị chặn vì chưa có bo mạch*. Thiết lập môi trường này chính là thứ mở khóa nó.

### 2.1 Công cụ phía máy tính

| Công cụ | Dùng để | Cài đặt |
|---|---|---|
| **CanMV IDE** | Xem camera, quản lý file, REPL | tải từ trang phát hành CanMV của Kendryte (`github.com/kendryte/canmv_ide`) |
| **`mpremote`** | Chép file + REPL qua USB serial, chạy script được | đã cài ở §1 (`python -m mpremote`) |
| **nncase** | chuyển bộ phát hiện → `kmodel` | **hoãn** theo nhánh công việc bộ phát hiện (ADR-0003); `pip install nncase nncase-kpu` khi bắt đầu |

### 2.2 Khởi động bo mạch

1. **Ảnh firmware:** tải ảnh CanMV-K230 đúng biến thể bo mạch của nhóm (phát hành
   Kendryte: `github.com/kendryte/canmv_k230`; bo của Sipeed cũng có biến thể riêng —
   ghi lại **đúng phiên bản** đã nạp, mẫu báo cáo spike có hỏi).
2. **Ghi vào microSD** (K230 khởi động từ SD): ghi file `.img` bằng balenaEtcher /
   Rufus / `dd`. Cắm thẻ, cấp nguồn qua USB-C.
3. **Cổng nối tiếp:** bo mạch hiện ra như một cổng USB-CDC (`COMx`). Kiểm tra:

   ```
   python -m mpremote connect list
   python -m mpremote connect COMx repl     # Ctrl-] để thoát
   ```

4. **Triển khai SUT** (chỉ tập con xuất xưởng — harness không bao giờ được triển khai):

   ```
   python -m mpremote connect COMx fs cp -r software/esw :/sdcard/esw
   ```

   (Một số bản CanMV gắn hệ thống file ghi được ở `/flash` thay vì `/sdcard` — `fs ls :/`
   cho biết; chỉnh đích tương ứng.)

### 2.3 Cổng nghiệm thu — chạy phép đo thời gian

Đây mới là *sản phẩm bàn giao* thực sự của môi trường camera (ADR-0015 AI#1):

```
python -m mpremote connect COMx fs cp software/spikes/k230_timing_spike.py :/sdcard/
# rồi làm theo software/spikes/README.vi.md §4: bật demo YOLO trước (tạo tranh chấp
# KPU/heap thật), chạy spike ở phiên thứ hai, ghi lại bảng số + dòng VERDICT.
```

**Bạn biết §2 xong khi:** `mpremote repl` cho dấu nhắc MicroPython, `import esw` chạy
được trên bo, và spike in ra bảng số (còn *phán quyết* PASS/FAIL thuộc về quyết định
ADR-0015 D3, không thuộc sổ tay này).

---

## 3. Module 2 — server giám sát CoreIOT

**Chốt phạm vi trước (ADR-0002):** vòng lặp an toàn **không bao giờ phụ thuộc module
này**. Đo xa IF-6/7 là lưu-rồi-chuyển (mất kết nối thì xếp hàng tại chỗ,
[`esw/sink.py`](../software/esw/sink.py) chứng minh không mất gì), còn lệnh IF-8/9/10
được xác thực đầu-cuối trong [`esw/command.py`](../software/esw/command.py) — CoreIOT là
*đường truyền và bảng điều khiển*, không bao giờ là thẩm quyền. Vì vậy phần thiết lập
của module này là một tài khoản + một bài kiểm tra nhanh, không phải một tạo tác an toàn.

CoreIOT (`coreiot.io`) là nền tảng IoT Việt Nam xây trên **ThingsBoard** (theo chính tài
liệu của họ; do ADT vận hành, thuộc hệ sinh thái OhStem), nên API thiết bị theo quy ước
MQTT của ThingsBoard: **mã truy cập** thiết bị làm username MQTT (mật khẩu bị bỏ qua), đo
xa gửi lên `v1/devices/me/telemetry`, RPC server→thiết bị trên
`v1/devices/me/rpc/request/+`. Broker là **`app.coreiot.io:1883`** — đúng hằng số mà SDK
client chính thức của OhStem dùng (`ohstem-public/coreiot-client-sdk`).

> ⚠️ **Hạng mục mở cho quyết định tầng giám sát:** [ICD §2](08-interface-control-document.vi.md)
> đặc tả IF-6/7 là **MQTT qua TLS**, nhưng tính đến 09-07-2026 CoreIOT chỉ mở **1883
> thuần** (8883 đóng). Chấp nhận được cho đo xa trên bàn — kênh này phi-an-toàn và kênh
> lệnh có HMAC riêng (ADR-0012) — nhưng tư thế TLS phải được chốt (lộ trình CoreIOT, một
> relay chấm dứt TLS, hoặc broker khác) trước bất kỳ thí điểm hiện trường nào. Ghi lại ở
> đây để nó không âm thầm trở thành "chuyện đương nhiên".

### 3.1 Tài khoản + thiết bị

1. Đăng ký tại cổng CoreIOT (`app.coreiot.io/signup` — tự đăng ký được, nền tảng miễn
   phí cho giáo dục) và đăng nhập.
2. Tạo một thiết bị cho đơn vị bench của bạn (Devices → **Add device**), đặt tên theo
   site id sẽ dùng (ví dụ `SITE-DEV`).
3. Chép **mã truy cập** (access token) của thiết bị (trang thiết bị → *Manage
   credentials / Copy access token*). Coi nó như mật khẩu — nó không phải *khóa* bí mật
   theo nghĩa ADR-0012 (kênh lệnh có HMAC riêng), nhưng nó gác cổng ghi vào dashboard
   của bạn.

### 3.2 Bài kiểm tra nhanh

[`software/tools/coreiot_smoke.py`](../software/tools/coreiot_smoke.py) chứng minh đường
truyền theo ba bước — DNS/TCP (không cần thông tin đăng nhập), xác thực MQTT bằng token,
rồi phát **một bản tin nhịp tim IF-6 thật do bộ phát thật tạo ra** (`esw/telemetry.py`,
đóng dấu vân tay cấu hình §7a thật) và đăng ký chủ đề RPC (chiều mà ràng buộc IF-8/9/10
sẽ đi):

```
python software/tools/coreiot_smoke.py                          # chỉ kiểm tra kết nối
python software/tools/coreiot_smoke.py --token <ACCESS_TOKEN>   # đủ ba bước
python software/tools/coreiot_smoke.py --token ... --tls        # tư thế sản xuất (8883)
python software/tools/coreiot_smoke.py --token ... --wait-rpc 30  # + chứng minh server->thiết bị
```

**Bạn biết §3 xong khi:** script in `PASS: the IF-6 record landed on CoreIOT.` và mục
**Latest telemetry** của thiết bị trên dashboard hiện các trường `if`/`site_id`/
`sensor_mode`/`posture`/`state`.

**Cố ý chưa làm ở đây:** backend MQTT thật của hộp thư đi bền vững (máy bơm
[`esw/sink.py`](../software/esw/sink.py) chạy trên đường truyền này) là nhánh công việc
riêng — bài kiểm tra nhanh chứng minh con đường đã thông, chứ chưa xếp lịch cho chuyến xe.

**Tài liệu tham khảo hữu ích:** tài liệu CoreIOT (`coreiot.io/docs`, tiếng Việt); SDK
thiết bị của OhStem cho CoreIOT — Arduino/ESP32 `github.com/ohstem-public/coreiot-client-sdk`,
MicroPython `github.com/AITT-VN/yolouno_extension_core_iot` — là ví dụ thực hành tốt về
API thiết bị ThingsBoard, dù đo xa biên của ESW sẽ ràng buộc qua `esw/sink.py`, không qua
SDK kiểu ứng dụng.

---

## 4. Module 3 — bộ điều khiển biển báo ESP32 (YoloUno)

**Module này là gì:** đầu kia của vòng lặp an toàn — cơ chế tự ngắt an toàn IF-4
([tài liệu 10](10-if4-sign-controller-firmware-spec.vi.md)). Khung firmware hiện thực
hợp đồng tài liệu 10 **đã tồn tại** tại [`firmware/sign-controller/`](../firmware/sign-controller/README.md):
bản C phản chiếu `esw/if4.verify()`, chống phát lại hai lớp, quy tắc làm-trống-theo-độ-tươi,
các vector kiểm thử lúc khởi động sinh từ bộ mã hóa Python chuẩn, và một bench phía máy
tính chấm các hàng C1–C7 của tài liệu 10 §7.

**Bo mạch:** OhStem **Yolo:UNO** — ESP32-S3 **N16R8** (16 MB flash, 8 MB PSRAM, theo
chính định nghĩa bo PlatformIO của OhStem), khuôn dạng Uno, **USB-C native**
(`0x303A:0x1001` — Windows 10/11 không cần driver cầu UART), nút BOOT ở GPIO0, LED D13
trên GPIO48 và đèn RGB WS2812 trên GPIO45. Env YoloUno của firmware dùng hai đèn onboard
đó làm **"biển báo" bench không cần đấu dây** (LED/đèn đỏ = SHOW, tắt = trống). Registry
PlatformIO không có YoloUno;
[`firmware/sign-controller/boards/esp32s3-n16r8.json`](../firmware/sign-controller/boards/esp32s3-n16r8.json)
mang định nghĩa bo.

### 4.1 Biên dịch + nạp

```
cd firmware/sign-controller
python -m platformio run                        # biên dịch (lần đầu tải toolchain)
python -m platformio run -t upload              # nạp qua USB-C
python -m platformio device monitor -b 115200   # chờ thấy: BOOT ... / KEY dev ... / VECTORS PASS 16/16
```

Nếu không mở được cổng khi nạp: giữ **BOOT** (GPIO0), nhấn **RESET**, thả BOOT (vào chế
độ nạp thủ công), thử lại; xong nhấn RESET một lần để chạy.

*Bộ công cụ thay thế, để đầy đủ:* Arduino IDE dùng được qua gói bo của OhStem (URL Boards
Manager
`https://raw.githubusercontent.com/AITT-VN/ohstem_arduino_board/main/package_xcon_index.json`,
bo **"Yolo UNO (ESP32-S3)"**) — hợp cho thử nhanh, nhưng sản phẩm bàn giao bộ điều khiển
biển báo vẫn là dự án PlatformIO (tái lập được, chạy CI được). OhStem cũng phát hành
firmware **MicroPython** cho bo này (nạp qua trình duyệt tại `fw.ohstem.vn`, dùng cho IDE
khối lệnh của họ) — **không** phải thứ bộ điều khiển biển báo dùng: cơ chế tự ngắt an toàn
của tài liệu 10 là firmware C/Arduino ở đây, và nạp MicroPython của OhStem sẽ thay thế nó.

### 4.2 Bench cơ chế tự ngắt an toàn

Với bo đã nạp firmware trên `COMx`:

```
python tools/bench_send.py --port COMx          # C1, C2/C4, C5, C6, C7 chấm tự động
python tools/bench_send.py --port COMx --soak   # làm mới liên tục (demo / soak Tier-2)
```

Bench bắn **khung 29 byte thật từ bộ mã hóa Python thật** vào bo, nên PASS ở đây là cùng
một hợp đồng mà bảng Level-A ghim trong mô phỏng (SC-01/21/23/33/34/15).

**Bạn biết §4 xong khi:** log khởi động in `VECTORS PASS 16/16` và bench in
`bench: 5/5 PASS`. C3 (ngắt nguồn một hộp biên thật) và C8 (đọc-ngược IF-3 khi panel
kẹt) vẫn là kiểm thử trên giàn vật lý — xem
[bảng phù hợp](../firmware/sign-controller/README.md#conformance-status-doc-10-7).

---

## 5. Trạng thái máy — lần thực thi đầu (máy Windows 11 của trưởng nhóm phần mềm, 09-07-2026)

Do lần thực thi đầu của sổ tay này thực hiện; chạy lại các lệnh để tái hiện trên máy khác.

| Hạng mục | Trạng thái 09-07-2026 |
|---|---|
| Python 3.12.2 | ✅ có sẵn |
| esptool 5.3.1 · mpremote 1.28.0 · paho-mqtt 2.1.0 · PlatformIO 6.1.19 | ✅ đã cài (`--user`; lưu ý PATH ở §1.3) |
| Nền tảng PlatformIO `espressif32 @ 7.0.1` + toolchain ESP32-S3 | ✅ đã cài; `firmware/sign-controller` **biên dịch xanh** trên định nghĩa bo YoloUno N16R8 (RAM ~5,8 %) |
| Sáu bảng mô phỏng + `mp_safe_check` | ✅ tất cả PASS trên cây hiện tại |
| Kết nối tới broker CoreIOT | ✅ `app.coreiot.io:1883` DNS + TCP thông từ mạng này |
| Tài khoản CoreIOT + mã thiết bị | ⬜ việc của người dùng (§3.1) — rồi chạy bước 2–3 của smoke test |
| CanMV IDE + ảnh firmware K230 | ⬜ tải khi có bo trong tay (§2.1–2.2) |
| Quyền tiếp cận bo K230 | ⬜ ở Nhóm ACLAB ELMS — **đang chặn phép đo D3 của ADR-0015** |
| Bo YoloUno trong tay | ⬜ nạp + bench theo §4 khi có |
| Docker/WSL (`micropython-unix` tại máy) | ⬜ tùy chọn — CI đã bao phủ |

---

## 6. Thuật ngữ (EN glossary)

| VI | EN |
|---|---|
| môi trường lập trình / bộ công cụ | dev environment / toolchain |
| nạp (firmware) | flash (firmware) |
| cổng nối tiếp / REPL | serial port / REPL |
| mã truy cập thiết bị | device access token |
| máy chủ trung gian MQTT | broker (MQTT) |
| kiểm thử trên bàn (bench) | bench (test) |
| cơ chế tự ngắt an toàn | dead-man's switch |
| kiểm tra nhanh (smoke test) | smoke test |
