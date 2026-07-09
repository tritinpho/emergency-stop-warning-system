# Nhật ký Tiến độ Phát triển Dự án Giám sát Làn Khẩn Cấp K230

Tài liệu này ghi lại tiến độ hiện tại, các chức năng đã triển khai, các lỗi đã xử lý và các bước tiếp theo của dự án K230-ESP32.

---

## 📊 Bảng Tiến độ Thành phần

| Thành phần | Chức năng | Trạng thái | Ghi chú / Chi tiết |
| :--- | :--- | :--- | :--- |
| **Hệ thống** | Kết nối Wi-Fi | ✅ Hoàn thành | Đã kết nối thành công tới mạng `ACLAB` (`172.28.182.122`). |
| | Tự động Fallback màn hình | ✅ Hoàn thành | Tự động dò và chuyển đổi thông minh giữa LCD (ST7701) và HDMI. |
| **Cấu hình ROI (`setup_roi.py`)** | Chụp hình tham chiếu | ✅ Hoàn thành | Chụp bằng nút bấm vật lý KEY của K230 và hiển thị trực tiếp IP webserver. |
| | Web Server cổng `8081` | ✅ Hoàn thành | Giao diện vẽ ROI, hỗ trợ ghép cấu hình bảo toàn cấu trúc mạng có sẵn. |
| | Cấu hình & Chống treo | ✅ Hoàn thành | Đóng hoàn toàn camera pipeline (`pl.destroy()`) sau khi chụp để tránh cạn kiệt RAM. |
| **Ứng dụng Chính (`main.py`)** | Đọc cấu hình ROI | ✅ Hoàn thành | Tải cấu hình `/sdcard/config.json`, hỗ trợ đa vùng ROI và đa vùng loại trừ. |
| | Vẽ ROI lên OSD | ✅ Hoàn thành | Vẽ đa giác ROI màu xanh ngọc Cyan neon và vùng loại trừ màu đỏ Red neon nét dày trên OSD. |
| | Thuật toán Ray-Casting | ✅ Hoàn thành | Lọc tất cả vật thể nằm ngoài vùng ROI và nằm trong vùng loại trừ. Chỉ vẽ bounding box và gửi cảnh báo LED nếu vật thể hợp lệ (phương tiện `car`, `truck`, `bus` hoặc người `person`) nằm trong ROI. |
| | Giao tiếp ESP32 | ✅ Hoàn thành | Gửi tín hiệu điều khiển `LED:ON` và `LED:OFF` qua TCP Socket. |
| **Kiểm thử (`test_roi.py`)** | Kiểm tra hiển thị ROI & Nhận diện vật thể OBB | ✅ Chuẩn hóa | Tải `/sdcard/config.json` và mô hình xoay YOLOv8n-OBB để kiểm tra nhận diện vật thể trong ROI ngoại tuyến. LED sáng màu đỏ khi phát hiện mục tiêu và màu xanh dương khi an toàn. Có đầy đủ cleanup/fallback. |
| **Truyền thông UART (`main_uart.py`)** | Lọc ROI & UART | ✅ Hoàn thành | Tải cấu hình ROI, lọc vật thể YOLOv8 và truyền gói dữ liệu tọa độ qua UART1. |
| **Kiểm thử camera & MQTT (`test_mqtt_roi.py`)** | Kết nối Wi-Fi, tải ROI, YOLOv8n_320, LED & MQTT CoreIoT | ✅ Hoàn thành | Standalone script khởi chạy camera, tải yolov8n_320.kmodel với letterbox padding chuẩn, vẽ ROI, và truyền telemetry trạng thái làn khẩn cấp lên CoreIoT MQTT khi có thay đổi. LED sáng Đỏ khi có xe, Xanh lá khi an toàn, và Tắt khi dừng. |

---

## 🛠️ Lịch sử Sửa lỗi & Tối ưu hóa quan trọng

> [!TIP]
> **Tích hợp nút bấm vật lý KEY và hiển thị URL tự động (`setup_roi.py`)**:
> - Loại bỏ nút bấm ảo (Red Touch Circle) trên màn hình OSD nhằm đơn giản hóa UI, tránh các lỗi lệch tọa độ cảm ứng khi chưa cân chỉnh màn hình.
> - Kích hoạt chụp ảnh `/sdcard/capture.jpg` thông qua nút bấm vật lý KEY tích hợp trên K230 (`ybUtils.YbKey`).
> - Khi chụp thành công, địa chỉ IP của Web Server (`http://<K230_IP>:8081/`) sẽ được in ra console terminal và vẽ trực tiếp trên màn hình hiển thị OSD để người vận hành kết nối dễ dàng.
> - Gọi `pl.destroy()` giải phóng cảm biến và RAM ngay lập tức khi hoàn tất chụp, giúp Web Server chạy ổn định, không bị tràn bộ nhớ.

> [!TIP]
> **Sửa lỗi chụp ảnh (`setup_roi.py`)**:
> - Khắc phục lỗi đối tượng numpy `ndarray` không hỗ trợ lưu ảnh bằng cách sử dụng API chính thức `pl.sensor.snapshot(chn=CAM_CHN_ID_1)` để thu được đối tượng `image.Image` chuẩn.
> - Thêm vòng lặp thử lại (Retry Loop) 20 lần (2 giây) để tránh lỗi buffer chưa sẵn sàng từ cảm biến lúc khởi động (`failed(3)`).

> [!IMPORTANT]
> **Khắc phục lỗi treo socket và đứng trình duyệt**:
> - Chuyển đổi cơ chế gửi toàn bộ sang **gửi phân đoạn (Chunked Write 1KB)** để không làm tràn bộ đệm gửi TCP nhỏ của K230.
> - Sử dụng `s.settimeout(1.0)` kết hợp với `os.exitpoint()` để server không chặn vô hạn, giúp CanMV IDE ngắt kết nối/stop chương trình bình thường (không bị lỗi "Connecting...").
> - Gọi `client_sock.setblocking(True)` ngay khi kết nối được chấp nhận nhằm ngăn socket truyền dữ liệu bị timeout thừa kế từ server.

> [!IMPORTANT]
> **Ràng buộc an toàn, Hỗ trợ đa vùng ROI & LED RGB tích hợp (`main.py` & `test_roi.py`)**:
> - Hỗ trợ nạp đồng thời nhiều đa giác ROI (`regions`) và đa giác loại trừ (`exclusion_regions`) từ file cấu hình.
> - Thiết lập cơ chế kiểm tra nghiêm ngặt (Strict Validation): Nếu không tải được cấu hình hoặc cấu hình không có vùng ROI hợp lệ, hệ thống sẽ chuyển về trạng thái an toàn (gửi `LED:OFF` tắt cảnh báo ESP32, tắt LED RGB nội bộ), hủy pipeline camera và dừng chạy để người vận hành cấu hình lại.
> - Lọc kết quả nhận diện ở cấp độ đầu vào: Điểm đáy giữa (bottom center) hoặc tâm OBB được kiểm tra xem có thuộc vùng ROI và nằm ngoài vùng loại trừ không. Các phương tiện ngoài ROI sẽ bị bỏ qua hoàn toàn (không vẽ khung hình và không kích hoạt cảnh báo).
> - Tích hợp LED RGB của K230 để chỉ báo trạng thái trực quan tại chỗ:
>   - Ở `main.py`: LED chuyển sang màu **Đỏ** (Cảnh báo) khi phát hiện xe trong ROI, màu **Xanh lá** (An toàn) khi không có xe, và tắt khi dừng chương trình.
>   - Ở `test_roi.py`: LED chuyển sang màu **Xanh dương** để chỉ báo trạng thái đang chạy chế độ kiểm tra và tắt khi thoát.
> - **Khắc phục triệt để lỗi treo camera / đen màn hình (VB memory leak & Heap exhaust)**:
>   - Tách biệt `Display.deinit()` và `MediaManager.deinit()` vào các khối độc lập để luôn giải phóng camera sensor ngay cả khi display chưa được khởi tạo.
>   - Chuyển đổi thuật toán hậu xử lý YOLOv8 từ vòng lặp Python thuần (lặp 8400 lần gây cạn kiệt bộ nhớ heap MicroPython và làm treo/crash CPU1) sang hàm tăng tốc phần cứng chính thức của SDK là `aidemo.yolov8_det_postprocess` chạy bằng C/C++. FPS tăng vượt trội và hệ thống không còn bị tràn RAM dẫn tới ngắt kết nối IDE.
> - **Hỗ trợ mô hình Oriented Bounding Box (YOLOv8-OBB) (`test_roi.py`)**:
>   - Tích hợp mô hình phát hiện vật thể xoay `yolov8n-obb.kmodel` với hàm hậu xử lý `aidemo.yolo_obb_postprocess(...)` tăng tốc bằng C.
>   - Tính toán điểm trung tâm của OBB từ 4 góc `(x1, y1) -> (x4, y4)` để lọc đối tượng nằm trong vùng ROI và ngoài vùng loại trừ (Exclusion), hỗ trợ đầy đủ 15 lớp nhận diện OBB (plane, ship, vehicles, etc.).
> - **Bảo vệ lỗi NameError trong khối giải phóng tài nguyên**: Khởi tạo biến `ob_det = None` ở đầu hàm main để luôn đảm bảo `pl.destroy()` được gọi thành công trong khối `finally` ngay cả khi KPU model bị lỗi nạp nửa chừng.

---

## 📍 Cấu hình ROI đã xác thực thành công

Cấu hình ROI làn khẩn cấp đã được người dùng vẽ, kiểm tra và lưu thành công vào file cấu hình `/sdcard/config.json` vào lúc **11:26 ngày 04/07/2026**:

```json
{
  "version": 1,
  "camera_id": "k230-01",
  "reference_resolution": [320, 320],
  "regions": [
    {
      "id": "emergency-lane-main",
      "polygon": [
        [0.4661459, 0.001966702],
        [0.4791667, 0.9904717],
        [0.001302083, 0.9937269],
        [0.005208334, 0.02692347]
      ]
    }
  ],
  "exclusion_regions": []
}
```

---

## 🚀 Quy trình và các bước triển khai tiếp theo

1. **Chuẩn bị thẻ nhớ SD**:
   - Sao chép các tệp mã nguồn từ máy tính vào thẻ nhớ TF thông qua CanMV IDE hoặc đầu đọc thẻ nhớ theo tài liệu hướng dẫn [deployment_guide.md](file:///e:/k230-project/deployment_guide.md).
2. **Cấu hình ROI tại thực địa**:
   - Chạy `setup_roi.py` trên K230, kết nối mạng Wi-Fi và truy cập `http://<K230_IP>:8081` để vẽ phân làn khẩn cấp, hệ thống tự động lưu trữ và giữ nguyên các cài đặt Wi-Fi/Server cũ.
3. **Xác thực và chạy thử**:
   - Chạy `test_roi.py` để trực quan kiểm tra khu vực nhận diện OBB cũng như kiểm tra đèn LED chỉ báo trạng thái tại chỗ.
   - Chạy `test_mqtt_roi.py` để chạy thử toàn bộ chu trình khởi tạo camera, tải mô hình YOLOv8n_320, lọc ROI trực quan, cảnh báo bằng LED RGB và truyền gói tin telemetry trực tiếp lên CoreIoT MQTT.
4. **Vận hành hệ thống (Production)**:
   - Triển khai chạy chính thức không dây qua `main.py` kết nối ESP32 hoặc nối dây truyền gói dữ liệu tọa độ qua `main_uart.py`. Cài đặt tự chạy offline bằng cách đặt tên file chạy chính thành `main.py` trong thư mục gốc của thẻ SD.
