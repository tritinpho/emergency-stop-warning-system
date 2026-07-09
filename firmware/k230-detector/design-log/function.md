# BÁO CÁO TIẾN ĐỘ DỰ ÁN
## Hệ thống Giám sát và Cảnh báo Làn khẩn cấp Thông minh (Yahboom K230 AI Vision)

Tài liệu này tổng hợp toàn bộ các tính năng, cải tiến đã phát triển thành công (Missions Accomplished) phục vụ cho báo cáo tiến độ dự án.

---

## PHẦN I. CÁC TÍNH NĂNG VÀ CẢI TIẾN MỚI CẬP NHẬT (IoT & CLOCK SYNC)

### 1. Đồng bộ thời gian thực từ Cloud CoreIoT (`update_mode_from_mqtt`)
- **Mục tiêu:** Đồng bộ hóa đồng hồ hệ thống theo thời gian thực từ máy chủ CoreIoT để chuyển đổi chế độ Day/Night chính xác.
- **Tính năng phân tích thông minh:**
  - Tự động tách chuỗi ngày/tháng khỏi giờ đối với các định dạng ngày giờ phức tạp (ví dụ: biến đổi `"7/8/26, 1:40:31 PM"` chỉ lấy phần giờ `"1:40:31 PM"`).
  - Tự động chuyển đổi định dạng 12 giờ có ký tự **AM/PM** về định dạng 24 giờ để so sánh mốc thời gian chuẩn xác.
  - Tự động làm sạch các ký tự không phải số ở phần giờ trước khi chuyển đổi sang số nguyên (`int`).
  - Cập nhật lại thời gian mỗi 5 giây.

### 2. Thiết kế Hộp hiển thị đồng hồ (HUD Clock Box) trên OSD
- **Thiết kế trực quan:**
  - Vẽ một hộp đồng hồ riêng biệt hiển thị ở **phía trên bên phải màn hình camera OSD**.
  - Khung viền hộp đồng hồ màu **Xanh Cyan Neon** (255, 0, 226, 252) với độ dày nét vẽ là 2.
  - Hiển thị `"Syncing..."` khi đang chờ kết nối, và tự động chuyển sang giờ thực tế (ví dụ: `"13:40"`) ngay khi nhận được tín hiệu đồng bộ từ CoreIoT.

### 3. Tích hợp quét Wi-Fi lúc khởi động (`scan_wifi_networks`)
- **Mục tiêu:** Quét tìm các điểm truy cập Wi-Fi xung quanh tại thời điểm khởi động máy trước khi kết nối mạng.
- **Tính năng:**
  - Quét mạng sóng, ghi danh sách SSID và cường độ sóng (RSSI) tìm thấy ra log hệ thống.
  - Hiển thị danh sách top 5 mạng sóng Wi-Fi mạnh nhất lên màn hình OSD trong 3 giây để người vận hành dễ theo dõi.

### 4. Chi tiết hóa Log kết nối và Bảo mật MQTT
- Định cấu hình kết nối chuẩn xác của thiết bị lên Cloud CoreIoT: sử dụng Access Token làm Username kết nối MQTT (đúng chuẩn xác thực ThingsBoard).
- Thay thế dòng thông báo chung chung bằng log chi tiết mô tả đầy đủ thông tin máy chủ, mã định danh và token đang sử dụng:
  `[MQTT] Loaded settings from config.json: broker=<broker>, client_id=<client_id>, token=<username>`

---

## PHẦN II. CÁC TÍNH NĂNG NỀN TẢNG (BASELINE DỰ ÁN)

### 5. Bộ lọc khử nhiễu môi trường (Noise Filter Module)
Nhằm khắc phục tình trạng nhận diện nhầm các vật thể không phải phương tiện hoặc cảnh báo sai do nhiễu môi trường, hệ thống được trang bị 3 bộ lọc nhiễu chuyên dụng chạy song song:
- **Bộ lọc rung lắc (ShakingFilter):** Loại bỏ các rung động vật lý của camera do tác động của gió hoặc rung động của cột treo bằng thuật toán so khớp độ dịch chuyển khung hình.
- **Bộ lọc ánh sáng đột ngột (LightFilter):** Loại bỏ hiện tượng nhiễu do đèn pha ô tô quét qua vào ban đêm hoặc thay đổi ánh sáng đột ngột làm lóa camera.
- **Bộ lọc mật độ phương tiện quá tải (OverVehiclesFilter):** Kiểm soát mật độ phương tiện vượt quá ngưỡng để đưa ra cảnh báo chính xác và tối ưu hiệu suất tính toán cho thiết bị.

### 6. Giao diện Web GUI vẽ ROI trước khi nạp mô hình AI (Setup Mode)
Để tiết kiệm tài nguyên bộ nhớ cực kỳ hạn chế của chip K230, hệ thống được thiết kế chạy qua 2 chế độ độc lập:
- **Cơ chế kích hoạt bằng phím vật lý (KEY button):** Lúc khởi động, hệ thống sẽ chờ nút vật lý KEY được nhấn giữ:
  - **Nhấn giữ KEY:** Hệ thống vào **Chế độ Cấu hình (Setup Mode)**.
  - **Không nhấn giữ (hoặc bỏ qua):** Hệ thống vào **Chế độ Vận hành (Production Mode)** và nạp mô hình AI.
- **Chức năng trong Setup Mode (Web GUI):**
  - Camera chụp một ảnh tham chiếu chất lượng cao lưu vào `/sdcard/capture.jpg`.
  - Thiết bị tự động khởi chạy một máy chủ HTTP mini (cổng `8081`).
  - Người dùng truy cập bằng trình duyệt web để vẽ trực tiếp các đa giác Vùng khẩn cấp (ROI) và Vùng loại trừ (Exclusion zones) trực quan trên ảnh tham chiếu.
  - **Bảo toàn dữ liệu:** Tự động đọc và ghép (merge) tọa độ đa giác mới vẽ vào tệp cấu hình `/sdcard/config.json` mà không làm mất thông tin mạng Wi-Fi và tài khoản liên kết MQTT cũ.
  - Tự động khởi động lại (Reboot) thiết bị để áp dụng cấu hình mới vào Production Mode.

### 7. Giao diện OSD chọn nhanh Wi-Fi tại Boot (Boot Menu)
- Sử dụng nút bấm vật lý KEY để tương tác trực tiếp trên màn hình OSD của camera:
  - **Nhấn ngắn (<1.5s):** Di chuyển con trỏ chọn mạng trong danh sách mạng định sẵn (Presets).
  - **Nhấn giữ (2s):** Xác nhận kết nối vào mạng đã chọn và lưu cấu hình Wi-Fi vào `sys_config.json`.
  - **Nhấn giữ dài (5s+):** Bỏ qua (Skip) màn hình để chạy tiếp bằng cấu hình mạng đã lưu sẵn.

### 8. Tối ưu hóa hiệu năng mô hình AI YOLOv8n trên K230
- **Đồng bộ hóa Day/Night:** Cả chế độ Ngày và Đêm đều sử dụng chung mô hình YOLOv8n mang lại độ chính xác cao.
- **Hậu xử lý tăng tốc phần cứng:** Hỗ trợ giải mã hộp nhận diện (Bounding Box) trực tiếp bằng thư viện phần cứng C++ `aidemo.yolov8_det_postprocess` giúp duy trì tốc độ khung hình (FPS) mượt mà.
- **Khử lỗi Socket:** Khắc phục lỗi thiếu phương thức `gettimeout()` trên MicroPython bằng cách cấu hình trực tiếp thuộc tính `self.timeout`.

## PHẦN III. Các hạn chế
### 9. Wifi đang được hardcode trên `sys_config.json`
- **Nhập SSID và Password thủ công:** Mỗi lần thay đổi địa điểm thì cần vào `sdcard/config/sys_config.json` ra để thay đổi thông tin kết nối Wifi.
- **Thuận lợi:** Khi cố định thiết bị và wifi thì việc cấu hình cứng wifi giúp thiết bị hoạt động ổn định.
