# spikes/ — các phép đo dùng-một-lần để chốt một quyết định

Các script nhỏ, độc lập, trả lời **một** câu hỏi còn bỏ ngỏ bằng **một con số**. Chúng
**không** thuộc hệ thống-đang-kiểm-thử (SUT) và **không** được nạp lên thiết bị chạy thật.

> 🇬🇧 Bản tiếng Anh: [README.md](README.md) là bản gốc.

---

# Sổ tay vận hành phép đo thời gian K230 — cổng quyết định ADR-0015 D3

**Ai chạy:** Nhóm ACLAB ELMS (phần cứng/firmware), trên board K230 thực.
**Ai sở hữu quyết định:** phía phần mềm (Tin) — kết quả **xác nhận hoặc bác bỏ** ADR-0015 D3.
**Trạng thái:** đang chờ quyền truy cập board. Công cụ ([`k230_timing_spike.py`](k230_timing_spike.py))
đã sẵn sàng và qua được phép chạy thử trên máy host; nhưng **con số quyết định phải đến từ K230** —
bộ thu gom bộ nhớ (GC) của CPython hoàn toàn khác của MicroPython, nên một kết quả PASS trên host
**không** phải là bằng chứng.

## 1. Vì sao cần phép đo này (quyết định đang được đặt cược)

[ADR-0015 **D3**](../../docs/adr/ADR-0015-state-machine-implementation-strategy.vi.md) đặt cược rằng
**một mã nguồn giống hệt từng byte trên MicroPython** có thể chạy vòng lặp an toàn trên cả máy host
lẫn K230 — **không cần lõi C riêng**. Cược này dựa trên một giả định chưa được kiểm chứng: rằng
**khoảng dừng thu gom bộ nhớ (dừng toàn bộ)** của MicroPython không bao giờ làm nghẽn vòng lặp nhịp
đủ lâu để gây hại. Điều này chưa từng được đo trên board dưới tải thực. Phép đo này thay giả định
bằng một con số.

- **PASS** → nạp một mã nguồn MicroPython duy nhất; đóng ADR-0015 AI#1 / ADR-0002 AI#3 / RQ-H4.
- **FAIL** → kích hoạt phương án dự phòng: chuyển vòng lặp an toàn (máy trạng thái + làm mới khung
  SHOW) sang **lõi C** (hoặc ESP32 ở đầu biển báo), giữ khối tri giác (perception) trên MicroPython.
  Dữ liệu đo sẽ chỉ ra *khâu nào* vượt định mức.

## 2. Các định mức thời gian (vì sao ngưỡng lại như vậy)

Thiết bị biên tái khẳng định biển báo bằng cách **làm mới một khung SHOW đã xác thực**; bộ điều
khiển biển **làm trống nếu không có khung SHOW hợp lệ mới đến kịp** (cơ chế tự ngắt an toàn của
IF-4). Từ [`esw/params.py`](../esw/params.py) (tài liệu 02 §7a):

| Hằng số | Giá trị | Ý nghĩa |
|---|---|---|
| chu kỳ nhịp | **0,1 s** (10 Hz) | một chu kỳ vòng lặp an toàn nhịp cố định (ADR-0015 D2) |
| `T_assert_refresh` | **0,5 s** | thiết bị biên phát khung SHOW mới ít nhất theo nhịp này |
| `T_signhold` | **2,0 s** | biển làm trống nếu không có SHOW hợp lệ trong cửa sổ này |
| `T_watchdog` | **30 s** | chốt chặn độc lập cho tình trạng kẹt-BẬT |

**Hệ số an toàn là 4×:** làm mới mỗi 0,5 s so với cửa sổ giữ 2,0 s nghĩa là thiết bị biên có thể lỡ
**ba lần làm mới liên tiếp** (~1,5 s) mà biển vẫn giữ sáng đúng. Để một khoảng dừng GC gây ra kết cục
*sai*, nó phải làm nghẽn vòng lặp **~1,5–2,0 s** — lớn gấp khoảng **40–100 lần** một khoảng dừng GC
điển hình của MicroPython (từ vài ms đến vài chục ms). Hướng sự cố là **an toàn khi sự cố
(fail-safe)**: một lần làm mới trễ gây **làm trống** sai (báo động giả / mất tính khả dụng), chứ
không bao giờ là bỏ sót âm thầm. Phép đo cho biết ta thực sự tiến sát cửa sổ đó đến đâu.

## 3. Cần đo cái gì

Dưới **tải thực, kéo dài**:
1. **Thời gian nghẽn nhịp (tick stall)** — thời gian thực thi công việc của một nhịp (máy trạng thái
   + cấp phát bộ nhớ), bao gồm mọi khoảng dừng GC xảy ra giữa nhịp *(đây là con số script in ra)*.
2. **Khoảng dừng GC** — thời lượng một lần `gc.collect()` dừng-toàn-bộ dưới áp lực bộ nhớ.
3. **Khoảng hở giữa hai lần làm mới (refresh gap)** *(quyết định, Tầng 2)* — thời gian thực tế giữa
   hai khung SHOW liên tiếp rời khỏi thiết bị biên; đây chính là thứ cơ chế tự ngắt an toàn "nhìn thấy".

## 4. Quy trình

**Điều kiện tiên quyết:** một board **K230** thực (CanMV/MicroPython) đã nạp bộ con `esw/`; **`kmodel`**
sản xuất (YOLO) + luồng camera (hoặc video đại diện chạy lặp) để KPU/CPU/bộ nhớ chịu **tranh chấp tài
nguyên thực**, không phải chạy rỗi. Ghi lại: xung nhịp K230, RAM/PSRAM, phiên bản CanMV/mpy, kích thước
`kmodel`, FPS.

### Tầng 1 — script phép đo (nhanh)
Đo các khoảng nghẽn nhịp do GC gây ra của chính vòng lặp an toàn, dưới tải tranh chấp YOLO chạy riêng.
1. Chép [`k230_timing_spike.py`](k230_timing_spike.py) lên board.
2. **Chạy demo YOLO trước** (để có tranh chấp KPU/CPU/bộ nhớ thực tế).
3. Chạy script phép đo trong một phiên CanMV thứ hai (hoặc từ `main.py`).
4. Để có bức tranh đầy đủ hơn, tăng `N_TICKS` (đầu script) từ 300 (~30 s) lên **~18000 (~30 phút)**
   rồi chạy lại — GC chậm / phân mảnh bộ nhớ chỉ lộ ra khi chạy bền.
5. Ghi lại bảng in ra + dòng **VERDICT** (kết luận).

### Tầng 2 — đo trên vòng lặp tích hợp (quyết định)
Cổng chuẩn-vàng: đo **vòng lặp triển khai thật**, không phải đo mô phỏng đại diện.
1. Trong firmware tích hợp (YOLO → tri giác → máy trạng thái → cơ cấu chấp hành), đóng dấu thời gian
   **mọi khung SHOW được phát**.
2. Trong một lần **chạy bền ≥ 2 giờ** với cảnh thực (kèm một **đợt nhiều xe cùng lúc** để gây áp lực
   cấp phát bộ nhớ), ghi lại: **khoảng hở SHOW lớn nhất**, độ dao động chu kỳ nhịp (max / p99 / p999),
   khoảng dừng `gc.collect()` lớn nhất.
3. Nếu được, gắn đo trên **bộ điều khiển biển ESP32** để ghi lại mọi lần **làm trống** thực tế (khoảng
   hở làm mới > `T_signhold`) — đây là phép kiểm an toàn theo chân trị (ground-truth).

## 5. Ngưỡng chấp nhận

Kết luận của script dựa trên **thời gian nghẽn nhịp tệ nhất so với `T_assert_refresh` (500 ms)** — cố
tình đặt bảo thủ (một khoảng nghẽn nhỏ hơn một chu kỳ làm mới thì không thể tiến gần cửa sổ giữ 2 s):

| Chỉ số | PASS (xác nhận D3) | MARGINAL (cần soi / chạy bền lại) | FAIL (dự phòng) |
|---|---|---|---|
| **Nghẽn nhịp lớn nhất** *(VERDICT của script)* | < **50 ms** | 50 – 250 ms | ≥ **250 ms** |
| **Khoảng dừng `gc.collect()` lớn nhất** | < 50 ms | 50 – 200 ms | > 200 ms |
| **Khoảng hở SHOW lớn nhất** *(Tầng 2)* | < **1,0 s** (dư ≥ 2×) | 1,0 – 1,8 s | ≥ 1,8 s |
| **Độ dao động chu kỳ nhịp (max)** | < 0,2 s (không lỡ 2 nhịp) | 0,2 – 0,5 s | > 0,5 s kéo dài |
| **Có làm trống sai** *(Tầng 2)* | **không** | — | **có bất kỳ** |

**Cổng cứng:** bất kỳ lần làm trống sai nào quan sát được, hoặc khoảng hở SHOW lớn nhất ≥ `T_signhold`
(2,0 s), đều là **FAIL** tự động bất kể các con số khác. Kết quả **MARGINAL** → chạy lại dưới tải nặng
hơn và chạy bền lâu hơn trước khi chốt D3.

## 6. Diễn giải kết quả → quyết định

- **PASS** → xác nhận MicroPython cho vòng lặp an toàn. Nạp mã nguồn giống hệt từng byte duy nhất; đánh
  dấu ADR-0015 D3 **đã kiểm chứng**; đóng ADR-0002 AI#3 / RQ-H4.
- **MARGINAL** → chấp nhận được nhưng chưa chốt. Chạy bền lại (§4, ≥ 30 phút / ≥ 2 giờ) dưới tải cảnh
  nặng hơn; nếu vẫn cận biên, lập kế hoạch cho phương án dự phòng.
- **FAIL** → **phương án dự phòng lõi C**: giữ khối tri giác (YOLO + bám vết) trên MicroPython, chuyển
  **máy trạng thái + làm mới cơ cấu chấp hành** sang một mô-đun C hoặc một MCU riêng (ESP32 vốn đã giữ
  cơ chế tự ngắt an toàn). Bảng phân tích của phép đo (nghẽn nhịp vs khoảng dừng GC vs khâu nào) chỉ ra
  chính xác cái gì cần chuyển.

Dù kết quả nào, đầu ra là **một con số ghi vào ADR**, không phải một giả định.

## 7. Báo cáo về (điền vào và gửi lại)

```
Phép đo thời gian K230 — kết quả
  board          : K230 @ ____ MHz, ____ MB RAM, CanMV/mpy ____
  kmodel / FPS   : ________________  @ ____ FPS
  thời lượng chạy: Tầng 1 số nhịp = ____ ; Tầng 2 chạy bền = ____ giờ
  YOLO đang chạy : có / không   cảnh: ____ (số vết, có đợt dồn không?)

  nghẽn nhịp  p50 / p95 / p99 / MAX : ____ / ____ / ____ / ____ ms
  số nhịp vượt 50 ms                : ____ / ____
  gc.collect() MAX                  : ____ ms
  Tầng 2 — khoảng hở SHOW lớn nhất  : ____ ms   (định mức T_signhold = 2000 ms)
  Tầng 2 — có làm trống sai         : không / ____
  VERDICT (script)                  : PASS / MARGINAL / FAIL
```

Đính kèm log thô của phép đo (và log khoảng-hở-SHOW của Tầng 2 nếu có) vào mục theo dõi ADR-0015 AI#1.

## 8. Thuật ngữ (đối chiếu Anh–Việt)

| EN | VI |
|---|---|
| timing spike | phép đo thời gian thực thi (spike) |
| safety loop / tick | vòng lặp an toàn / nhịp (10 Hz) |
| GC pause (stop-the-world) | khoảng dừng thu gom bộ nhớ (dừng toàn bộ) |
| refresh (SHOW frame) | làm mới (khung SHOW) |
| sign-hold window / blank | cửa sổ giữ biển / làm trống |
| dead-man's switch | cơ chế tự ngắt an toàn |
| soak (test) | chạy bền (dài giờ) |
| C-core fallback | phương án dự phòng lõi C |
| perception | khối tri giác (nhận dạng ảnh) |
| contention | tranh chấp tài nguyên |
| jitter | độ dao động chu kỳ |

## Tài liệu tham chiếu
- [ADR-0015 — chiến lược hiện thực máy trạng thái](../../docs/adr/ADR-0015-state-machine-implementation-strategy.vi.md) (D2 nhịp, **D3** MicroPython)
- [tài liệu 09 — Bàn giao Phần mềm→Phần cứng](../../docs/09-software-hardware-handoff.vi.md) (RQ-H4 đo trễ/điện năng)
- [tài liệu 02 §7a — bề mặt tham số](../../docs/02-system-architecture.vi.md) (các định mức thời gian)
- [`k230_timing_spike.py`](k230_timing_spike.py) — script phép đo chạy được
