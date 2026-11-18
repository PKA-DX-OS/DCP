<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Quyết định kiến trúc

Mỗi mục ghi bối cảnh, lựa chọn, lý do và hệ quả. Chỉ ghi quyết định đã có trong mã ở nhánh này;
mục nào còn giới hạn thì ghi rõ ở phần hệ quả. Sơ đồ và luồng dữ liệu xem
[architecture.md](architecture.md).

## ADR-001: APISIX chạy standalone, cấu hình bằng tệp YAML

- **Bối cảnh:** APISIX có thể lưu cấu hình trong etcd hoặc đọc từ tệp.
- **Lựa chọn:** `core/apisix/config.yaml` đặt `role: data_plane`, `config_provider: yaml`. Route nằm
  ở `core/apisix/apisix.template.yaml` (trong Git); `scripts/init.py` kết xuất ra
  `core/apisix/apisix.yaml` (không đưa vào Git), thay `connect-src` của CSP theo `PUBLIC_BASE_URL`
  và `KEYCLOAK_PUBLIC_URL`.
- **Lý do:** Không cần thêm etcd; route, plugin và CSP được quản lý như mã và được reconciler đối
  soát.
- **Hệ quả:** Đổi route thì sửa template rồi chạy lại `dx init` và khởi động lại `apisix`. Tệp phải
  kết thúc bằng dòng `#END`.

## ADR-002: Flowable REST độc lập, người dùng chỉ đi qua façade `flow`

- **Bối cảnh:** Cần động cơ BPMN chuẩn mở, nhưng không để người dùng gọi thẳng API quản trị.
- **Lựa chọn:** Image `flowable/flowable-rest:7.1.0`, CSDL riêng `flowable` trên cùng PostgreSQL,
  cổng chỉ bind `127.0.0.1:8082`. Giao diện và app gọi `/api/v1/flow/*` của dịch vụ `flow`.
- **Lý do:** `flow` là nơi kiểm tenant, người được giao hoặc nhóm ứng viên, biến được phép và SoD
  theo chính sách của app; Flowable không biết gì về JWT.
- **Hệ quả:** Mọi quy tắc phân quyền quy trình nằm trong `flow_policies` của `app.yaml` và trong
  `flow`. Nếu Flowable không phản hồi trong 3 giây, `flow` trả 503.

## ADR-003: SeaweedFS làm kho đối tượng S3

- **Bối cảnh:** Cần kho tương thích S3 cho tệp hồ sơ, văn bản đã ký, dữ liệu ấm và niêm phong audit.
- **Lựa chọn:** SeaweedFS 3.85 (Apache-2.0), các bucket `staging`, `files`, `lake`, `worm`, `logs`
  được tạo khi dịch vụ khởi động.
- **Lý do:** Nhẹ, giấy phép Apache-2.0, có API S3 đủ dùng với boto3.
- **Hệ quả:** Bucket `worm` là quy ước của ứng dụng (chỉ ghi thêm bản niêm phong), không phải khóa
  đối tượng ở mức kho. Sao lưu phải chép cả các bucket (ADR-014).

## ADR-004: Đa tenant bằng RLS của PostgreSQL theo claim JWT

- **Bối cảnh:** Nhiều phường (`phuong-a`, `phuong-b`) dùng chung một CSDL và một schema.
- **Lựa chọn:** Bảng lõi và bảng app có cột `tenant`, bật và `FORCE ROW LEVEL SECURITY`. Chính sách
  dùng `core.jwt_tenant()`, `core.jwt_sub()`, `core.has_role()` đọc từ `request.jwt.claims` mà
  PostgREST đặt. Dịch vụ nền dùng vai `dxos_svc` không có `BYPASSRLS`.
- **Lý do:** Lọc ở nhân CSDL nên mã ứng dụng quên điều kiện `tenant` vẫn không lộ dữ liệu.
- **Hệ quả:** Mỗi bảng mới của app phải có chính sách RLS; test `test_V3_02`, `test_S06`,
  kịch bản e2e số 4 kiểm cách ly theo chủ thể và theo phường.

## ADR-005: Tầng 1 không chứa nghiệp vụ, app khai báo qua `app.yaml`

- **Bối cảnh:** Lõi phải dùng lại được cho app khác; gỡ app mẫu thì lõi vẫn chạy.
- **Lựa chọn:** `scripts/app_manager.py` đọc `app.yaml` (kiểm bằng `dxos_core.app_contract`), chạy
  migration của app, triển khai BPMN và nạp chính sách vào `core.app_policies`: `flow_policies`,
  `doc_signers`, `break_glass`, `alert_hooks`, `metrics`, danh mục giấy tờ. `ingest` đọc ngưỡng từ
  `apps/*/rules/*.yaml`; `metrics-api` đọc danh sách chỉ số từ chính sách `metrics`.
- **Lý do:** Lõi chỉ biết khái niệm chung (việc, biến, vai, tài liệu, ngưỡng, chỉ số); tên bước,
  vai và chỉ số của cấp phép nằm trong gói app.
- **Hệ quả:** Khóa `doc_templates` và đường dẫn `ingest_rules.rules_file` đã khai báo nhưng lõi
  chưa đọc (xem [app-package.md](app-package.md)); `doc-sign` sinh PDF bằng một mẫu chung từ dữ
  liệu JSON. Test `test_V3_01` cài và gỡ một app tạm để kiểm vòng đời.

## ADR-006: Fail-closed, không dùng dữ liệu giả trong mã chạy thật

- **Bối cảnh:** Dịch vụ phụ thuộc (CSDL, S3, ClamAV, OpenBao, Flowable) có thể lỗi.
- **Lựa chọn:** Phụ thuộc lỗi thì từ chối yêu cầu: `files` trả 503 kèm `Retry-After` khi ClamAV
  không quét được, không bao giờ coi tệp là sạch; `flow` trả 503 khi Flowable quá hạn; `ingest`
  không có ngưỡng mặc định trong mã. `scripts/check_no_fakes.py` quét mã tìm mock và mật khẩu
  mặc định.
- **Lý do:** Với hồ sơ hành chính, từ chối và báo lỗi rõ an toàn hơn nhận sai.
- **Hệ quả:** Stack phải healthy trước khi dùng; `dx up` chờ healthcheck (`up --wait`) và chạy
  `dx doctor` ở cuối.

## ADR-007: JWT RS256 kiểm bằng JWKS của Keycloak

- **Bối cảnh:** Khóa đối xứng dùng chung giữa các dịch vụ dễ bị lộ và cho phép tự ký token.
- **Lựa chọn:** APISIX dùng `openid-connect` với `use_jwks`; dịch vụ kiểm chữ ký bằng JWKS;
  PostgREST đọc `@/etc/postgrest/jwks.json` do `scripts/fetch_jwks.py` lấy từ Keycloak (`dx up`,
  `dx postgrest-jwks`).
- **Lý do:** Chỉ Keycloak giữ khóa riêng; token HS256 tự ký hoặc token bị sửa chữ ký bị 401
  (kịch bản e2e số 1).
- **Hệ quả:** Khi Keycloak đổi khóa phải đồng bộ lại JWKS cho PostgREST.

## ADR-008: Ký PAdES bằng SoftHSM/PKCS#11, OpenBao Transit để tương thích

- **Bối cảnh:** Giấy phép cần chữ ký PDF kiểm được bằng công cụ chuẩn; khóa ký không được nằm
  trong tiến trình ứng dụng.
- **Lựa chọn:** `softhsm-init` tạo token SoftHSM2 và CA thử nghiệm; `doc-sign` mặc định
  `SIGNING_MODE=pkcs11`, ký PAdES bằng pyHanko và python-pkcs11. `SIGNING_MODE=openbao` ký Ed25519
  qua OpenBao Transit. OpenBao khởi tạo Shamir 5 mảnh, ngưỡng 3 (`scripts/bao_ops.py`).
- **Lý do:** Khóa nằm trong token PKCS#11; PDF mang chữ ký nhúng, người dân đối soát được trên
  trang công khai.
- **Hệ quả:** CA thử nghiệm không có giá trị pháp lý. Sao lưu phải gồm volume SoftHSM và dữ liệu
  OpenBao. Ở `DEMO_MODE=true`, `dx up` tự khởi tạo và mở khóa OpenBao bằng
  `secrets/bao-unseal.json`; ngoài demo, OpenBao đang khóa thì `dx up` dừng và yêu cầu
  `dx bao-unseal`.

## ADR-009: Giao diện Vue 3 + Vite + TypeScript, đăng nhập OIDC PKCE

- **Bối cảnh:** CSP của gateway không cho script nội tuyến; không dùng CDN bên ngoài.
- **Lựa chọn:** `apps/cap-phep/web` và `apps/bang-dieu-hanh/web` build bằng Vite trong Dockerfile
  nhiều tầng; phông Inter đóng gói từ `@fontsource`; đăng nhập Authorization Code + PKCE bằng
  `oidc-client-ts` với client `dxos-web`. Thư mục `dist/` không đưa vào Git.
- **Lý do:** Tệp tĩnh tự chứa, chạy được không cần Internet, hợp CSP.
- **Hệ quả:** Thông báo thời gian thực dùng SSE với vé một lần (ADR-012). Giao diện cán bộ hiện chỉ
  có nút hoàn thành cho việc đã giao đích danh; việc nhận theo nhóm (một cửa tiếp nhận, lãnh đạo
  phân công và phê duyệt) và biến quy trình của các bước đó chưa có biểu mẫu, phải gọi API
  (kịch bản UI ghi rõ các bước này).

## ADR-010: Hồ sơ mới có trạng thái `DA_NOP`

- **Bối cảnh:** Danh mục trạng thái của đề C3 bắt đầu bằng `DA_NOP`.
- **Lựa chọn:** `nop_ho_so` tạo hồ sơ `DA_NOP`; RLS `rls_ho_so_insert` chỉ cho chèn trạng thái này.
- **Lý do:** Khớp đặc tả và test; các bước sau do quy trình đồng bộ trạng thái
  (`flow_policies.sync_state_sql`).
- **Hệ quả:** Giao diện và test kiểm trạng thái khởi tạo `DA_NOP`.

## ADR-011: Danh mục giấy tờ trong `app.yaml`, kiểm tra lại ở server

- **Bối cảnh:** Nộp thiếu hoặc sai giấy tờ là lỗi thường gặp nhất ở một cửa.
- **Lựa chọn:** `document_manifest` khai báo loại giấy, bắt buộc, yêu cầu hiệu lực và trường đối
  chiếu; giao diện sinh checklist từ đó. `nop_ho_so(p_ho_so_id, p_tep)` chạy
  `kiem_tra_giay_to_nop` (đủ loại bắt buộc, còn hiệu lực, khớp thông tin khai, không trùng SHA-256,
  giới hạn số tầng và diện tích) và trả 422 kèm lỗi theo từng giấy.
- **Lý do:** Không tin kiểm tra phía trình duyệt.
- **Hệ quả:** Đối chiếu dựa trên thông tin người nộp khai từ giấy tờ, chưa đọc nội dung PDF
  (không OCR).

## ADR-012: Thông báo thời gian thực bằng SSE và vé dùng một lần

- **Bối cảnh:** `EventSource` không gửi được header `Authorization`; không muốn đặt JWT lên URL.
- **Lựa chọn:** `POST /api/v1/events/ticket` (có JWT) trả vé ngẫu nhiên hết hạn sau 30 giây;
  `GET /api/v1/events?ticket=...` mở luồng. Sự kiện có tên `notification`; giao diện lắng nghe
  đúng tên này.
- **Lý do:** Token không lộ trong log truy cập; vé chỉ dùng được một lần.
- **Hệ quả:** Danh sách phiên SSE nằm trong bộ nhớ của tiến trình `flow`; chạy nhiều bản `flow`
  thì cần kênh chung (chưa làm).

## ADR-013: Trợ lý tìm theo từ khóa, Ollama là tùy chọn

- **Bối cảnh:** Máy chấm có thể không có GPU hay mô hình; trợ lý không được bịa.
- **Lựa chọn:** `assistant` chấm điểm từ khóa trên `core.knowledge_chunks` của đúng tenant. Có
  Ollama (profile `ai`, mô hình mặc định `qwen2.5:0.5b`) thì sinh câu trả lời chỉ từ các đoạn tìm
  được, kèm số trích dẫn; không có thì trả nguyên văn đoạn liên quan nhất.
- **Lý do:** Chạy được trên CPU và không phụ thuộc mô hình; câu trả lời luôn có nguồn.
- **Hệ quả:** Chưa dùng embedding hay pgvector để tìm kiếm ngữ nghĩa; câu hỏi khác từ ngữ với tài
  liệu có thể không tìm thấy.

## ADR-014: Sao lưu mã hóa bằng restic, kèm manifest mã băm, phục hồi có kiểm tra

- **Bối cảnh:** Cần sao lưu đủ để dựng lại: CSDL, tệp, khóa ký; bản sao lưu không được nằm trong
  thư mục mã nguồn và không được lộ bí mật.
- **Lựa chọn:** `dx backup` chạy `scripts/backup.py` trong container `tools`: `pg_dumpall`, chép
  các bucket S3, dữ liệu OpenBao, token và chứng thư SoftHSM vào thư mục tạm; ghi `manifest.json`
  (SHA-256 từng tệp); mã hóa vào kho restic ở volume `dxos-backups`; xóa thư mục tạm.
  `dx restore` giải mã, kiểm manifest (thiếu, sai mã băm, tệp lạ đều dừng) rồi mới ghi, và cần
  `--yes` hoặc gõ `PHUC HOI`. `--chi-kiem` chỉ kiểm, không ghi.
- **Lý do:** restic mã hóa và khử trùng lặp; manifest phát hiện bản sao lưu hỏng trước khi đè dữ
  liệu đang chạy.
- **Hệ quả:** Mất `secrets/restic-password.txt` là mất khả năng giải mã; phải cất mật khẩu này
  ngoài máy chủ.

## ADR-015: Đối soát GitOps bằng reconciler chạy theo systemd timer

- **Bối cảnh:** Cấu hình chạy thật có thể lệch khỏi Git (sửa tay container, sửa tay chính sách
  trong CSDL).
- **Lựa chọn:** `ops/reconciler/reconciler.py` (`dx gitops`) so `docker compose config --hash` với
  nhãn `com.docker.compose.config-hash` của container, kiểm container thiếu hoặc không chạy, kiểm
  thay đổi chưa commit ở `compose.yaml`, `apps/`, `core/`, và so `core.app_policies` với `app.yaml`.
  `--apply` chạy `compose up -d` (không `-v`, không `--remove-orphans`) và `app_manager upgrade`.
  Có khóa tệp chống chạy chồng; ghi log JSON `logs/reconciler.jsonl`; mã thoát 3 khi có lệch.
  `dxos-reconciler.timer` chạy 5 phút một lần.
- **Lý do:** Chỉ dùng công cụ sẵn có (Compose, Git, psql), không cần dịch vụ GitOps riêng.
- **Hệ quả:** Reconciler không tự `git pull` và không kiểm chữ ký image; cập nhật mã vẫn do người
  vận hành kéo về.

## ADR-016: Một lệnh vận hành cho cả Linux và Windows

- **Bối cảnh:** Người chấm và người vận hành dùng cả Linux lẫn Windows.
- **Lựa chọn:** `dx.sh` (bash) và `dx.ps1` (PowerShell 5.1, chỉ ký tự ASCII) có cùng tập lệnh; script
  Python chạy trong container `tools` (`docker compose --profile tools run --rm -T tools ...`). Riêng
  `init` dùng Python trên máy nếu có sẵn `cryptography`, `pyyaml`, `httpx`; không có thì build image
  `tools` và chạy trong đó. `run.cmd`/`run.ps1` gọi `init --demo`, `up`, `doctor`.
- **Lý do:** Máy chủ chỉ cần Docker; không phụ thuộc phiên bản Python và thư viện trên máy.
- **Hệ quả:** Container `tools` chạy bằng root và gắn `docker.sock` để điều khiển Compose; chỉ chạy
  trên máy vận hành tin cậy.
