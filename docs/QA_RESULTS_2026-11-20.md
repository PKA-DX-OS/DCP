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

### 20/11/2026, commit `7420be4`, Windows 11 AMD64, Python 3.14.5

Stack dựng lại bằng `dx up` (DEMO_MODE=true), đã nạp `seed_hero`. Tổng hợp:

| Phần | Kết quả |
| :--- | :--- |
| Test theo vai + đa trình duyệt (`test_roles.py`, `test_cross_browser.py`) | 37 đạt, 5 bỏ qua có lý do, 0 lỗi |
| Tiếp cận (axe-core) | 0 lỗi serious/critical trên cả ba trình duyệt; còn `page-has-heading-one`, `heading-order`, `landmark-unique` mức moderate |
| Hiệu năng (Chromium) | Trong ngân sách ở cả ba trang (bảng dưới) |
| Hồi quy hình ảnh (`test_visual.py`, 9 màn hình) | Đạt hai lần liên tiếp so với ảnh nền đã commit |

Chưa chạy trong đợt này: `test_B_a11y.py` (axe trên trang chào, danh sách hồ sơ, bảng điều hành, kiểm toán) và các test e2e luồng đầy đủ khác của Track A/B.

5 test bỏ qua: 3 test thẩm định viên (td.binh chưa được phân công hồ sơ nào trong dữ liệu mẫu; chạy lại sau cảnh 4 của kịch bản demo) và 2 phép đo LCP/transferSize chỉ có trên Chromium.

Lỗi phát hiện và đã sửa trong đợt này: vùng cuộn không nhận focus bàn phím (Firefox/WebKit), độ tương phản màu nền sáng của trang tra cứu, thanh tiến độ và ô chọn tệp nghiệm thu thiếu nhãn, route APISIX thiếu trên máy đã `dx init` trước khi có route fragment mới (cảnh báo hồ sơ, quy hoạch, nghiệm thu trả 404).

#### chromium 159.0.8154.6

- Ngày giờ: 2026-11-20T15:07:21+07:00; commit `7420be4`
- Môi trường: Windows 11 AMD64, Python 3.14.5, http://localhost:8080

| Màn hình | Kết quả |
| :--- | :--- |
| trang chào, tra cứu | đạt |
| đăng nhập, bàn làm việc, chi tiết hồ sơ | đạt |
| bảng điều hành | đạt |

| Màn hình (axe) | serious/critical | Mức khác |
| :--- | :--- | :--- |
| tra cứu công khai | không | không |
| đăng nhập Keycloak | không | không |
| bàn làm việc | không | page-has-heading-one:moderate |
| chi tiết hồ sơ (cán bộ) | không | không |
| thẩm định thiết kế (chủ đầu tư) | không | heading-order:moderate |

| Trang | DCL (ms) | load (ms) | LCP (ms) | JS+CSS (KB) |
| :--- | ---: | ---: | ---: | ---: |
| trang chào / | 86 | 179 | 200 | 459 |
| tra cứu /kiem-tra/ | 17 | 19 | 80 | 0 |
| bảng điều hành /dieu-hanh/ | 30 | 32 | 80 | 199 |

#### firefox 159.0

- Ngày giờ: 2026-11-20T15:08:00+07:00; commit `7420be4`
- Môi trường: Windows 11 AMD64, Python 3.14.5, http://localhost:8080

| Màn hình | Kết quả |
| :--- | :--- |
| trang chào, tra cứu | đạt |
| đăng nhập, bàn làm việc, chi tiết hồ sơ | đạt |
| bảng điều hành | đạt |

| Màn hình (axe) | serious/critical | Mức khác |
| :--- | :--- | :--- |
| tra cứu công khai | không | không |
| đăng nhập Keycloak | không | không |
| bàn làm việc | không | page-has-heading-one:moderate |
| chi tiết hồ sơ (cán bộ) | không | không |
| thẩm định thiết kế (chủ đầu tư) | không | heading-order:moderate, landmark-unique:moderate |

#### webkit 27.2

- Ngày giờ: 2026-11-20T15:08:15+07:00; commit `7420be4`
- Môi trường: Windows 11 AMD64, Python 3.14.5, http://localhost:8080

| Màn hình | Kết quả |
| :--- | :--- |
| trang chào, tra cứu | đạt |
| đăng nhập, bàn làm việc, chi tiết hồ sơ | đạt |
| bảng điều hành | đạt |

| Màn hình (axe) | serious/critical | Mức khác |
| :--- | :--- | :--- |
| tra cứu công khai | không | không |
| đăng nhập Keycloak | không | không |
| bàn làm việc | không | page-has-heading-one:moderate |
| chi tiết hồ sơ (cán bộ) | không | không |
| thẩm định thiết kế (chủ đầu tư) | không | heading-order:moderate |
