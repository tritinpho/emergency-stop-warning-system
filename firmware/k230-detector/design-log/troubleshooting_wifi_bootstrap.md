# Nhật ký xử lý lỗi bootstrap Wi-Fi/LVGL trên K230

## Phạm vi

Tài liệu ghi lại sự cố màn hình đen khi chạy `k230/connect_wifi.py` bằng CanMV IDE trên Yahboom K230 image `1.4.1` (phát hành `2025-08-20`). Mục tiêu là lưu bằng chứng, nguyên nhân gốc và contract kiến trúc để tránh tái diễn.

## Triệu chứng ban đầu

- CanMV IDE hiện `Connecting...` hoặc framebuffer đen.
- Histogram/FPS không cập nhật hoặc FPS bằng 0.
- Serial có thể dừng sau khi MediaManager báo `vb common pool count 3`.
- Không có log scan/reconnect, khiến lỗi ban đầu dễ bị nhầm là lỗi Wi-Fi.

`vb common pool count 3` không phải lỗi. Các lần chạy sau chứng minh MediaManager đã trả về thành công ngay sau thông báo này.

## Cách khoanh vùng

Checkpoint được đặt tại ranh giới của từng native subsystem thay vì suy luận từ màn hình đen:

```text
[BOOT]       vòng đời Display / MediaManager / LVGL
[TOUCH]      tạo indev, TOUCH(0), đọc và trả dữ liệu cảm ứng
[LVGL]       timer handler và flush callback
[WIFI]       startup, scan, connect và lưu cấu hình
```

### Kết quả theo từng lớp

| Bằng chứng serial | Kết luận |
|---|---|
| `Display ready` | `Display.init(ST7701)` đã trả về |
| `MediaManager ready` | VB pool được tạo thành công |
| `lv.init returned` | LVGL core đã init |
| `Display buffer allocated` | BGRA8888 buffer đã cấp phát |
| `Display driver configured` | draw buffer và flush callback đã bind |
| `lv.indev_create returned` | LVGL input device hợp lệ |
| `read callback configured` | callback cảm ứng đã bind |
| dừng tại `calling TOUCH(0)` | native touch constructor bị block |

Các probe trước đó cũng xác nhận `TOUCH.read(1)`, gán `data.point` và `data.state` đều có thể hoàn tất khi `TOUCH(0)` được khởi tạo đúng thứ tự. Vì vậy callback đọc touch không phải nguyên nhân gốc.

## Nguyên nhân gốc

Script đã tạo `network.WLAN(network.STA_IF)` trước khi khởi tạo display/touch. Thứ tự này khác GUI Yahboom:

1. Core engine tạo Display, MediaManager, LVGL và Touch.
2. Trang `wifi_settings.py` được mở sau đó mới tạo `YbNetwork`.

Trên image `1.4.1`, khi WLAN được tạo trước, `TOUCH(0)` có thể block trong native driver. Đây là lỗi theo thứ tự resource, không phải lỗi password, scan, LVGL widget hay VB pool.

## Giải pháp đã xác nhận trên thiết bị

Thứ tự cuối cùng:

```text
Display → MediaManager → LVGL → framebuffer → indev → TOUCH(0)
        → minimal render gate → WLAN → Wi-Fi UI
```

Ngoài ra:

- Dùng một framebuffer BGRA8888 với `DISP_RENDER_MODE.DIRECT`, bám example `k230-firmware/src/13.Lvgl/`.
- Không gọi `lv.deinit()` trước `lv.init()` sau soft reboot.
- Dùng `lv.timer_handler()` từng vòng để giữ vòng lặp có thể quan sát và giới hạn sleep 1–10 ms.
- Nếu native touch đã bị kẹt trong một lần thử, power cycle trước khi chạy bản đã sửa.

## Xác nhận thành công

Ảnh kiểm thử thiết bị ngày `2026-07-06` cho thấy:

- LCD hiển thị đầy đủ Wi-Fi UI.
- Framebuffer IDE đạt khoảng `26.3 FPS`.
- Scan tìm thấy 5 mạng và sắp xếp theo RSSI.
- Bàn phím cảm ứng nhận password.
- Connect thành công và nhận IP `192.168.1.3`.
- Credential được lưu lại vào section `WLAN`.

Log thành công tối thiểu:

```text
[TOUCH][INIT] TOUCH(0) returned
[BOOT][5.5/7] Minimal render gate passed
[LVGL][FLUSH] Display.show_image returned
[WIFI][INFO] Scanning for Wi-Fi networks...
[WIFI][INFO] Found ... Wi-Fi network(s)
[WIFI][INFO] Connected to <ssid> | IP: <ip>
```

## Sai lệch API cần lưu ý

Trên image này, `wlan.config("ssid")` có thể trả boolean `True` dù kết nối thành công. Code không được chuyển thẳng giá trị đó thành chuỗi, nếu không LCD sẽ hiện `Connected to True`. Chỉ dùng kết quả khi kiểu dữ liệu là `str` hoặc `bytes`; trường hợp khác dùng SSID đang connect hoặc giá trị đã lưu.

## Checklist khi lỗi tái diễn

1. Xác nhận đúng file/bản script đang chạy; đối chiếu checkpoint serial thay vì chỉ tên tab IDE.
2. Tìm dòng log cuối cùng và gán nó cho đúng subsystem trong bảng trên.
3. Không thay đổi nhiều subsystem cùng lúc.
4. Giữ thứ tự Display/Touch trước WLAN.
5. Power cycle nếu lần chạy trước dừng trong native constructor.
6. Không ghi password vào serial hoặc tài liệu sự cố.
