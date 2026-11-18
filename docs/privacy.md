<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Bảo Vệ Dữ Liệu Cá Nhân & Quyền Chủ Thể Dữ Liệu (Privacy & Data Subject Rights)

> **Tuyên bố giới hạn pháp lý quan trọng:**
> Hệ thống DX-OS Open-Core chỉ mô phỏng các quy trình kỹ thuật nhằm phục vụ cuộc thi Olympic Tin học Sinh viên Việt Nam 2026. **Hệ thống không tuyên bố tuân thủ pháp lý chính thức. Mọi triển khai thực tế trong cơ quan nhà nước bắt buộc phải được các chuyên gia pháp lý và cơ quan chức năng có thẩm quyền thẩm định và phê duyệt.**

---

## 1. Các Quy Định Pháp Lý Được Mô Phỏng

Kiến trúc bảo vệ dữ liệu cá nhân của DX-OS được thiết kế tham chiếu theo tinh thần:
- Nghị định số 13/2023/NĐ-CP và dự thảo Nghị định quy định chi tiết Luật Bảo vệ dữ liệu cá nhân (tham chiếu Nghị định 356/2025/NĐ-CP).
- Các nguyên tắc cốt lõi: Hạn chế mục đích, Thu thập tối thiểu, Minh bạch trong xử lý, và Trao quyền kiểm soát dữ liệu cho chủ thể dữ liệu (Data Subject Rights).

---

## 2. Quản Lý Sự Đồng Ý Xử Lý Dữ Liệu (Consent Management)

- **Quy tắc thu thập sự đồng ý:**
  - Không sử dụng ô đánh dấu tích sẵn (no pre-ticked checkboxes).
  - Tách bạch rõ ràng từng mục đích xử lý dữ liệu:
    1. Xử lý hồ sơ cấp phép xây dựng.
    2. Nhận thông báo tiến độ qua SMS / Email.
    3. Kết nối chia sẻ dữ liệu phục vụ hậu kiểm công trường.
  - Bản ghi đồng ý được lưu trữ bất biến tại bảng `core.consents(tenant, subject_sub, purpose, text_version, granted_at, withdrawn_at)`.
- **Rút lại sự đồng ý:**
  - Chủ đầu tư có thể vào mục "Dữ liệu của tôi" để xem lại toàn bộ các mục đích đã đồng ý và thực hiện rút lại sự đồng ý bất kỳ lúc nào.

---

## 3. Quy Trình Yêu Cầu Của Chủ Thể Dữ Liệu (DSAR Workflow)

Hệ thống cung cấp quy trình BPMN tự động `yeu-cau-du-lieu` để xử lý các loại yêu cầu của công dân:

| Loại Yêu Cầu (`type`) | Mục Đích | Thời Hạn Phản Hồi Ban Đầu | Thời Hạn Xử Lý Tối Đa |
| :--- | :--- | :--- | :--- |
| `access` | Yêu cầu xem và cung cấp dữ liệu cá nhân đang lưu trữ | 2 ngày làm việc | 10 ngày làm việc |
| `rectify` | Yêu cầu chỉnh sửa thông tin cá nhân chưa chính xác | 2 ngày làm việc | 10 ngày làm việc |
| `withdraw` | Yêu cầu rút lại sự đồng ý xử lý dữ liệu | 2 ngày làm việc | 15 ngày làm việc |
| `restrict` | Yêu cầu hạn chế xử lý dữ liệu cá nhân | 2 ngày làm việc | 15 ngày làm việc |
| `erase` | Yêu cầu xóa dữ liệu cá nhân (Quyền được quên) | 2 ngày làm việc | 20 ngày làm việc |

### Xử lý yêu cầu Xóa dữ liệu (`erase`) đối với hồ sơ hành chính
- Theo quy định pháp luật về lưu trữ tài liệu hành chính công vụ, các thông tin định danh gắn liền với hồ sơ cấp phép đã phê duyệt bắt buộc phải lưu trữ theo thời hạn quy định của nhà nước.
- Khi công dân gửi yêu cầu xóa dữ liệu đối với hồ sơ đang thi công hoặc đã cấp phép: Cán bộ xử lý sẽ từ chối yêu cầu xóa và ghi rõ căn cứ pháp lý từ chối tại trường `legal_basis_note`.

---

## 4. Che Giấu Dữ Liệu Nhạy Cảm (Data Masking)

- Nhằm tránh lộ lọt thông tin cá nhân của công dân khi cán bộ xem danh sách chung, hệ thống cung cấp khung nhìn `app_cap_phep.v_ho_so`:
  - **Số CCCD:** Tự động che dấu chỉ để lại 4 số cuối (ví dụ: `********0123`), ngoại trừ chính chủ hồ sơ (`core.jwt_sub() = chu_dau_tu_sub`) hoặc cán bộ đã được phân công thẩm định cụ thể (`core.can_access('ho_so', id) = true`).
  - **Số điện thoại:** Tương tự, chỉ hiển thị đầy đủ cho người có thẩm quyền trực tiếp xử lý hồ sơ.

---

## 5. Công Khai Giấy Phép Xây Dựng & Giới Hạn Dữ Liệu (Q-02)

- **Căn cứ pháp lý:**
  - Điều 53 Luật Xây dựng 2014 (sửa đổi, bổ sung 2020) và Điều 107 Luật Tổ chức chính quyền địa phương: Công khai thông tin giấy phép xây dựng trên cổng thông tin điện tử của Ủy ban nhân dân cấp xã/phường để nhân dân và các tổ chức giám sát trật tự xây dựng tại cộng đồng.
  - Điều 28 Nghị định số 13/2023/NĐ-CP và Luật Bảo vệ dữ liệu cá nhân: Xử lý và công khai thông tin theo quy định của pháp luật chuyên ngành.
- **Nguyên tắc giảm thiểu dữ liệu cá nhân:**
  - Khung nhìn công khai `app_cap_phep.cong_khai_giay_phep` chỉ công khai các trường thông tin kỹ thuật phục vụ nhận diện công trình: `so_giay_phep`, `ma_cong_trinh`, `dia_chi`, `trang_thai`, `ngay_cap`.
  - Tuyệt đối không để lộ bất kỳ khóa ngoại hay dữ liệu định danh nhạy cảm nào như `ho_so_id`, `signed_doc_id`, số CCCD, hay số điện thoại. Bảng gốc `giay_phep`, `cong_trinh`, `phieu_kiem_tra` được bảo vệ nghiêm ngặt bằng Row Level Security (RLS), chỉ chủ sở hữu hồ sơ và cán bộ có trách nhiệm trong cùng phường mới có quyền đọc.
