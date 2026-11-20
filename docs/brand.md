<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Nhận diện thương hiệu DX-OS Open-Core

## Logo

- Biểu tượng: mái nhà + dấu kiểm, tượng trưng cho cấp phép xây dựng và xác thực.
- File dùng chung: `apps/cap-phep/web/src/components/LogoMark.vue`,
  `apps/bang-dieu-hanh/web/src/components/LogoMark.vue`.
- Favicon: `apps/*/web/public/favicon.svg`.
- Theme Keycloak: `core/keycloak/themes/dxos/login` (chỉ CSS, giữ nguyên form và ID đăng nhập).
- Nền tối dùng logo trắng; nền sáng dùng logo xanh navy. Không đổi tỉ lệ, không thêm chữ vào icon.

## Bảng màu

| Token | Vai trò |
|---|---|
| `--ds-brand` | Lam, màu nhấn chính, link, trạng thái đang xử lý |
| `--ds-gold` | Vàng, cảnh báo/điểm nhấn |
| `--ds-success` | Xanh lá, đạt/thành công |
| `--ds-danger` | Đỏ, lỗi/từ chối/quá hạn |
| `--ds-text` / `--ds-muted` | Chữ chính / chữ phụ |
| `--ds-bg` | Nền chung |

Không đặt mã màu trực tiếp trong màn hình mới; dùng token trong
`apps/cap-phep/web/src/design-system/tokens.css` và `tailwind.config.js`.

## Typography

- Font: Inter, weight 400/600.
- Cỡ: 12 / 13 / 14 / 16 / 20 / 24 / 32 px (token `--ds-text-*`).
- Tiêu đề màn hình: 24–32 px, weight 600; nội dung: 14 px, line-height 1.55.

## Icon

- Dùng bộ icon trong design system và emoji có nhãn `aria-hidden` khi chỉ trang trí.
- Icon chức năng luôn có `aria-label` hoặc text đi kèm; không dùng icon một mình cho thao tác phá hủy.
- Kích thước chạm tối thiểu 44×44 px trên mobile.

## Giọng điệu

- Ngắn, rõ, tiếng Việt hành chính nhưng không quan liêu.
- Trạng thái dùng từ thống nhất: Đạt / Không đạt / Chờ thẩm định / Quá hạn.
- Không hiển thị mã kỹ thuật thô (`file.md`, UUID) cho công dân.

## Ghi chú

- Hai giao diện dùng chung palette và logo nhưng khác mật độ: citizen thoáng, điều hành dày thông tin.
- Mọi màn hình mới cần kiểm tra ở nền sáng/tối và breakpoint 375/768/1024/1440.
