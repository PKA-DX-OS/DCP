# Kết quả QA giao diện — B-TEST-01/02/03

- **Ngày chạy:** 2026-11-20
- **Môi trường:** Windows 11, Docker Desktop 29.9.3, stack `dx up` tại `http://localhost:8080`
- **Phiên bản:** Python 3.12.5, pytest 9.2.0, Playwright 1.62.0, Pillow 10.2.0,
  Node 24.22.1, npm 11.17.0
- **Trình duyệt:** Chromium 151.0.7922.34, Firefox 153.0, WebKit 26.5

## 1. Unit test giao diện (B-TEST-01)

| Ứng dụng | Lệnh | Kết quả |
|---|---|---|
| cap-phep | `npm test` | 99 test đạt |
| bang-dieu-hanh | `npm test` | 17 test đạt (metrics, markdown, theme/anhSang, useTheme) |

Bảng điều hành đã chuyển từ `node --test` sang Vitest 3.2.7, cùng chuẩn với app cấp phép.
Các test design system, notification, registry và formatter tiếp tục nằm ở `apps/cap-phep/web/tests`.

## 2. Playwright theo vai (B-TEST-02)

`tests/e2e-ui/test_roles.py` — 9 test đạt:

| Vai | Tài khoản | Luồng chính |
|---|---|---|
| Chủ đầu tư | `cdt.minh` | Hồ sơ của tôi, bảng hồ sơ |
| Một cửa | `mc.thu` | Bàn làm việc |
| Thẩm định | `td.binh` | Bàn làm việc |
| Trật tự xây dựng | `tt.khanh` | Bàn làm việc |
| Lãnh đạo | `ld.hoa` | Bàn làm việc, truy cập khẩn, bảng điều hành, trợ lý |
| Kiểm toán viên | `kt.an` | Nhật ký kiểm toán, trạng thái chuỗi |
| Quản trị nền tảng | `admin` | Quản trị địa bàn |

## 3. Hồi quy hình ảnh (B-TEST-02)

`tests/e2e-ui/test_visual.py` — 9 ảnh nền tại `tests/e2e-ui/baseline/`:

`login-cap-phep`, `login-dieu-hanh`, `public-lookup`, `dashboard`, `workspace`,
`dossier-detail`, `design-review`, `planning`, `acceptance`.

- Viewport cố định 1366×900, locale `vi-VN`, scale 1, tắt animation.
- **Ngưỡng:** tối đa **3%** số điểm ảnh có kênh màu lệch quá 16/255.
- Vùng dữ liệu động (số KPI, ngày giờ, bảng, danh sách tệp, audit) được che trước khi so sánh.
- Tạo lại ảnh nền: `$env:E2E_UPDATE_BASELINE="1"; pytest tests/e2e-ui/test_visual.py -q`.

## 4. Khả năng tiếp cận (B-TEST-03)

`tests/e2e-ui/test_B_a11y.py` — axe-core 4.10.2, chỉ xét `serious`/`critical`, kết quả **0 vi phạm** trên:

- Trang chào và danh sách hồ sơ (sáng/tối)
- Bảng điều hành lãnh đạo (sáng/tối)
- Nhật ký kiểm toán
- Chi tiết hồ sơ + tab Thiết kế
- Quản trị địa bàn

Đã sửa trong đợt này: vùng cuộn `#list-dossier-audit` có `tabindex="0"` và nhãn
`aria-label`, đủ điều kiện `scrollable-region-focusable`.

## 5. Đa trình duyệt (B-TEST-03)

`tests/e2e-ui/test_cross_browser.py` — 4 test đạt:

- Chromium, Firefox, WebKit: trang chào + đăng nhập Keycloak + bảng điều hành.
- Ghi chú môi trường Windows: máy có listener IPv4 khác trên cổng 8080
  (Docker/WSL/Hyper-V), nên Firefox được đặt `network.dns.preferIPv6=true`
  để đi đúng cổng của stack. Không ảnh hưởng cấu hình ứng dụng.

## 6. Hiệu năng cơ bản (B-TEST-03)

Đo bằng Navigation Timing và Paint Timing trên Chromium, viewport 1366×900,
stack cục bộ (không phải Lighthouse, không đại diện mạng production):

| Trang | FCP | DOMContentLoaded | Load | Tài nguyên |
|---|---|---|---|---|
| Trang chào | 104 ms | 49 ms | 99 ms | 586 KB |
| Tra cứu công khai | — | 38 ms | 38 ms | 0 KB |

Kết quả thô: `logs/qa-ui/performance.json`.
Ngưỡng test hiện tại: FCP < 5 s, DOMContentLoaded < 10 s — đủ để bắt hồi quy lớn,
không dùng làm cam kết SLA.

## 7. Lệnh chạy lại

```powershell
cd D:\PMNM\DCP
$env:PYTHONPATH="D:\PMNM\DCP\services;D:\PMNM\DCP"
py -3 -m pytest tests/e2e-ui -q
cd apps\cap-phep\web; npm test; npm run build
cd ..\bang-dieu-hanh\web; npm test; npm run build
```

## 8. Hạn chế đã biết

- Ảnh nền gắn với dữ liệu seed và viewport 1366×900; đổi seed lớn cần tạo lại baseline.
- Test hồi quy ảnh cần thêm `Pillow` (`pip install pillow`) ngoài Playwright; nếu thiếu, test tự skip.
- Hiệu năng mới đo trên máy cục bộ, chưa có Lighthouse/CI runner riêng.
- Firefox cần ưu tiên IPv6 trên máy Windows có xung đột cổng 8080.
