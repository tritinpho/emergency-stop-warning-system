# ADR-0014: Phương tiện mang tín hiệu cho liên kết biển báo IF-4 — LoRa điểm-điểm, và ràng buộc chu kỳ làm việc lên cơ chế tự ngắt an toàn

> 🇬🇧 Bản gốc tiếng Anh: [ADR-0014-sign-link-bearer.md](ADR-0014-sign-link-bearer.md)

**Trạng thái:** Đề xuất — phần cứng/firmware (RF + pháp lý) + phần mềm (định thời/xác thực IF-4). Phân tích phía phần mềm đã xong; **bị chặn** chờ một phép thử thời gian chiếm sóng trên bàn thử, một xác nhận phân loại pháp lý về chu kỳ làm việc, và một phép thử tầm xa qua khoảng cách trước khi có thể được Chấp nhận.
**Ngày:** 2026-07-03
**Người quyết định:** Chủ nhiệm đề tài / trưởng nhóm phần mềm, trưởng nhóm phần cứng/firmware, khâu kiểm tra pháp lý/tuân thủ

## Bối cảnh

IF-4 (thiết bị biên → bộ điều khiển biển báo, [ICD §3](../08-interface-control-document.vi.md)) là giao diện **mang an toàn khi sự cố** duy nhất: bộ điều khiển hiển thị `SHOW` **chỉ** trong khi một khẳng định mới, được xác thực đến trong vòng `T_signhold`, ngược lại thì **làm trống** — cơ chế tự ngắt an toàn (dead-man's switch) nằm trong bộ điều khiển biển báo ([ADR-0009 §A](ADR-0009-failsafe-placement-and-degraded-modes.vi.md)). Điều đó đòi hỏi phương tiện mang phải duy trì một **khẳng định làm mới với `T_assert_refresh` ≤ ¼·`T_signhold`**. Biển báo nằm **cách ≥ DSD (~315 m) về phía thượng lưu** của thiết bị biên (bố trí theo TCVN 5729), nên một liên kết dài là không thể tránh khỏi và việc đặt biển báo cùng chỗ với thiết bị biên là bị loại trừ.

Hai diễn biến buộc quyết định này phải đưa ra bây giờ:

1. **Nguyên mẫu Tuần 1 của nhóm phần cứng** (2026-06-29) đặt liên kết biên→biển báo lên **LoRa 433 MHz (ESP32 + SX1276)**. Bản demo thực tế chốt sáng một LED bằng một khung tín hiệu một-lần, nhưng phương tiện mang dự kiến là LoRa — một lựa chọn trên-thực-tế của lớp vật lý IF-4, vốn [ICD §7](../08-interface-control-document.vi.md) đã **hoãn sang tích hợp** một cách tường minh.
2. [ADR-0006](ADR-0006-connectivity-and-power.vi.md) chỉ nêu LoRaWAN như một kênh phụ đo lường từ xa **không-trọng-yếu-an-toàn** tới TMC ("vòng lặp an toàn không bao giờ phụ thuộc vào bất kỳ thứ nào trong số này"). Đặt LoRa lên **IF-4** đưa nó vào đường an toàn — một tập yêu cầu khác (xác thực, chống phát lại, định thời làm mới) mà ADR này ghi lại.

Các yếu tố tác động: tầm với (≥315 m, gần tầm nhìn thẳng dọc làn dừng, biên dự phòng cho mưa/tán lá), nguồn điện (năng lượng mặt trời, cả hai cụm), **ngân sách thời gian chiếm sóng/chu kỳ làm việc so với tốc độ làm mới yêu cầu**, chi phí xác thực (HMAC + seq/nonce → kích thước khung → thời gian chiếm sóng), các **giới hạn pháp lý về 433 MHz của Việt Nam**, và chi phí nguyên mẫu.

## Quyết định

Áp dụng **LoRa thô (loại SX1276) điểm-điểm** — *không* dùng LoRaWAN (không có cổng gateway hay lớp MAC quản-lý-chu-kỳ trong đường an toàn; ta điều khiển định thời trực tiếp) — làm phương tiện mang IF-4 **cho nguyên mẫu, với điều kiện** một ngân sách thời-gian-chiếm-sóng/chu-kỳ-làm-việc được chứng minh trên bàn thử duy trì được `T_assert_refresh` ≤ ¼·`T_signhold` ở một hệ số trải phổ (SF) mà **đồng thời** khép được liên kết ≥315 m trong trần công suất miễn giấy phép. Nếu ngân sách đó không khép được, cách giải quyết là một sự nới lỏng `T_signhold` **tường minh, có ghi nhận** (một cận BẬT-cũ-tối-đa tệ hơn) **hoặc** một phương tiện mang khác (Phương án C) — mỗi cách đều là thay đổi cấp-ADR, không phải một lần tinh chỉnh âm thầm.

Điều này **thay thế giả định ngầm** trong [ICD §7](../08-interface-control-document.vi.md) rằng phương tiện mang IF-4 còn chưa quyết, và **làm rõ nhập nhằng** ở [ADR-0006](ADR-0006-connectivity-and-power.vi.md): LoRa-làm-đo-lường-TMC (không-trọng-yếu-an-toàn) và LoRa-làm-phương-tiện-mang-IF-4 (trọng yếu an toàn) là hai kênh khác nhau với yêu cầu khác nhau.

## Các phương án đã xét

### Phương án A: LoRa 433 MHz điểm-điểm *(được chọn, có điều kiện)*
| Khía cạnh | Đánh giá |
|-----------|------------|
| Độ phức tạp | Thấp–Trung bình (demo Tuần 1 đã chạy SX1276 trên ESP32) |
| Chi phí | Thấp — nằm trong khung 20M |
| Tầm với | Tốt ở ~315 m gần tầm nhìn thẳng, ngay cả ở SF thấp |
| Nguồn điện | Thấp — thân thiện năng lượng mặt trời |
| Dư địa chu kỳ làm việc | **Chật / bị giới hạn bởi pháp lý** |

**Ưu điểm:** rẻ nhất, công suất thấp nhất, đã có nguyên mẫu, PHY điều khiển được cho một nhịp tim tất định.
**Nhược điểm:** một sự ghép nối **tốc-độ-làm-mới ↔ thời-gian-chiếm-sóng ↔ chu-kỳ-làm-việc ↔ tầm-xa** mà pháp luật Việt Nam khiến trở nên ràng buộc (xem Phân tích đánh đổi). Chi phí xác thực (HMAC + seq/nonce) *làm tăng* thời gian chiếm sóng, nên an ninh đánh đổi trực tiếp với độ cũ của tín hiệu.

### Phương án B: Có dây (cáp chôn / luồn ống) biên↔biển báo
| Khía cạnh | Đánh giá |
|-----------|------------|
| Tính tất định | **Cao** — không giới hạn chu kỳ, xác thực dễ |
| Tính khả thi | **Thấp** đối với nguyên mẫu |

**Ưu điểm:** tất định, không trần chu kỳ làm việc pháp lý, kênh xác thực đơn giản.
**Nhược điểm:** đào rãnh ~315 m dọc làn dừng là không khả thi cho một nguyên mẫu bàn thử 20M (công trình dân dụng, giấy phép đào đường) và thường cả ở hiện trường. Bị loại cho nguyên mẫu; giữ lại như một phương án cho một số vị trí hiện trường cố định.

### Phương án C: RF tốc độ cao hơn không có trần chu kỳ nghiêm ngặt
Liên kết định hướng 2.4 GHz; một mô-đun FHSS dưới-1-GHz trong một băng cho phép chu kỳ cao / LBT; hoặc LTE-M / di động riêng.

**Ưu điểm:** loại bỏ trần chu kỳ → có thể duy trì một nhịp tim nhanh.
**Nhược điểm:** 2.4 GHz có biên tầm-xa/mưa/tán-lá tệ hơn và cần căn chỉnh ăng-ten; di động tái-đưa-vào một chi phí định kỳ và một yếu tố WAN mà ta đã chủ ý giữ ngoài đường an toàn; công suất/chi phí cao hơn. **Được giữ làm phương án dự phòng nếu ngân sách chu kỳ làm việc của Phương án A thất bại**, với băng **920–923 MHz** LPWAN của VN là ứng viên hàng đầu cần đánh giá.

### Phương án D: Thiết kế lại IF-4 bỏ làm mới liên tục
`SHOW` theo sự kiện + keepalive chậm + bộ điều khiển làm trống sau N keepalive bị lỡ.

**Ưu điểm:** cắt giảm thời gian chiếm sóng.
**Nhược điểm:** một keepalive chậm nghĩa là một `T_signhold` **lớn** → BẬT-cũ-tối-đa dài hơn — tư thế "VMS chốt trạng thái" yếu hơn mà [ICD §3](../08-interface-control-document.vi.md) đã cảnh báo. Chỉ chấp nhận được như một sự suy giảm có ghi nhận, không phải mặc định.

## Phân tích đánh đổi

Mấu chốt là một sự ghép nối mà bản demo ngây thơ che giấu: **`T_signhold` ↔ tốc-độ-làm-mới ↔ thời-gian-chiếm-sóng ↔ tầm-xa**, nay trở nên *ràng buộc* bởi pháp luật Việt Nam. Theo **Thông tư 08/2021/TT-BTTTT**, LoRa 433 MHz chỉ miễn giấy phép như một thiết bị **LPWAN** (Phụ lục 19) với **≤ 25 mW ERP** và một chu kỳ làm việc **≤ 10 % cho đầu truyền-dữ-liệu / cổng (gateway)** và **≤ 1 % cho đầu cuối (terminal)**. Thiết bị biên liên tục làm mới khẳng định là nguồn dữ liệu — có lẽ thuộc lớp "gateway" 10 %, nhưng một cách hiểu thận trọng cho một nút điểm-điểm là lớp terminal 1 %. **Việc phân loại này có tính chịu lực và phải được xác nhận.**

Minh họa: một khung được xác thực ~40 byte chiếm sóng ~70 ms ở SF7/BW125 (và ~250 ms ở SF9, mà trần 25 mW thấp có thể buộc phải dùng để giữ tầm xa trong mưa). Ở tốc độ làm mới 2 Hz (`T_signhold` = 2 s → `T_assert_refresh` ≤ 0.5 s) đó là **~14 % chu kỳ ở SF7 — đã vượt trần 10 %**, và vô vọng ở SF9 hoặc dưới lớp 1 %. Để giữ dưới 10 % ở SF7, tốc độ làm mới hạ xuống ≈1.4 Hz → một **sàn `T_signhold` ≈3 s**; dưới lớp terminal 1 % nó sụp xuống ~30 s, điều **thực sự vô hiệu hóa cơ chế tự ngắt an toàn**. Trần **25 mW ERP** và trần **chu kỳ làm việc cộng dồn**: công suất thấp đẩy về SF cao hơn để có biên tầm xa, và SF cao hơn nhân lên thời gian chiếm sóng, làm tệ thêm chu kỳ.

Nên mọi điều tốt về LoRa (tầm với, nguồn điện, chi phí) đều là thật, và Phương án A là phương tiện mang *nguyên mẫu* đúng đắn **nếu** ngân sách khép được ở lớp gateway-10 % với SF7 và biên 25 mW đủ dùng — một góc hẹp. Rủi ro trung thực là nó có thể không, buộc phải nới `T_signhold` (kiểu Phương án D, an toàn tệ hơn) hoặc Phương án C. Đây là một quyết định **đo-đừng-giả-định**: một phép thử thời gian chiếm sóng trên bàn thử + một xác nhận phân loại pháp lý + một phép thử tầm xa ≥315 m giải quyết nó trong vài ngày. Cho đến lúc đó, **LoRa-trên-đường-an-toàn là đề xuất, chưa được chứng minh**, và 920–923 MHz nên được đánh giá song song.

## Hệ quả

- **Dễ hơn:** một liên kết biển báo rẻ, công suất thấp, thân thiện năng lượng mặt trời đã có sẵn, với một PHY ta điều khiển đầu-cuối.
- **Khó hơn:** `T_signhold` **không còn là một núm phần mềm tự do** — nó được đồng-quyết-định bởi lớp RF và phải được đặt từ thời gian chiếm sóng *đã đo* + biên liên kết + lớp chu kỳ pháp lý, rồi cố định thành một hằng số có giới hạn theo §7a ([tài liệu 02 §7a](../02-system-architecture.vi.md)). Kích thước khung xác thực nay có một chi phí định thời phải được đồng-thiết-kế với an ninh ([ADR-0012](ADR-0012-security-and-threat-model.vi.md)).
- **Chỉnh lại hồ sơ:** LoRa nay nằm trên **đường an toàn** và thừa hưởng các yêu cầu xác thực + chống phát lại + làm mới của IF-4 — không còn là kênh phụ đo lường từ xa không-trọng-yếu-an-toàn của [ADR-0006](ADR-0006-connectivity-and-power.vi.md). ADR-0006 được bổ sung để giữ hai vai trò tách bạch.
- **Hạng mục mới hoãn-hiện-trường:** ngân sách chu-kỳ-làm-việc / mất-gói / độ-trễ qua khoảng cách vốn đặt ra `T_signhold` gia nhập việc kiểm chứng liên kết hoãn-hiện-trường của [ADR-0009 §A](ADR-0009-failsafe-placement-and-degraded-modes.vi.md) và các ghi chú bao phủ của [tài liệu 06](../06-traceability-matrix.vi.md).
- **Xem xét lại khi:** các phép thử bàn-thử/pháp-lý hoàn tất (chấp nhận, hoặc chuyển sang Phương án C), hoặc dữ liệu tầm-xa/độ-vững ở hiện trường xuất hiện.

## Hạng mục hành động

1. [ ] **Phép thử thời gian chiếm sóng trên bàn thử** (pm + fw): đo thời gian chiếm sóng của SX1276 cho khung được xác thực thực tế ở các SF/BW/CR ứng viên; tính tốc độ làm mới đạt được; xác minh `T_assert_refresh` ≤ ¼·`T_signhold` giữ được ở một chu kỳ làm việc hợp pháp.
2. [ ] **Xác nhận phân loại pháp lý** (pc/vận hành): xác nhận theo Thông tư 08/2021/TT-BTTTT liệu bộ phát biên→biển báo thuộc lớp **10 % (gateway)** hay **1 % (terminal)**, và trần **25 mW ERP**; ghi lại giới hạn chu kỳ ràng buộc.
3. [ ] **Phép thử tầm xa/biên** ở ≥315 m gần tầm nhìn thẳng gồm cả điều kiện ẩm ướt ở SF đã chọn; xác nhận ngân sách liên kết với biên suy hao ở ≤ 25 mW ERP.
4. [ ] **Đánh giá 920–923 MHz** LPWAN của VN như ứng viên hàng đầu cho Phương án C (quy tắc chu kỳ / LBT, mức sẵn có của mô-đun, công suất).
5. [ ] Nếu (1)–(3) thất bại → leo thang sang Phương án C hoặc một sự nới lỏng `T_signhold` có ghi nhận (cấp-ADR).
6. [ ] Đưa công suất tiêu thụ của SX1276 + bộ điều khiển biển báo ESP32 vào ngân sách nguồn điện của [ADR-0006](ADR-0006-connectivity-and-power.vi.md).
7. [ ] Sửa dòng liên-kết-hiện-trường của [ICD §7](../08-interface-control-document.vi.md) (phương tiện mang = LoRa P2P, ngân sách còn chờ) và ghi chú bao phủ của [tài liệu 06](../06-traceability-matrix.vi.md).
