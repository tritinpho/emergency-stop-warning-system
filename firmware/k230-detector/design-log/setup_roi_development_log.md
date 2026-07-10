# Nhật ký Phát triển & Khắc phục Lỗi Module Setup ROI trên K230

Tài liệu này tổng hợp toàn bộ quá trình phát triển, các vấn đề kỹ thuật nghiêm trọng liên quan đến phần cứng/firmware K230 được phát hiện và các giải pháp tương ứng đã áp dụng cho module cấu hình ROI (`setup_roi.py`).

---

## 1. Bối cảnh & Mục tiêu
Thiết bị **Yahboom K230 AI Vision Module** chạy MicroPython có tài nguyên giới hạn (đặc biệt là bộ nhớ RAM heap và bộ đệm video VB). Module `setup_roi.py` có nhiệm vụ:
- Kết nối Wi-Fi tự động.
- Thông báo trạng thái mạng lên hệ thống IoT (CoreIoT).
- Mở camera hiển thị preview trên màn hình (LCD ST7701 hoặc HDMI) và cho phép người vận hành nhấn nút để chụp lại một ảnh thực địa.
- Khởi chạy một Web Server (cổng `8081`) để người dùng truy cập vẽ các vùng ROI (làn khẩn cấp) và Exclusion (vùng loại trừ), lưu cấu hình xuống thẻ SD mà không làm mất thông tin Wi-Fi/Server có sẵn.

---

## 2. Các vấn đề kỹ thuật & Giải pháp đã áp dụng

### Vấn đề 1: Khởi động bị treo camera do giải phóng tài nguyên sai cách (Display.deinit)
- **Mô tả**: Khi chạy hoặc debug `setup_roi.py` qua CanMV IDE khi launcher GUI mặc định của hãng đang chạy, việc gọi `Display.deinit()` hoặc `MediaManager.deinit()` tại startup của script sẽ làm lỗi bộ nhớ dùng chung (VB buffer heap), dẫn tới camera khởi động (`pl.create()`) bị treo vĩnh viễn (black screen / CPU freeze).
- **Nguyên nhân**: Launcher GUI mặc định đang sở hữu và quản lý Display/Media. Việc tranh chấp giải phóng bộ nhớ từ bên ngoài làm lỗi luồng hoạt động phần cứng của CPU1.
- **Giải pháp**: Tuyệt đối **không** được gọi `Display.deinit()` hay `MediaManager.deinit()` lúc khởi động script. Chỉ khởi tạo lớp `PipeLine` và chỉ gọi `pl.destroy()` ở khối `finally` khi kết thúc quá trình camera hoạt động.

---

### Vấn đề 2: Cạn kiệt bộ nhớ RAM và treo IDE khi chạy Web Server
- **Mô tả**: Nếu khởi chạy HTTP Web Server trong khi camera pipeline vẫn đang chạy ngầm để phát luồng live preview, thiết bị sẽ bị crash/treo cứng chỉ sau vài giây hoặc ngắt kết nối với CanMV IDE với lỗi `"Connecting..."`.
- **Nguyên nhân**: Camera pipeline ngốn rất nhiều RAM heap cho các frame ảnh RGB/YUV và VB buffers. Web Server MicroPython hoạt động đơn luồng, khi chạy đồng thời với camera sẽ đẩy bộ nhớ heap của K230 vượt ngưỡng giới hạn, gây crash hệ điều hành thời gian thực (RTOS).
- **Giải pháp**: Thiết kế quy trình hoạt động tuần tự nghiêm ngặt:
  1. Camera chỉ chạy trong **Giai đoạn Chụp ảnh (Capture Phase)**.
  2. Ngay sau khi người dùng nhấn nút KEY để chụp và lưu thành công `/sdcard/capture.jpg`, gọi ngay lập tức **`pl.destroy()`** và tắt LED RGB (`k230_rgb.show_rgb((0,0,0))`) ở khối `finally`.
  3. Sau khi giải phóng toàn bộ tài nguyên camera, hệ thống mới tiến hành chạy Web Server. Lúc này bộ nhớ RAM đã hoàn toàn trống trải giúp Web Server phản hồi cực nhanh và ổn định.

---

### Vấn đề 3: Sai lệch tọa độ nút cảm ứng (Touch Button Drift)
- **Mô tả**: Ban đầu thiết kế một nút bấm cảm ứng màu đỏ (Touch Circle) trên màn hình OSD. Tuy nhiên thực tế sử dụng cho thấy tọa độ cảm ứng màn hình LCD ST7701 trên K230 rất dễ bị trôi (drift) nếu chưa được căn chỉnh (calibrate), dẫn tới người dùng bấm nút ảo không ăn, hoặc chạm tay vào màn hình làm xê dịch góc lắp đặt của camera.
- **Giải pháp**: Loại bỏ hoàn toàn nút bấm ảo và các hàm kiểm tra touch event trên OSD để đảm bảo an toàn. Thay thế hoàn toàn bằng **Nút bấm vật lý KEY** (`ybUtils.YbKey`) tích hợp trên bo mạch K230 để thực hiện lệnh chụp. Cơ chế này hoạt động chính xác 100% và không bị ảnh hưởng bởi lỗi màn hình cảm ứng.

---

### Vấn đề 4: Khó xác định địa chỉ IP để đăng nhập cấu hình
- **Mô tả**: Khi chạy offline hoặc không kết nối trực tiếp với máy tính, người vận hành rất khó biết IP của K230 để truy cập vào Web Server cổng 8081.
- **Giải pháp**:
  - Khi camera đang mở preview, in trực tiếp dòng chữ hướng dẫn kèm IP tạm thời trên OSD: `IP WEB: http://<K230_IP>:8081`.
  - Ngay sau khi chụp thành công, in ra terminal: `[SETUP_ROI] Capture success! Please configure ROI at: http://<K230_IP>:8081/`.
  - Đồng thời vẽ khung viền xanh ngọc kèm URL trực tiếp trên màn hình OSD trong 3 giây: `URL: http://<K230_IP>:8081/` trước khi tắt màn hình, giúp người dùng dễ dàng đọc và nhập trên điện thoại/máy tính.

---

### Vấn đề 5: Socket bị nghẽn (TCP Blocking) và Tràn bộ đệm gửi (Socket Buffer Overflow)
- **Mô tả**: Web Server sử dụng TCP sockets mặc định có thể chặn luồng MicroPython vô hạn trên hàm `accept()` hoặc `read()`, làm IDE không thể Ctrl+C để dừng chương trình. Ngoài ra, việc gửi file giao diện HTML lớn hoặc ảnh JPEG (`capture.jpg` khoảng 50KB-100KB) trong một lần ghi duy nhất (`sendall`) sẽ làm tràn bộ đệm gửi TCP nhỏ của K230, dẫn tới mất gói tin hoặc đứng trang web.
- **Giải pháp**:
  - Sử dụng `s.settimeout(1.0)` kết hợp vòng lặp kiểm tra `os.exitpoint()` liên tục để cho phép ngắt kết nối từ CanMV IDE bất kỳ lúc nào.
  - Khi đã chấp nhận kết nối (`s.accept()`), gọi `client_sock.setblocking(True)` để bảo vệ quá trình truyền dẫn không bị timeout ngắt quãng giữa chừng.
  - Tất cả các luồng phản hồi dữ liệu lớn (file HTML và ảnh chụp JPEG `/capture.jpg`) đều được đọc từ thẻ SD và gửi qua mạng theo cơ chế phân đoạn **1KB mỗi lần (Chunked Write 1KB)**.

---

### Vấn đề 6: Ghi đè làm mất cấu hình Wi-Fi/Server cũ
- **Mô tả**: Khi người dùng nhấn nút Save trên Web UI, nếu server ghi đè trực tiếp dữ liệu tọa độ ROI nhận được vào file `/sdcard/config.json`, nó sẽ xóa sạch các cài đặt mạng Wi-Fi và khóa kết nối ESP32/CoreIoT đã cấu hình trước đó.
- **Giải pháp**:
  - Tại endpoint `POST /save`, Web Server tiến hành đọc file cấu hình cũ `/sdcard/config.json` lên trước (nếu tồn tại) dưới dạng dict.
  - Chỉ tiến hành cập nhật/ghi đè các trường thông tin liên quan đến ROI (`regions`, `exclusion_regions`, `reference_resolution`, `version`, `camera_id`).
  - Giữ nguyên các key cấu hình khác (`wifi`, `network`, `server`, `device_pair`,...) rồi mới ghi ngược lại file `/sdcard/config.json`.

---

## 3. Kết luận
Nhờ áp dụng đồng bộ các giải pháp tối ưu hóa vòng đời thiết bị, quản lý luồng socket không chặn và truyền tải phân đoạn dữ liệu, module `setup_roi.py` đã hoạt động cực kỳ mượt mà, phản hồi Web UI vẽ đa giác ROI/Exclusion vô cùng nhạy, không rò rỉ bộ nhớ, và tuyệt đối an toàn cho phần cứng K230.
