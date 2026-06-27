# 01 — Yêu cầu & Tiêu chí nghiệm thu

> 🇬🇧 Bản gốc tiếng Anh: [01-requirements.md](01-requirements.md)

**Dự án:** Hệ thống cảnh báo tự động làn dừng xe khẩn cấp (ESW)
**Trạng thái:** Đề xuất
**Cập nhật:** 2026-06-26

Tài liệu này chuyển các mục tiêu được trình bày dưới dạng văn xuôi trong đề xuất thành các yêu cầu có thể kiểm thử. Nó cũng bổ sung ba thứ mà đề xuất cần có trước khi có thể được xây dựng: một **khung an toàn**, **phép tính bố trí cảnh báo**, và **các tiêu chí nghiệm thu đo lường được**.

---

## 1. Tái định khung an toàn (đọc phần này trước)

Đề xuất xem công việc này là "phát hiện một chiếc xe đang dừng và hiển thị một bảng cảnh báo." Về mặt chức năng thì đúng, nhưng hệ thống này **liên quan đến an toàn**: đầu ra của nó ảnh hưởng đến cách những người lái xe đang di chuyển nhanh hành xử khi ở gần một chướng ngại vật đứng yên. Điều đó thay đổi cách chúng ta phải lập luận về sự cố.

Hai kiểu lỗi chiếm ưu thế, và chúng kéo về hai hướng đối lập nhau:

| Lỗi | Điều xảy ra | Hệ quả | Tệ hơn vì… |
|---------|--------------|-------------|----------------|
| **Bỏ sót (âm tính giả)** | Xe đang dừng; cảnh báo không bao giờ hiển thị | Không có cảnh báo sớm — đúng tình huống mà chúng ta đặt ra để khắc phục | Hệ thống đã *được tin tưởng* để bao quát trường hợp này nhưng lại lặng lẽ không làm được. |
| **Báo động giả (dương tính giả)** | Cảnh báo hiển thị mà không có nguy hiểm thực sự | Người lái xe giảm tốc/lách không cần thiết; lặp lại → họ không còn tin vào nó | "Báo động giả lặp lại" (cry wolf) — bào mòn niềm tin vốn làm cho cảnh báo *thực sự* phát huy tác dụng. |

Các hệ quả thiết kế (xuyên suốt mọi tài liệu khác):

- **An toàn khi sự cố (fail-safe) + báo lỗi rõ ràng (fail-loud).** Hệ thống phải phát hiện được sự suy giảm của chính nó và báo cho người vận hành. Một thiết bị bị "mù" không được phép tỏ ra là khỏe mạnh. Xem [ADR-0005](adr/ADR-0005-fail-safe-and-system-safety.vi.md).
- **Cả hai tỉ lệ lỗi đều là yêu cầu hạng nhất** với các chỉ tiêu bằng số (§5), không phải là thứ được nghĩ đến sau cùng.
- **Hiệu chỉnh niềm tin.** Nội dung và hành vi cảnh báo phải giữ được độ tin cậy; không chập chờn, không có cảnh báo cũ kỹ. Logic trễ (hysteresis) và thời gian chờ (dwell) tồn tại vì lý do này ([tài liệu 02](02-system-architecture.vi.md)).
- **Hệ thống đưa ra khuyến cáo; nó không bao giờ điều khiển** các phương tiện khác. Trách nhiệm cuối cùng vẫn thuộc về người lái xe.
- **Phạm vi bảo vệ có giới hạn (nêu rõ, không ngầm định).** Hệ thống cảnh báo về một phương tiện *đã được xác nhận đang dừng* trong một *vùng được giám sát*; nó **không** cảnh báo về một phương tiện vẫn *đang giảm tốc để tấp vào* làn dừng (thời điểm động nhất), một phương tiện dừng *giữa* các vùng được giám sát, hay một người lái xe phớt lờ biển báo. Những nguy cơ còn lại này được liệt kê trong [tài liệu 04 §0](04-risk-and-safety.vi.md#0-giới-hạn-bảo-vệ-mối-nguy-còn-lại) và giới hạn những gì hệ thống có thể cam kết — đó cũng là cách quản lý R7 (phụ thuộc quá mức).

Đây không phải là "thực hiện chứng nhận ISO 26262 / SIL ngay bây giờ" — điều đó dành cho một hệ thống hiện trường đã được sản phẩm hóa. Đây là: *tiếp nhận tư duy an toàn khi sự cố ngay từ ngày đầu để mô hình thử nghiệm trung thực về những gì nó có thể và không thể làm.*

---

## 2. Yêu cầu chức năng

Mức ưu tiên dùng MoSCoW: **M**ust (Phải) / **S**hould (Nên) / **C**ould (Có thể) / **W**on't-now (Chưa làm).

| ID | Yêu cầu | Pri |
|----|-------------|-----|
| FR-01 | Liên tục giám sát một vùng phát hiện (ROI) cấu hình được, bao phủ làn dừng xe khẩn cấp trong tầm nhìn của cảm biến. | M |
| FR-02 | Phát hiện sự hiện diện của một phương tiện (ô tô con, xe tải, xe buýt, xe máy) bên trong ROI. | M |
| FR-03 | Phân biệt một phương tiện **đang dừng** (đứng yên ≥ thời gian chờ) với một phương tiện chỉ đang đi qua/dọc theo làn dừng. | M |
| FR-04 | Xác nhận một lần phát hiện qua một **thời gian chờ (dwell)** cấu hình được trước khi tuyên bố "đang dừng" (mặc định 5 s, dải 3–10 s). | M |
| FR-05 | Khi được xác nhận, tự động kích hoạt (các) bảng cảnh báo phía trước (theo hướng xe tới) hiển thị "STOPPED VEHICLE AHEAD" (*PHÍA TRƯỚC CÓ XE DỪNG KHẨN CẤP*). | M |
| FR-06 | Tiếp tục theo dõi (bám vết) phương tiện đang dừng trong khi cảnh báo đang hoạt động. | M |
| FR-07 | Tự động xóa cảnh báo sau khi phương tiện đã rời khỏi ROI, áp dụng một độ trễ **giữ/trễ (hold/hysteresis)** (mặc định 10 s) để hiện tượng che khuất ngắn không làm rớt một cảnh báo đang hoạt động. | M |
| FR-08 | Phát hiện một **người đi bộ** ở trong hoặc ngay sát ROI (người mắc kẹt trên xe) và coi đó là căn cứ để cảnh báo. *(Hồ sơ cảm biến khó hơn so với phương tiện — diện tích phản xạ radar nhỏ + camera yếu nhất vào ban đêm; §5 đặt một chỉ tiêu riêng, thực tế cho người đi bộ thay vì gộp vào recall của phương tiện.)* | S |
| FR-09 | Hoạt động qua ban ngày, ban đêm, mưa và sương mù (suy giảm nhưng vẫn vận hành được). | M |
| FR-10 | Liên tục tự giám sát tình trạng của cảm biến, khối tính toán, đường truyền và bảng cảnh báo; phát ra một nhịp tín hiệu (heartbeat). | M |
| FR-11 | Chuyển vào một **trạng thái an toàn** đã định nghĩa và cảnh báo người vận hành khi có bất kỳ lỗi trọng yếu nào (xem ADR-0005). | M |
| FR-12 | Gửi các sự kiện kích hoạt/xóa/lỗi kèm dấu thời gian tới TMC và một nhật ký sự kiện (nhật ký kiểm toán). | S |
| FR-13 | Cho phép người vận hành can thiệp thủ công (cưỡng bức bật, cưỡng bức tắt, tắt tiếng) một bảng cảnh báo. | S |
| FR-14 | Hỗ trợ cấu hình từ xa cho ROI, các ngưỡng và các thời gian chờ/giữ (dwell/hold). | S |
| FR-15 | Hỗ trợ cập nhật từ xa (OTA) phần mềm/mô hình kèm khả năng khôi phục về bản trước (rollback). | C |
| FR-16 | Ghi lại đủ bằng chứng phát hiện (ảnh chụp/siêu dữ liệu của sự kiện, không phải video thô liên tục) để kiểm toán một quyết định. | S |
| FR-17 | Tích hợp với một bảng thông báo điện tử (VMS) hiện có do người vận hành điều khiển ở nơi có sẵn, thay vì lắp thêm một bảng cảnh báo. | S |
| FR-18 | Phát hiện các chướng ngại vật chung (mảnh vỡ, động vật) / phương tiện đi ngược chiều. | W (tương lai) |
| FR-19 | Tự động thông báo cho các dịch vụ khẩn cấp / quản lý sự cố. | W (tương lai) |
| FR-20 | Thực thi **ràng buộc biên tham số tại thiết bị**: từ chối hoặc kẹp (clamp) bất kỳ cấu hình nào được đẩy xuống (ROI, dwell, hold, ngưỡng tốc độ, tập thông điệp) nằm ngoài dải an toàn đã khai báo của nó, và phân giai/kiểm chứng một thay đổi cấu hình giống như một bản cập nhật. Việc ký số ngăn *giả mạo*, không phải *lỗi* của người vận hành — một ROI sai hay `T_dwell=900 s` âm thầm phá vỡ chức năng an toàn và sẽ không kích hoạt một canary mô hình. | M |
| FR-21 | Hoãn **các bản cập nhật OTA và các lần khởi động lại không trọng yếu trong khi một cảnh báo đang hoạt động** (tập bám vết không rỗng), hoặc đưa bảng cảnh báo về một trạng thái trống đã biết *báo rõ cho người vận hành* trong cửa sổ cập nhật — không bao giờ âm thầm làm rớt một cảnh báo đang hoạt động cho một bản cập nhật phần mềm (xem xử lý hiện-diện-lúc-khởi-động, [tài liệu 02 §4](02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo)). | S |

### Hành vi từ phát hiện đến cảnh báo (vòng lặp chuẩn tắc)

```
idle → (vehicle enters ROI) → tracking
tracking → (stationary ≥ dwell) → CONFIRMED → WARN ON
WARN ON → (vehicle still present) → hold
WARN ON → (vehicle absent ≥ hold) → WARN OFF → idle
any state → (critical fault) → SAFE STATE + operator alert
```

Máy trạng thái (state machine) đầy đủ, kèm các bộ định thời và các trường hợp biên, được đặc tả trong
[tài liệu 02 §4](02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo).

---

## 3. Yêu cầu phi chức năng

| ID | Hạng mục | Yêu cầu |
|----|----------|-------------|
| NFR-01 | **Độ trễ** | Xác nhận đang dừng → cảnh báo BẬT ≤ 2 s sau khi thời gian chờ trôi qua (nên tổng thời gian từ dừng→cảnh báo ≈ dwell + ≤2 s). **Đạt theo bộ truyền động (backend-qualified):** đáp ứng trực tiếp bởi bảng LED chuyên dụng; với một **VMS** hiện có do người vận hành điều khiển, chu trình lệnh/làm tươi và phân xử thông điệp của người vận hành có thể vượt quá 2 s, nên NFR-01 mang theo ngân sách độ trễ riêng của bộ điều hợp VMS ([ADR-0004](adr/ADR-0004-warning-actuator-integration.vi.md), [ADR-0009 §A](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md)). |
| NFR-02 | **Độ trễ** | Xe đã rời đi → cảnh báo TẮT trong vòng hold + ≤ 2 s. |
| NFR-03 | **Độ sẵn sàng** | Độ sẵn sàng **chức năng** ≥ 99% trên mỗi điểm giám sát trong suốt giai đoạn thử nghiệm — tỉ lệ thời gian mà thiết bị thực sự có thể *phát hiện-và-cảnh báo đúng đặc tả*, không chỉ là "có điện và đang báo cáo"; thời gian ở trạng thái suy giảm/an toàn được tính là **không sẵn sàng**. Không tính bảo trì theo lịch. Đo tại hiện trường (xem §3a). |
| NFR-04 | **Độ tin cậy** | Không một lỗi phần mềm đơn lẻ nào được phép để một cảnh báo **BẬT cũ kỹ (stale ON)** kéo dài vô thời hạn — một watchdog (bộ canh chừng) phải giới hạn thời gian của mọi lần kích hoạt và xác nhận lại. |
| NFR-05 | **Độ bền vững** | Duy trì mức phát hiện mục tiêu trong mưa và vào ban đêm thông qua cảm biến đa cảm biến ([ADR-0001](adr/ADR-0001-sensing-modality.vi.md)) — **phụ thuộc vào cổng kiểm chứng phát hiện vật đứng yên bằng radar**; được kiểm chứng tại hiện trường, không thể tuyên bố từ một bàn thử radar tổng hợp (§3a, §5). |
| NFR-06 | **Tự chủ tại biên** | Vòng lặp phát hiện→cảnh báo phải hoạt động được khi WAN/đám mây hoàn toàn mất kết nối ([ADR-0002](adr/ADR-0002-edge-vs-cloud-processing.vi.md)). |
| NFR-07 | **Năng lượng** | Chạy bằng điện lưới, hoặc pin mặt trời + ắc quy với khả năng tự chủ ≥ 72 h khi không có nắng ([ADR-0006](adr/ADR-0006-connectivity-and-power.vi.md)). |
| NFR-08 | **Khả năng bảo trì** | Giám sát tình trạng từ xa, cấu hình từ xa, cập nhật OTA; các khối cảm biến/tính toán/bảng cảnh báo dạng mô-đun. |
| NFR-09 | **Bảo mật** | Các kênh điều khiển + đo từ xa được xác thực và mã hóa; phần sụn được ký số; việc kích hoạt bảng cảnh báo không thể bị giả mạo bởi một bên ngoài. |
| NFR-10 | **Quyền riêng tư** | Suy luận trên thiết bị; **không lưu giữ video thô liên tục**; bằng chứng sự kiện được tối thiểu hóa và kiểm soát truy cập (xem [tài liệu 04](04-risk-and-safety.vi.md)). |
| NFR-11 | **Tiêu chuẩn** | Biển báo cảnh báo tuân thủ **QCVN 41** (quy chuẩn kỹ thuật quốc gia về báo hiệu đường bộ) và các tiêu chuẩn hình học đường cao tốc (ví dụ TCVN 5729 về thiết kế đường cao tốc). |
| NFR-12 | **Chi phí** | Bảng kê vật tư trên mỗi điểm hướng tới một thiết bị thử nghiệm hiện trường có tính khả thi (được theo dõi trong [tài liệu 03](03-roadmap-and-phasing.vi.md)); bản dựng cấp trường giữ trong mức ngân sách 20M VND (mô hình thử nghiệm/mô phỏng). |
| NFR-13 | **Môi trường** | Các thiết bị hiện trường được định mức cho nhiệt độ, độ ẩm, bụi, rung động ngoài trời (vỏ bảo vệ IP65+). |
| NFR-14 | **Khả năng mở rộng** | Kiến trúc phải cho phép bổ sung các loại cảm biến và các lớp sự kiện mới (FR-18/19) mà không cần thiết kế lại. |

---

## 3a. Phạm vi kiểm chứng — giai đoạn được tài trợ (bàn thử/mô phỏng) thực sự có thể chứng minh điều gì

Không phải mọi yêu cầu ở trên đều có thể được *kiểm chứng* trên một bàn thử trong phòng thí nghiệm trong phạm vi 20M VND; một số được **thiết kế ngay bây giờ nhưng chỉ chứng minh được tại hiện trường** (cấp sở). Nêu rõ điều này ngay từ đầu giúp báo cáo cuối cùng được trung thực — một yêu cầu "Phải" mà không có bằng chứng nghiệm thu trong phạm vi tài trợ được đánh dấu *ở đây*, không phải bị phát hiện lúc rà soát. Các nhãn: **B** = bàn thử · **S** = mô phỏng · **F** = hoãn sang giai đoạn hiện trường · **D** = chỉ thiết kế/rà soát. Phương pháp luận đằng sau cách phân tách này là [ADR-0007](adr/ADR-0007-validation-and-data-strategy.vi.md).

| Yêu cầu | Kiểm chứng trong phạm vi tài trợ | Vì sao |
|-------------|---------------------------|-----|
| FR-09 (ngày/đêm/mưa/sương mù) | **S (xấp xỉ) + F** | Một bàn thử không thể tạo ra mưa/lóa/sương mù thật; mô phỏng chỉ xấp xỉ. Recall trong điều kiện thực được hoãn sang giai đoạn hiện trường. |
| FR-17 (tái sử dụng VMS hiện có) | **F** | Cần một VMS thật do người vận hành điều khiển; bàn thử dùng một LED thay thế. |
| NFR-03 (độ sẵn sàng chức năng) | **F** | Một chỉ số vận hành; bàn thử chỉ có thể đặc trưng hóa MTBF của vòng lặp phần mềm dưới điều kiện tiêm lỗi. |
| NFR-05 (độ bền vững mưa/đêm) | **F** | Phụ thuộc vào cổng radar của [ADR-0001](adr/ADR-0001-sensing-modality.vi.md); không thể tuyên bố từ một bàn thử radar tổng hợp. |
| NFR-07 (pin mặt trời tự chủ ≥ 72 h) | **F** | Chỉ thiết kế ở phạm vi bàn thử (điện lưới phòng thí nghiệm). |
| NFR-11 / NFR-14 (tiêu chuẩn, khả năng mở rộng) | **D** | Rà soát mức độ tuân thủ và lập luận kiến trúc, không phải một phép kiểm thử lúc chạy. |
| NFR-13 (môi trường IP65) | **F** | Không có vỏ bảo vệ cấp hiện trường nào được chế tạo ở phạm vi bàn thử. |
| Tất cả FR/NFR còn lại | **B + S** | Logic, độ trễ, xử lý lỗi, quyền riêng tư, tự chủ tại biên, can thiệp thủ công, cấu hình và các sự kiện đều có thể thực thi được trên bàn thử/mô phỏng. |

Mọi thứ được gắn nhãn **F** đều được chuyển tiếp sang nghiệm thu thử nghiệm hiện trường
([tài liệu 05 §11](05-field-pilot-proposal.vi.md#11-kpi-nghiệm-thu-hiện-trường)); **không thứ gì gắn nhãn F được phép báo cáo
như một kết quả đo lường của mô hình thử nghiệm.**

---

## 4. Bố trí cảnh báo — phép tính mà đề xuất bỏ sót

Đề xuất nói bảng cảnh báo đặt "ở đầu đoạn làn dừng xe khẩn cấp / trước vùng nguy hiểm." Điều đó chưa được đặc tả đầy đủ và là quyết định hình học trọng yếu an toàn nhất trong số tất cả. Nếu cảnh báo quá gần phương tiện đang dừng, người lái xe không thể hành động kịp; hệ thống sẽ chỉ là **diễn kịch**.

Một người lái xe đi sau phải **phát hiện → nhận biết → quyết định → điều khiển** (giảm tốc và/hoặc chuyển làn). Vì vậy, tiêu chuẩn chi phối không chỉ là cự ly tầm nhìn dừng xe (SSD) mà là **cự ly tầm nhìn quyết định (DSD)** cho một thao tác đổi tốc độ/đổi hướng trên đường tốc độ cao.

**Cự ly tầm nhìn dừng xe** (dạng hệ mét theo AASHTO, độ dốc bằng phẳng, thời gian nhận biết-phản ứng t = 2.5 s, gia tốc hãm a = 3.4 m/s²):

```
SSD = 0.278 · V · t  +  0.039 · V² / a       (V in km/h, SSD in m)
```

| Tốc độ thiết kế V | SSD (phải dừng được) | DSD — thao tác C* (nhận biết + chuyển làn/giảm tốc) |
|---------------:|----------------:|--------------------------------------------------:|
| 80 km/h | ≈ 130 m | ≈ 230 m |
| 100 km/h | ≈ 185 m | ≈ 315 m |
| 120 km/h | ≈ 250 m | ≈ 360 m |

\* Thao tác DSD C = "đổi tốc độ/đổi đường đi/đổi hướng trên đường nông thôn/tốc độ cao" (AASHTO). Đây là cơ sở phù hợp vì phản ứng an toàn ở đây là một **lần chuyển làn**, không phải một lần dừng khẩn cấp. Cột DSD-C được đọc từ bảng đã công bố của AASHTO — một cự ly thao tác ở tốc độ không đổi có dạng `d = 0.278 · V · t_C` — và **không** được tính từ công thức SSD ở trên (nó không có số hạng hãm phanh), nên đừng kỳ vọng biểu thức đó tái tạo được 315 m ở 100 km/h.

**Vì sao dùng DSD-C chứ không chỉ "SSD + một lần chuyển làn"?** SSD giả định rằng người lái xe *dừng lại*; phản ứng an toàn trước một chướng ngại vật ở làn dừng thường là *giữ tốc độ và chuyển làn* — một nhiệm vụ quyết định-và-điều khiển — nên DSD (thao tác C) mới là cơ sở có thể bảo vệ được. Nó được chọn một cách **bảo thủ** có chủ ý: DSD-C vượt SSD khoảng ~130 m ở 100 km/h, điều này tạo ra biên dự phòng nhưng đồng thời cũng **nâng cao ngưỡng mà một điểm phải đạt** (PL-04). Một khoảng cách yêu cầu quá dài có thể đánh dấu những điểm vốn khả thi là "không phù hợp", vì vậy hãy coi bảng trên là một **mức sàn thiết kế** và, theo từng điểm, cũng tính "SSD + một khoảng cách chuyển làn thoải mái" như một cận dưới; hãy dùng phán đoán kỹ thuật (và sự đồng thuận của người vận hành) ở nơi hai giá trị này phân kỳ.

**Đối chiếu với tiêu chuẩn Việt Nam.** Các con số ở trên là theo AASHTO. Để được phê duyệt, cơ sở cự ly tầm nhìn phải được diễn đạt theo **tiêu chuẩn Việt Nam chi phối — TCVN 5729 (thiết kế hình học đường cao tốc), cùng với QCVN 41 cho bản thân biển báo**. Hãy ánh xạ lập luận DSD-C lên các quy định về cự ly tầm nhìn của TCVN 5729, hoặc biện giải DSD theo AASHTO như một cơ sở an toàn bổ sung ở nơi TCVN không đề cập. Đây là một **nhiệm vụ phương pháp luận cho nghiên cứu chọn vị trí** (Giai đoạn 1), không phải một việc nghĩ đến sau cho từng điểm.

**Yêu cầu PL (bố trí):**

- **PL-01 (M):** Bảng cảnh báo phải được hiển thị **cách vùng phát hiện ít nhất một khoảng DSD (thao tác C) về phía trước (theo hướng xe tới)** ứng với tốc độ thiết kế của tuyến (bảng trên là mức sàn thiết kế; cần đối chiếu với tiêu chuẩn Việt Nam chi phối cho từng điểm).
- **PL-02 (M):** Bổ sung một **cự ly đọc được (legibility distance)** để bảng cảnh báo có thể *đọc được* vào thời điểm người lái xe còn cách một khoảng DSD — với một VMS văn bản LED, khả năng đọc vào khoảng 1 m trên mỗi 4–8 mm chiều cao ký tự; hãy xác định kích thước bảng cho phù hợp, hoặc đặt nó xa hơn về phía trước tương ứng.
- **PL-03 (M):** Tính đến **độ trễ kích hoạt**: trong khoảng thời gian từ dừng→cảnh báo (≈ dwell + ≤2 s) dòng xe vẫn tiếp tục tiến đến. Bảng cảnh báo cố định ở phía trước, vì vậy một khi đã sáng thì mọi người lái xe đi sau đều nhận được trọn vẹn khoảng DSD; độ trễ chỉ giới hạn cửa sổ thời gian ngắn trước khi bảng sáng. Hãy giữ tổng thời gian từ dừng→cảnh báo nhỏ (NFR-01) để cửa sổ đó ngắn so với khoảng cách giữa các xe (headway).
- **PL-04 (S):** Ở nơi mà hình học (đường cong, đỉnh dốc, cửa hầm) chắn tầm nhìn tới một bảng cảnh báo đơn lẻ ở khoảng cách yêu cầu, hãy dùng một **bảng cảnh báo lặp lại thứ hai** hoặc tái bố trí; nếu cả hai đều không khả thi, điểm đó không phù hợp để triển khai thiết bị đơn lẻ — ghi nhận điều này như một ràng buộc về vị trí (giả định A4).

**Ngân sách phơi nhiễm chưa-cảnh-báo (cái giá của `T_dwell`).** Việc xác nhận không miễn phí. Trong cửa sổ `τ = T_dwell + T_activate` (danh định 5 + ≤2 ≈ **7 s**) sau khi một phương tiện vừa dừng, chưa có cảnh báo nào được hiển thị. Vì bảng cảnh báo cố định ở phía trước, điều này **không** rút ngắn khoảng dẫn (lead) của những người lái xe đi qua bảng *sau* khi nó sáng — họ vẫn nhận được trọn vẹn khoảng DSD; phần phơi nhiễm là **những phương tiện đi sau đi qua vị trí của bảng trong khoảng `τ`**, những người nhận được khoảng dẫn giảm đi hoặc bằng không. Hãy xấp xỉ nó như sau:

```
N_unwarned ≈ τ / h        (h = khoảng cách thời gian trung bình giữa các xe đi sau, s/xe, mỗi làn)
L_unwarned ≈ τ · V        (quãng đường một xe đi sau đi được trong khoảng τ; 7 s @ 100 km/h ≈ 194 m)
```

Ở khoảng cách thời gian (headway) 2 s, `τ ≈ 7 s` phơi nhiễm ~3–4 phương tiện đi sau mỗi làn trước khi cảnh báo xuất hiện. Đây là dạng định lượng của nguy cơ còn lại trong
[tài liệu 04 §0](04-risk-and-safety.vi.md#0-giới-hạn-bảo-vệ-mối-nguy-còn-lại), và nó giới hạn `T_dwell`
**từ phía trên**: một dwell dài hơn mua được ít báo động giả hơn (tốt) nhưng làm lớn `N_unwarned` và để phương tiện vừa-dừng không được bảo vệ lâu hơn (xấu). Hãy định cỡ `T_dwell` sao cho `N_unwarned` nằm trong một trần do người vận hành đồng thuận ứng với headway của điểm, và giữ `T_activate` nhỏ (NFR-01). **Đây chính là ngân sách** mà [tài liệu 02 §4](02-system-architecture.vi.md#4-máy-trạng-thái-phát-hiệncảnh-báo) nhắc đến khi nói hãy điều chỉnh dwell theo phơi nhiễm chưa-cảnh-báo.

> Điều này biến việc bố trí cảnh báo thành một **con số được suy ra, có thể bảo vệ được cho từng điểm**, không phải một phỏng đoán. Đây là một trong những bổ sung giá trị nhất so với đề xuất ban đầu.

---

## 5. Chỉ số đánh giá & tiêu chí nghiệm thu

Đề xuất nói cần "đánh giá khả năng phát hiện và tự động bật/tắt." Phần này nói **đối chiếu với cái gì**. Các chỉ tiêu được tách thành *mô hình thử nghiệm cấp trường* (bench/sim) và *thử nghiệm hiện trường* (giai đoạn tiếp theo) vì chúng được kiểm chứng theo những cách rất khác nhau.

| Chỉ số | Định nghĩa | Chỉ tiêu mô hình thử nghiệm (bench/sim) | Chỉ tiêu thử nghiệm hiện trường |
|--------|-----------|------------------------------|--------------------|
| **Recall — phương tiện** | số sự kiện xe dừng thực được phát hiện ÷ tất cả sự kiện như vậy | ≥ 95% ban ngày (bench/sim). **Ban đêm/điều kiện bất lợi bị khóa (gated)** — chỉ có thể tuyên bố nếu cổng radar của [ADR-0001](adr/ADR-0001-sensing-modality.vi.md) vượt qua trên phần cứng thật; nếu không thì **hoãn sang giai đoạn hiện trường**, không bao giờ khẳng định từ radar tổng hợp | ≥ 98% ban ngày · ≥ 95% ban đêm/điều kiện bất lợi |
| **Recall — người đi bộ** | số sự kiện người mắc kẹt trên xe được phát hiện ÷ tất cả sự kiện như vậy (FR-08) | theo dõi **riêng biệt**, nỗ lực tối đa (RCS nhỏ + camera yếu nhất vào ban đêm); chỉ tiêu được đặt sau khi có dữ liệu Giai đoạn 3, **không** giả định bằng với phương tiện | ≥ 90% ban ngày · nỗ lực tối đa vào ban đêm |
| **Tỉ lệ kích hoạt sai** | các cảnh báo sai ÷ **mức phơi nhiễm (exposure)** — báo cáo **cả hai** trên mỗi 100 kịch bản dàn dựng *và* trên mỗi giờ vận hành (số đếm thô qua các tổ hợp kịch bản khác nhau không thể so sánh được) | ≤ 1 trên mỗi 100 kịch bản dàn dựng *và* một tỉ lệ trên mỗi giờ được báo cáo | **tạm thời** ≤ 1 / điểm / tuần, **chờ hiệu chỉnh niềm tin của người vận hành** ([tài liệu 04 §5](04-risk-and-safety.vi.md#5-các-câu-hỏi-an-toàn-còn-mở-cho-nhóm)) |
| **Độ trễ phát hiện** | phương tiện trở nên đứng yên → cảnh báo BẬT | ≤ dwell + 2 s | như nhau |
| **Độ trễ xóa** | phương tiện rời ROI → cảnh báo TẮT | ≤ hold + 2 s **khi có thoát ra đã xác nhận** (một lần che khuất được giữ không phải là lỗi độ trễ xóa — [ADR-0008](adr/ADR-0008-detection-persistence-and-multitrack.vi.md)) | như nhau |
| **Cự ly cảnh báo hiệu dụng phía trước** | khoảng cách phía trước mà tại đó cảnh báo đang hoạt động nhìn thấy/đọc được | ≥ DSD ứng với tốc độ được mô hình hóa | ≥ DSD tại hiện trường, đã khảo sát |
| **Độ sẵn sàng chức năng** | thời gian có thể *phát hiện-và-cảnh báo đúng đặc tả* ÷ tổng thời gian (thời gian ở trạng thái suy giảm/an toàn được tính là không hoạt động — NFR-03) | MTBF của vòng lặp phần mềm dưới điều kiện tiêm lỗi (bản thân độ sẵn sàng được **hoãn sang giai đoạn hiện trường**) | ≥ 99% |
| **Phạm vi phát hiện lỗi** | các lỗi được tiêm vào mà bộ tự giám sát bắt được & báo leo thang | ≥ 95% danh sách lỗi FMEA ([tài liệu 04 §2](04-risk-and-safety.vi.md#2-fmea-lite-kiểu-lỗi--tác-động--phát-hiện--phản-ứng)) — **lưu ý:** chỉ số này đo việc phát hiện các lỗi *đã liệt kê*, không phải các lỗi chưa biết | ≥ 95% |
| **MTBF / MTTR** | thời gian trung bình giữa các lần lỗi / để sửa chữa | đặc trưng hóa trên mô hình | chỉ tiêu MTBF đặt ở giai đoạn thử nghiệm |

**Đủ về mặt thống kê (để một chỉ tiêu thực sự kiểm thử được).** Một ngưỡng trần trụi "≥ 95%" không phải là một ngưỡng đạt/không đạt nếu thiếu cỡ mẫu và mức độ tin cậy: 19/20 sự kiện là 95%, nhưng cận tin cậy 95% phía dưới của nó chỉ ~75%. Vì vậy mỗi chỉ số dạng **tỉ lệ** đều mang theo một **số sự kiện tối thiểu và một phát biểu về độ tin cậy** — ví dụ *recall ≥ 95% với cận 95% (Wilson) phía dưới ≥ 90% trên ≥ 200 sự kiện dàn dựng*, và kích hoạt sai được báo cáo kèm mẫu số phơi nhiễm và một khoảng tin cậy của nó. Mô phỏng có thể tạo ra khối lượng này một cách rẻ tiền — một lý do cụ thể để dùng nó — trong khi bàn thử báo cáo N mà nó thực sự đạt được. Hãy cố định N và cận chính xác cho từng chỉ số trong phương pháp luận mô phỏng
([ADR-0007](adr/ADR-0007-validation-and-data-strategy.vi.md) AI#1); một "≥ 95%" tuyên bố từ một nhúm lần chạy không phải là một kết quả đo lường.

**Nghiệm thu cho nhiệm vụ cấp trường** = trình diễn, trên mô hình thử nghiệm trên bàn (bench) và/hoặc mô phỏng, toàn bộ vòng kín (chu trình khép kín) (phát hiện → xác nhận → cảnh báo → theo dõi → xóa) đạt các chỉ tiêu ở cột mô hình thử nghiệm (ở các cỡ mẫu nêu trên) trên một tập kịch bản đã định nghĩa (ban ngày, ban đêm, mưa, đi qua thoáng qua, **ùn tắc / dừng-chạy (stop-and-go) đứng yên bên cạnh ROI ở làn lưu thông — _không_ được kích hoạt sai**, **che khuất ngắn và kéo dài có và không có sự chứng thực của radar**, **nhiều phương tiện đồng thời đi đến và rời đi**, người đi bộ, **một phương tiện đã hiện diện sẵn lúc khởi động (boot)**, và **các lỗi cảm biến/khối tính toán/bảng cảnh báo được tiêm vào — bao gồm cả việc giết tiến trình máy trạng thái, giết hộp biên (edge box), và cắt đường truyền tới bảng cảnh báo để chứng minh cơ chế tự ngắt an toàn (dead-man's switch) của bộ điều khiển biển báo làm trống biển báo trong mọi trường hợp** ([ADR-0009](adr/ADR-0009-failsafe-placement-and-degraded-modes.vi.md))), cùng với báo cáo khả thi và đề xuất phát triển thử nghiệm hiện trường mà đề tài tài trợ yêu cầu.

**Ranh giới chứng minh được (nêu rõ trong báo cáo).** Các kết quả bench/sim chứng thực *logic, thời gian định thời, xử lý lỗi, và khả năng kháng kích hoạt sai trước các nhiễu đã được mô hình hóa*; chúng **không** chứng thực recall trong điều kiện thực khi mưa/lóa/sương mù, tỉ lệ báo động giả thực, hay hiệu năng trước nhiễu lộn xộn (clutter) thực của radar — những điều này được hoãn sang giai đoạn hiện trường ([ADR-0007](adr/ADR-0007-validation-and-data-strategy.vi.md)). Hãy báo cáo mọi kết quả kèm theo cấp độ của nó (§3a) để không tuyên bố nào vượt quá bằng chứng của nó.

---

## Phụ lục A — Các thay đổi và chỉnh sửa so với đề xuất

| # | Trong đề xuất | Thay đổi / bổ sung ở đây | Vì sao |
|---|-----------------|------------------------|-----|
| 1 | "Phát hiện một chiếc xe đang dừng, hiển thị một bảng cảnh báo." | Tái định khung thành một hệ thống **liên quan đến an toàn** với các yêu cầu an toàn khi sự cố + niềm tin. | Sự cố thầm lặng và báo động giả lặp lại mới là những rủi ro thực sự. |
| 2 | Bảng cảnh báo "ở đầu làn." | **Yêu cầu bố trí dựa trên DSD** với các con số theo từng tốc độ (§4). | Nếu không, cảnh báo có thể quá muộn để hữu ích. |
| 3 | Đa cảm biến được liệt kê như một tùy chọn "có thể phát triển hướng tới." | **Nâng camera+radar lên thành cốt lõi** cho điều kiện đêm/mưa/sương mù. | Đó là những điều kiện rủi ro cao được nêu tên và phương án chỉ-camera là yếu nhất ở đó. |
| 4 | "Vòng kín: phát hiện–xác nhận–cảnh báo–theo dõi–hủy." | Biến thành một **máy trạng thái cụ thể** với dwell + trễ (hysteresis) + watchdog. | Ngăn các lần kích hoạt sai, sự chập chờn, và tình trạng BẬT cũ kỹ. |
| 5 | "Bộ xử lý trung tâm." | Được đặc tả thành **cục bộ tại biên**; đám mây không trọng yếu. | Một cảnh báo an toàn không được phép chờ một vòng truyền qua mạng. |
| 6 | "Đánh giá khả năng phát hiện." | **Các tiêu chí nghiệm thu bằng số** (§5). | "Đánh giá" cần một ngưỡng đạt/không đạt. |
| 7 | Ngầm định lắp bảng cảnh báo mới ở khắp nơi. | **Tái sử dụng VMS hiện có** ở nơi có sẵn; bảng cảnh báo LED dùng pin mặt trời làm phương án dự phòng. | Rẻ hơn, tránh rối loạn biển báo, được phê duyệt nhanh hơn. |
| 8 | Quyền riêng tư không được đề cập. | **Tối thiểu hóa dữ liệu, không lưu giữ video thô, tuân thủ QCVN 41.** | Camera trên đường công cộng mang theo PII và các nghĩa vụ pháp lý. |
| 9 | Ngân sách 20M VND, tham vọng hiện trường. | **Rà soát thực tế phạm vi**: mô hình thử nghiệm/mô phỏng bây giờ, thử nghiệm hiện trường = đề tài cấp sở ở giai đoạn tiếp theo. | Xác định phạm vi một cách trung thực; bản thân đề xuất đã dự liệu trước giai đoạn tiếp theo. |
| 10 | Cách đánh số mục (5→2.x, 6→3.x) là dấu vết còn sót lại của khuôn mẫu. | Mang tính hình thức — đánh số lại trong đề xuất cuối cùng. | Chỉ là vệ sinh tài liệu. |
