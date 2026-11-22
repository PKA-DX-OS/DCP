<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Nhật Ký Thay Đổi (Changelog)

Toàn bộ các thay đổi đáng chú ý của dự án **DX-OS Open-Core** được ghi lại tại tệp này.
Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/vi/1.0.0/), và dự án tuân thủ [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Chưa phát hành]

### Đã thêm (Added)
- **Kế hoạch D & H (D-P0-01):** `docs/data/ke-hoach-dh.md` bản chỉnh sau rà soát v1.1 và `OWNERSHIP.md` chia quyền sở hữu tệp giữa Track D và Track H.
- **Đo mốc D & H (D-P0-02):** `scripts/dh_baseline.py` đo thao tác thủ công, chuyển tay, làm lại, tự phục vụ và chất lượng dữ liệu hồ sơ (chỉ đọc, không in dữ liệu định danh).
- **Hợp đồng API D & H (D-P0-03):** `contracts/dh/` gồm 7 hợp đồng OpenAPI 3.1 (MDM và xem 360, tìm kiếm, chất lượng dữ liệu, danh mục, phả hệ, OCR, chỉ số hiệu quả) kèm mock và test kiểm mock khớp schema.
- **Danh mục dữ liệu (D-GOV-01, D-GOV-02, D-CAT-01):** `core.data_owners`, `core.data_assets`, `core.data_asset_columns`, `core.data_contracts` (migration lõi 20, 23); 9 miền có chủ quản, tài sản lõi và tài sản cấp phép có phân loại, thời hạn lưu trữ, cột cá nhân (`24-dh-danh-muc.sql`); API `/api/v1/catalog/*` theo `contracts/dh/catalog.yaml`, route APISIX `dh.yaml` cho các API Track D, lỗi `{code, message, details}`.
- **Dữ liệu chủ và xem 360 (D-MDM-01, D-MDM-02, D-MDM-04, D-360-01):** bảng `core.mdm_*`, `core.external_refs`, `core.dh_idempotency` (migration lõi 21, 24); CCCD chỉ lưu HMAC với khóa `secrets/mdm-hmac.key` (`scripts/dh_khoa.py`, `dx up` sinh nếu chưa có); khớp đúng chủ thể, thửa đất, công trình, giấy phép khi mở hồ sơ; API `/api/v1/mdm/*` (liên kết, 360, tìm thực thể, chi tiết, ứng viên trùng, tạo liên kết, gộp, hoàn tác) theo `contracts/dh/mdm.yaml`.
- **Tìm kiếm toàn cục (D-360-02):** `/api/v1/search` nhóm hồ sơ, chủ đầu tư, thửa đất, công trình, giấy phép; xếp hạng khớp đúng > đầu chuỗi > gần đúng; CCCD chỉ khớp đủ 12 số, điện thoại từ 9 số; kết quả theo RLS; audit chỉ ghi độ dài chuỗi tìm.
- **Chất lượng dữ liệu (D-DQ-01 đến D-DQ-04):** 22 rule trong `core/postgres/22-data-quality.sql` (web_user không đọc được câu SQL của rule); `scripts/data_quality_worker.py` chạy từng rule trong giao dịch chỉ đọc có giới hạn thời gian, ghi lần chạy, kết quả, vấn đề (mở lại khi lỗi lại, tự đóng khi hết lỗi), `dx up` chạy một lần; API `/api/v1/data-quality/*` (điểm theo miền, rule, lần chạy, vấn đề, giao, đóng/bỏ qua) theo `contracts/dh/data-quality.yaml`.
- **Phả hệ và chỉ số H (D-CAT-02, D-MART):** `/api/v1/lineage/{loại}/{id}` dựng đồ thị từ sự kiện có `facets.entity`, `/api/v1/lineage/jobs/{job}`; `/api/v1/automation/metrics?from=&to=` tính chỉ số H cùng định nghĩa `scripts/dh_baseline.py`, so với mốc trong `core.h_baseline` (`dh_baseline.py --save NHÃN`); thiếu dữ liệu trả null.
- **Kiểm thử và ghi chú Gate 1 Track D (D-TEST-01):** `tests/unit/test_dh_gate1.py` (hàm thuần, migration, rule, route phủ đủ hợp đồng trừ OCR, lỗi sai vai), `tests/integration/test_dh_gate1_api.py` (qua APISIX, che CCCD, cách ly phường); `docs/data/gate-1.md` ghi phần đã có và phần để Gate sau.
- **Gắn hồ sơ vào audit task (D-MET-00):** ghi `ho_so_id` và `process_instance_id` vào `detail` của `flow.task_completed`; `scripts/dh_baseline.py` tính thao tác task theo hồ sơ khi có trường này.
- **Ghi nhận phả hệ theo hồ sơ (D-CAT-02):** sự kiện lineage gắn `facets.entity` và `facets.tenant` khi nộp hồ sơ, kiểm tra quy hoạch, cấp giấy phép và nghiệm thu (`apps/cap-phep/db/migrations/25-lineage-nghiep-vu.sql`, `services/construction`); không ghi dữ liệu cá nhân vào facets.
- **Vai chủ quản dữ liệu (D-MDM-04):** thêm vai `dx:data-steward` vào realm qua `user_sync.py` (idempotent), gán vai cho tài khoản demo `mc.thu` để thực hiện quyền giao/đóng vấn đề chất lượng dữ liệu và quản trị dữ liệu chủ (#245).
- **Worker chất lượng dữ liệu định kỳ (D-DQ-02):** thêm chế độ lặp `--lap-giay N` cho `scripts/data_quality_worker.py` (lỗi một lượt chỉ ghi log, tiếp tục lượt sau); thêm dịch vụ nền `dq-worker` trong `compose.yaml` (profile core, restart unless-stopped, N=3600) (#246).
- **DSAR cho dữ liệu chủ (D-GOV-02):** bổ sung tài sản MDM vào danh mục dữ liệu, API xuất và xóa/ẩn danh dữ liệu MDM theo chính sách retention không lộ HMAC thô, có ghi audit (#162).
- **Khớp dữ liệu và backfill MDM (D-MDM-02):** `scripts/mdm_backfill.py` khớp chính xác dùng lại logic `dh_mdm.py`, khớp gần đúng tạo ứng viên trùng `core.mdm_link_candidate` dưới ngưỡng, hỗ trợ `--dry-run`, đạt 100% hồ sơ demo có chủ thể và thửa đất; thêm bước chạy tự động vào `dx.ps1` và `dx.sh`; `scripts/seed_mdm.py` nạp dữ liệu bịa (#164).
- **View 360 và golden view MDM (D-MDM-03):** tạo các view `core.v_dossier_360`, `core.v_permit_360`, `core.v_construction_360` (`core/postgres/26-mdm-360-views.sql`) với `security_invoker = true`, che CCCD và điện thoại, khớp schema `HoSo360`; router MDM đọc từ view 360; kiểm thử tích hợp cách ly phường (#165).
- **Dịch vụ OCR và hàng chờ duyệt (D-OCR):** backend `services/ocr` trích xuất 3 loại giấy tờ (CCCD, đất đai, đơn đề nghị) bằng Tesseract `vie`, hỗ trợ tính độ tin cậy từng trường; hàng chờ duyệt có cán bộ xác nhận hoặc từ chối; cờ `DH_OCR` (mặc định tắt trả 503); RLS cách ly theo phường; web_user chỉ đọc, ghi qua kết nối svc; không ghi PII vào log/audit và không trả trường fields ở danh sách (#247).

### Đã sửa (Fixed)
- **Lỗi kiểm tra đầu vào và lỗi nhỏ sau Gate 1 (FIX-V11-30):** Handler RequestValidationError ở construction và ocr trả lỗi 422 chuẩn hợp đồng `{code: "VALIDATION_ERROR", message, details: {fields: [...]}}`; giao vấn đề chất lượng dữ liệu nhận cả sub và username, trả 422 `DQ_ASSIGNEE_NOT_FOUND` khi không tìm thấy; `POST /api/v1/ocr/extract` ghi audit `ocr.requested` không ghi fields; xác nhận và từ chối OCR kiểm tồn tại theo phường trước khi kiểm thân yêu cầu, trả 404 `NOT_FOUND` khi bản ghi khác phường; API phả hệ chỉ số trả job `null` thay vì chuỗi rỗng (#258).
- **Khớp nhãn OCR không phân biệt dấu (FIX-V11-29):** parser trích xuất OCR chuẩn hóa NFC, so khớp nhãn trên bản bỏ dấu (NFD, đ->d) lấy giá trị từ văn bản gốc có dấu; nới mẫu nhận dạng các lỗi OCR phổ biến (6/o, 0/o, 1/l, mất dấu hai chấm); giảm độ tin cậy nhân 0.8 khi khớp mờ; nhận dạng tốt GCN QSDĐ và CCCD kể cả khi mất dấu (#257).
- **Cache web và theme (FIX-V11-01):** `index.html` không còn bị trình duyệt giữ bản cũ sau khi build lại; theme Keycloak đổi CSS có hiệu lực ngay; `dx up` nạp văn bản pháp lý cho trợ lý.
- **Hạn bước xử lý (FIX-V11-02):** việc trong hàng đợi có hạn suy ra từ SLA của bước khi quy trình không đặt `dueDate`, nên cảnh báo quá hạn và leo thang hoạt động.
- **Bảng điều hành (FIX-V11-03):** quản trị nền tảng chọn được phường để xem chỉ số và nhật ký; nhật ký kiểm toán hiện mới nhất trước kèm tên người thực hiện; tỷ lệ đúng hạn hiện "—" khi chưa có giấy phép.
- **Nhật ký hồ sơ và DSAR (FIX-V11-04):** nhãn tiếng Việt cho mã hành động, vai nghiệp vụ thay vai kỹ thuật, tên người yêu cầu thay UUID (view `v_ten_nguoi_dung`), đánh dấu quá hạn xác nhận.
- **Bàn làm việc (FIX-V11-05):** nhãn lọc đi cùng ô chọn, lịch sử dùng nhãn tiếng Việt, che số CCCD; trang không quyền có nút đăng xuất và lối sang bảng điều hành; chuông hiện 99+.
- **Trợ lý pháp lý (FIX-V11-06):** câu trả lời trích xuất ghép tối đa 3 câu trọn vẹn, bỏ ký hiệu markdown; nguồn hiện "Nghị định 217, Điều 54".
- **Thời hạn giải quyết (FIX-V11-07):** hồ sơ mới có hạn 7 ngày làm việc theo Điều 54 NĐ 217/2026 thay vì 15; SLA từng bước, form nộp và thanh tiến độ khớp con số này (`app_cap_phep.so_ngay_giai_quyet()`).
- **404 cho API (FIX-V11-09):** đường dẫn `/api/` không có route trả 404 JSON (`ma_loi` `NOT_FOUND`) thay vì trang HTML của web cấp phép.
- **Hàng đợi hậu kiểm và hồ sơ hero (FIX-V11-08):** phiếu kiểm tra (lập tay hoặc từ cảm biến) có việc trong Bàn làm việc của trật tự xây dựng, kết luận Đạt/Vi phạm được ghi vào phiếu; `seed_hero.py` đưa `CP-HERO-2026-001` tới bước thẩm định giao `td.binh`.
- **Hồ sơ hero và kết luận hậu kiểm (FIX-V11-10):** `seed_hero.py` tạo phân công thẩm định cho `td.binh` nên chi tiết hồ sơ mở được; kết luận phiếu dùng lại `sync_flow_state` (ghi "Đạt tiêu chuẩn", người kiểm tra, ghi chú).
- **Nghiệm thu móng (FIX-V11-11):** bấm "Không đạt" sinh việc khắc phục móng thay vì sang nghiệm thu kết cấu.
- **Trật tự xây dựng mở hồ sơ (FIX-V11-12):** cán bộ trật tự xây dựng mở được hồ sơ cùng phường đã cấp phép khi nghiệm thu; hồ sơ chưa cấp phép vẫn bị từ chối.
- **Trợ lý pháp lý (FIX-V11-13):** hỏi giấy tờ thì trả lời đúng danh mục giấy tờ; câu hỏi không có căn cứ trong kho trả lời không tìm thấy thay vì đoạn lạc đề.
- **Kịch bản demo (FIX-V11-14):** nhãn và thứ tự bước khớp giao diện (Bàn làm việc, Mở hồ sơ đầy đủ, tab bảng điều hành); ghi chú giấy phép ghi quy mô theo hồ sơ nộp.
- **Mục Nghiệm thu của trật tự xây dựng (FIX-V11-15):** chính sách RLS hồ sơ cho cán bộ trật tự xây dựng khớp với `mo_ho_so` (chỉ hồ sơ đã cấp phép), nên mục Nghiệm thu tải được.
- **Mốc nghiệm thu từ Bàn làm việc (FIX-V11-16):** bấm Đạt/Không đạt ở thanh thao tác ghi mốc nghiệm thu (từng lần) trước khi chuyển bước, nên mục Nghiệm thu hiện đúng lịch sử.
- **Nghiệm thu bởi trật tự xây dựng (FIX-V11-17):** cán bộ trật tự xây dựng ghi được mốc nghiệm thu, biên bản và bản vẽ hoàn công (API `services/construction` và chính sách RLS ghi), khớp nhóm được BPMN giao việc nghiệm thu; quyền kiểm tra quy hoạch và pháp lý giữ nguyên.
- **Cảnh báo hồ sơ cho trật tự xây dựng (FIX-V11-18):** cán bộ trật tự xây dựng xem được cảnh báo của hồ sơ đã cấp phép (hàm `danh_sach_canh_bao_ho_so`, migration 20); DB từ chối quyền (SQLSTATE 42501) trả 403 thay vì 503 "Cơ sở dữ liệu tạm thời không sẵn sàng".
- **Trang tra cứu công khai (FIX-V11-19):** `/kiem-tra/{mã}` hiện tên loại văn bản (theo `doc_templates` của ứng dụng) và tên đơn vị ban hành (`core.tenants`) thay vì mã; JSON thêm `ten_loai_van_ban`, `ten_don_vi`, giữ nguyên trường mã.
- **Chỉ số thời gian xử lý (FIX-V11-20):** `thoi_gian_xu_ly_tb` tính số ngày làm việc từ nộp đến ngày cấp giấy phép (hàm `so_ngay_lam_viec`, migration 21), trả null khi chưa có giấy phép; `ty_le_dung_han` so ngày cấp với hạn; `/api/v1/metrics?thang=YYYY-MM` lọc các chỉ số khai báo đầu/cuối kỳ.
- **Ngưỡng liên quan của trợ lý (FIX-V11-21):** câu hỏi có âm tiết nội dung không xuất hiện trong kho tri thức (ví dụ "kết hôn", "căn cước", "mật độ") trả "không tìm thấy căn cứ" thay vì ghép đoạn trùng cụm chung như "giấy tờ", "thời hạn".
- **Hạn hậu kiểm (FIX-V11-22):** phiếu kiểm tra có cột `han_xu_ly_at` (2 ngày từ lúc lập, tự điền khi lập phiếu, điền lại cho phiếu cũ; migration 22); việc kiểm tra hiện trường (P2D) và khắc phục vi phạm (P7D) có SLA nên hiện hạn trong hàng đợi.
- **Quy mô trên giấy phép (FIX-V11-23):** văn bản ký và bảng `giay_phep` (cột mới `so_tang`, `dien_tich_san_m2`, `nguon_quy_mo`) dùng quy mô của lần kiểm tra quy hoạch đạt gần nhất, chưa có thì quy mô hồ sơ (migration 23); giấy phép cũ ghi theo quy mô hồ sơ.
- **Tỷ lệ đúng hạn theo ngày cấp (FIX-V11-25):** `/api/v1/metrics/on-time` tính tỷ lệ cấp phép đúng hạn theo ngày cấp của giấy phép (`giay_phep.ngay_cap <= ho_so.han_tong_at`) và nhóm theo tháng của ngày cấp (giờ Việt Nam), khớp định nghĩa với thẻ chỉ số điều hành thay vì dùng `ho_so.updated_at`.
- **Bảng điều hành lọc chỉ số theo tháng (FIX-V11-24):** thẻ chỉ số điều hành gọi `/api/v1/metrics?thang=YYYY-MM` theo ô Tháng; tháng không có dữ liệu trả 0 hoặc `—`; thẻ có `theo_ky: false` mang nhãn “(toàn kỳ)” để không hiểu nhầm là số của tháng đang chọn.
- **Cấu hình OCR và baseline H (D-OCR/D-MART):** service `ocr` nhận `DEMO_MODE` để token `dx-test` hợp lệ; lưu mốc H v1.1 cho `phuong-a`/`phuong-b` và cập nhật `docs/data/baseline-v1.1.md`, dashboard Hiệu quả vận hành có mốc so sánh.
- **Dashboard chất lượng dữ liệu (D-DQ-04):** tab “Chất lượng dữ liệu” hiển thị điểm tổng và theo miền, rule nghiêm trọng đang lỗi, vấn đề dữ liệu; quản trị dữ liệu đóng/bỏ qua và backend ghi audit.
- **Dashboard danh mục dữ liệu (D-CAT-01):** tab “Danh mục dữ liệu” cho kiểm toán viên/quản trị, hiển thị tài sản, chủ quản, phân loại, thời hạn lưu trữ, độ tươi, điểm DQ; chọn tài sản xem cột và hợp đồng dữ liệu (chỉ đọc, không hiển thị PII).
- **Nút đổi nền bảng điều hành (FIX-V11-26):** nút đổi giao diện ở màn hình chưa đăng nhập của Bảng điều hành dùng icon đồng bộ với thanh điều hướng thay vì hiển thị chữ.
- **Đổi nền theo giao diện thực tế (FIX-V11-27):** nút đổi nền bảng điều hành chọn icon và hành vi chuyển theo nền đang hiển thị (xử lý chế độ theo hệ thống); nút màn đăng nhập có `z-10` tránh bị khung giới thiệu che khi màn hình hẹp.
- **Phả hệ chỉ số điều hành (FIX-V11-28):** `/api/v1/metrics/{code}/lineage` lọc sự kiện theo bảng nguồn của chỉ số và phường người gọi thay vì job mặc định; bỏ `lineage_job: export_warm_lakehouse` khỏi các chỉ số không đọc lakehouse; `services/export-warm` ghi lineage cho mỗi đợt xuất Parquet.

---

## [1.1] - 2026-11-20

### Đã thêm (Added)
- **Construction Core (Track A):** kiểm tra quy hoạch theo thửa đất và vùng quy hoạch (tầng cao, chiều cao, mật độ, hệ số sử dụng đất, khoảng lùi), quy trình nghiệm thu móng/kết cấu, phần pháp lý của hồ sơ (thẩm quyền, phí và biên lai, lưu trữ, chia sẻ dữ liệu), thư viện văn bản pháp lý.
- **Thẩm định thiết kế (B-REVIEW-01..08):** phiên bản hồ sơ thiết kế, bản vẽ theo bộ môn, ý kiến thẩm định và giao diện đối chiếu.
- **Bàn làm việc ba cột** cho cán bộ (hàng đợi việc, chi tiết hồ sơ, thao tác xử lý); nộp hồ sơ từng bước trên điện thoại; bản đồ Leaflet.
- **Quản trị địa bàn (B-PLAT-01):** quản lý phường và người dùng theo địa bàn trong bảng điều hành; xử lý yêu cầu dữ liệu cá nhân (DSAR) cho người duyệt.
- **Bảng điều hành:** đủ 11 chỉ số (thêm không đạt quy hoạch, đang nghiệm thu, tỷ lệ cấp phép đúng hạn), xuất Excel/PDF, hỏi đáp quy định, nhật ký kiểm toán.
- **Design system kính** dùng chung, feature registry, app contract 5.2; theme Keycloak DX-OS có nhãn tiếng Việt.
- **Kiểm thử:** Vitest cho component và composable (hai ứng dụng web), Playwright theo 7 vai, hồi quy hình ảnh 9 màn, axe-core và phép thử khói trên Chromium/Firefox/WebKit, đo hiệu năng; kết quả ở `docs/QA_RESULTS_2026-11-20.md`.
- **Tài liệu demo (B-DEMO-01..06):** kịch bản 9 cảnh, sơ đồ kiến trúc một trang, chỉ số tác động (`scripts/impact_metrics.py`), hướng dẫn demo, slide, phụ đề video; dữ liệu hồ sơ hero (`scripts/seed_hero.py`).

### Đã thay đổi (Changed)
- Giao diện Cấp phép, Bảng điều hành và trang tra cứu chuyển sang phong cách kính (Glassmorphism), có giao diện tối và sáng; icon nét thay emoji; khung tải thay dòng chữ "Đang tải".
- Bảng điều hành chỉ mở cho lãnh đạo, quản trị và kiểm toán viên; trợ lý chỉ trả lời khi tìm thấy đoạn tài liệu liên quan.
- Bàn làm việc không tự mở hồ sơ khi vào trang (mỗi lần mở được ghi nhật ký truy cập).
- Phần pháp lý lọc biên lai, lưu trữ, nhật ký chia sẻ theo hồ sơ ở máy chủ (`?ho_so_id=`); các lần lấy danh sách việc trùng nhau khi mở hồ sơ được gộp làm một.
- `dx up` ghép lại route APISIX từ `core/apisix/routes/` và đồng bộ theme/ngôn ngữ của realm Keycloak đang chạy.

### Bảo mật (Security)
- **U-01:** bỏ tải bản gốc công khai `/kiem-tra/{mã}/download`; bản gốc tải qua `GET /api/v1/docs/{id}/download` (bắt buộc JWT, kiểm quyền theo hồ sơ hoặc người đã ký, có audit). Mã tra cứu dài 128 bit (`DOC-` + 22 ký tự).
- **U-02:** trang `/kiem-tra` escape mọi giá trị, CSP không cho chạy script; biểu mẫu đối soát PDF gửi thẳng về máy chủ, tệp tối đa 25 MB.
- **U-03:** dịch vụ `files` tự quyết định MIME theo phần mở rộng, chỉ PDF/PNG/JPEG mở inline, còn lại tải về kèm `nosniff`.
- **U-04..U-07:** mô phỏng cảm biến kiểm địa bàn và quyền, người ký lấy từ `signer_sub`, bổ sung hồ sơ chỉ khi có nhiệm vụ chờ bổ sung, nhật ký hồ sơ không lộ người xem cho công dân.

### Đã sửa (Fixed)
- Route APISIX planning/acceptance/exports thiếu trên máy đã `dx init` trước (cảnh báo hồ sơ, quy hoạch, nghiệm thu trả 404).
- Trang đăng nhập Keycloak: khung gọn giữa màn hình, tiêu đề đọc được; realm dựng trước nhận theme DX-OS.
- Khả năng tiếp cận: vùng cuộn nhận focus bàn phím, tương phản trang tra cứu, nhãn thanh tiến độ và ô chọn tệp, cấp tiêu đề liền mạch; ô chọn tệp có chữ tiếng Việt.

## [1.0] - 2026-11-19

### Đã thêm (Added)
- **PAdES/SoftHSM:** `softhsm-init` tạo token, test CA và leaf cert; `doc-sign` ký PAdES qua `pyHanko` + `python-pkcs11`, mặc định `SIGNING_MODE=pkcs11`.
- **Dashboard [D] thật:** gọi `/api/v1/metrics` và `/api/v1/metrics/{code}/lineage` bằng JWT; bỏ toàn bộ số liệu hardcoded.
- **Trợ lý [I] thật:** gọi `/api/v1/assistant/ask`, hiển thị citation; bỏ câu trả lời canned.
- **SBOM:** `scripts/sbom.py` + `sbom/dxos-1.0.cdx.json` (CycloneDX 1.5).
- **CLI:** thêm `e2e`, `e2e-ui`, `test-qa`, `check-no-fakes`, `sbom` cho `dx.ps1`/`dx.sh` và Makefile.
- **One-shot:** `run.ps1` + `run.cmd` tự kiểm tra Docker, dừng stack cũ, init `.env`/secrets, bật DEMO_MODE, chạy `up → app-install → seed → doctor`, chờ dịch vụ healthy, kiểm tra gateway HTTP và mở trình duyệt. Có `-Reset` và `-NoBrowser`.
- **P1 Manifest giấy tờ:** `document_manifest` trong `app.yaml` + bảng `app_cap_phep.document_requirements`; checklist động trên UI; RPC `nop_ho_so` kiểm tra 7 lớp và trả **422** kèm `{field, loai_giay, reason, action}`.
- **Review từng tệp + versioning:** `ho_so_tep` thêm `sha256/size/mime/nguoi_tai/trang_thai_kiem_tra/ly_do/ngay_cap/ngay_het_han/version/tep_goc_id/thong_tin`; RPC `danh_gia_tep` cho cán bộ đánh giá đạt/không đạt kèm lý do; UI Bàn làm việc có nút Đạt/Không đạt; Chi tiết hồ sơ hiển thị trạng thái từng giấy.
- **Đủ 8 chỉ số dashboard:** thêm `ho_so_dang_xu_ly`, `thoi_gian_xu_ly_tb`, `phieu_kiem_tra`, `vi_pham`; dashboard render động theo API thay vì 5 thẻ hardcoded.

### Đã sửa (Fixed)
- `metrics-api`: parse `jsonb` từ asyncpg trước khi dùng `.get()`.
- `doc-sign`: sửa trang công khai bỏ CDN Tailwind, dùng CSS nội bộ; thêm form đối soát PDF và hiển thị PAdES.
- `tests/e2e`: dùng token cảm biến `dxos-sensor-phuong-a` thay vì token cán bộ; thêm kiểm tra tải PDF + tamper.
- `tests/e2e-ui`: chấp nhận PAdES thay vì chỉ Ed25519.
- `dx.ps1 init`: fallback `py -3.12` hoặc tools container khi host Python thiếu `cryptography`.
- `dx.sh reset`: dùng image tools `1.0` và gọi đúng `python scripts/init.py`.
- `sensor-spike`/`demo-sensor`: dùng cổng APISIX `8080` thay vì `9080`.
- `gitops`: chạy reconciler trên host để có Docker CLI; `init` đồng bộ `COMPOSE_FILE_SHA256` để không báo drift giả.
- REUSE: bổ sung annotation cho `secrets/`, cache, `node_modules`, `tests/`; thêm `LICENSES/ISC.txt`.
- UI: thống nhất banner, header indigo, font, card, footer và link chéo giữa C3 ↔ Bảng điều hành.
- UI: xử lý 401 bằng cách xóa phiên OIDC, hiển thị thông báo đăng nhập lại thay vì raw HTML APISIX.
- `nop_ho_so`: bắt buộc đủ giấy theo manifest, kiểm tra hạn/đối chiếu chéo/trùng SHA-256; không còn tạo hồ sơ rỗng.
- `dinh_kem_tep`: validate loại giấy theo manifest, chống trùng SHA-256, tự tăng version khi bổ sung.
- `files`: cho phép tải trước vào `draft.ho_so` để nộp hồ sơ một bước; vẫn kiểm tra chủ sở hữu khi tạo hồ sơ.
- `scan_exposure`: whitelist `document_requirements` (danh mục công khai, không chứa PII).

---

## [0.9.0]

### Security

Các lỗ hổng an toàn thông tin và điểm yếu phân quyền được rà soát, vá triệt để ở phiên bản v0.9.0:
- **`sync_flow_state` (Kiểm soát đồng bộ trạng thái quy trình):** Loại bỏ việc cho phép người dùng web hoặc cán bộ tự gọi RPC sửa trực tiếp trạng thái hồ sơ qua REST API; chỉ dịch vụ backend `flow` (vai trò hệ thống `dx:service`) mới có quyền đồng bộ trạng thái BPMN vào cơ sở dữ liệu dựa trên sự kiện BPMN chính thức từ Flowable engine.
- **`dsar` (Bảo vệ tính toàn vẹn yêu cầu dữ liệu cá nhân):** Chặn đứng nguy cơ sửa đổi, giả mạo các trường định danh chủ thể (`subject_sub`, `tenant`); áp dụng triệt để chính sách `rls_dsar_requests_tenant` và tự động tính toán thời hạn tiếp nhận (2 ngày làm việc), giải quyết (7 ngày làm việc) dựa trên hàm lịch hành chính `core.add_business_days`.
- **`dinh_kem_tep` (Cách ly tệp đính kèm hồ sơ):** Hàm RPC `dinh_kem_tep` bổ sung kiểm tra nghiêm ngặt: tệp đính kèm bắt buộc phải thuộc sở hữu của người gọi (`v_file.owner_sub = cur_sub`), cùng đơn vị (tenant), và hồ sơ phải ở trạng thái cho phép nộp bổ sung (`DA_NOP`, `CAN_BO_SUNG`), ngăn chặn hoàn toàn việc chèn tệp trái phép vào hồ sơ của công dân hoặc phường khác.
- **`Bí mật dùng chung (Shared Secrets)`:** Loại bỏ triệt để toàn bộ khóa bí mật đối xứng HS256 dùng chung (`test_e2e_secret_key_2026`) vốn tạo ra lỗ hổng tự ký token; chuyển dịch toàn bộ hệ thống sang xác thực bất đối xứng qua tập khóa công khai JWKS RS256 trích xuất trực tiếp từ Keycloak 26.
- **`Superuser & Nguyên tắc đặc quyền tối thiểu (Least Privilege)`:** Thu hồi quyền siêu người dùng `postgres` khỏi toàn bộ các microservices và ứng dụng; chuyển sang tài khoản dịch vụ chuyên dụng `dxos_svc` có phân quyền chặt chẽ; thiết lập `FORCE ROW LEVEL SECURITY` trên toàn bộ các bảng trong lược đồ `core` và `app_cap_phep`.

### Đã sửa & Nâng cấp (Changed / Fixed)
- **Kiến trúc Fail-Closed & Loại bỏ toàn bộ Mock/Fallback (F-11 đến F-22):**
  - Xóa bỏ triệt để toàn bộ mã giả định, mock connection (`MockConnection`), bộ nhớ RAM tạm thời (`_memory_store`, `_SIGNED_DOCS_STORE`), khóa bí mật nội bộ (`_LOCAL_PRIVATE_KEY`) và các khối nuốt lỗi `except Exception: pass` trong toàn bộ mã nguồn `services/`, `scripts/`, `ops/`, `tools/` và `apps/`.
  - Áp dụng nghiêm ngặt nguyên tắc Fail-Closed: khi bất kỳ dịch vụ phụ thuộc nào (PostgreSQL, SeaweedFS S3, ClamAV, OpenBao KMS, Flowable BPMN, Keycloak SSO, NATS) gặp sự cố hoặc chưa sẵn sàng, hệ thống trả về mã lỗi HTTP 503 Service Unavailable kèm thông báo tiếng Việt có dấu và mã nhật ký lỗi chi tiết.
- **Bảo mật Định danh & Xác thực Token Thực tế (F-03, F-04, F-11, F-12, F-38, F-39):**
  - Chuyển đổi PostgREST sang xác thực bằng tập khóa công khai JWKS RS256 thực tế trích xuất từ Keycloak (`@/etc/postgrest/jwks.json`), trả HTTP 401 khi không có JWT.
  - Cổng biên mạng Apache APISIX cấu hình chính xác `client_secret` OIDC, kích hoạt bộ tiêu đề bảo mật CSP, chặn đứng hoàn toàn việc truy cập giao diện quản trị `/auth/admin` và Realm quản trị `/auth/realms/master`.
  - Thẩm định token JWT nghiêm ngặt qua khóa công khai Keycloak thật: kiểm tra chữ ký số, thời điểm hiệu lực `nbf`, thời hạn hết hạn `exp`, định danh tổ chức cấp phát `iss` và danh sách ủy thác `azp`. Client thử nghiệm `dx-test` chỉ được kích hoạt khi biến môi trường `DEMO_MODE=true`.
- **Quản lý Khóa KMS & Ký số Transit Độc lập (F-05, F-15, F-30, F-31):**
  - Triển khai OpenBao chạy chế độ máy chủ lưu trữ trên Docker volume bền vững, khởi tạo với cơ chế phân tán khóa Shamir 5/3, lưu trữ unseal keys an toàn và hỗ trợ tự động mở khóa (unseal).
  - Dịch vụ `doc-sign` ký số tài liệu và giấy phép bằng khóa mật mã học Ed25519 thông qua OpenBao Transit Secrets Engine, lưu phiên bản khóa `key_version` và cung cấp điểm cuối kiểm tra tính toàn vẹn công khai `/kiem-tra/{public_code}`.
- **Kiểm soát Tách biệt Nghĩa vụ SoD & Quy trình BPMN Đa thuê ước (F-19, F-32, F-33, F-44, F-45, F-46):**
  - Đọc trực tiếp biến tiến trình `nguoiThamDinh` từ cơ sở dữ liệu Flowable để kiểm soát nghiêm ngặt nguyên tắc tách biệt nghĩa vụ SoD (`dx:sodExclude`), ngăn chặn triệt để trường hợp thẩm định viên tự phê duyệt hồ sơ của mình.
  - BPMN 2.0 triển khai cổng rẽ nhánh Exclusive Gateway phân loại hồ sơ thẩm định nhanh hoặc thẩm định chuyên sâu dựa trên diện tích sàn và khu vực kiến trúc, hỗ trợ đa thuê ước với `tenantId`.
  - Dịch vụ `flow` tự động đồng bộ trạng thái hồ sơ hai chiều giữa tiến trình Flowable BPMN và cơ sở dữ liệu `app_cap_phep.ho_so`.
- **Phân quyền Cơ sở Dữ liệu & Cách ly Dữ liệu RLS Đa tầng (F-23 đến F-28):**
  - Đổi vai trò kết nối cơ sở dữ liệu mặc định của dịch vụ từ `postgres` sang tài khoản dịch vụ `dxos_svc` tuân thủ nguyên tắc đặc quyền tối thiểu.
  - Phân tách chính sách RLS riêng biệt cho INSERT và UPDATE trên bảng hồ sơ; kích hoạt Trigger `trg_ho_so_protect` và RLS chặn đứng người dùng web tự ý chuyển trạng thái sang `DA_CAP`.
  - Thiết lập chính sách bảo vệ mức dòng bắt buộc (FORCE ROW LEVEL SECURITY) trên toàn bộ các bảng trong lược đồ `core` (bao gồm `core.outbox`).
- **Kiểm soát Tệp tin & Quét Mã độc ClamAV Thực tế (F-16, F-17, F-34):**
  - Quét mã độc trực tiếp bằng ClamAV qua giao thức INSTREAM; tệp chứa mã độc (như chuỗi kiểm tra EICAR) bị cô lập ngay vào thư mục cách ly `staging/quarantine/`, ghi nhận sự kiện kiểm toán và trả về HTTP 422 Unprocessable Entity.
  - Thao tác lưu trữ metadata tệp `core.files`, ghi nhật ký kiểm toán `core.audit_log` và lưu sự kiện outbox `core.outbox` được hợp nhất trong một giao dịch cơ sở dữ liệu nguyên tử duy nhất (Atomicity).
- **Phân quyền Cảm biến IoT NATS Subject ACL (F-37):**
  - Thiết lập danh sách kiểm soát truy cập (Subject ACL) nghiêm ngặt cho từng thiết bị cảm biến môi trường (`dxos.<tenant>.site.<device_id>.>`), ngăn chặn trạm đo giả mạo hoặc ghi đè dữ liệu của trạm khác.
- **Giao diện Web Tự hành & Độc lập Ngoại mạng (F-49 đến F-52):**
  - Đóng gói toàn bộ thư viện giao diện Vue 3 và Tailwind CSS vào thư mục nội bộ `vendor/`, sử dụng phông chữ hệ thống. Hệ thống vận hành hoàn toàn độc lập, không gửi bất kỳ truy vấn nào ra Internet.
  - Bổ sung thanh biểu ngữ cảnh báo nổi bật bắt buộc "Bản mô phỏng phục vụ cuộc thi" trên tất cả giao diện ứng dụng; đồng bộ nhận diện phiên bản lên `v0.9.0`.
- **Vận hành Không Phụ thuộc Máy chủ Host (F-06, F-21, F-22, F-47, F-48):**
  - Cung cấp container công cụ quản trị `dxos/tools:0.9.0` tích hợp toàn bộ các tiện ích; cung cấp script tiện ích `.\dx.ps1` (PowerShell) và `./dx.sh` (Bash). Máy chủ chỉ yêu cầu cài đặt Docker Engine.
  - Tích hợp quy trình sao lưu và phục hồi thảm họa thực tế (PostgreSQL pg_dumpall và SeaweedFS S3 sync), đo lường RTO thực tế < 2 giây.
  - Công cụ GitOps `reconciler` xác minh chữ ký container bằng Cosign thật (mã thoát 2 khi sai chữ ký) và tự động khắc phục sai lệch cấu hình đang chạy.
- **Hệ thống Kiểm thử Tự động & Nghiệm thu Thực tế (F-53 đến F-56):**
  - 15/15 bài kiểm thử đơn vị `tests/unit/` đạt 100%.
  - 13/13 kịch bản kiểm thử tích hợp liên dịch vụ E2E `tests/e2e/test_e2e_scenarios.py` thực thi qua Gateway APISIX đạt 100%.
  - 13/13 ca kiểm tra chức năng và an toàn thông tin độc lập `tests/qa/` đạt 100%.
  - Bộ kiểm tra 0 mã giả `scripts/check_no_fakes.py` đạt chuẩn 100%.

---

## [0.8.0] - 2026-11-04

### Đã thêm (Added)
- **Tầng 1 - Nền tảng Dịch vụ Lõi số (Headless PaaS):**
  - Cổng biên mạng Apache APISIX (chế độ Standalone) với xác thực JWT OIDC, giới hạn tốc độ truy cập, tiêu đề bảo mật CSP và tích hợp Prometheus.
  - Hệ thống Quản lý Định danh & Phân quyền Keycloak 26.x hỗ trợ OIDC PKCE, đa thuê ước (`tenant` claim), vai trò phẳng và cấu hình MFA TOTP.
  - Cơ sở dữ liệu PostgreSQL 16 tích hợp tiện ích mở rộng pgvector, hỗ trợ Row-Level Security (RLS) đa tầng và hàm tính ngày làm việc `core.add_business_days`.
  - Cơ chế Kiểm toán chuỗi băm bất biến (`audit_log`) với liên kết băm SHA-256 (`prev_hash || canonical_json(row)`), ngăn chặn sửa đổi trái phép bằng khóa giao dịch `pg_advisory_xact_lock`.
  - Dịch vụ mỏng `files` kiểm soát tải tệp, quét mã độc trực tiếp bằng ClamAV qua INSTREAM, tự động cách ly tệp độc hại và sinh URL truy cập có chữ ký thời hạn.
  - Dịch vụ mỏng `doc-sign` kết xuất tài liệu PDF động có gắn mã QR công khai và ký số mật mã học Ed25519 bằng OpenBao Transit.
  - Dịch vụ mỏng `flow` đóng vai trò Façade bảo mật phía trước Flowable BPMN, kiểm soát phân tách nhiệm vụ `dx:sodExclude` và phát sự kiện thông báo SSE thời gian thực.
  - Dịch vụ mỏng `ingest` thu thập dữ liệu cảm biến IoT qua NATS MQTT, đánh giá ngưỡng theo khung giờ và tự động kích hoạt quy trình hậu kiểm.
  - Dịch vụ mỏng `ngsi-ld` cung cấp giao diện truy vấn thực thể đô thị theo chuẩn NGSI-LD.
  - Dịch vụ mỏng `outbox-relay` truyền dẫn sự kiện nghiệp vụ từ bảng `core.outbox` sang NATS JetStream theo mẫu Transactional Outbox.
  - Dịch vụ mỏng `audit` cung cấp API xác minh chuỗi băm `/api/v1/audit/verify` và niêm phong định kỳ mỏ neo băm vào bucket WORM trên SeaweedFS.
  - Dịch vụ mỏng `export-warm` và `metrics-api` xử lý dữ liệu hồ sơ đã đóng sang định dạng Parquet trên Data Lake và truy vấn số liệu phân tích kèm phả hệ OpenLineage.
  - Dịch vụ `assistant` hỗ trợ hỏi đáp quy chuẩn bằng kỹ thuật RAG trên kho tài liệu tri thức với mô hình nhẹ chạy CPU.
- **Tầng 2 - Không gian Năng lực số:**
  - Ứng dụng Cấp phép Xây dựng `apps/cap-phep` (Không gian [H] cho Chủ đầu tư và [P] cho Cán bộ Một cửa, Thẩm định viên, Lãnh đạo và Trật tự xây dựng).
  - Ứng dụng Bảng Điều hành `apps/bang-dieu-hanh` (Không gian [D] hiển thị 5 chỉ số điều hành & phả hệ dữ liệu; Không gian [I] trợ lý tra cứu chính sách).
  - Trang kiểm tra giấy phép công khai tại đường dẫn `/kiem-tra/{public_code}` cho phép tra cứu trạng thái và tải tệp PDF lên để so sánh tính toàn vẹn chữ ký.
- **Vận hành & Tự động hóa GitOps:**
  - Công cụ `reconciler` tự động so khớp cấu hình đang chạy với thẻ Git release đã ký bằng `cosign`.
  - Bộ công cụ giả lập cảm biến `tools/sensor-sim` phát dữ liệu đo tiếng ồn và bụi mịn qua MQTT với chế độ tạo đột biến tiếng ồn (`sensor-spike`).
  - Hợp đồng gói ứng dụng `app.yaml` cùng bộ script cài đặt/gỡ bỏ gói ứng dụng (`make app-install`, `make app-uninstall`).
  - Bộ kiểm thử tự động toàn diện: Unit tests, End-to-End tests (13 kịch bản), Smoke test và kiểm tra bản quyền REUSE.
