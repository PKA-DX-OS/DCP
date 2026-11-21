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
| H-FIELD | PWA hiện trường: nháp offline, ảnh, GPS, checklist, ký tay, đồng bộ | Xong phần UI + lưu máy |
| H-SELF | Tự phục vụ công dân: tiến độ, bổ sung, tải giấy phép, QR tra cứu | Xong |
| H-FLOW | Hỗ trợ xử lý: gợi ý phân công, cảnh báo SLA, nháp thông báo | Xong |
| H-UX | Trợ giúp F1, phím tắt, ARIA/focus, kiểm tra axe | Xong phần component |
| H-METRIC-01 | Tab “Hiệu quả vận hành” trong bảng điều hành | Xong phần khung + dữ liệu |

Chưa làm trong lát cắt này: autofill từ OCR thật, đặt lịch/thanh toán trực tuyến,
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

## 7. PWA hiện trường

### 7.1. PWA

- `manifest.webmanifest`: standalone, icon 192/512, shortcut “Phiếu hiện trường”.
- `sw.js`: cache app shell và tài nguyên tĩnh; network-first cho điều hướng; không cache
  `/api/`, `/auth/`, `/files/`, `/realms/`.
- `offline.html` dự phòng; đăng ký service worker chỉ ở bản build.
- Nút “Cài ứng dụng” khi trình duyệt phát `beforeinstallprompt`.

### 7.2. Phiếu nháp trên thiết bị

- Tab “Hiện trường” cho `app:cap-phep:trat-tu-xd` và `app:cap-phep:lanh-dao`.
- Chọn công trình; danh sách công trình được cache để dùng offline.
- Checklist 6 mục, ghi chú, GPS hiện tại.
- Tối đa 6 ảnh, mỗi ảnh ≤ 8 MB; xem thumbnail và xóa trước khi gửi.
- Ký tay bằng canvas; lưu data URL.
- Nháp, ảnh và chữ ký lưu trong IndexedDB; fallback bộ nhớ tab nếu trình duyệt chặn.
- Tự lưu sau 600 ms; mở lại trang vẫn còn nháp.

### 7.3. Đồng bộ & xung đột

- Chặn gửi khi đang ngoại tuyến; phiếu vẫn nằm trên thiết bị.
- Gửi qua `lap_phieu_kiem_tra` hiện có; checklist/GPS/ghi chú được tóm tắt vào `p_ghi_chu`.
- Ảnh và chữ ký **chưa tải lên** vì API phiếu kiểm tra chưa nhận tệp đính kèm.
- Phát hiện phiếu trên máy chủ lập sau bản nháp cho cùng công trình; cảnh báo và cho
  phép “Vẫn gửi”.
- Gửi lỗi thì giữ trạng thái “Lỗi đồng bộ” để thử lại; gửi thành công lưu mã phiếu.
- “Gửi tất cả” chỉ gửi phiếu hợp lệ và không xung đột; phiếu xung đột phải xác nhận riêng.

## 8. Tự phục vụ công dân

- Tab “Tự phục vụ” cho `app:cap-phep:chu-dau-tu`.
- Tổng quan 4 nhóm: tổng hồ sơ, đang xử lý, cần bổ sung, đã cấp; bấm để lọc.
- Từng hồ sơ hiện trạng thái, bước hiện tại, hạn xử lý/quá hạn, thanh tiến trình.
- Hồ sơ cần bổ sung có lý do, hạn và nút mở form bổ sung hiện có.
- Hồ sơ đã cấp:
  - Tải giấy phép PDF qua `fetchPermitInfo` + `downloadFile`.
  - QR tra cứu công khai từ `ma_cong_khai`, tạo trên trình duyệt bằng thư viện
    `qrcode`; không gọi dịch vụ ngoài.
  - Chép liên kết, tải ảnh QR, mở trang tra cứu.
- Trạng thái rỗng có nút nộp hồ sơ mới; tải/lỗi có retry.
- Đặt lịch và thanh toán trực tuyến chưa làm vì backend chưa có API/nghiệp vụ.

## 9. Hỗ trợ xử lý

- Panel “Hỗ trợ xử lý” trong Bàn làm việc khi chọn một việc/hồ sơ.
- Cảnh báo hạn/SLA của việc: quá hạn, còn ≤ 48 giờ, còn ngày.
- Gợi ý phân công:
  - Chọn nhóm vai theo loại việc: một cửa, thẩm định, lãnh đạo, trật tự.
  - Lấy `GET /api/v1/metrics/workload` và `fetchOfficers` để xếp cán bộ ít việc
    đang xử lý trước; hiện top 3.
  - Cán bộ phải chọn và bấm “Xác nhận giao việc”; không tự giao.
- Nháp thông báo theo mẫu: nhắc bổ sung, tiếp nhận, đã cấp, nhắc việc nội bộ.
  - Sinh từ mã hồ sơ, chủ đầu tư, địa chỉ, lý do bổ sung, hạn xử lý.
  - Sửa được, tạo lại, chép nội dung.
  - “Gửi nhắc việc nội bộ” dùng `remindTask` với nội dung nháp.
  - Không tự gửi cho công dân; cán bộ gửi qua kênh chính thức.
- Chỉ lãnh đạo/một cửa thấy nút giao việc/nhắc việc; cán bộ khác vẫn tạo nháp.

## 10. Trợ giúp & khả năng tiếp cận

- Nút “Trợ giúp” trên Navbar và phím `F1`.
- Drawer trợ giúp có:
  - Phím tắt: `Ctrl/Cmd+K`, `F1`, `Tab`, `Enter/Space`, `Esc`.
  - Mô tả ngắn các màn hình theo vai.
  - Liên hệ Bộ phận Một cửa; lưu ý giảm chuyển động.
- `aria-keyshortcuts` cho tìm kiếm và trợ giúp.
- Input chọn ảnh hiện trường có nhãn ARIA dù bị ẩn bằng `sr-only`.
- Giữ hành vi có sẵn:
  - Skip link “Bỏ qua điều hướng”.
  - Focus-visible 2 px màu champagne.
  - Dialog trap focus, đóng bằng Esc, trả focus.
  - `prefers-reduced-motion` tắt animation/transition.
- Test axe chạy trên `HelpDrawer` và `QrCodeModal`: không có vi phạm
  serious/critical (tắt `color-contrast` vì happy-dom không có layout thật).

## 11. File chính

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
| `apps/cap-phep/web/src/features/hien-truong/*` | Tab hiện trường, ký tay, nháp/đồng bộ |
| `apps/cap-phep/web/src/utils/field-inspection.ts` | Kiểu phiếu, checklist, tóm tắt ghi chú, xung đột |
| `apps/cap-phep/web/src/utils/field-drafts.ts` | IndexedDB/fallback lưu nháp, ảnh, cache công trình |
| `apps/cap-phep/web/src/features/tu-phuc-vu/*` | Tab Tự phục vụ: tổng quan, tiến độ, bổ sung, tải kết quả, QR |
| `apps/cap-phep/web/src/components/QrCodeModal.vue` | Tạo QR tra cứu bằng thư viện `qrcode` |
| `apps/cap-phep/web/src/components/workflow/WorkflowAssistantPanel.vue` | Gợi ý phân công, SLA, nháp thông báo |
| `apps/cap-phep/web/src/utils/workflow-assist.ts` | Chọn vai, xếp hạng cán bộ, sinh nháp |
| `apps/cap-phep/web/src/components/HelpDrawer.vue` | Trợ giúp, phím tắt, mô tả màn hình |
| `apps/cap-phep/web/src/components/Navbar.vue` | Nút trợ giúp + `aria-keyshortcuts` |
| `apps/cap-phep/web/public/{manifest.webmanifest,sw.js,offline.html,icon-*.png}` | PWA shell |

## 12. Phân quyền hiển thị

| Màn | Vai |
| :--- | :--- |
| Nút tìm kiếm + palette | Người đã đăng nhập |
| 360 hồ sơ | Người đã đăng nhập; API quyết định dữ liệu trả về |
| Duyệt OCR | `app:cap-phep:mot-cua`, `app:cap-phep:tham-dinh`, `app:cap-phep:lanh-dao` |
| Nhắc/phân công hàng loạt | `app:cap-phep:lanh-dao`, `app:cap-phep:mot-cua` |
| Chọn & xuất CSV | Cán bộ thấy Bàn làm việc |
| Hiện trường / PWA | `app:cap-phep:trat-tu-xd`, `app:cap-phep:lanh-dao` |
| Tự phục vụ | `app:cap-phep:chu-dau-tu` |
| Giao việc/nhắc việc hỗ trợ | `app:cap-phep:lanh-dao`, `app:cap-phep:mot-cua` |
| Nháp thông báo | Cán bộ thấy Bàn làm việc |
| Trợ giúp / phím tắt | Mọi người dùng đã đăng nhập |
| Hiệu quả vận hành | `app:cap-phep:lanh-dao`, `dx:auditor`, `dx:tenant-admin`, `dx:platform-admin` |

## 13. Kiểm thử

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

- Cấp phép: 33 tệp test, 198 test pass; type-check và build pass.
- Bảng điều hành: 5 tệp test, 26 test pass; type-check và build pass.
- Test H-WORK: `tests/dh.test.js`, `tests/global-search.test.js`,
  `tests/dossier-360.test.js`, `tests/automation-panel.test.js`.
- Test H-AUTO: `tests/validation.test.js`, `tests/nop-ho-so.test.js`,
  `tests/create-dossier-autofill.test.js`, `tests/create-dossier-validation.test.js`,
  `tests/create-dossier-draft.test.js`, `tests/supplement-validation.test.js`.
- Test H-OCR: `tests/ocr-api.test.js`, `tests/ocr-review.test.js`.
- Test H-WORK-04: `tests/workspace-filters.test.js`, `tests/csv.test.js`,
  `tests/workspace-bulk.test.js`.
- Test H-FIELD: `tests/field-inspection.test.js`, `tests/field-drafts.test.js`,
  `tests/field-pwa.test.js`.
- Test H-SELF: `tests/self-service.test.js`, `tests/qr-code.test.js`.
- Test H-FLOW: `tests/workflow-assist.test.js`, `tests/workflow-assistant.test.js`.
- Test H-UX: `tests/a11y.test.js`; axe bổ sung trong `tests/qr-code.test.js`.

## 14. Việc Gate 2

1. Track D merge `GET /api/v1/mdm/dossiers/{id}/360`, `GET /api/v1/search`,
   `GET /api/v1/automation/metrics`, `/api/v1/ocr/*`.
2. Chạy lại 4 lệnh kiểm thử ở trên với API thật; xác nhận panel 360 chuyển nhãn
   “Dữ liệu MDM”, search chuyển nhãn “Dữ liệu tìm kiếm toàn cục”, metrics chuyển
   nhãn “Số đo thật”, OCR chuyển nhãn “API OCR”.
3. Thêm E2E: mở hồ sơ → tab Tổng hợp; `Ctrl/Cmd+K` → tìm mã hồ sơ → mở đúng hồ sơ;
   bảng điều hành → tab Hiệu quả vận hành; duyệt OCR → sửa trường → xác nhận;
   chọn nhiều việc → nhắc/phân công/CSV; PWA hiện trường → tạo nháp offline → sync;
   tự phục vụ → bổ sung → tải giấy phép → QR; hỗ trợ xử lý → gợi ý phân công → nháp.
4. Nối OCR thật: `POST /api/v1/ocr/extract` → review → điền tiếp vào form nộp hồ sơ.
5. Bổ sung API nhận ảnh/chữ ký/GPS của phiếu hiện trường; hiện chỉ tóm tắt vào ghi chú.
6. Làm đặt lịch/thanh toán khi có API và nghiệp vụ được chốt.
7. Chạy axe/Playwright trên trình duyệt thật cho các màn chính; kiểm tra color-contrast.
8. Đo lại baseline H trên dữ liệu thật trước khi công bố tiết kiệm.
9. Giữ fallback có nhãn; không xóa cho tới khi API thật ổn định qua một vòng kiểm thử.

## 15. Giới hạn đã biết

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
- Phiếu hiện trường chỉ tóm tắt checklist/GPS/ghi chú vào `p_ghi_chu`; ảnh/chữ ký chưa
  tải lên máy chủ.
- Xung đột dựa trên `created_at` của phiếu cùng công trình, chưa phải version chính thức.
- H-LINK mới là adapter mock; chưa gọi CSDL liên ngành thật và chưa ghi audit.
  Xác nhận chỉ nằm trong bộ nhớ phiên, không đồng bộ giữa thiết bị.
- PWA cache app shell; nếu phiên OIDC hết hạn khi offline, ứng dụng có thể yêu cầu đăng
  nhập lại trước khi mở tab.
- Tự phục vụ chưa có đặt lịch/thanh toán; chưa gửi thông báo đẩy riêng.
- QR dùng `ma_cong_khai`; nếu giấy phép chưa có mã/tệp thì chỉ báo chưa sẵn sàng.
- Tải giấy phép phụ thuộc `file_url` và quyền của chủ hồ sơ.
- Gợi ý phân công dựa trên số việc đang xử lý, chưa có mô hình kỹ năng/chuyên môn.
- Nháp thông báo là văn bản hỗ trợ, không phải quyết định pháp lý; chưa tự gửi công dân.
- Gửi nhắc việc nội bộ cần việc đã có cán bộ xử lý.
- Axe mới chạy component-level trong happy-dom, tắt `color-contrast`; chưa phải audit
  trình duyệt thật/Playwright.
- Chưa có tour tự động; trợ giúp mở theo yêu cầu để không làm phiền.

## 16. Đối chiếu liên ngành (H-LINK)

- Tab **Liên ngành** trong chi tiết hồ sơ cho cán bộ, đăng ký qua `features/link`.
- Bốn nguồn mẫu: dân cư, đất đai, thuế, PCCC; kết quả hiển thị cạnh hồ sơ.
- `features/link/adapter.ts` sinh dữ liệu mẫu, che CCCD/điện thoại/mã số thuế và
  tạo UUID giả lập; không đọc/ghi `localStorage` hay `sessionStorage`.
- `api/mdm.ts` gọi `GET /api/v1/mdm/dossiers/{id}/links`; 404 thì hiện ghi chú
  “API liên kết MDM chưa sẵn sàng”, không chặn tra cứu.
- Cán bộ xác nhận đối chiếu; trạng thái chỉ nằm trong bộ nhớ phiên.
- Test: `tests/link-adapter.test.js`, `tests/external-lookup.test.js`,
  `tests/mdm-api.test.js`, `tests/e2e-ui/test_B_link_ui.py`.
