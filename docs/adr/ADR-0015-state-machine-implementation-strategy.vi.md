# ADR-0015: Chiến lược hiện thực máy trạng thái — đặc tả thực thi, mô hình thực thi, runtime

> 🇬🇧 Bản gốc tiếng Anh: [ADR-0015-state-machine-implementation-strategy.md](ADR-0015-state-machine-implementation-strategy.md)

**Trạng thái:** Đã chấp nhận (phía phần mềm) — 2026-07-03 (D3 runtime **có điều kiện** theo một phép thử định thời xác nhận trên K230)
**Ngày:** 2026-07-03
**Người quyết định:** Chủ nhiệm đề tài / trưởng nhóm phần mềm (Tin)

## Bối cảnh

Đợt rà soát mức-sẵn-sàng trước khi xây dựng kết luận lớp thiết kế đã đủ để dựng: các hợp đồng giao diện đã đóng băng ([ICD v1](../08-interface-control-document.vi.md)), máy trạng thái được đặc tả ở mức chi tiết cạnh chuyển ([tài liệu 02 §4](../02-system-architecture.vi.md) + mặt phẳng tham số §7a), và có một danh mục 30 kịch bản oracle ([tài liệu 07](../07-simulation-methodology.vi.md)). Điều còn lại là ba lựa chọn **ở mức hiện thực** mà các ADR thiết kế chủ ý không quyết — chúng nằm dưới độ cao mà các ADR đó vận hành, nhưng mỗi cái định hình từng dòng mã của máy trạng thái. ADR này ghi cả ba cùng nhau vì trên thực tế chúng là một quyết định gắn kết: *ta xây dựng và kiểm thử vòng lặp an toàn thế nào.* (Nó chủ ý gộp ba quyết định con thay vì tách thành 0015/0016/0017 — chúng không thể tách rời khi ngồi xuống viết mã.)

## Quyết định

- **D1 — Bộ oracle SC-01..30 là đặc tả thực thi.** Các oracle kịch bản trong [tài liệu 07 §5](../07-simulation-methodology.vi.md) là đặc tả thực thi, có thẩm quyền, của máy trạng thái: mã đúng khi trạng-thái-biển-báo-theo-thời-gian của nó khớp mọi oracle. Sơ đồ trạng thái ([tài liệu 02 §4](../02-system-architecture.vi.md)) và ma trận chế-độ-cảm-biến 5×4 trở thành tài liệu mà các bài kiểm thử thực thi. Dựng theo TDD-trước, đối chiếu bảng điểm.
- **D2 — Thực thi theo tick cố định nhịp.** Máy là một `tick(now, observations, health)` được đánh giá mỗi chu kỳ cố định (10 Hz trong harness): tính lại tập vết trong-ROI một cách nguyên tử mỗi tick, đánh giá mọi bộ định thời như một hạn chót đối với `now`. Không đọc đồng hồ tường bên trong SUT — tính tất định và tái phát chính xác.
- **D3 — Runtime MicroPython/CanMV**, một cơ sở mã **giống hệt từng byte** trong harness mô phỏng và trên K230 — **có điều kiện** theo một phép thử định thời trên K230 xác nhận khoảng dừng GC / jitter nằm sâu trong các bộ định thời an toàn. Chỉ lùi về một lõi C nếu phép thử thất bại.

## Các phương án đã xét

### D1 — cái gì phân xử khi ba biểu diễn của máy trạng thái bất đồng
| Phương án | Đánh giá |
|-----------|----------|
| **Oracle kịch bản SC-01..30 (được chọn)** | Thực thi được; bắt trôi lệch một cách cơ học; kiêm luôn xương sống nghiệm thu Giai đoạn 3 |
| Sơ đồ trạng thái là chuẩn | Quen thuộc, nhưng không gì buộc nó nhất quán với ma trận / kịch bản |
| Cả ba ngang hàng, hòa giải khi review | Ít công nhất, rủi ro cao nhất một bất nhất tiềm ẩn lọt vào mã |

### D2 — hình dạng thực thi
| Phương án | Đánh giá |
|-----------|----------|
| **Tick cố định nhịp (được chọn)** | Tất định, thân thiện watchdog, tái phát dễ đối chiếu oracle; chi phí nhàn rỗi không đáng kể |
| Hướng-sự-kiện | CPU nhàn rỗi thấp hơn; định thời/thứ tự khó suy luận và khó tái tạo hơn |
| Lai (sự kiện vào, tick định thời) | Nhiều bộ phận hơn; chỉ khi CPU nhàn rỗi trên K230 thực sự quan trọng |

### D3 — ngôn ngữ / runtime (một cơ sở mã, sim + K230; [tài liệu 07 §2](../07-simulation-methodology.vi.md) cấm tách sim-với-bản-giao)
| Phương án | Đánh giá |
|-----------|----------|
| **MicroPython/CanMV (được chọn, đã xác nhận bằng spike)** | Cùng runtime với nhận diện; kỹ năng sẵn có của nhóm; đường nhanh nhất. Các định thời an toàn (làm mới 0.5 s, signhold 2 s, watchdog 30 s) gấp 40×+ một khoảng dừng GC điển hình |
| C thuần / lõi C | Tất định mạnh nhất, hồ sơ an toàn sạch hơn; tốn một ngôn ngữ thứ hai ở phía K230 và lặp chậm hơn |
| Spike trước, rồi quyết | An toàn nhất về nhận thức; chặn workstream #1 vài ngày |

## Phân tích đánh đổi

Ba lựa chọn chung một xương sống: **làm cho logic an toàn rẻ để kiểm chứng.** D1 biến "ba biểu diễn có thể trôi lệch" thành một bộ kiểm thử đạt và trao cho Giai đoạn 3 bằng chứng miễn phí. D2 là cái làm các oracle tái phát được và các định thời an-toàn-khi-sự-cố đúng một cách chứng minh được — một vòng lặp hướng-sự-kiện đánh đổi điều đó lấy CPU nhàn rỗi mà K230 không cần tiết kiệm. D3 là lựa chọn duy nhất có rủi ro mở thực sự (khoảng dừng GC trong một vòng lặp an toàn), nhưng số học thì trấn an: hạn chót chặt nhất là `T_assert_refresh` ở 0.5 s — gấp ~40× một khoảng dừng GC điển hình của MicroPython — và biển báo chỉ làm trống sau `T_signhold` = 2 s, nên một khoảng dừng lạc không xáo trộn gì. Thay vì trả giá một ngôn ngữ thứ hai (C) vì giáo điều, ta dựng bằng MicroPython và để một spike rẻ *xác nhận* biên. Nếu spike gây bất ngờ, chỉ D3 lật sang một lõi C; D1/D2 không bị ảnh hưởng.

## Hệ quả

- **Dễ hơn:** một runtime xuyên suốt nhận diện + vòng lặp an toàn; kiểm thử tất định, tái phát được; bảng SC đồng thời là đặc tả và bằng chứng nghiệm thu; hành vi mới được dẫn dắt bởi TDD.
- **Khó hơn:** SUT phải ở trong tập-con-an-toàn-của-MicroPython (không `enum` / `dataclasses` / `typing`, không stdlib chỉ-cho-host) — giữ trung thực bằng cách chạy bảng trên **cổng unix MicroPython** trong CI, chứ không chỉ CPython. Nhịp tick tự thân là một tham số an toàn (quá chậm làm cùn độ trễ NFR-01; quá nhanh phí điện mặt trời) và phải được biện minh.
- **Xem xét lại khi:** phép thử định thời K230 hoàn tất (xác nhận MicroPython, hoặc lật D3 sang lõi C), hoặc một khối lượng công việc trên-thiết-bị nặng hơn trong tương lai bào mòn biên GC.

## Hạng mục hành động

1. [ ] **Phép thử định thời K230** — đo khoảng dừng GC / jitter vòng lặp dưới tải YOLO; xác nhận nó `« T_assert_refresh`. Đây là cổng cho D3.
2. [ ] **Đấu nối kẹp cấu hình FR-20** trong `StateMachine.__init__` (`esw.params.clamp_config`) → chuyển **SC-19** sang xanh (mục tiêu đỏ đầu tiên của bộ khung; đã kiểm chứng là sửa một dòng).
3. [ ] **Mở rộng bảng** — soạn các kịch bản `todo` và hiện thực đến xanh: watchdog (SC-28), che khuất / `CAMERA_OCCLUDED_DEGRADED` + `T_degraded_max` (SC-06..09), ma trận chế-độ-cảm-biến (SC-25..27), ghi đè (SC-16..18), ùn tắc (SC-11), khởi phát người đi bộ (SC-12).
4. [ ] **Chạy bảng trên cổng unix MicroPython trong CI** để thực thi tập con.
