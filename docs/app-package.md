<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Gói ứng dụng (app package)

Tầng 1 của DX-OS không chứa nghiệp vụ. Mỗi nghiệp vụ là một gói đặt trong
`apps/<mã-app>/`, được cài vào lõi bằng `scripts/app_manager.py`. Tài liệu này
mô tả đúng những gì mã hiện tại đọc và làm, lấy `apps/cap-phep` làm ví dụ.

## 1. Cấu trúc thư mục

```
apps/cap-phep/
├─ app.yaml                 # hợp đồng của gói (bắt buộc)
├─ db/migrations/           # SQL: schema, bảng, RLS, view, hàm RPC
│  ├─ 01-app-cap-phep.sql
│  └─ 02-document-manifest.sql
├─ bpmn/                    # quy trình BPMN 2.0 deploy vào Flowable
│  ├─ cap-phep.bpmn20.xml
│  └─ hau-kiem.bpmn20.xml
├─ templates/giay-phep.html # mẫu giấy phép (khai báo trong doc_templates)
├─ rules/nguong.yaml        # ngưỡng tiếng ồn/bụi (khai báo trong ingest_rules)
├─ knowledge/               # Markdown cho trợ lý RAG
├─ seed/seed.py             # dữ liệu mẫu hai phường
└─ web/                     # SPA Vue 3 + Vite, đóng gói bằng Dockerfile
```

Mã app (`code`) dùng chữ thường và gạch ngang. Schema PostgreSQL riêng của app
khai báo ở `schema` (`app_cap_phep`).

## 2. `app.yaml`

`app.yaml` được đọc bằng `services/dxos_core/app_contract.py`
(`load_app_manifest`). Các khóa dưới đây là khóa mã hiện tại dùng.

### 2.1 Định danh và phạm vi

| Khóa | Ví dụ | Ý nghĩa |
|---|---|---|
| `code` | `cap-phep` | Mã app; tiền tố vai trò `app:<code>:` |
| `name` | | Tên hiển thị |
| `version` | `1.0.0` | Phiên bản SemVer |
| `schema` | `app_cap_phep` | Schema PostgreSQL của app |
| `tenants` | `[phuong-a, phuong-b]` | Phường dùng app. Thiếu khóa này thì mặc định `phuong-a`, `phuong-b` |
| `migrations` | `db/migrations` | Thư mục SQL. Mặc định `db/migrations` |

### 2.2 Vai trò

```yaml
roles:
  - code: tham-dinh
    name: Thẩm định viên
    description: Thẩm định nội dung kỹ thuật hồ sơ
```

Mỗi vai được tạo trong realm `dxos` với tên `app:<code>:<role>`, ví dụ
`app:cap-phep:tham-dinh`. Vai đã có thì giữ nguyên.

### 2.3 Quy trình

```yaml
bpmn:
  - bpmn/cap-phep.bpmn20.xml
  - bpmn/hau-kiem.bpmn20.xml
```

Mỗi tệp được deploy cho bản global và cho từng tenant trong `tenants`. Flowable
đặt tên deployment theo tên tệp (bỏ `.bpmn20.xml`); nếu nội dung tệp không đổi so
với deployment mới nhất cùng tên thì bỏ qua, nên chạy lại không sinh phiên bản mới.

### 2.4 Giấy tờ bắt buộc

```yaml
document_manifest:
  thu_tuc: cap-phep-nha-o-rieng-le
  ten: Cấp phép xây dựng nhà ở riêng lẻ
  requirements:
    - loai: giay_to_dat
      ten: Giấy chứng nhận quyền sử dụng đất
      bat_buoc: true
      yeu_cau_hieu_luc: true
      thong_tin: [so_thua, dien_tich]
```

Khi cài, bảng `app_cap_phep.document_requirements` được xóa và nạp lại theo
danh sách này (giữ thứ tự khai báo ở cột `thu_tu`). Giao diện dựng checklist từ
view `app_cap_phep.document_manifest`; RPC `nop_ho_so` kiểm tra lại ở server.
`cap-phep` có 6 loại bắt buộc và 5 loại tùy chọn.

### 2.5 Chính sách ghi vào `core.app_policies`

Các khóa sau được lưu nguyên dạng JSON vào `core.app_policies` để dịch vụ lõi
đọc lúc chạy, không cần biết nghiệp vụ:

| Khóa | `policy_type` | Dịch vụ đọc |
|---|---|---|
| `object_access` | `object_access` | Hàm lõi `core.can_access`: gọi hàm SQL của app theo loại đối tượng (`ho_so` → `app_cap_phep_private.can_access_ho_so`) |
| `flow_policies` | `flow_policies` | `flow`: biến được phép theo task, vai được đặt biến, SoD, SLA, hook khi hoàn thành task |
| `doc_signers` | `doc_signers` | `doc-sign`, `flow`: vai được ký và thu hồi theo loại tài liệu |
| `break_glass` | `break_glass` | `core_api.xin_truy_cap_khan`, `core_api.duyet_truy_cap_khan`: vai được xin và được duyệt truy cập khẩn |
| `metrics` | `metrics` | `metrics-api`: 8 chỉ số, mỗi chỉ số một câu SQL nhận `$1 = tenant` |

Mỗi lần cài, mọi chính sách cũ của app bị xóa rồi ghi lại.

Ví dụ hook ký giấy phép trong `flow_policies.on_task_complete`: khi
`taskDuyetCapPhep` hoàn thành với `dongYCapPhep: true`, `flow` gọi
`guard_sql`, lấy dữ liệu bằng `data_sql`, gọi `doc-sign` ký PAdES, rồi gọi
`after_sql` (`app_cap_phep_private.cap_giay_phep`) để ghi giấy phép.

### 2.6 Khóa đọc trực tiếp từ tệp

- `alert_hooks`: `outbox-relay` đọc thẳng `app.yaml` khi có cảnh báo, gọi
  `on_alert` để lập phiếu kiểm tra và `on_process_started` để gắn quy trình
  `hau-kiem` vào phiếu.
- `seed.script`: `app_manager` chạy tệp này khi có cờ `--seed`.

### 2.7 Khóa đã khai báo nhưng chưa có dịch vụ đọc

Các khóa sau được kiểm tra cú pháp khi nạp `app.yaml` nhưng hiện chưa dịch vụ nào
dùng:

- `doc_templates`: `doc-sign` dựng PDF bằng ReportLab, không đọc
  `templates/giay-phep.html`.
- `ingest_rules.rules_file`: `ingest` lấy ngưỡng ồn từ biến môi trường
  `INGEST_NOISE_DAY_MAX` (mặc định 70 dBA) và `INGEST_NOISE_NIGHT_MAX`
  (mặc định 55 dBA), không đọc `rules/nguong.yaml`.
- `flow_policies.demo_sensor`: lưu vào `core.app_policies` nhưng `ingest`
  chưa có endpoint mô phỏng cảm biến.

## 3. Migration

Các tệp `*.sql` trong thư mục migration chạy theo thứ tự tên tệp, bằng tài khoản
`dxos_owner` (mật khẩu `DXOS_OWNER_PASSWORD` trong môi trường hoặc `.env`). Trước
đó schema được tạo với `AUTHORIZATION dxos_owner`. Sau khi chạy, `app_manager`
gửi `NOTIFY pgrst, 'reload schema'` để PostgREST nạp hàm mới.

Tệp migration phải chạy lại được (`CREATE ... IF NOT EXISTS`,
`CREATE OR REPLACE`), vì `upgrade` chạy lại toàn bộ.

## 4. Tri thức RAG

Mỗi tệp `.md` trong `knowledge.dir` được bỏ phần chú thích SPDX, cắt theo tiêu
đề `## `, rồi ghi vào `core.knowledge_chunks` với `app = <code>` cho từng tenant
đích. Nạp lại thì xóa các đoạn cũ của app trước.

## 5. Dữ liệu mẫu

```bash
python apps/cap-phep/seed/seed.py                       # mọi phường
python apps/cap-phep/seed/seed.py --tenant phuong-a     # một phường
python apps/cap-phep/seed/seed.py --tenant phuong-a --reset
python apps/cap-phep/seed/seed.py --chi-xoa             # chỉ xóa dữ liệu mẫu
make seed
```

Chạy lặp an toàn: phường đã đủ dữ liệu mẫu thì bỏ qua. `--reset` và `--chi-xoa`
chỉ xóa bản ghi mẫu (hồ sơ, công trình, giấy phép, phiếu kiểm tra, lịch sử, phân
công và process instance Flowable của chúng), không chạm dữ liệu người dùng tạo.

## 6. Giao diện web

`web/` là SPA độc lập. Compose dựng image từ `apps/cap-phep/web/Dockerfile`
(service `main-web`): Node 22 chạy `npm ci` và `npm run build`, sau đó nginx
chạy bằng user `nginx` phục vụ `dist/`. APISIX chuyển `/*` tới `main-web:80`, nên
giao diện và API (`/api/v1/...`) cùng một origin.

Biến lúc build (`import.meta.env`): `VITE_API_BASE` (mặc định `/api/v1`),
`VITE_OIDC_REALM`, `VITE_OIDC_CLIENT_ID`, `VITE_SOURCE_URL`.

```bash
cd apps/cap-phep/web
npm ci
npm test         # unit test định dạng, nhãn, bản đồ quyền (Vitest)
npm run build
```

## 7. Cài, nâng cấp, gỡ

```bash
python scripts/app_manager.py install cap-phep                    # = make app-install APP=cap-phep
python scripts/app_manager.py install cap-phep --tenant phuong-a  # chỉ một phường
python scripts/app_manager.py install cap-phep --seed             # cài rồi nạp dữ liệu mẫu
python scripts/app_manager.py upgrade cap-phep                    # chạy lại các bước
python scripts/app_manager.py uninstall cap-phep                  # = make app-uninstall APP=cap-phep
```

Mã app có thể viết dạng `--app cap-phep`. `--tenant` phải nằm trong `tenants`
của `app.yaml`. Mã thoát: `0` thành công, `1` lỗi cài đặt hoặc hạ tầng, `2` tham
số sai.

### 7.1 `install` / `upgrade`

1. Chạy migration (mục 3).
2. Nạp manifest giấy tờ (mục 2.4).
3. Deploy BPMN cho global và từng tenant đích (mục 2.3).
4. Tạo vai trò trong Keycloak (mục 2.2).
5. Nạp tri thức RAG cho từng tenant đích (mục 4).
6. Ghi chính sách vào `core.app_policies` (mục 2.5).
7. Nếu có `--seed`: chạy `seed.script`, truyền tiếp `--tenant` nếu có.

Bước 1 cần PostgreSQL, bước 3 cần Flowable, bước 4 cần Keycloak; thiếu một
trong ba thì dừng với mã `1`.

### 7.2 `uninstall`

1. `DROP SCHEMA <schema> CASCADE`.
2. Xóa tri thức của app trong `core.knowledge_chunks`.
3. Xóa chính sách của app trong `core.app_policies`.

`uninstall` không xóa vai trò trong Keycloak và không gỡ deployment BPMN khỏi
Flowable. Sau khi gỡ, các dịch vụ lõi vẫn chạy: chúng chỉ đọc chính sách từ
`core.app_policies`, nên không còn chính sách thì không còn hành vi của app.
