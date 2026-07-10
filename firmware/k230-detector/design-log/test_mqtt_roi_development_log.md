# Nhật ký Phát triển & Khắc phục Lỗi Module Kiểm thử Cảnh báo Làn Khẩn Cấp (test_mqtt_roi.py) trên K230

Tài liệu này tổng hợp toàn bộ quá trình phát triển, các vấn đề kỹ thuật nghiêm trọng liên quan đến phần cứng/firmware K230 được phát hiện và các giải pháp tương ứng đã áp dụng cho module kiểm thử tích hợp camera, mô hình nhận diện YOLOv8n_320, chỉ báo LED RGB vật lý và truyền tin cảnh báo MQTT CoreIoT (`test_mqtt_roi.py`).

---

## 1. Bối cảnh & Mục tiêu
Module `test_mqtt_roi.py` hoạt động độc lập nhằm mục đích kiểm tra và chạy thử toàn bộ chu trình nghiệp vụ giám sát làn đường khẩn cấp trước khi đưa vào vận hành chính thức. Các yêu cầu cốt lõi bao gồm:
- Tự động kết nối Wi-Fi sử dụng thông tin lưu trong cấu hình.
- Khởi động camera và nạp mô hình nhận diện vật thể `yolov8n_320.kmodel`.
- Tải các đa giác ROI (làn khẩn cấp) và Exclusion (vùng loại trừ) từ `/sdcard/config.json`.
- Chạy vòng lặp nhận diện liên tục: lọc các phương tiện (`car`, `truck`, `bus`, `motorcycle`, `motorbike`) nằm trong ROI.
- Điều khiển LED RGB vật lý tại chỗ: màu **Đỏ** khi phát hiện vi phạm, màu **Xanh lá** khi an toàn, và **Tắt** khi dừng chương trình.
- Truyền gói tin telemetry trạng thái làn khẩn cấp về Broker MQTT CoreIoT (`app.coreiot.io`) ngay khi có sự thay đổi trạng thái (xâm nhập hoặc giải tỏa).

---

## 2. Các vấn đề kỹ thuật & Giải pháp đã áp dụng

### Vấn đề 1: Tránh méo hình ảnh khi co giãn (Aspect Ratio Distortion) trong tiền xử lý AI2D
- **Mô tả**: Khi co giãn trực tiếp luồng camera (thường có tỷ lệ khác biệt) về kích thước đầu vào mô hình YOLOv8n (`320x320`) không qua bù viền (padding), hình ảnh vật thể (xe cộ) sẽ bị méo, bóp dẹt hoặc kéo giãn, làm giảm sút nghiêm trọng độ chính xác của mô hình nhận diện.
- **Giải pháp**: 
  - Sử dụng hàm `letterbox_pad_param` để tính toán biên bù viền trên-dưới hoặc trái-phải nhằm giữ nguyên tỷ lệ khung hình gốc.
  - Cấu hình Ai2d thực hiện pad thêm viền màu xám với giá trị màu `[128, 128, 128]` bằng phương thức `self.ai2d.pad([0, 0, 0, 0, top, bottom, left, right], 0, [128, 128, 128])` trước khi thực hiện co giãn bằng thuật toán `tf_bilinear` kết hợp chế độ căn chỉnh pixel `half_pixel`.

---

### Vấn đề 2: Treo chương trình và tràn RAM Heap do hậu xử lý YOLOv8 bằng Python thuần
- **Mô tả**: Hậu xử lý YOLOv8 (bao gồm tính toán anchor, sigmoid, lọc ngưỡng tự tin confidence, và triệt tiêu hộp trùng lặp NMS) nếu thực hiện bằng các vòng lặp Python thuần sẽ cực kỳ chậm (chỉ đạt ~0.5 FPS) và gây cạn kiệt bộ nhớ RAM Heap của MicroPython sau vài khung hình, dẫn tới CPU1 bị treo cứng hoặc ngắt kết nối CanMV IDE.
- **Giải pháp**: Chuyển đổi toàn bộ quá trình hậu xử lý sang hàm tăng tốc phần cứng bằng C/C++ tích hợp trong SDK: **`aidemo.yolov8_det_postprocess(...)`**. Giải pháp này đẩy tốc độ hậu xử lý lên mức mili-giây, đảm bảo hệ thống chạy ổn định 24/7 mà không xảy ra rò rỉ hay tràn RAM.

---

### Vấn đề 3: Lọc chính xác phương tiện vi phạm nằm trong vùng ROI phức tạp
- **Mô tả**: Bounding box của xe cộ có thể rất lớn và chỉ chớm chạm vào ROI hoặc xe ở làn chính kế bên có thể bị nhận nhầm là đang vi phạm làn khẩn cấp.
- **Giải pháp**: Kết hợp hai tầng lọc hình học chặt chẽ:
  1. **Lọc điểm đáy giữa (Bottom Center)**: Tính toán điểm tiếp xúc mặt đường của xe `(x + w/2, y + h)`. Chuẩn hóa tọa độ này về dải `[0, 1]` tương ứng với màn hình hiển thị, sau đó dùng thuật toán **Ray-Casting** (`is_point_in_polygon`) để xác định xem điểm này có nằm trong bất kỳ đa giác ROI nào và phải nằm ngoài các đa giác loại trừ (Exclusion zones).
  2. **Lọc tỷ lệ đè diện tích (Bbox Overlap Ratio)**: Dùng hàm `bbox_roi_intersection_area` tính toán phần diện tích giao nhau giữa bounding box của xe và đa giác ROI. Chỉ xác nhận hợp lệ nếu tỷ lệ diện tích giao nhau so với toàn bộ bbox vượt ngưỡng cấu hình `ROI_OVERLAP_THRESHOLD` (mặc định `0.2`).

---

### Vấn đề 4: Rung nhiễu tín hiệu cảnh báo (Warning Flicker/Chattering)
- **Mô tả**: Do yếu tố nhiễu ánh sáng hoặc xe bị che khuất tạm thời trong 1-2 khung hình, trạng thái phát hiện xe có thể bị nhảy liên tục giữa Xâm nhập và An toàn, gây nhấp nháy đèn LED cảnh báo và bắn hàng loạt tin nhắn trùng lặp lên broker MQTT làm nghẽn mạng.
- **Giải pháp**: Tích hợp bộ lọc trạng thái **`VehiclePresenceFilter`** với cơ chế debounce:
  - Chỉ chuyển sang trạng thái cảnh báo khi xe xuất hiện liên tục tối thiểu `MIN_CONFIRM_FRAMES` khung hình.
  - Khi xe rời đi, thiết lập một khoảng trễ giữ trạng thái (hạn chế mất dấu tạm thời) tối đa `ABSENCE_THRESHOLD_SECONDS` (mặc định 3 giây) trước khi chính thức hạ cảnh báo xuống mức An toàn.

---

### Vấn đề 5: Truyền tin MQTT tin cậy và Tiết kiệm băng thông
- **Mô tả**: Việc gửi liên tục trạng thái mỗi khi xử lý xong một khung hình sẽ gây lãng phí tài nguyên và làm nghẽn kết nối Socket.
- **Giải pháp**: 
  - Chỉ đẩy gói tin telemetry lên hàng đợi `MqttStatePublisher` khi có sự **thay đổi trạng thái thực sự** (từ an toàn sang cảnh báo và ngược lại).
  - Vòng lặp chính liên tục gọi phương thức phi chặn `mqtt_publisher.service(now_ms)` để gửi gói tin đi khi sẵn sàng và tự động gửi gói PINGREQ định kỳ bảo trì keepalive mà không làm chậm chu kỳ suy luận AI.
  - Sử dụng cơ chế nạp lại / thử lại thông minh để tự động kết nối lại broker MQTT nếu gặp sự cố mất mạng mà không làm dừng luồng camera OSD.

---

### Vấn đề 6: Quản lý vòng đời tài nguyên phần cứng an toàn (Safe Exit & Cleanup)
- **Mô tả**: Nếu dừng chương trình đột ngột mà không giải phóng camera sensor, RAM hoặc không tắt đèn chỉ báo LED, thiết bị sẽ giữ nguyên trạng thái LED đỏ và hệ thống VB memory của camera sẽ bị rò rỉ, gây lỗi màn hình đen ở lần chạy tiếp theo.
- **Giải pháp**: 
  - Bọc toàn bộ chương trình trong cấu trúc `try...finally`.
  - Trong khối `finally`, luôn đảm bảo gọi đầy đủ các hàm giải phóng tài nguyên phần cứng: `pl.destroy()` (giải phóng camera, display layer, VO buffer), `ob_det.deinit()` (giải phóng mô hình KPU, bộ nhớ tensor), tắt LED RGB vật lý `k230_rgb.show_rgb((0,0,0))` và ngắt kết nối client MQTT một cách lịch sự.

---

## 3. Kết luận
Module `test_mqtt_roi.py` là một công cụ kiểm thử tích hợp hoàn chỉnh và tin cậy. Nhờ sự kết hợp đồng bộ giữa tiền xử lý AI2D chuẩn hóa, hậu xử lý tăng tốc phần cứng, thuật toán ray-casting lọc ROI hai lớp, bộ lọc debounce trạng thái xe, và quản lý kết nối socket phi chặn, module đã chứng minh khả năng chạy mượt mà, phản hồi cảnh báo tức thời tại chỗ và đẩy dữ liệu lên CoreIoT MQTT vô cùng ổn định trên Yahboom K230.
