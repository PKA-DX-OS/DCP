<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Track H — Human Workspace (lát cắt Gate 1)

Tài liệu bàn giao cho các lát cắt H đã làm trên nhánh `feat/human-workspace`.
Track H chỉ sửa file giao diện/API client thuộc quyền H; không sửa SQL, migration,
service backend hay `contracts/dh/*` của Track D.

## 1. Đã làm

| Mã việc | Nội dung | Trạng thái |
| :--- | :--- | :--- |
| H-WORK-01 | Client H theo hợp đồng `contracts/dh/*`, có fallback khi API chưa có | Xong phần 360/search |
| H-WORK-02 | Tab “Tổng hợp” trong chi tiết hồ sơ: chủ đầu tư, thửa đất, công trình, giấy phép, kiểm tra, tài chính, cảnh báo, nhật ký | Xong |
| H-WORK-03 | Tìm kiếm toàn cục `Ctrl/Cmd+K`, nhóm kết quả, điều hướng bàn phím | Xong |
| H-METRIC-01 | Tab “Hiệu quả vận hành” trong bảng điều hành | Xong phần khung + dữ liệu |

Chưa làm trong lát cắt này: autofill, OCR review, PWA hiện trường, self-service,
external lookup, workflow assistance, a11y/help đầy đủ.

## 2. API tiêu thụ

| API | Dùng ở | Hợp đồng |
| :--- | :--- | :--- |
| `GET /api/v1/mdm/dossiers/{id}/360` | `Dossier360Panel.vue` | `contracts/dh/mdm.yaml` |
| `GET /api/v1/search?q=&limit=` | `GlobalSearch.vue` | `contracts/dh/search.yaml` |
| `GET /api/v1/automation/metrics?from=&to=` | `AutomationMetricsPanel.vue` | `contracts/dh/automation.yaml` |

Mọi lời gọi H dùng timeout ngắn và không thử lại để UI không bị treo khi Track D chưa
triển khai endpoint:

- 360 và search: 5 giây, `retries: 0`.
- Metrics: dùng client chung của bảng điều hành (10 giây).

## 3. Fallback khi API chưa có

Không hiển thị số liệu giả như số thật. Mỗi fallback đều có nhãn nguồn:

| Màn | Khi API thiếu | Nhãn |
| :--- | :--- | :--- |
| 360 hồ sơ | Dùng dữ liệu hồ sơ đang mở | “Từ hồ sơ hiện tại” + ghi chú API 360 chưa sẵn sàng |
| Tìm kiếm | Lọc danh sách `fetchHoSo` hiện có | “Tìm trong danh sách hồ sơ hiện có — API tìm kiếm chưa sẵn sàng” |
| Hiệu quả vận hành | Chỉ hiện mốc v1.1, `current = null` | “Mốc v1.1, chưa có số hiện tại” + cảnh báo màu vàng |

Fallback tìm kiếm không trả CCCD hay số điện thoại đầy đủ; chỉ trả mã hồ sơ, họ tên,
trạng thái và địa chỉ. Kết quả không gắn hồ sơ thì không mở được và có ghi chú rõ.

## 4. File chính

| File | Vai trò |
| :--- | :--- |
| `apps/cap-phep/web/src/api/dh.ts` | Kiểu dữ liệu + client 360/search + fallback |
| `apps/cap-phep/web/src/components/Dossier360Panel.vue` | Panel 360 và fallback theo hồ sơ |
| `apps/cap-phep/web/src/components/GlobalSearch.vue` | Command palette tìm kiếm |
| `apps/cap-phep/web/src/components/DetailDossierModal.vue` | Thêm tab “Tổng hợp” |
| `apps/cap-phep/web/src/components/Navbar.vue` | Nút tìm kiếm toàn cục |
| `apps/cap-phep/web/src/App.vue` | Mở/đóng palette, phím tắt `Ctrl/Cmd+K`, mở hồ sơ từ kết quả |
| `apps/bang-dieu-hanh/web/src/api/automation.ts` | Kiểu + client chỉ số H, mốc v1.1 |
| `apps/bang-dieu-hanh/web/src/components/automation/AutomationMetricsPanel.vue` | Tab hiệu quả vận hành |
| `apps/bang-dieu-hanh/web/src/App.vue` | Thêm tab và phân quyền hiển thị |

## 5. Phân quyền hiển thị

| Màn | Vai |
| :--- | :--- |
| Nút tìm kiếm + palette | Người đã đăng nhập |
| 360 hồ sơ | Người đã đăng nhập; API quyết định dữ liệu trả về |
| Hiệu quả vận hành | `app:cap-phep:lanh-dao`, `dx:auditor`, `dx:tenant-admin`, `dx:platform-admin` |

## 6. Kiểm thử

```powershell
cd apps/cap-phep/web
npm run type-check
npm test
npm run build

cd apps/bang-dieu-hanh/web
npm run type-check
npm test
npm run build
```

Kết quả tại lát cắt này:

- Cấp phép: 14 tệp test, 121 test pass; type-check và build pass.
- Bảng điều hành: 5 tệp test, 26 test pass; type-check và build pass.
- Test mới: `tests/dh.test.js`, `tests/global-search.test.js`,
  `tests/dossier-360.test.js`, `tests/automation-panel.test.js`.

## 7. Việc Gate 2

1. Track D merge `GET /api/v1/mdm/dossiers/{id}/360`, `GET /api/v1/search`,
   `GET /api/v1/automation/metrics`.
2. Chạy lại 4 lệnh kiểm thử ở trên với API thật; xác nhận panel 360 chuyển nhãn
   “Dữ liệu MDM”, search chuyển nhãn “Dữ liệu tìm kiếm toàn cục”, metrics chuyển
   nhãn “Số đo thật”.
3. Thêm E2E: mở hồ sơ → tab Tổng hợp; `Ctrl/Cmd+K` → tìm mã hồ sơ → mở đúng hồ sơ;
   bảng điều hành → tab Hiệu quả vận hành.
4. Đo lại baseline H trên dữ liệu thật trước khi công bố tiết kiệm.
5. Giữ fallback có nhãn; không xóa cho tới khi API thật ổn định qua một vòng kiểm thử.

## 8. Giới hạn đã biết

- Chưa có mock server `VITE_API_MOCK`; fallback hiện dùng dữ liệu hồ sơ/baseline có nhãn.
- Fallback tìm kiếm chỉ lọc trong tối đa 100 hồ sơ gần nhất do `fetchHoSo` giới hạn
  `limit=100`; không thay thế được API `/search` khi dữ liệu lớn.
- Bảng điều hành chọn phường cho chỉ số cũ, nhưng API H đọc tenant từ JWT; chưa có
  tham số chọn địa bàn cho chỉ số H.
- 360 mới hiển thị một liên kết mỗi loại thực thể; chưa có màn hình chi tiết thực thể MDM.
- Chưa có autofill, OCR review, PWA, self-service.
