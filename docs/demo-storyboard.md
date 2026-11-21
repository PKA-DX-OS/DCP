# Storyboard demo DX-OS C3 (8–10 phút)

Tài liệu này là khung hình của buổi demo: mỗi cảnh dùng màn hình nào, đăng nhập tài khoản nào, dữ liệu nào và người xem phải thấy gì. Lời thoại chi tiết nằm ở [demo-script.md](demo-script.md), checklist trước giờ demo và phương án khi lỗi nằm ở [demo-guide.md](demo-guide.md).

## Câu chuyện dữ liệu

Một công dân, một hồ sơ, một địa bàn.

Ông **Nguyễn Văn Minh** (tài khoản `cdt.minh`, dữ liệu tổng hợp) muốn xây nhà ở riêng lẻ trên thửa **TD-A-01** (thửa 12, tờ 34, Số 18 Đường Hòa Bình, phường A, 180 m² đất ở). Ông nộp hồ sơ với phương án **5 tầng**.

1. **Nộp hồ sơ.** Hệ thống chặn ngay khi thiếu giấy tờ theo **Điều 60 NĐ 217/2026/NĐ-CP**: đơn Mẫu số 01 Phụ lục II, giấy tờ đất theo Điều 55, ba bản vẽ, bản cam kết an toàn công trình liền kề.
2. **Quy hoạch.** Thửa TD-A-01 nằm trong vùng QH-A1, tối đa **3 tầng / 12 m** (dữ liệu quy hoạch tổng hợp). Phương án 5 tầng **không đạt**, sửa thành **3 tầng** thì **đạt**. Kết quả có trích dẫn văn bản.
3. **Thiết kế (5.2).** Bộ hồ sơ thiết kế **v1** thiếu kết cấu và sơ đồ cấp điện bị đánh **không đạt**. Phiên bản **v2** bổ sung đủ ba bộ môn bắt buộc thì **đạt**.
4. **Duyệt và ký.** Lãnh đạo phê duyệt. Giấy phép được ký số **PAdES** bằng khoá trong SoftHSM, có **mã công khai** để tra cứu.
5. **Nghiệm thu.** Mốc **móng không đạt** (cao độ đáy móng thấp hơn thiết kế), khắc phục, rồi **đạt**.
6. **Minh bạch.** Ai cũng kiểm tra được giấy phép không cần tài khoản. Mọi thao tác có **nhật ký kiểm toán dạng chuỗi băm**. Công dân xem và yêu cầu dữ liệu cá nhân của mình (**DSAR**, Luật Bảo vệ dữ liệu cá nhân 91/2025).
7. **Điều hành.** Lãnh đạo xem chỉ số, hồ sơ theo tháng (6 tháng), tải việc và hỏi trợ lý pháp lý có trích dẫn.

Thời hạn giải quyết hiển thị theo **Điều 54 NĐ 217/2026**: cấp giấy phép xây dựng mới nhà ở riêng lẻ trong **07 ngày làm việc**, thẩm định trong **03 ngày làm việc**.

**Dữ liệu dùng trong demo:**

| Dữ liệu | Nguồn | Dùng ở cảnh |
|---|---|---|
| Hồ sơ nộp trực tiếp khi demo (5 tầng, thửa TD-A-01) | Người demo tạo ở cảnh 3 | 3, 4, 6, 7, 8 |
| `CP-HERO-2026-001`: thiết kế v1 không đạt, v2 đạt | `scripts/seed_hero.py` | 5 |
| `CP-HERO-ACC-2026-001`: móng không đạt rồi đạt | `scripts/seed_hero.py` | 7 (dự phòng) |
| Hồ sơ mẫu, công trình CT-01 | `apps/cap-phep/seed/seed.py` (chạy trong `dx up`) | 9 |
| Vùng quy hoạch QH-A1, thửa TD-A-01..03 | `core/postgres/13-construction-seed.sql` | 4 |

Mọi họ tên, CCCD, địa chỉ, quy hoạch trong demo là **dữ liệu tổng hợp**, không phải dữ liệu thật.

## Bảng cảnh

| Thời gian | Cảnh | Nội dung | Màn hình | Tài khoản | Người xem phải thấy |
|---|---|---|---|---|---|
| 0:00–1:00 | 1 | Vấn đề | Slide 1 | — | Hồ sơ giấy, nhiều vòng sửa, không biết hồ sơ đang ở đâu |
| 1:00–2:00 | 2 | Giải pháp và kiến trúc | Slide 2–3 | — | DX-OS C3: lõi nền tảng mở và ứng dụng cấp phép; sơ đồ một trang |
| 2:00–3:30 | 3 | Công dân nộp hồ sơ 5 tầng | `/` → **Hồ sơ của tôi** | `cdt.minh` | Bị chặn khi thiếu giấy, nộp được khi đủ; hồ sơ mới trạng thái **Đã nộp** |
| 3:30–5:00 | 4 | Tiếp nhận, phân công, kiểm tra quy hoạch | `/` → **Bàn làm việc** → chi tiết hồ sơ → mục **Quy hoạch** | `mc.thu` → `ld.hoa` → `td.binh` | 5 tầng **không đạt** (vượt số tầng tối đa), sửa 3 tầng **đạt**; bản đồ vùng QH-A1 |
| 5:00–6:00 | 5 | Thẩm định thiết kế đa bộ môn | `/` → **Hồ sơ của tôi** → `CP-HERO-2026-001` → mục **Thiết kế** | `cdt.minh` | v1 **không đạt** (thiếu kết cấu, lỗi MEP, có nhận xét), v2 **đạt** đủ 3 bộ môn |
| 6:00–7:00 | 6 | Thẩm định đạt, lãnh đạo duyệt và ký | Bàn làm việc → thanh hành động | `td.binh` → `ld.hoa` | **Phê duyệt và ký**: trạng thái **Đã cấp phép**, có mã công khai |
| 7:00–8:00 | 7 | Nghiệm thu móng: không đạt, khắc phục, đạt | Mục **Nghiệm thu** → Bàn làm việc | `ld.hoa` → `tt.khanh` | Mốc móng **Không đạt**, rồi **Đã khắc phục**, rồi **Đạt** |
| 8:00–9:00 | 8 | Tra cứu công khai, kiểm toán, dữ liệu cá nhân | `/kiem-tra/` (cửa sổ ẩn danh); `/dieu-hanh/` → **Kiểm toán**; **Dữ liệu của tôi** | không đăng nhập; `kt.an`; `cdt.minh` | Giấy phép **Hợp lệ**; chuỗi kiểm toán xác minh được; công dân gửi yêu cầu cung cấp dữ liệu |
| 9:00–10:00 | 9 | Dashboard, trợ lý AI, tác động, lộ trình | `/dieu-hanh/` → **Chỉ số**, **Trợ lý**; slide 9–10 | `ld.hoa` | Chỉ số thật từ hệ thống, câu trả lời có trích dẫn, số liệu tác động (`scripts/impact_metrics.py`) |

## Chuyển cảnh

- Mở sẵn bốn cửa sổ trình duyệt (mỗi cửa sổ một hồ sơ trình duyệt riêng để không lẫn phiên):
  1. `cdt.minh`
  2. `mc.thu` / `td.binh`
  3. `ld.hoa`
  4. Cửa sổ ẩn danh cho trang tra cứu
- Khi chuyển vai trong cùng một cửa sổ: bấm **Đăng xuất** rồi **Đăng nhập** lại. Không đổi tài khoản bằng cách mở tab mới vì phiên Keycloak dùng chung.
- Từ cảnh 3 trở đi, ghi mã hồ sơ vừa nộp (`CP-2026-…`) lên giấy để đọc cho người xem và dùng lại ở cảnh 6–8.

## Ảnh chụp dự phòng

Nếu một cảnh không chạy được, chiếu ảnh tương ứng trong `logs/e2e-ui/<lần chạy>/` (các test e2e-ui tự chụp) và đọc tiếp lời thoại. Cách chụp lại xem [demo-guide.md](demo-guide.md#du-phong).
