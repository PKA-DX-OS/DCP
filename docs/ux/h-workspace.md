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
| H-AUTO-01 | Điền nhanh từ hồ sơ cũ/tài khoản; không ghi đè dữ liệu đã nhập; cảnh báo trùng | Xong phần hồ sơ/tài khoản |
| H-AUTO-02 | Kiểm tra CCCD, điện thoại, địa chỉ, thửa đất, số tầng, diện tích; tự lưu bản nháp | Xong |
| H-OCR | Hàng chờ duyệt trích xuất, xem tệp gốc, sửa trường, xác nhận/từ chối | Xong UI + mock; chờ API D |
| H-WORK-04 | Lưu bộ lọc, chọn nhiều, nhắc/phân công hàng loạt, xuất CSV | Xong |
| H-METRIC-01 | Tab “Hiệu quả vận hành” trong bảng điều hành | Xong phần khung + dữ liệu |

Chưa làm trong lát cắt này: autofill từ OCR thật, PWA hiện trường, self-service,
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

## 4. Autofill, kiểm tra dữ liệu và bản nháp

### 4.1. Điền nhanh

- Nguồn: hồ sơ cũ của chính chủ đầu tư (ưu tiên hồ sơ cùng CCCD) và họ tên từ tài khoản.
- Chỉ điền vào ô đang trống. Số tầng/diện tích còn ở giá trị mặc định `1`/`100` cũng được
  coi là ô trống; dữ liệu người dùng đã sửa không bị ghi đè.
- Không điền CCCD hoặc điện thoại đã bị che (`****`).
- OCR là nguồn tiếp theo nhưng chưa dùng vì Track D chưa có `/api/v1/ocr/*`.

### 4.2. Kiểm tra trước khi nộp

| Trường | Quy tắc |
| :--- | :--- |
| Họ tên | Ít nhất 3 ký tự, không có chữ số |
| CCCD | Đúng 12 chữ số, không bắt đầu `000`, không toàn số giống nhau |
| Điện thoại | 10–11 chữ số, đầu số 02/03/05/07/08/09; tự đổi `+84` thành `0` |
| Địa chỉ | Ít nhất 5 ký tự |
| Thửa đất | Có ít nhất 3 ký tự và có số |
| Số tầng | Số nguyên 1–5 |
| Diện tích sàn | Lớn hơn 0 và không quá 100.000 m² |

Lỗi hiện tại chỗ, có `aria-invalid`, tổng hợp ở đầu form và chặn gửi. Hồ sơ trùng
CCCD + thửa đất hiện cảnh báo kèm nút mở hồ sơ đã có; cảnh báo không tự chặn nộp.
Form bổ sung hồ sơ dùng cùng bộ kiểm tra cho địa chỉ, thửa đất, số tầng, diện tích.

### 4.3. Bản nháp

- Tự lưu sau 500 ms vào `sessionStorage`, khóa theo người dùng; hết hạn sau 24 giờ.
- Chỉ lưu biểu mẫu, không lưu tệp đã chọn (trình duyệt không cho khôi phục `File`).
- Nộp thành công hoặc đăng xuất thì xóa; người dùng có nút “Xóa bản nháp” và ghi chú
  không dùng máy tính dùng chung.
- Không gửi bản nháp lên máy chủ; chỉ dùng trong tab trình duyệt hiện tại.

## 5. Duyệt OCR

- Tab “Duyệt OCR” cho `app:cap-phep:mot-cua`, `app:cap-phep:tham-dinh`,
  `app:cap-phep:lanh-dao`.
- Hàng chờ lọc theo trạng thái, loại giấy và độ tin cậy ≤ 80%; có phân trang.
- Chi tiết hiện từng trường, độ tin cậy, trang và vùng `bbox`; ảnh gốc có ô bao vùng
  tương ứng, PDF xem bằng iframe.
- Cán bộ sửa giá trị trường rồi xác nhận, hoặc từ chối kèm lý do.
- Không tự ghi vào hồ sơ: chỉ sau xác nhận mới dùng để điền sẵn; cán bộ vẫn phải lưu.
- Gọi API thật `GET /api/v1/ocr`, `GET /api/v1/ocr/{id}`,
  `POST /api/v1/ocr/{id}/confirm`, `POST /api/v1/ocr/{id}/reject` với `Idempotency-Key`.
- Khi API chưa có: dùng dữ liệu mẫu theo `contracts/dh/ocr.yaml`, ghi rõ “Dữ liệu mẫu”;
  xác nhận/từ chối chỉ đổi trên trình duyệt, không tạo audit thật.

## 6. Bộ lọc đã lưu & thao tác hàng loạt

### 6.1. Bộ lọc đã lưu

- Lưu cặp “Hạn” + “Loại việc” theo tên vào `localStorage`, tối đa 10 bộ lọc.
- Chọn lại để áp dụng, hoặc xóa bộ lọc đang chọn.
- Chỉ lưu nhãn bộ lọc, không lưu hồ sơ, CCCD hay dữ liệu cá nhân.

### 6.2. Thao tác hàng loạt

- Chọn từng việc hoặc chọn tất cả việc đang lọc.
- **Nhắc việc**: chỉ lãnh đạo/một cửa; có bước xác nhận; báo số thành công/thất bại.
- **Phân công**: chọn nhóm cán bộ (thẩm định/một cửa/lãnh đạo/trật tự), chọn cán bộ, lý do; có xác nhận.
- Việc lỗi được giữ chọn để thử lại; việc thành công được bỏ chọn.
- **Xuất CSV** các việc đã chọn: mã hồ sơ, tên việc, địa chỉ, hạn, trạng thái, mức ưu tiên.
- CSV tạo và tải trên máy, không gửi lên máy chủ; nhắc/phân công được ghi audit phía máy chủ.
- API dùng: `fetchOfficers`, `assignTask`, `remindTask` (đã có).

## 7. File chính

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
| `apps/cap-phep/web/src/components/CreateDossierModal.vue` | Điền nhanh, kiểm tra, cảnh báo trùng, bản nháp |
| `apps/cap-phep/web/src/components/SupplementModal.vue` | Kiểm tra dữ liệu bổ sung |
| `apps/cap-phep/web/src/utils/validation.ts` | Quy tắc kiểm tra CCCD, điện thoại, địa chỉ, thửa đất, tầng, diện tích |
| `apps/cap-phep/web/src/utils/nop-ho-so.ts` | Form mặc định, bản nháp sessionStorage, điền từ hồ sơ cũ |
| `apps/cap-phep/web/src/api/ocr.ts` | Client OCR, kiểu dữ liệu, mock có nhãn, idempotency |
| `apps/cap-phep/web/src/features/ocr-review/*` | Tab Duyệt OCR: hàng chờ, chi tiết, xác nhận/từ chối |
| `apps/cap-phep/web/src/views/WorkspaceView.vue` | Bộ lọc đã lưu, chọn nhiều, nhắc/phân công/CSV |
| `apps/cap-phep/web/src/utils/workspace-filters.ts` | Đọc/ghi/xóa bộ lọc Bàn làm việc trong localStorage |
| `apps/cap-phep/web/src/utils/csv.ts` | Tạo CSV có BOM và escape đúng |

## 8. Phân quyền hiển thị

| Màn | Vai |
| :--- | :--- |
| Nút tìm kiếm + palette | Người đã đăng nhập |
| 360 hồ sơ | Người đã đăng nhập; API quyết định dữ liệu trả về |
| Duyệt OCR | `app:cap-phep:mot-cua`, `app:cap-phep:tham-dinh`, `app:cap-phep:lanh-dao` |
| Nhắc/phân công hàng loạt | `app:cap-phep:lanh-dao`, `app:cap-phep:mot-cua` |
| Chọn & xuất CSV | Cán bộ thấy Bàn làm việc |
| Hiệu quả vận hành | `app:cap-phep:lanh-dao`, `dx:auditor`, `dx:tenant-admin`, `dx:platform-admin` |

## 9. Kiểm thử

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

- Cấp phép: 25 tệp test, 171 test pass; type-check và build pass.
- Bảng điều hành: 5 tệp test, 26 test pass; type-check và build pass.
- Test H-WORK: `tests/dh.test.js`, `tests/global-search.test.js`,
  `tests/dossier-360.test.js`, `tests/automation-panel.test.js`.
- Test H-AUTO: `tests/validation.test.js`, `tests/nop-ho-so.test.js`,
  `tests/create-dossier-autofill.test.js`, `tests/create-dossier-validation.test.js`,
  `tests/create-dossier-draft.test.js`, `tests/supplement-validation.test.js`.
- Test H-OCR: `tests/ocr-api.test.js`, `tests/ocr-review.test.js`.
- Test H-WORK-04: `tests/workspace-filters.test.js`, `tests/csv.test.js`,
  `tests/workspace-bulk.test.js`.

## 10. Việc Gate 2

1. Track D merge `GET /api/v1/mdm/dossiers/{id}/360`, `GET /api/v1/search`,
   `GET /api/v1/automation/metrics`, `/api/v1/ocr/*`.
2. Chạy lại 4 lệnh kiểm thử ở trên với API thật; xác nhận panel 360 chuyển nhãn
   “Dữ liệu MDM”, search chuyển nhãn “Dữ liệu tìm kiếm toàn cục”, metrics chuyển
   nhãn “Số đo thật”, OCR chuyển nhãn “API OCR”.
3. Thêm E2E: mở hồ sơ → tab Tổng hợp; `Ctrl/Cmd+K` → tìm mã hồ sơ → mở đúng hồ sơ;
   bảng điều hành → tab Hiệu quả vận hành; duyệt OCR → sửa trường → xác nhận;
   chọn nhiều việc → nhắc/phân công/CSV.
4. Nối OCR thật: `POST /api/v1/ocr/extract` → review → điền tiếp vào form nộp hồ sơ.
5. Đo lại baseline H trên dữ liệu thật trước khi công bố tiết kiệm.
6. Giữ fallback có nhãn; không xóa cho tới khi API thật ổn định qua một vòng kiểm thử.

## 11. Giới hạn đã biết

- Chưa có mock server `VITE_API_MOCK`; fallback hiện dùng dữ liệu hồ sơ/baseline có nhãn.
- Fallback tìm kiếm chỉ lọc trong tối đa 100 hồ sơ gần nhất do `fetchHoSo` giới hạn
  `limit=100`; không thay thế được API `/search` khi dữ liệu lớn.
- Bảng điều hành chọn phường cho chỉ số cũ, nhưng API H đọc tenant từ JWT; chưa có
  tham số chọn địa bàn cho chỉ số H.
- 360 mới hiển thị một liên kết mỗi loại thực thể; chưa có màn hình chi tiết thực thể MDM.
- Autofill từ OCR chưa có vì Track D chưa triển khai `/api/v1/ocr/*`.
- Chưa kiểm tra mã định danh địa điểm 12 số vì RPC nộp hồ sơ hiện chưa nhận trường này;
  cần Track D bổ sung trước khi thêm vào form.
- Bản nháp dùng `sessionStorage` của tab hiện tại; đóng tab là mất, không đồng bộ giữa thiết bị.
- OCR mới có UI + mock; chưa kiểm chứng audit thật, chưa có hàng chờ thật, chưa nối
  kết quả đã xác nhận vào autofill.
- Xem tệp gốc phụ thuộc dịch vụ files và quyền của người dùng; PDF/ảnh lỗi MIME sẽ
  chỉ hiện nút tải tệp.
- Bộ lọc đã lưu chỉ nằm trong trình duyệt hiện tại, không đồng bộ giữa thiết bị.
- CSV xuất trên máy, không gửi máy chủ và không tạo audit; chỉ nhắc/phân công mới
  được ghi audit.
- Phân công hàng loạt chọn cán bộ theo nhóm vai, chưa tự cân bằng tải việc.
- Chưa có PWA, self-service.
