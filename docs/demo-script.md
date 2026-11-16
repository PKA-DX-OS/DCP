<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Kịch Bản Trình Diễn Chi Tiết 10 Bước (P0 Demo Script)

Tài liệu này cung cấp kịch bản trình diễn trọn vẹn 10 bước trong vòng **15 phút** cho Ban Giám khảo Hội đồng Chung kết Olympic Tin học Sinh viên Việt Nam 2026.

---

## 1. Thông Tin Đăng Nhập Mẫu

Mật khẩu dùng chung cho toàn bộ các tài khoản demo là: **`Demo@2026!`**

| Bước | Tài Khoản | Mật Khẩu | Vai Trò | Người Đại Diện (mẫu) |
| :--- | :--- | :--- | :--- | :--- |
| **Bước 1, 7** | `cdt.minh` | `Demo@2026!` | Chủ đầu tư | Trần Văn Minh (mẫu) |
| **Bước 2** | `mc.thu` | `Demo@2026!` | Cán bộ Một cửa | Nguyễn Thị Thu (mẫu) |
| **Bước 2, 4** | `ld.hoa` | `Demo@2026!` | Lãnh đạo UBND | Phạm Thanh Hoa (mẫu) |
| **Bước 3** | `td.cuong`| `Demo@2026!` | Thẩm định viên | Vũ Quốc Cường (mẫu) |
| **Bước 4** | `td.binh` | `Demo@2026!` | Thẩm định viên | Hoàng Văn Bình (mẫu) |
| **Bước 6** | `tt.khanh`| `Demo@2026!` | Trật tự xây dựng | Đặng Quốc Khánh (mẫu) |

---

## 2. Kịch Bản 10 Bước Trình Diễn Chi Tiết

### Bước 1: Nộp hồ sơ và Thử nghiệm Kiểm dịch Mã độc ClamAV (Khoảnh khắc 1)
- **Thao tác:**
  1. Mở trình duyệt truy cập `http://localhost:8080/`.
  2. Bấm "Đăng nhập" -> Hệ thống chuyển hướng qua Keycloak SSO. Đăng nhập bằng `cdt.minh`.
  3. Chọn "Nộp hồ sơ cấp phép". Điền các thông tin: Địa chỉ "Số 123 Đường Hoa Phượng (mẫu)", diện tích 120 m2, 3 tầng.
  4. Đánh dấu các ô đồng ý xử lý dữ liệu (riêng rẽ từng mục đích, không có ô tích sẵn).
  5. Tại phần đính kèm bản vẽ: Tải lên tệp thử nghiệm virus `eicar.txt`. Bấm "Nộp hồ sơ".
- **Kết quả kỳ vọng:**
  - Hệ thống lập tức hiển thị thông báo lỗi màu đỏ: *"Lỗi 422: Tệp chứa mã độc - Hệ thống đã cách ly tệp tin an toàn"*.
  - Tải lại bằng tệp bản vẽ sạch `ban-ve-sach.pdf`.
  - Nộp hồ sơ thành công, mã hồ sơ sinh tự động dạng `CP-2026-000101`, trạng thái `DA_NOP`.

### Bước 2: Tiếp nhận Một cửa và Phân công Thẩm định
- **Thao tác:**
  1. Đăng xuất, đăng nhập bằng tài khoản `mc.thu`.
  2. Tại danh sách việc: Mở hồ sơ `CP-2026-000101`, kiểm tra thành phần giấy tờ và bấm "Tiếp nhận hồ sơ". Trạng thái chuyển thành `TIEP_NHAN`.
  3. Đăng xuất, đăng nhập tài khoản Lãnh đạo `ld.hoa`.
  4. Chọn hồ sơ, phân công thẩm định viên phụ trách là `td.binh` (Hoàng Văn Bình).
- **Kết quả kỳ vọng:**
  - Hồ sơ chuyển sang trạng thái `DUOC_PHAN_CONG`. Bảng phân công `core.assignments` ghi nhận bản ghi hiệu lực.

### Bước 3: Từ chối có lưu vết (403) và Quy trình Truy cập Khẩn cấp (Khoảnh khắc 2)
- **Thao tác:**
  1. Đăng nhập tài khoản thẩm định viên khác: `td.cuong` (không được phân công hồ sơ này).
  2. Tìm kiếm và cố tình bấm mở chi tiết hồ sơ `CP-2026-000101`.
  3. Màn hình hiện thông báo từ chối 403. Bấm nút "Xin truy cập khẩn cấp", nhập lý do: *"Hỗ trợ đồng nghiệp thẩm định kết cấu đặc biệt"*.
  4. Chuyển sang tài khoản `ld.hoa`: Vào mục "Truy cập khẩn chờ duyệt", thấy yêu cầu của Cường, bấm "Phê duyệt" (hiệu lực 2 giờ).
  5. Quay lại tài khoản `td.cuong`: Tải lại trang -> Mở hồ sơ thành công!
- **Kết quả kỳ vọng:**
  - Tại bước bị chặn, nhật ký audit ghi nhận hành động `access.denied`. Sau khi duyệt, quyền xem được kích hoạt; sau thời hạn quy định, quyền sẽ tự động thu hồi.

### Bước 4: Thẩm định Hồ sơ và Phân tách Nhiệm vụ SoD khi Duyệt Cấp phép (Khoảnh khắc 3)
- **Thao tác:**
  1. Đăng nhập tài khoản `td.binh` (thẩm định viên được phân công).
  2. Mở hồ sơ, đánh giá các hạng mục kỹ thuật, chọn kết luận "Thẩm định Đạt" và gửi Lãnh đạo.
  3. Thử nghiệm SoD: Nếu `td.binh` cố tình dùng API hoàn thành tác vụ duyệt -> Bị chặn từ chối (`dx:sodExclude`). Trên giao diện của Bình hoàn toàn không có nút "Phê duyệt cấp phép".
  4. Đăng nhập `ld.hoa` (yêu cầu xác thực OTP nếu bật `DEMO_MFA=true`).
  5. Lãnh đạo xem hồ sơ và bấm "Phê duyệt Cấp giấy phép".
- **Kết quả kỳ vọng:**
  - Dịch vụ `doc-sign` tự động sinh PDF giấy phép xây dựng chính thức kèm mã QR công khai và ký PAdES qua SoftHSM/PKCS#11. Hồ sơ chuyển sang trạng thái `DA_CAP`.

### Bước 5: Kiểm tra Giấy phép Công khai và Xử lý Thu hồi
- **Thao tác:**
  1. Mở cửa sổ ẩn danh (không đăng nhập), truy cập đường dẫn công khai trên mã QR của giấy phép: `http://localhost:8080/kiem-tra/{public_code}`.
  2. Hệ thống hiển thị: Trạng thái *"Hợp lệ"*, ngày cấp, đơn vị cấp "UBND Phường A (mẫu)".
  3. Thử tải lên một tệp PDF giả mạo (đã bị sửa đổi một ký tự nội dung) -> Hệ thống tính lại mã băm và báo: *"Chữ ký số không khớp - Tài liệu không hợp lệ"*.
  4. Đăng nhập lại `ld.hoa`, chọn chức năng "Thu hồi giấy phép" đối với hồ sơ này.
  5. Quay lại trang kiểm tra công khai tải lại -> Hệ thống hiển thị huy hiệu màu đỏ: *"ĐÃ THU HỒI"* kèm lý do thu hồi.

### Bước 6: Hội tụ IT/OT - Cảm biến Phát hiện Tiếng ồn và Mở Phiếu Hậu kiểm
- **Thao tác:**
  1. Chạy lệnh từ terminal:
     ```bash
     make sensor-spike
     ```
  2. Đăng nhập tài khoản Trật tự xây dựng `tt.khanh`.
  3. Mở mục "Hàng việc Trật tự xây dựng".
- **Kết quả kỳ vọng:**
  - Trong vòng dưới 15 giây, một phiếu kiểm tra hiện trường mới tự động xuất hiện với nguồn "Cảm biến", chỉ số `laeq_dba` vượt ngưỡng 78 dBA (ngưỡng quy chuẩn ban ngày là 70 dBA).

### Bước 7: Quyền Chủ thể Dữ liệu (DSAR Request)
- **Thao tác:**
  1. Đăng nhập tài khoản công dân `cdt.minh`.
  2. Vào trang "Dữ liệu của tôi" -> Thấy các mục đích đồng ý.
  3. Bấm "Gửi yêu cầu về dữ liệu cá nhân", chọn loại `access` (Yêu cầu xem và trích xuất toàn bộ dữ liệu).
- **Kết quả kỳ vọng:**
  - Yêu cầu được ghi nhận vào bảng `core.dsar_requests` kèm đồng hồ đếm ngược hạn phản hồi (2 ngày làm việc) và hạn cung cấp tối đa (10 ngày làm việc). Cán bộ có thể mở phiếu xử lý trích xuất dữ liệu cho công dân đúng hạn.

### Bước 8: Bảng Điều Hành 8 Chỉ Số và Phả Hệ Dữ Liệu (OpenLineage)
- **Thao tác:**
  1. Mở trình duyệt vào đường dẫn: `http://localhost:8080/dieu-hanh/`.
  2. Quan sát 8 chỉ số điều hành then chốt của phường (hồ sơ mới, đang xử lý, quá hạn, thời gian TB, 403, phiếu kiểm tra, cảnh báo, vi phạm).
  3. Nhấp chuột vào chỉ số "Hồ sơ mới trong kỳ".
- **Kết quả kỳ vọng:**
  - Bảng phả hệ OpenLineage mở ra, hiển thị các bước tạo dữ liệu: từ giao dịch nộp hồ sơ, qua tác vụ kết xuất Parquet `export-warm`, đến tính toán DuckDB của `metrics-api`.

### Bước 9: Phát Hiện Sửa Đổi Dữ Liệu Lén Lút Bằng Chuỗi Băm Kiểm Toán (Khoảnh khắc 4)
- **Thao tác:**
  1. Chạy lệnh kiểm tra tính toàn vẹn:
     ```bash
     make verify
     ```
     -> Hệ thống báo: `[PASS] Toàn bộ chuỗi kiểm toán hợp lệ.`
  2. Giả lập kẻ xấu có quyền superuser sửa lén một ký tự trong bảng `core.audit_log`:
     ```bash
     docker compose exec postgres psql -U postgres -d dxos -c "UPDATE core.audit_log SET detail = detail || '{\"gian_lan\": true}' WHERE id = 3;"
     ```
  3. Chạy lại lệnh xác minh:
     ```bash
     make verify
     ```
- **Kết quả kỳ vọng:**
  - Hệ thống lập tức báo lỗi đứt chuỗi băm:  
    `[FAIL] Phát hiện gian lận dữ liệu tại bản ghi Audit ID: 3! Mã băm không khớp.`

### Bước 10: Tự Phục Hồi Container & Tự Động Hóa Đối Soát GitOps
- **Thao tác:**
  1. Giả lập sự cố dịch vụ chết:
     ```bash
     docker kill dxos-files-1
     ```
  2. Đợi 5 giây và kiểm tra lại `docker ps` -> Container đã tự động khởi động lại và trở về trạng thái healthy.
  3. Giả lập có người can thiệp sửa đổi trái phép tệp cấu hình trên máy chủ:
     ```bash
     make gitops
     ```
- **Kết quả kỳ vọng:**
  - Reconciler đối chiếu cấu hình, phát hiện sự trôi dạt (drift), tự động kéo về đúng trạng thái đã ký trong Git.
