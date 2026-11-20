<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Kết quả kiểm thử giao diện: tiếp cận, đa trình duyệt, hiệu năng (B-TEST-03)

Bộ test: `tests/e2e-ui/` (Playwright), tệp chính `test_cross_browser.py`, cùng `test_roles.py`, `test_visual.py`, `test_B_a11y.py`.

## Cách chạy

```bash
# Một lần: trình duyệt cho Playwright và axe-core
python -m playwright install chromium firefox webkit
(cd apps/cap-phep/web && npm ci)

# Stack đã dx up (DEMO_MODE=true) và đã nạp hero
python scripts/seed_hero.py
pytest tests/e2e-ui -q --browser chromium --browser firefox --browser webkit
```

Mỗi trình duyệt ghi kết quả vào `logs/e2e-ui/qa/ket-qua-<trình duyệt>.md` và `.json`, kèm ngày giờ, commit, phiên bản trình duyệt, hệ điều hành. Chép bảng ở đó vào mục **Kết quả** bên dưới, mỗi lần chạy một mục mới.

## Tiêu chí

| Phần | Tiêu chí đạt |
| :--- | :--- |
| Đa trình duyệt | Phép thử khói (trang chào, tra cứu, đăng nhập, bàn làm việc, chi tiết hồ sơ, bảng điều hành) và test theo vai đạt trên Chromium, Firefox, WebKit |
| Tiếp cận (axe-core) | Không có lỗi mức serious/critical trên: trang chào, danh sách hồ sơ, bảng điều hành, kiểm toán (`test_B_a11y.py`); đăng nhập Keycloak, tra cứu công khai, bàn làm việc, chi tiết hồ sơ, thẩm định thiết kế (`test_cross_browser.py`). Lỗi mức thấp hơn được ghi lại, không chặn |
| Hiệu năng (Chromium, đo tương đương Lighthouse) | DOMContentLoaded ≤ 2 500 ms, load ≤ 4 000 ms, LCP ≤ 2 500 ms, JS + CSS tải về ≤ 1 500 KB cho trang chào, tra cứu, bảng điều hành; đo trên máy chạy stack, mạng nội bộ, không giả lập mạng chậm |
| Hồi quy hình ảnh (Chromium) | Mỗi màn hình khác ảnh nền ≤ 2 % điểm ảnh (điểm khác: một kênh lệch > 40/255) |

Không chạy Lighthouse CLI vì cần Node và Chrome riêng ngoài stack. Các số đo trên lấy từ Performance API của trình duyệt (Navigation Timing, Largest Contentful Paint, Resource Timing), cùng nguồn Lighthouse dùng.

## Kết quả

### Lần chạy đầu: chưa có

Chưa chạy trên stack thật. Môi trường phát triển của commit này không tải được trình duyệt Playwright. Đã kiểm ở đây:
- `pytest tests/e2e-ui --collect-only --browser chromium --browser firefox --browser webkit` thu thập đủ test cho cả ba trình duyệt, không lỗi import;
- `ruff check`, `reuse lint` đạt.

Điền kết quả lần chạy thật vào đây theo mẫu:

```
### <ngày>, commit <mã>, <hệ điều hành>, Python <phiên bản>
<bảng từ logs/e2e-ui/qa/ket-qua-chromium.md>
<bảng từ logs/e2e-ui/qa/ket-qua-firefox.md>
<bảng từ logs/e2e-ui/qa/ket-qua-webkit.md>
```
