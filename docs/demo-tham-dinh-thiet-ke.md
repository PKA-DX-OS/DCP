<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Demo 5.2 — Thẩm định thiết kế đa bộ môn (60–90 giây)

## Chuẩn bị

```powershell
py -3 scripts/seed_hero.py
```

Mở giao diện cấp phép, đăng nhập `cdt.minh` (mật khẩu trong `secrets/demo-accounts.txt`).

## Kịch bản

1. **Hồ sơ của tôi** → mở `CP-HERO-2026-001`.
2. Bấm tab **Thiết kế**.
   - Nói: “Hồ sơ có 2 phiên bản. v1 thiếu bộ môn kết cấu và MEP không đạt, nên kết luận không đạt.”
3. Bấm tab **Phiên bản**.
   - Chỉ vào dòng `v1 → v2: thêm 1 bản vẽ; đổi 1 bản vẽ` và mô tả “Bổ sung kết cấu và sửa sơ đồ cấp điện”.
4. Bấm tab **Nhận xét**.
   - Chỉ nhận xét mức **Lỗi**: “Bổ sung sơ đồ cấp điện và ghi rõ công suất phụ tải.”
   - Nói: “Thẩm định viên nhận xét theo bộ môn; chủ đầu tư xử lý xong thì đánh dấu đã xử lý.”
5. Quay lại **Bản vẽ**, bấm **Xem** một bản vẽ PDF để mở preview, thử zoom/tải.
6. Kết luận: “v2 đủ 3 bộ môn bắt buộc, tất cả bản vẽ đạt, trạng thái tổng hợp là Đạt.”

## Tài khoản minh họa

| Vai | Tài khoản |
|---|---|
| Chủ đầu tư | `cdt.minh` |
| Thẩm định viên | `td.binh` |
| Lãnh đạo | `ld.hoa` |

## Ghi chú

- PCCC là bộ môn tùy chọn trong danh mục hiện tại.
- Nếu preview báo không tải được tệp, chạy lại `seed_hero.py` để tạo bản ghi tệp mẫu.
