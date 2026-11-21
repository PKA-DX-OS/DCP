# Kịch bản demo DX-OS C3: 9 cảnh, 8–10 phút

Kịch bản đi theo một câu chuyện: ông Nguyễn Văn Minh xin phép xây nhà 5 tầng trên thửa TD-A-01, phải sửa còn 3 tầng, sửa thiết kế từ v1 lên v2, được cấp phép ký số, nghiệm thu móng, rồi ai cũng tra cứu được. Khung cảnh và dữ liệu xem [demo-storyboard.md](demo-storyboard.md). Checklist trước demo và phương án khi lỗi xem [demo-guide.md](demo-guide.md).

**Điều kiện:**
- Stack đã `dx up` với `DEMO_MODE=true` và đã chạy `python scripts/seed_hero.py`.
- Đã có 6 tệp PDF giấy tờ trong thư mục `demo-giay-to/` (cách tạo xem demo-guide).
- Mật khẩu các tài khoản nằm trong `secrets/demo-accounts.txt`. Không đọc to và không chiếu tệp này.

Mỗi cảnh gồm **Thao tác** (làm gì, bấm nút nào, đúng nhãn trên màn hình), **Kết quả** (người xem phải thấy gì) và **Lời thoại**.

---

## Cảnh 1: Vấn đề (0:00–1:00), slide 1

**Lời thoại:**
> Xin phép xây một căn nhà ở riêng lẻ, người dân thường phải đi lại nhiều lần. Hồ sơ thiếu một tờ giấy là quay về. Bản vẽ sai quy hoạch thì đến lúc thẩm định mới biết. Cán bộ phải đối chiếu tay hàng chục chỉ tiêu, còn lãnh đạo không biết hồ sơ nào sắp quá hạn. Luật cho phép giải quyết trong 7 ngày làm việc (Điều 54 Nghị định 217/2026), nhưng thực tế hồ sơ thường đi nhiều vòng.

## Cảnh 2: Giải pháp (1:00–2:00), slide 2–3

**Lời thoại:**
> DX-OS C3 là một nền tảng mã nguồn mở cho phường. Lõi nền tảng lo đăng nhập một lần, phân quyền, lưu tệp quét virus, chữ ký số, quy trình, nhật ký kiểm toán. Ứng dụng cấp phép xây dựng chạy trên lõi đó. Cả hệ thống chạy được trên một máy chủ của phường, không phụ thuộc dịch vụ đám mây nước ngoài.

Chiếu sơ đồ [architecture-onepage.md](architecture-onepage.md) và chỉ bốn lớp: biên, ứng dụng, dữ liệu, bảo mật.

## Cảnh 3: Công dân nộp hồ sơ 5 tầng (2:00–3:30)

**Tài khoản:** `cdt.minh`.

| # | Thao tác | Kết quả |
|---|---|---|
| 1 | Mở `/`, bấm **Đăng nhập**, đăng nhập `cdt.minh` | Vào tab **Hồ sơ của tôi** |
| 2 | Bấm **Nộp hồ sơ mới** | Mở hộp **Nộp hồ sơ cấp phép xây dựng** |
| 3 | Điền: Họ tên `Nguyễn Văn Minh`, CCCD `001099000001`, điện thoại `0901234567`, Địa chỉ công trình `Số 18 Đường Hòa Bình, phường A`, **Thửa đất, tờ bản đồ** `TD-A-01`, **Số tầng** `5`, **Diện tích sàn** `600` | — |
| 4 | Chưa tải giấy tờ, bấm **Kiểm tra và nộp hồ sơ** | Báo hồ sơ chưa đủ, liệt kê đúng tên từng giấy còn thiếu |
| 5 | Tải 6 tệp trong `demo-giay-to/` vào đúng 6 ô: đơn, giấy tờ đất, 3 bản vẽ, bản cam kết. Điền ngày cấp và ngày hết hạn của giấy tờ đất. Bấm **Kiểm tra và nộp hồ sơ** | Hộp đóng; hồ sơ mới ở đầu danh sách, trạng thái **Đã nộp**. Ghi lại mã `CP-2026-…` |

**Lời thoại:**
> Ông Minh nộp hồ sơ xây nhà 5 tầng. Danh mục giấy tờ lấy đúng Điều 60 Nghị định 217: đơn theo Mẫu số 01, giấy tờ đất, ba bản vẽ và bản cam kết an toàn công trình liền kề. Thiếu giấy nào hệ thống báo đúng giấy đó ngay trên màn hình, không đợi cán bộ trả về. Tệp được quét virus trước khi lưu.

## Cảnh 4: Tiếp nhận, phân công, kiểm tra quy hoạch (3:30–5:00)

**Tài khoản:** `mc.thu`, sau đó `ld.hoa`, sau đó `td.binh`.

| # | Thao tác | Kết quả |
|---|---|---|
| 1 | Đăng nhập `mc.thu`, tab **Bàn làm việc**, trong **Hàng đợi công việc** chọn việc **Kiểm tra Hồ sơ Hợp lệ** của hồ sơ vừa nộp | Cột giữa hiện chi tiết hồ sơ; cột phải có **Việc đang chờ bạn** |
| 2 | Ở cột phải bấm **Tiếp nhận hợp lệ**, rồi **Xác nhận** | Hồ sơ sang bước phân công |
| 3 | Đăng nhập `ld.hoa`, **Bàn làm việc**, chọn việc **Lãnh đạo Phân công Thẩm định viên**, bấm **Phân công thẩm định**, chọn `td.binh`, **Xác nhận** | Việc thẩm định chuyển sang `td.binh` |
| 4 | Đăng nhập `td.binh`, **Bàn làm việc**, chọn việc **Thẩm định Hồ sơ Kỹ thuật**, bấm **Mở hồ sơ đầy đủ**, chọn mục **Quy hoạch** | Bản đồ vùng QH-A1; **Thửa đất kiểm tra** tự chọn `TD-A-01`; Số tầng điền sẵn `5` |
| 5 | Ở **Thông số đề xuất**: Số tầng `5`, Chiều cao `18`. Bấm **Kiểm tra quy hoạch** | Kết quả **Không đạt quy hoạch**: R03 chiều cao 18 > 12 m, R04 số tầng 5 > 3, kèm trích dẫn văn bản |
| 6 | (Nếu còn thời gian) Ngay dưới kết quả không đạt, bấm **Giải thích bằng trợ lý (có trích dẫn)** | Trợ lý giải thích, có nguồn. Nút chỉ hiện khi kết quả không đạt |
| 7 | Sửa Số tầng `3`, Chiều cao `11.5`, bấm **Kiểm tra quy hoạch** | Kết quả **Đạt quy hoạch**; **Lịch sử kiểm tra** có cả hai lần |

**Lời thoại:**
> Một cửa tiếp nhận, lãnh đạo phân công. Mỗi người chỉ thấy việc của mình, lấy từ quy trình thật chứ không phải danh sách cứng. Thẩm định viên kiểm tra quy hoạch trên bản đồ. Thửa TD-A-01 thuộc vùng chỉ cho phép tối đa 3 tầng, 12 mét. Phương án 5 tầng bị chỉ ra ngay từng chỉ tiêu vi phạm, có trích dẫn. Sửa còn 3 tầng thì đạt, và cả hai lần kiểm tra đều được lưu lại. Dữ liệu quy hoạch ở đây là dữ liệu tổng hợp cho demo.

## Cảnh 5: Thẩm định thiết kế đa bộ môn (5:00–6:00)

**Tài khoản:** `cdt.minh`. Dùng hồ sơ dựng sẵn `CP-HERO-2026-001` để không phải tải bộ bản vẽ khi demo.

| # | Thao tác | Kết quả |
|---|---|---|
| 1 | Đăng nhập `cdt.minh`, **Hồ sơ của tôi**, ở `CP-HERO-2026-001` bấm **Xem** | Mở chi tiết |
| 2 | Chọn mục **Thiết kế** | Khung **Thẩm định thiết kế đa bộ môn** |
| 3 | Xem phiên bản **v1** | **Không đạt**: thiếu bộ môn kết cấu, bản vẽ MEP-01 không đạt, nhận xét "Bổ sung sơ đồ cấp điện và ghi rõ công suất phụ tải" |
| 4 | Xem phiên bản **v2** | **Đạt**: đủ kiến trúc, kết cấu, MEP |

**Lời thoại:**
> Thiết kế được thẩm định theo từng bộ môn: kiến trúc, kết cấu, cơ điện. Bản v1 thiếu kết cấu và sơ đồ cấp điện sai, nên thẩm định viên để lại nhận xét ngay trên bản vẽ. Chủ đầu tư nộp v2, hệ thống so sánh hai phiên bản và chỉ cần thẩm định lại phần đã thay đổi. Không còn cảnh gửi đi gửi lại cả bộ hồ sơ giấy.

## Cảnh 6: Thẩm định đạt, lãnh đạo duyệt và ký số (6:00–7:00)

**Tài khoản:** `td.binh`, sau đó `ld.hoa`. Quay lại hồ sơ nộp ở cảnh 3.

| # | Thao tác | Kết quả |
|---|---|---|
| 1 | `td.binh`, **Bàn làm việc**, chọn việc thẩm định của hồ sơ, bấm **Đạt thẩm định**, **Xác nhận** | Hồ sơ chuyển lãnh đạo duyệt |
| 2 | `ld.hoa`, **Bàn làm việc**, chọn việc **Lãnh đạo Phê duyệt Cấp phép**, bấm **Phê duyệt và ký**, **Xác nhận** | Trạng thái **Đã cấp phép** |
| 3 | Bấm **Mở hồ sơ đầy đủ**, mục **Thông tin**, phần **Giấy phép và chữ ký số** | Số giấy phép, người ký, chữ ký PAdES, **Mã tra cứu** và nút **Mở trang tra cứu** |

Giấy phép ghi quy mô theo hồ sơ đã nộp ở cảnh 3 (5 tầng). Kiểm tra quy hoạch ở cảnh 4 không sửa quy mô trong hồ sơ, nên khi demo không nói giấy phép ghi 3 tầng.

**Lời thoại:**
> Lãnh đạo phê duyệt, giấy phép được ký số chuẩn PAdES bằng khoá nằm trong thiết bị bảo mật mềm SoftHSM. Khoá không bao giờ rời thiết bị. Mỗi giấy phép có một mã công khai ngẫu nhiên, không đoán được.

## Cảnh 7: Nghiệm thu móng (7:00–8:00)

**Tài khoản:** `ld.hoa`, sau đó `tt.khanh`.

| # | Thao tác | Kết quả |
|---|---|---|
| 1 | Vẫn trong **Mở hồ sơ đầy đủ** (`ld.hoa`), mục **Nghiệm thu**, bấm **Bắt đầu quy trình nghiệm thu** | Thông báo **Đã tạo quy trình nghiệm thu trong Bàn làm việc** |
| 2 | Đăng nhập `tt.khanh`, **Bàn làm việc**, chọn việc **Nghiệm thu móng** của hồ sơ, bấm **Không đạt**, lý do `Cao độ đáy móng thấp hơn thiết kế 12 cm`, **Xác nhận** | Mốc móng **Không đạt**; sinh việc **Khắc phục móng và nghiệm thu lại** |
| 3 | Chọn việc khắc phục, bấm **Đã khắc phục**, ghi nội dung, **Xác nhận** | Quay về việc nghiệm thu móng |
| 4 | Chọn lại việc **Nghiệm thu móng**, bấm **Đạt**, **Xác nhận** | Mốc móng **Đạt**; chuyển sang nghiệm thu kết cấu |

Nếu thiếu thời gian: chỉ làm bước 1–2 và nói tiếp phần còn lại. Ví dụ đủ ba lần (móng không đạt, đạt sau khắc phục, kết cấu đạt) có sẵn ở hồ sơ `CP-HERO-ACC-2026-001`.

**Lời thoại:**
> Cấp phép xong chưa phải là hết. Trật tự xây dựng nghiệm thu theo mốc. Móng sai cao độ thì ghi không đạt kèm lý do, chủ đầu tư khắc phục, kiểm tra lại mới cho làm tiếp. Từng lần nghiệm thu đều được lưu thành phiên bản, không ghi đè.

## Cảnh 8: Tra cứu công khai, kiểm toán, dữ liệu cá nhân (8:00–9:00)

| # | Thao tác | Kết quả |
|---|---|---|
| 1 | Cửa sổ ẩn danh, mở `/kiem-tra/` và nhập mã công khai của giấy phép vừa cấp (hoặc bấm **Mở trang tra cứu** ở cảnh 6) | Trang không cần đăng nhập: **Hợp lệ**, ngày ký, đơn vị, mã băm, chữ ký số |
| 2 | Ở mục đối soát, tải lên một bản PDF đã sửa (`demo-giay-to/giay-phep-da-sua.pdf`) | Báo tệp **không khớp** |
| 3 | Đăng nhập `kt.an` ở `/dieu-hanh/`, tab **Kiểm toán**, bấm **Xác minh** | Chuỗi kiểm toán hợp lệ, có các bản ghi vừa tạo |
| 4 | `cdt.minh`, tab **Dữ liệu của tôi**, bấm **Yêu cầu cung cấp dữ liệu** | Yêu cầu được ghi nhận |

**Lời thoại:**
> Người dân, ngân hàng hay hàng xóm đều kiểm tra được giấy phép thật hay giả mà không cần tài khoản, và không thấy dữ liệu cá nhân. Sửa một byte trong PDF là chữ ký không còn khớp. Mọi thao tác, kể cả truy cập khẩn, đều nằm trong nhật ký dạng chuỗi băm: sửa một dòng là chuỗi gãy. Công dân tự xem, rút đồng thuận hoặc yêu cầu dữ liệu của mình theo Luật Bảo vệ dữ liệu cá nhân.

## Cảnh 9: Điều hành, trợ lý AI, tác động, lộ trình (9:00–10:00)

**Tài khoản:** `ld.hoa`.

| # | Thao tác | Kết quả |
|---|---|---|
| 1 | Mở `/dieu-hanh/`, tab **Chỉ số điều hành** | Thẻ chỉ số, hồ sơ theo tháng (6 tháng), hồ sơ quá hạn, tải việc theo cán bộ |
| 2 | Tab **Hỏi đáp quy định**, hỏi `Hồ sơ cấp phép xây dựng nhà ở riêng lẻ gồm những giấy tờ gì?`, bấm **Hỏi** | Câu trả lời liệt kê đơn, giấy tờ đất, bản vẽ, bản cam kết, có trích dẫn nguồn. Hỏi điều không có trong kho (ví dụ `Khi nào phải xin điều chỉnh giấy phép?`) thì trợ lý nói không tìm thấy căn cứ |
| 3 | Chuyển slide 9 (tác động) và slide 10 (lộ trình) | Số liệu lấy từ `python scripts/impact_metrics.py` |

**Lời thoại:**
> Lãnh đạo thấy ngay hồ sơ nào quá hạn, cán bộ nào đang quá tải. Trợ lý pháp lý chạy trên máy chủ của phường, chỉ trả lời khi có căn cứ trong kho văn bản và luôn ghi nguồn. Số liệu tác động trên slide được đo từ chính hệ thống vừa demo; phần nào là giả định, chúng tôi ghi rõ. Bước tiếp theo là kết nối Cổng Dịch vụ công Quốc gia và cơ sở dữ liệu đất đai để công dân không phải nộp lại giấy tờ đã có.
