<!--
SPDX-FileCopyrightText: 2026 DCP contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Hướng Dẫn Đóng Góp (Contributing Guidelines)

Cảm ơn bạn đã quan tâm và muốn đóng góp cho dự án **DCP**! Chúng tôi trân trọng mọi đóng góp nhằm xây dựng một hệ điều hành chuyển đổi số nguồn mở an toàn, minh bạch và bền vững.

---

## 1. Nguyên Tắc Quản Lý Mã Nguồn

- Nhánh **`main`** là nhánh được bảo vệ (protected branch), phản ánh trạng thái phát hành ổn định và luôn vượt qua toàn bộ quy trình kiểm thử CI.
- Mọi thay đổi đều phải được thực hiện thông qua nhánh tính năng hoặc sửa lỗi riêng và gửi qua **Pull Request (PR)**.
- Không commit trực tiếp vào nhánh `main`. Không sử dụng `git push --force` trên các nhánh dùng chung.

---

## 2. Quy Định Commit (Conventional Commits)

Mọi thông điệp commit phải tuân thủ chuẩn [Conventional Commits 1.0.0](https://www.conventionalcommits.org/):

```
<loại>[phạm_vi]: <mô tả ngắn bằng tiếng Việt hoặc tiếng Anh>

[nội dung chi tiết nếu có]

[thẻ liên kết issue nếu có]
```

Các loại commit được chấp nhận:
- `feat`: Thêm tính năng mới
- `fix`: Sửa lỗi
- `docs`: Cập nhật tài liệu
- `style`: Định dạng mã nguồn (không ảnh hưởng logic)
- `refactor`: Tái cấu trúc mã nguồn
- `perf`: Cải thiện hiệu năng
- `test`: Thêm hoặc sửa đổi bài kiểm thử
- `chore`: Thay đổi cấu hình build, công cụ, quản lý phụ thuộc

Ví dụ:
- `feat(audit): bổ sung API verify chuỗi băm và phát hiện sai lệch`
- `fix(files): xử lý mã lỗi 422 khi phát hiện tệp eicar`
- `docs: cập nhật sơ đồ kiến trúc hệ thống trong README`

---

## 3. Khai Báo Bản Quyền & Giấy Phép (SPDX & REUSE)

Dự án tuân thủ nghiêm ngặt chuẩn **REUSE 3.0**:
- Mọi tệp nguồn có thể chứa chú thích (`.py`, `.ts`, `.vue`, `.js`, `.sql`, `.yaml`, `.yml`, `Dockerfile`, `Makefile`, `.sh`, `.bpmn20.xml`, `.css`, `.html`) bắt buộc phải có tiêu đề bản quyền:
  ```
  SPDX-FileCopyrightText: 2026 DCP contributors
  SPDX-License-Identifier: AGPL-3.0-or-later
  ```
- Tài liệu và dữ liệu mẫu sử dụng giấy phép `CC-BY-4.0`.
- Các tệp nhị phân hoặc định dạng không hỗ trợ chú thích phải được khai báo trong `REUSE.toml`.

---

## 4. Quy Trình Kiểm Tra Trước Khi Gửi PR

Trước khi tạo Pull Request, bạn bắt buộc phải chạy các lệnh sau cục bộ và đảm bảo không có bất kỳ lỗi nào:

```bash
# 1. Kiểm tra tuân thủ bản quyền REUSE và giấy phép thư viện
make license-check

# 2. Kiểm tra chất lượng và định dạng mã nguồn
make lint

# 3. Chạy toàn bộ kiểm thử đơn vị
make test

# 4. Chạy kiểm thử End-to-End
make e2e
```

---

## 5. Tạo Pull Request

1. Fork kho mã nguồn và tạo nhánh mới từ `main` (ví dụ: `git checkout -b feat/audit-tamper-check`).
2. Viết mã, bổ sung kiểm thử tương ứng và commit tuân thủ Conventional Commits.
3. Đảm bảo toàn bộ kiểm thử và linter thành công.
4. Mở Pull Request vào nhánh `main` của kho gốc và điền đầy đủ thông tin theo mẫu PR template.
