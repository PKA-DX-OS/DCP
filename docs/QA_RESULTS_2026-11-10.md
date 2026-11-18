<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Kết quả kiểm thử

Tên tệp theo mốc kế hoạch C15 (10/11/2026); mỗi lần chạy ghi rõ ngày chạy thật bên dưới.
Cách chạy từng bộ test xem [install.md](install.md#6-kiểm-thử-sau-cài-đặt).

## 1. Lần chạy 18/11/2026: kiểm tra tĩnh và test không cần stack

- **Mã:** nhánh `feat/duyanh`, các commit C11–C15 đặt trên `develop` f20196f (chưa đẩy lên GitHub tại thời điểm chạy).
  Phiên bản image trong `compose.yaml`: `1.1.0`.
- **Môi trường:** Linux 6.18 x86_64 (container phát triển, không có Docker), Python 3.13.17,
  pytest 9.2.0, pytest-asyncio 1.5.0, ruff 0.17.5, reuse 6.3.0, Node 22.23.4, npm 10.9.9,
  vitest 3.2.7, Playwright cho Python 1.65.2 (không tải được trình duyệt Chromium trong môi trường
  này).

| Bộ kiểm tra | Lệnh | Kết quả |
| :--- | :--- | :--- |
| Unit test | `pytest tests/unit -q` | 66 đạt |
| Thu thập toàn bộ test | `pytest tests --collect-only -q` | 220 test, không lỗi import |
| Tệp mẫu e2e-ui | `pytest tests/e2e-ui -q -k tep_mau` | 1 đạt (SHA-256 `f247e7c6…dab2`, giấy phép CC0-1.0) |
| Lint Python | `ruff check .` | không lỗi |
| Bản quyền | `reuse lint`, `python scripts/license_check.py` | tuân thủ REUSE 3.3, không có phần mềm cấm |
| Mã giả, mật khẩu mặc định | `python scripts/check_no_fakes.py` | đạt |
| Giao diện cap-phep-web | `npm test` (vitest) | 29 đạt (3 tệp) |
| Kiểu và build giao diện | `vue-tsc --noEmit`, `vite build` | đạt |
| Cú pháp `dx.sh` | `bash -n dx.sh`, `./dx.sh --help` | đạt |
| Liên kết tài liệu | kiểm liên kết tương đối và neo trong `docs/*.md`, `README.md` | không gãy |

Các test sau cần stack và **chưa chạy** trong lần này: `tests/integration`, `tests/e2e`
(6 kịch bản), `tests/e2e-ui/test_demo_flow.py::test_hanh_trinh_demo_tren_giao_dien`.

## 2. Lần chạy 18/11/2026 trên stack thật

- **Mã:** commit `bb1deed` (đỉnh nhánh `feat/duyanh`, 16 commit trên `develop` f20196f), kiểm ra
  vào `D:\DCP`; stack đang chạy (project `dxos`) được nâng cấp lên mã này, giữ nguyên dữ liệu và mật
  khẩu. Chạy bằng `kiem-C11-C15.ps1`, bắt đầu 23:18 (giờ Việt Nam).
- **Môi trường:** Windows 11 (NT 10.0.26300), Docker Desktop (client và server 29.4.2),
  Docker Compose v5.1.3, Python 3.14.5, Node v24.15.0, PowerShell 5.1.

| Bước | Lệnh | Kết quả |
| :--- | :--- | :--- |
| Trợ giúp, lệnh sai | `dx.ps1 --help`, `dx.ps1 backup --help`, `dx.ps1 <lệnh sai>` | mã 0, 0 và 2 như thiết kế |
| Khởi tạo, chạy | `dx init`, `dx up` | đạt |
| Chẩn đoán | `dx doctor` | 21 dịch vụ running hoặc healthy, `softhsm-init` thoát mã 0; cổng, chứng chỉ (còn 352 ngày), dung lượng, token Keycloak và PostgREST qua APISIX đều OK |
| Trôi cấu hình | `dx gitops` | không có lệch |
| Sao lưu | `dx backup` | 395 tệp trong manifest, mã hóa vào kho Restic |
| Phục hồi | `dx restore --list`, `dx restore --chi-kiem` | giải mã snapshot, mã băm mọi tệp khớp manifest |
| Shell | `bash dx.sh` | mã 0 |
| Giao diện | `npm test`, `npm run build` | 29 đạt (3 tệp), build đạt |
| Unit test | `pytest tests/unit` | 66 đạt |
| Đầu-cuối API | `pytest tests/e2e` | 6 đạt (29,7 giây) |
| Đầu-cuối giao diện | `pytest tests/e2e-ui` | 2 đạt (87,7 giây) |
| Tích hợp | `pytest tests/integration` | 145 đạt, 1 bỏ qua (11 phút 52 giây) |

Test bỏ qua: `test_R01_kms_restart.py` chỉ áp dụng khi `SIGNING_MODE=openbao`; stack demo ký PAdES
bằng SoftHSM nên OpenBao bị niêm phong không chặn việc ký.

Chưa chạy trên macOS và trên WSL. Các lỗi riêng của hai môi trường này (mục 3) được sửa theo đọc mã
và báo lỗi của người thử trên WSL, chưa có lần chạy xác nhận.

## 3. Lỗi tìm thấy và đã sửa trong đợt C11–C15

| Lỗi | Phát hiện | Sửa |
| :--- | :--- | :--- |
| Chuông thông báo không bao giờ tăng: server gửi sự kiện SSE có tên `notification`, giao diện chỉ nghe `onmessage` | đọc mã khi viết kịch bản UI | `useNotifications.ts` nghe `addEventListener("notification")`, thêm `tests/notifications.test.js` (fail với mã cũ, đạt với mã mới) |
| Biểu mẫu đối soát tệp trên `/kiem-tra/{mã}` bị trình duyệt chặn: route APISIX ghi đè CSP của `doc-sign` bằng `form-action 'none'` | đọc mã khi viết kịch bản UI | `core/apisix/apisix.template.yaml` dùng `form-action 'self'`; cài đặt đang chạy cần `dx init` rồi `dx restart apisix` |
| Script sao lưu và phục hồi có khóa S3 mặc định viết cứng khi thiếu biến môi trường | rà soát C11 | bỏ giá trị mặc định, thiếu biến thì dừng với thông báo |
| Liên kết `#trạng-thái` trong README không khớp tiêu đề | kiểm liên kết | đổi thành `#2-trạng-thái` |
| `make init`, `make up` trên WSL không dựng được stack: Makefile gọi thẳng `docker compose`, bỏ qua bước sinh `.env`, `secrets/` và chứng chỉ | người thử trên WSL | các đích của Makefile gọi `dx.sh` (`DX ?= bash ./dx.sh`) |
| `dx.sh init` lần đầu build image `tools` qua compose khi chưa có `.env` nên lỗi; `grep \s` không chạy trên macOS; Restic chỉ tải bản amd64 | đọc mã sau báo lỗi WSL | build bằng `docker build`, dùng `[[:space:]]`, Restic chọn theo `TARGETARCH` (amd64, arm64) có kiểm SHA-256 |
| Image `tools` không có lệnh `docker` (gói `docker.io` cài không kèm CLI) nên `dx gitops`, `dx backup` lỗi | chạy trên stack | chép `docker` và plugin compose từ image `docker:27.5.1-cli` |
| `tools python scripts/...` chạy thành `python3 python ...` | test Q01, S04 | thêm `tools/entrypoint.sh`: đường dẫn script thì chạy bằng `python3`, tên lệnh thì chạy nguyên lệnh |
| `export-warm` khởi động lại liên tục vì thiếu `--month` | `dx doctor` | thêm `--lap-giay`, compose chạy `--lap-giay 3600` |
| `dx gitops` báo lệch ở `softhsm-init` | chạy trên stack | `softhsm-init` nhận `SOFTHSM_TOKEN`, `SOFTHSM_PIN` qua `environment` thay vì cả tệp `.env` |
| Bảng điều hành `/dieu-hanh/` trắng trang: build với base `/` | mở bằng trình duyệt, test V3_08 | `vite` dùng `base: "/dieu-hanh/"`, `redirect_uri` lấy từ `BASE_URL` |
| `web_user` gọi được RPC `giay_to_con_thieu` | test V3_03 | thu hồi quyền của `PUBLIC`, `web_user`; chỉ cấp cho vai trò dịch vụ |
| Bàn làm việc hiện "Mã hồ sơ: —": Flowable REST không trả `businessKey` | kịch bản UI | đọc biến quy trình `ma_ho_so` |
| Test N04 chạy trước khi `ingest` sẵn sàng; Z05 gửi giá trị vượt ngưỡng ban đêm | test tích hợp | N04 chờ trạng thái health tối đa 60 giây; Z05 gửi 50 dBA |

## 4. Giới hạn còn lại

- Giao diện cán bộ chỉ có nút hoàn thành cho việc giao đích danh. Một cửa tiếp nhận, lãnh đạo phân
  công và phê duyệt (việc theo nhóm, cần biến quy trình) chưa có biểu mẫu; kịch bản UI gọi API cho
  ba bước này và ghi rõ trong mã test.
- NATS mở cổng MQTT TLS 8883 nhưng chưa có dịch vụ đọc số đo từ MQTT; số đo đi vào qua
  `POST /api/v1/ingest`.
- Lõi chưa đọc khóa `doc_templates` và đường dẫn `ingest_rules.rules_file` của `app.yaml`
  (xem [app-package.md](app-package.md)).
- Biến `DEMO_MFA` và `DEMO_TIME_SCALE` có trong `.env.example` và `dxos_core/config.py` nhưng chưa
  dịch vụ nào dùng.
- Trợ lý tìm theo từ khóa, chưa tìm kiếm ngữ nghĩa ([DECISIONS.md](DECISIONS.md), ADR-013).
