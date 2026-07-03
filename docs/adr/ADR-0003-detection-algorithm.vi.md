# ADR-0003: Cách tiếp cận phát hiện — bộ phát hiện nhẹ + giới hạn theo ROI + logic thời gian chờ

> 🇬🇧 Bản gốc tiếng Anh: [ADR-0003-detection-algorithm.md](ADR-0003-detection-algorithm.md)

**Trạng thái:** Đã chấp nhận (phía phần mềm) — 2026-06-27
**Ngày:** 2026-06-26
**Người quyết định:** Chủ nhiệm đề tài, trưởng nhóm kỹ thuật, kỹ sư thị giác máy tính (CV)

## Bối cảnh

Ta phải quyết định *cách* lớp nhận diện kết luận rằng "một xe đang dừng trong làn dừng xe khẩn cấp".
Bài toán hẹp và thuận lợi: một **camera cố định**, một **vùng quan tâm cố định** (đa giác làn dừng xe
khẩn cấp), và một câu hỏi chủ yếu là **sự hiện diện + tính đứng yên**, chứ không phải hiểu cảnh ở mức
chi tiết. Lựa chọn này đánh đổi giữa độ chính xác, độ vững chắc, chi phí tại biên và công sức kỹ thuật.

Các yếu tố tác động: ngân sách tính toán/nguồn điện tại biên (năng lượng mặt trời), độ vững chắc trước
ánh sáng/bóng đổ/che khuất, cân bằng giữa báo động giả và bỏ sót, kỹ năng và dữ liệu sẵn có, cùng nhu
cầu giới hạn theo một ROI hình học.

## Quyết định

Sử dụng một **bộ phát hiện đối tượng nhỏ gọn** (loại YOLO-nano / SSD-MobileNet) tạo ra các phát hiện
xe/người, **được giới hạn bởi đa giác ROI**, theo sau là một **bộ theo dõi nhẹ** (SORT/ByteTrack) và
**logic thời gian chờ theo thời gian** trong máy trạng thái. Kết hợp với kênh hiện diện/tốc độ của radar
([ADR-0001](ADR-0001-sensing-modality.vi.md)) để xác nhận tính đứng yên. Cách lai này — diện mạo học
được + giới hạn hình học + xác nhận theo thời gian + kiểm tra chéo bằng radar — vững chắc hơn bất kỳ kỹ
thuật đơn lẻ nào.

**Hai kích hoạt khởi phát khác biệt, theo lớp.** Một cảnh báo cho **xe** dùng *tính đứng yên* — tốc độ
vết dưới cổng (`< 3 km/h`) trong `T_dwell`. Một cảnh báo cho **người** dùng *hiện diện* — một phát hiện
lớp `person` trong hoặc ngay cạnh ROI, có khử dội (`T_person_debounce`), **không** theo cổng tĩnh tại: một
người mắc kẹt thường *đi bộ* (3–6 km/h) và sẽ không bao giờ thỏa `< 3 km/h`, nên tái dùng đường của xe sẽ
bỏ sót một cách hệ thống đúng cái hiểm họa người đi bộ ([tài liệu 04 H-C](../04-risk-and-safety.vi.md#1-bảng-đăng-ký-rủi-ro))
mà lớp `person` tồn tại để bao phủ. Tính bền vững cho một cảnh báo chỉ-do-người-đi-bộ tương ứng hẹp hơn
(không có giữ-khi-che-khuất bằng radar — [ADR-0008](ADR-0008-detection-persistence-and-multitrack.vi.md)).
Một chiếc **mô tô** đang dừng nằm giữa hai loại: là một lớp xe (khởi phát theo tính đứng yên), nhưng tiết
diện phản xạ radar nhỏ khiến đối chứng giữ-khi-che-khuất của nó yếu hơn của một ô tô — coi tính bền vững
của nó là cấp-độ-xe chỉ khi radar thực sự còn trả tín hiệu, ngược lại là chỉ-camera.

## Các phương án đã xét

### Phương án A: Chỉ trừ nền cổ điển / sai phân khung
| Khía cạnh | Đánh giá |
|-----------|------------|
| Độ phức tạp | Thấp |
| Chi phí tại biên | Rất thấp |
| Độ vững chắc | **Kém** — nhạy với thay đổi ánh sáng, bóng đổ, đèn pha, các kiểu dừng chậm/từ từ, rung camera |
| Thông tin lớp | Không có (chỉ là khối blob) — không phân biệt được xe ô tô với mảnh vỡ/người |

**Ưu điểm:** đơn giản, rẻ, không cần dữ liệu huấn luyện.
**Nhược điểm:** mong manh khi ở ngoài trời; một xe dừng đủ lâu sẽ tan vào nền đã học được; bóng đổ/quét
đèn pha gây dương tính giả. Không an toàn nếu là phương pháp duy nhất.

### Phương án B: Bộ phát hiện nhẹ + giới hạn theo ROI + thời gian chờ + radar *(được chọn)*
| Khía cạnh | Đánh giá |
|-----------|------------|
| Độ phức tạp | Trung bình |
| Chi phí tại biên | Vừa phải (phù hợp với Jetson/bộ tăng tốc) |
| Độ vững chắc | **Tốt** — diện mạo + hình học + thời gian + radar |
| Thông tin lớp | Có (ô tô/xe tải/xe buýt/xe máy/người) |

**Ưu điểm:** vững chắc và giải thích được; các lớp cho phép xử lý trường hợp người đi bộ (FR-08);
giới hạn theo ROI loại bỏ phần lớn báo động giả ngoài làn; thời gian chờ + radar cho một tín hiệu
"đã dừng" sạch; tính toán vừa phải.
**Nhược điểm:** cần một mô hình + một ít dữ liệu cục bộ để tinh chỉnh; phải tích hợp bộ phát hiện + bộ
theo dõi + hợp nhất.

### Phương án C: Mô hình sâu đầu-cuối nặng (bộ phát hiện lớn / mô hình sự cố dựa trên video)
| Khía cạnh | Đánh giá |
|-----------|------------|
| Độ phức tạp | Cao |
| Chi phí tại biên | **Cao** (điện năng/nhiệt không thân thiện với năng lượng mặt trời) |
| Độ vững chắc | Cao, nhưng đòi hỏi nhiều dữ liệu |
| Khả năng giải thích | Thấp hơn |

**Ưu điểm:** có khả năng đạt độ chính xác thô cao nhất; có thể tiếp nhận thêm các loại sự cố phong phú
hơn về sau.
**Nhược điểm:** vượt ngân sách/điện năng cho biên; gánh nặng lớn về dữ liệu và huấn luyện; khó kiểm
định và giải thích hơn cho một chức năng an toàn; quá mức cần thiết cho việc hiện diện+đứng yên.

## Phân tích đánh đổi

Tác vụ này **bị ràng buộc và mang tính hình học**, đó chính là nơi mà học đầu-cuối nặng là không cần
thiết và chỉ-dùng-cổ-điển là quá mong manh. Phương án B khai thác cấu trúc đó: bộ phát hiện lo phần
*cái gì*, ROI lo phần *ở đâu*, thời gian chờ lo phần *trong bao lâu*, và radar độc lập lo phần *liệu nó
có thực sự đứng yên hay không*. Cách phân lớp đó cũng **dễ kiểm định và giải thích hơn** — điều quan
trọng cho một hệ thống an toàn — so với một mô hình đơn lẻ mờ đục (Phương án C), và vững chắc hơn nhiều
so với sai phân điểm ảnh (Phương án A). Nó phù hợp với giới hạn biên/năng lượng mặt trời từ
[ADR-0002](ADR-0002-edge-vs-cloud-processing.vi.md).

## Hệ quả

- **Dễ hơn:** phát hiện vững chắc trong ngân sách; quyết định giải thích được; xử lý người đi bộ; cân
  bằng báo-động-giả/bỏ-sót có thể tinh chỉnh qua các ngưỡng ROI + thời gian chờ + hợp nhất.
- **Khó hơn:** lắp ráp/tinh chỉnh bộ phát hiện + bộ theo dõi + hợp nhất; thu thập các đoạn clip cục bộ
  mang tính đại diện (ngày/đêm/mưa) để tinh chỉnh ngưỡng và đánh giá; quản lý các phiên bản mô hình
  qua OTA.
- **Xem xét lại khi:** độ chính xác hiện trường đòi hỏi một mô hình mạnh hơn tại các vị trí khó (thay
  bộ phát hiện phía sau cùng một giao diện), hoặc khi các lớp sự kiện mới (mảnh vỡ, đi ngược chiều)
  biện minh cho một mô hình phong phú hơn (FR-18).
- **Ghi chú nền tảng (2026-07-03, Tuần 1 phần cứng):** mục tiêu biên cụ thể là **Kendryte K230**
  (RISC-V + KPU, CanMV/MicroPython, `kmodel`), không phải đường Jetson/TensorRT mà Phương án B ngầm giả
  định — bộ phát hiện phải chuyển đổi/lượng-tử-hóa sang `kmodel` và đo chuẩn lại (AI#1). Với radar hiện
  đang vắng mặt ([ADR-0001](ADR-0001-sensing-modality.vi.md) chưa được giải quyết), việc kiểm tra chéo
  tính đứng yên bằng radar là không có — tính đứng yên chỉ dựa vào theo dõi bằng camera cho đến khi RQ-H1
  được giải quyết ([tài liệu 09](../09-software-hardware-handoff.vi.md)).

## Hạng mục hành động

1. [ ] Chọn bộ phát hiện + bộ theo dõi và đo chuẩn độ trễ/độ chính xác trên thiết bị biên mục tiêu.
2. [ ] Xác định định dạng cấu hình đa giác ROI và một quy trình hiệu chuẩn theo từng vị trí.
3. [ ] Đặc tả quyết định tính đứng yên: tốc độ vết của bộ phát hiện + tốc độ radar + thời gian chờ, cùng các ngưỡng.
4. [ ] Lắp ráp một tập clip đánh giá bao phủ các kịch bản ở tài liệu 01 §5 (gồm cả ban đêm/mưa/che khuất).
5. [ ] Đặc tả **khởi phát cảnh báo cho người** là *hiện diện* trong/cạnh ROI với một khoảng khử dội (`T_person_debounce`) và một biên "cạnh-ROI" được định nghĩa — khác biệt với cổng tĩnh tại của xe; đưa một **người mắc kẹt đang di chuyển** vào tập đánh giá.
