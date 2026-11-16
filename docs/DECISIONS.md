<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Nhật Ký Quyết Định Thiết Kế (Architectural Decision Records - ADR)

Tài liệu này ghi lại các quyết định kỹ thuật quan trọng trong quá trình thiết kế và hiện thực hệ thống **DX-OS Open-Core (v5)**, tuân thủ nguyên tắc: chọn giải pháp đơn giản nhất thỏa mãn mọi ràng buộc đề bài, ghi rõ bối cảnh, lựa chọn, lý do và hệ quả.

---

## ADR-001: Sử dụng Apache APISIX ở chế độ Standalone (YAML-based)

- **Bối cảnh:** APISIX có thể vận hành ở 2 chế độ: kết nối cụm phân tán `etcd` hoặc chế độ `standalone` đọc cấu hình từ tệp tin `apisix.yaml`.
- **Lựa chọn:** Chế độ `standalone` với tệp cấu hình `core/apisix/apisix.yaml`.
- **Lý do:**
  - Tiết kiệm 300MB - 500MB RAM do không phải chạy thêm container `etcd`.
  - Phù hợp hoàn hảo với nguyên tắc GitOps và cấu hình bằng mã nguồn (Config-as-Code): toàn bộ routes, upstream, plugins đều được version-control trong repo.
  - Khởi động nhanh, ổn định, tránh các sự cố mất đồng bộ cụm etcd trên môi trường chạy thử và máy trạm đánh giá.
- **Hệ quả:** Khi muốn cập nhật route động, ta thay đổi tệp `apisix.yaml` và reload cấu hình (APISIX tự động watch file). Kết thúc tệp bắt buộc có dòng `#END`.

---

## ADR-002: Triển khai động cơ quy trình Flowable REST độc lập

- **Bối cảnh:** Lõi DX-OS yêu cầu động cơ BPMN tiêu chuẩn mở (Flowable 7.x) phục vụ PaaS Tầng 1, không phục vụ trực tiếp người dùng cuối.
- **Lựa chọn:** Sử dụng image chính thức `flowable/flowable-rest:7.1.0` trên Apache Tomcat, kết nối đến database `flowable` trong PostgreSQL chung.
- **Lý do:**
  - Đáp ứng chuẩn xác yêu cầu phiên bản 7.x, giấy phép Apache-2.0.
  - Phân tách cơ sở dữ liệu quy trình (`flowable`) khỏi dữ liệu giao dịch của lõi (`dxos`) nhằm đảm bảo tính toàn vẹn và dễ dàng bảo trì nâng cấp.
  - Flowable REST chỉ lắng nghe trong mạng nội bộ (`app`), cổng bên ngoài chỉ bind `127.0.0.1:8082` cho mục đích kiểm tra; người dùng và ứng dụng Tầng 2 chỉ tương tác qua facade service `flow` của Tầng 1.
- **Hệ quả:** Dịch vụ `flow` đảm nhiệm vai trò kiểm soát an toàn, RBAC/ABAC và áp dụng quy tắc phân tách nhiệm vụ `dx:sodExclude`.

---

## ADR-003: Cơ chế Niêm phong Bằng chứng (WORM Bucket) trên SeaweedFS

- **Bối cảnh:** Yêu cầu lưu trữ các bản băm chuỗi kiểm toán (audit seal) vào bucket dạng WORM (Write Once Read Many) chống sửa đổi.
- **Lựa chọn:** Sử dụng SeaweedFS (Apache-2.0) với bucket chuyên biệt `worm`. Dịch vụ `audit` định kỳ đóng gói mỏ neo chuỗi băm (audit head hash) và lưu vào bucket này, đồng thời đối chiếu khóa tính toàn vẹn.
- **Lý do:**
  - SeaweedFS là hệ thống lưu trữ đối tượng mã nguồn mở gọn nhẹ, hiệu năng cao, hỗ trợ chuẩn S3 API.
  - Tránh dùng MinIO do MinIO đã chuyển đổi sang giấy phép AGPL kèm các rủi ro thương mại, đảm bảo tuân thủ tuyệt đối quy định không dùng các phần mềm thuộc danh sách cấm của đề thi.
- **Hệ quả:** Dữ liệu niêm phong được bảo vệ đa tầng: bảng `core.audit_seal` lưu vết cùng khóa băm, tệp vật lý lưu trong bucket `worm`. Bất kỳ hành vi can thiệp trái phép vào database đều bị phát hiện ngay lập tức qua API `/api/v1/audit/verify`.

---

## ADR-004: Mô hình AI nhúng (Embedding) và Mô hình Ngôn ngữ (LLM) cho Trợ lý Tra cứu

- **Bối cảnh:** Tầng 1 cung cấp năng lực Trợ lý AI (không gian [I]) tra cứu quy chuẩn, văn bản chính sách qua RAG có trích dẫn nguồn. Cần đảm bảo chạy tốt trên CPU máy tính 16GB RAM, giấy phép OSI tương thích.
- **Lựa chọn:**
  - Mô hình Embedding: `bge-m3` (giấy phép MIT).
  - Mô hình Chat LLM: `qwen2.5:0.5b` (giấy phép Apache-2.0).
  - Động cơ thực thi: `ollama` (giấy phép MIT) trong profile `ai`.
- **Lý do:**
  - Cả hai mô hình đều có giấy phép mã nguồn mở hoàn toàn (MIT và Apache-2.0), không phải giấy phép cộng đồng hạn chế như dòng Llama.
  - `qwen2.5:0.5b` có khả năng hiểu và trích xuất ngữ cảnh tiếng Việt rất tốt trong phân khúc mô hình siêu nhẹ, đáp ứng thời gian phản hồi dưới 2 giây trên CPU.
  - Phù hợp với nguyên tắc: Trọng số mô hình không lưu trong Git, tự động kéo khi kích hoạt profile `ai`.
- **Hệ quả:** Đảm bảo hệ sinh thái lõi hoàn toàn miễn phí, tuân thủ giấy phép và có thể vận hành độc lập không cần kết nối Internet khi đã tải mô hình.

---

## ADR-005: Cấu trúc Microservices Python chung gói `dxos_core`

- **Bối cảnh:** Tầng 1 gồm nhiều dịch vụ mỏng: `files`, `doc-sign`, `flow`, `ingest`, `ngsi-ld`, `export-warm`, `metrics-api`, `audit`, `outbox-relay`, `assistant`.
- **Lựa chọn:** Đóng gói toàn bộ mã dùng chung vào thư viện nội bộ `services/dxos_core/` (xác thực JWT, kết nối asyncpg, S3 client, OpenBao Transit, NATS JetStream, metrics, logging JSON). Mỗi dịch vụ là một entrypoint FastAPI hoặc worker riêng biệt trong thư mục con của `services/`.
- **Lý do:**
  - Đảm bảo DRY (Don't Repeat Yourself), thống nhất chuẩn bảo mật nhiều lớp (defense-in-depth), kiểm tra JWT và ghi audit đồng nhất.
  - Tối ưu hóa việc đóng gói container: chung một base image và layer phụ thuộc Python, giúp giảm dung lượng ổ đĩa từ vài GB xuống dưới 400MB.
- **Hệ quả:** Mã nguồn gọn gàng, kiểm thử đơn vị tập trung và nhất quán giữa các dịch vụ.

---

## ADR-006: Kiến trúc Đa Thuê ước (Multi-Tenancy) và RLS

- **Bối cảnh:** Hệ thống phục vụ nhiều phường xã (`phuong-a`, `phuong-b`) trên cùng một thể hiện cài đặt (shared database, shared schema).
- **Lựa chọn:** Sử dụng PostgreSQL Row-Level Security (RLS) kết hợp với JWT claim `tenant`. Cung cấp các hàm tiện ích lõi `core.jwt_tenant()`, `core.jwt_sub()`, `core.has_role()`.
- **Lý do:**
  - RLS được thực thi ở tầng nhân PostgreSQL, ngăn chặn triệt để rủi ro rò rỉ dữ liệu giữa các tenant kể cả khi mã ứng dụng có thiếu sót câu lệnh `WHERE tenant = ...`.
  - Tương thích tự nhiên với PostgREST: PostgREST tự động đặt các claim từ JWT vào session setting `request.jwt.claims`.
- **Hệ quả:** Mọi bảng dữ liệu lõi và bảng nghiệp vụ của app đều bắt buộc có cột `tenant` và kích hoạt RLS.

---

## ADR-007: Tính Tổng quát Tuyệt đối của Tầng 1 (decoupling nghiệp vụ)

- **Bối cảnh:** Yêu cầu đặc tả: Tầng 1 không chứa bất kỳ chuỗi nghiệp vụ nào liên quan đến cấp phép xây dựng.
- **Lựa chọn:** Lõi chỉ cung cấp:
  - Khung quy trình tổng quát (Flowable BPMN engine, SOD enforcement).
  - Khung lưu trữ tệp có kiểm dịch ClamAV và phân quyền đối tượng (`object_type`, `object_id`).
  - Khung ký số động (`doc-sign` nhận template HTML và dữ liệu JSON).
  - Khung thu nạp dữ liệu cảm biến dựa trên quy tắc cấu hình (`ingest_rules` từ `app.yaml`).
  - Khung tính toán chỉ số dựa trên metadata khai báo (`metrics` từ `app.yaml`).
- **Lý do:**
  - Thỏa mãn 100% tiêu chí đề thi: Tháo gỡ ứng dụng mẫu `apps/cap-phep`, Lõi Tầng 1 vẫn hoạt động trọn vẹn và mọi kiểm thử của Lõi đều thành công.
- **Hệ quả:** Ứng dụng nghiệp vụ chỉ là một gói plugin cắm vào lõi thông qua hợp đồng `app.yaml`.

---

## ADR-008: Nguyên tắc Fail-Closed và Loại bỏ Toàn bộ Mock/Fallback trong Môi trường Sản phẩm

- **Bối cảnh:** Ở phiên bản v1.0.0, khi một dịch vụ phụ thuộc (Postgres, S3, ClamAV, OpenBao) gặp lỗi hoặc quá tải, hệ thống có xu hướng fallback dùng dữ liệu giả lập trong RAM (`MockConnection`, `_memory_store`, sinh khóa riêng trong tiến trình) để tiếp tục phản hồi 200 OK. Điều này tạo ra ảo giác chạy được nhưng làm thất thoát dữ liệu và vi phạm nghiêm trọng an toàn thông tin.
- **Lựa chọn:** Xóa bỏ hoàn toàn mã mock, memory store và các khối nuốt lỗi `except Exception: pass` trong mã nguồn sản phẩm. Áp dụng triệt để nguyên tắc **Fail-Closed**: khi bất kỳ phụ thuộc nào không sẵn sàng, dịch vụ lập tức từ chối yêu cầu và trả về HTTP 503 Service Unavailable kèm thông báo tiếng Việt có dấu và mã lỗi rõ ràng.
- **Lý do:**
  - Bảo đảm tính toàn vẹn dữ liệu: Không bao giờ chấp nhận tạo hoặc cập nhật hồ sơ khi chuỗi kiểm toán bất biến `audit_log` hay cơ sở dữ liệu không ghi nhận được.
  - Ngăn ngừa tệp chứa mã độc: Khi ClamAV gặp sự cố, hệ thống không được phép cho qua tệp với giả định là an toàn; phải chặn lại và yêu cầu thử lại sau.
  - Phù hợp với tiêu chuẩn an toàn cho hệ thống chính quyền số.
- **Hệ quả:** Mọi thành phần phụ thuộc bắt buộc phải đạt trạng thái healthy trước khi phục vụ giao dịch; các bài kiểm thử tích hợp phản ánh đúng năng lực vận hành thực tế của hệ thống.

---

## ADR-009: Quản lý Khóa Transit KMS qua OpenBao và Xác thực JWKS Keycloak RS256

- **Bối cảnh:** Chữ ký số tài liệu điện tử và cơ chế xác thực JWT cần loại trừ triệt để nguy cơ lộ khóa bí mật và tấn công mạo danh (forgery token).
- **Lựa chọn:**
  - Sử dụng OpenBao Transit Secrets Engine với thuật toán Ed25519 để ký số văn bản giấy phép. Khóa bí mật nằm hoàn toàn trong OpenBao; dịch vụ `doc-sign` chỉ gửi yêu cầu ký qua REST API và lưu trữ `key_version` cùng chữ ký base64.
  - Cổng PostgREST và toàn bộ microservices chuyển sang xác thực khóa bất đối xứng qua bộ khóa công khai JWKS RS256 trích xuất từ Keycloak (`@/etc/postgrest/jwks.json`). Loại bỏ hoàn toàn khóa bí mật đối xứng HS256 dùng chung.
- **Lý do:**
  - Ngăn chặn nguy cơ lộ khóa riêng tư ký số khi container ứng dụng bị xâm nhập.
  - Khóa công khai Ed25519 cho phép bất kỳ bên thứ ba nào cũng có thể kiểm tra tính toàn vẹn tài liệu trên cổng công khai `/kiem-tra/{public_code}` mà không cần quyền truy cập vào hệ thống nội bộ.
  - Chống giả mạo JWT: Kẻ tấn công không thể tự sinh token bằng khóa bí mật đối xứng giả mạo.
- **Hệ quả:** Dịch vụ OpenBao được khởi tạo với Shamir 5/3 và lưu trữ bền vững trên Docker volume; quy trình tự động mở khóa (unseal) được cấu hình an toàn.

---

## ADR-010: Giao diện Người dùng Tự hành (Offline-First) và Độc lập Ngoại mạng

- **Bối cảnh:** Các ứng dụng web của chính quyền số cần hoạt động ổn định trên mạng truyền số liệu chuyên dùng hoặc môi trường cô lập (air-gapped), đồng thời ngăn ngừa rủi ro rò rỉ dữ liệu qua các CDN ngoại mạng.
- **Lựa chọn:**
  - Tải về và đóng gói cục bộ 100% thư viện giao diện Vue 3 và Tailwind CSS vào thư mục tĩnh `apps/*/web/dist/vendor/`. Sử dụng phông chữ có sẵn của hệ điều hành (system font stack).
  - Cổng biên mạng APISIX áp dụng nghiêm ngặt chính sách `Content-Security-Policy: default-src 'self'`.
- **Lý do:**
  - Triệt tiêu hoàn toàn sự phụ thuộc vào các dịch vụ CDN công cộng (`unpkg.com`, `cdn.jsdelivr.net`, `fonts.googleapis.com`).
  - Đảm bảo quyền riêng tư: Trình duyệt của cán bộ và công dân không gửi bất kỳ yêu cầu hay IP nào ra máy chủ nước ngoài.
  - Tăng tốc độ tải trang ban đầu và đảm bảo hệ thống có thể trình diễn ngay cả khi mất kết nối Internet.
- **Hệ quả:** Mã nguồn giao diện tăng kích thước thêm khoảng 300KB cho các tệp tĩnh nội bộ, nhưng đạt độ sẵn sàng và tin cậy 100%.

---

## ADR-011: Kiến trúc Frontend Vue 3 + Vite + TypeScript (Build-time SPA) và Xác thực OIDC PKCE

- **Bối cảnh:** Bản mẫu giao diện ban đầu sử dụng các script nhúng trực tiếp trong HTML với các chuỗi placeholder chưa biên dịch, vi phạm chính sách bảo mật nội dung `Content-Security-Policy: default-src 'self'` do chứa inline styles và inline scripts, đồng thời sử dụng dropdown giả lập người dùng thay vì luồng đăng nhập chuẩn.
- **Lựa chọn:**
  - Chuyển đổi toàn bộ ứng dụng frontend `apps/cap-phep/web` sang kiến trúc Single Page Application (SPA) xây dựng bằng Vue 3 + Vite + TypeScript + Tailwind CSS theo mô hình biên dịch trước (build-time).
  - Loại bỏ hoàn toàn inline scripts và inline styles trong mã nguồn và gói xuất bản `dist/`, đảm bảo 100% tuân thủ CSP `default-src 'self'` mà không cần bật `unsafe-inline` hay `unsafe-eval`.
  - Tích hợp thư viện chuẩn mở `oidc-client-ts` để thực hiện xác thực OpenID Connect Authorization Code Flow kết hợp PKCE trực tiếp với Keycloak 26 thông qua client `dxos-web`.
  - Loại bỏ các tệp sinh tự động `dist/` khỏi hệ thống quản lý phiên bản Git, cấu hình Dockerfile nhiều tầng (multi-stage build) để biên dịch tự động.
  - Cập nhật biểu mẫu đồng thuận xử lý dữ liệu cá nhân theo Luật Bảo vệ dữ liệu cá nhân 2025 (Luật 91/2025/QH15) và Nghị định 356/2025/NĐ-CP, áp dụng nguyên tắc đồng thuận theo từng mục đích riêng biệt và không tích sẵn mặc định (opt-in).
- **Lý do:**
  - Đáp ứng triệt để các tiêu chuẩn bảo mật hiện đại của cổng dịch vụ công trực tuyến.
  - Loại bỏ mọi dữ liệu giả lập (mock), kết nối trực tiếp đến các API thật của DX-OS Core (`/api/v1/rest/v_ho_so` với phân quyền RLS, `/api/v1/flow/tasks`).
  - Giao diện đáp ứng mượt mà trên cả thiết bị di động (chiều rộng 390px không tràn màn hình).
- **Hệ quả:** Quá trình đóng gói và triển khai sản xuất thực hiện qua lệnh `npm run build` hoặc Docker multi-stage build, tạo ra các tệp tĩnh tối ưu hóa và bảo mật cao.

---

## ADR-012: Chuẩn hóa Trạng thái Khởi tạo Hồ sơ Cấp phép Trực tuyến thành `DA_NOP`

- **Bối cảnh:** Theo đặc tả C3 mục 14 (Hành trình người dùng P0), hồ sơ cấp phép xây dựng khi công dân nộp trực tuyến có trạng thái ban đầu là `DA_NOP`. Trong mã nguồn phiên bản trước, hàm `nop_ho_so` gán trạng thái `CHO_TIEP_NHAN`, không nằm trong danh mục các trạng thái chính thức của quy chuẩn C3.
- **Lựa chọn:** Chuẩn hóa giá trị khởi tạo trong hàm RPC `nop_ho_so` sang `DA_NOP`. Đồng thời đồng bộ các chính sách RLS (`rls_ho_so_insert`, `dinh_kem_tep`), bộ định dạng giao diện (`formatters.js`) và các kịch bản kiểm thử (E2E / Integration) kiểm tra trạng thái khởi tạo `DA_NOP`.
- **Lý do:**
  - Hoàn toàn tuân thủ danh mục trạng thái đặc tả C3 và các bài kiểm tra tự động.
  - Các bước chuyển tiếp quy trình BPMN tiếp theo (`CAN_BO_SUNG`, `TIEP_NHAN`, `DUOC_PHAN_CONG`, `CHO_DUYET`, `DA_CAP`) vận hành chuẩn xác và nhất quán.
- **Hệ quả:** Hồ sơ mới tạo luôn có `trang_thai = 'DA_NOP'`, được cán bộ Một cửa tiếp nhận và chuyển tiếp sang bước `phan_cong`.

---

## ADR-013: Ký PAdES qua SoftHSM/PKCS#11 và Dashboard/Assistant thật

- **Bối cảnh:** Bản v1.1.0 dùng OpenBao Transit Ed25519; dashboard [D] và trợ lý [I] còn hardcoded. Yêu cầu demo cần chữ ký PDF chuẩn PAdES, dashboard lấy metrics-api thật và trợ lý gọi RAG thật.
- **Lựa chọn:**
  - Thêm `softhsm-init` tạo token SoftHSM2 + test CA; `doc-sign` mặc định `SIGNING_MODE=pkcs11`, ký PAdES bằng `pyHanko` + `python-pkcs11`.
  - Giữ `SIGNING_MODE=openbao` làm legacy cho tài liệu cũ.
  - Dashboard [D] dùng OIDC PKCE, gọi `/api/v1/metrics` và `/api/v1/metrics/{code}/lineage`.
  - Trợ lý [I] gọi `/api/v1/assistant/ask`, hiển thị citation từ kho tri thức.
  - Trang `/kiem-tra` bỏ CDN, dùng CSS nội bộ, thêm form đối soát PDF.
- **Lý do:** Đáp ứng yêu cầu chữ ký PDF, loại bỏ dữ liệu giả, giữ fail-closed và không phụ thuộc CDN.
- **Hệ quả:** Private key nằm trong token; backup/restore phải gồm volume SoftHSM. Test CA chỉ dùng cho demo, không có giá trị pháp lý.

---

## ADR-014: Manifest giấy tờ + 7 lớp kiểm tra ở Server và 8 chỉ số dashboard

- **Bối cảnh:** Đặc tả C3 xác định P1 (nộp thiếu/sai giấy) là nỗi đau số 1 và là khoảnh khắc demo 2–4. Bản trước chỉ có một input tệp, `nop_ho_so` không kiểm tra giấy tờ; dashboard chỉ có 5 chỉ số.
- **Lựa chọn:**
  - Khai báo `document_manifest` trong `app.yaml`, seed vào `app_cap_phep.document_requirements` khi cài app.
  - UI sinh checklist động theo manifest; tải tệp vào `draft.ho_so` trước khi tạo hồ sơ.
  - `nop_ho_so` nhận `p_ho_so_id` + `p_tep`, chạy `kiem_tra_giay_to_nop` (L1, L4, L5, L6, L7; L2/L3 do `files` đảm bảo) và trả `PT422` kèm danh sách lỗi có cấu trúc.
  - `ho_so_tep` lưu metadata, trạng thái review, version và `tep_goc_id`; `dinh_kem_tep` validate loại/trùng SHA-256 và tự tăng version.
  - `danh_gia_tep` cho cán bộ kết luận từng tệp đạt/không đạt kèm lý do.
  - Bổ sung 4 chỉ số còn thiếu để đủ 8 chỉ số theo đặc tả; dashboard render động từ API.
- **Lý do:** Chặn lỗi tại cửa ngõ (Poka-yoke thật), không tin UI, giữ fail-closed; đáp ứng đúng khoảnh khắc demo và D1.
- **Hệ quả:** Mọi client muốn nộp hồ sơ phải gửi kèm danh sách tệp; test/seed cũ được cập nhật helper `submit_dossier`. L5 ở mức demo dựa trên metadata người dùng khai báo từ giấy tờ (không OCR); production nên bổ sung trích xuất PDF/OCR và CA/HSM thật.

