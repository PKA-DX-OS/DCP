<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# KẾ HOẠCH CẢI THIỆN D & H CHO 2 NGƯỜI LÀM ĐỘC LẬP

> **Bản chỉnh sau rà soát v1.1 (2026-11-21).** Người A (Track D) là Duy Anh (`caduoiduianh`), người B
> (Track H) là Hoàng (`5coinin1`). Các chỗ đổi so với bản đầu nằm ở mục 18; phần còn lại giữ nguyên.

**Mục tiêu:** Hai người làm song song, ít giẫm file, ghép được thành một sản phẩm.
**Cách chia:** Một người làm **D — Data Foundation**, một người làm **H — Human Workspace & Automation**.
**Không gắn thời gian:** Kế hoạch dùng **cổng ghép (Gate)** và **thứ tự công việc**, không dùng tuần/ngày.

---

## 0. Kết luận điều hành

DCP hiện có P (workflow, ký số, thông báo, audit) và một phần D (PostgreSQL/PostgREST, kho tệp, audit, metrics, lineage, cảm biến). H đã giảm thao tác ở luồng hành chính nhưng chưa đo được, chưa có MDM/data quality, chưa có OCR/PWA.

Kế hoạch chia 2 track:

| Track | Người | Trọng tâm | Sản phẩm cuối |
|---|---|---|---|
| **D — Data Foundation** | Người A | MDM, data quality, catalog, lineage, 360, marts, external refs, OCR backend | Dữ liệu có nguồn sự thật, đo được, có phả hệ |
| **H — Human Workspace** | Người B | 360 UI, search, autofill, OCR review, PWA, self-service, H dashboard | Người dùng ít thao tác thủ công, có đo lường |

**Điều kiện sống còn để độc lập:**

1. **Contract-first** — A công bố OpenAPI/schema trước, B code theo mock.
2. **File ownership rõ** — không ai sửa file của người kia.
3. **B không viết SQL/migration** — chỉ gọi API.
4. **A không sửa UI shell** — chỉ tạo component con.
5. **Merge theo cổng** — không merge liên tục vào file chung.
6. **Mock trước, API thật sau** — B không bị block.
7. **Đo baseline trước khi claim tiết kiệm** — không nói giảm H khi chưa có số.

---

## 1. Đầu vào & phạm vi

### 1.1. Mục tiêu D

1. Có mã chuẩn cho công dân, thửa đất, công trình, hồ sơ, giấy phép.
2. Có bộ rule chất lượng dữ liệu và dashboard DQ.
3. Có catalog + data contract + lineage end-to-end.
4. Có 360 view và search API.
5. Có marts phục vụ dashboard, có định nghĩa và freshness.
6. Có external_refs để sau này nối dân cư/đất đai/thuế/PCCC/CSDL quốc gia.
7. Có OCR backend + queue + API cho H dùng.

### 1.2. Mục tiêu H

1. Giảm thao tác tìm hồ sơ, mở nhiều màn hình, nhập lại dữ liệu.
2. Có 360 view và tìm kiếm toàn cục.
3. Có autofill/validation/draft autosave.
4. Có OCR review queue (human-in-the-loop).
5. Có PWA kiểm tra hiện trường.
6. Có self-service công dân.
7. Có H metrics dashboard: thao tác thủ công, handoff, rework, cycle time, self-service.

### 1.3. Baseline hiện có

| Lớp | Đã có |
|---|---|
| Dữ liệu tác nghiệp | `app_cap_phep`, `app_construction`, PostgREST, RLS |
| Tệp | SeaweedFS, ClamAV, files service |
| Audit | hash chain, WORM seal, `core.audit_log`, `core.audit_seal` |
| Metrics | metrics-api, dashboard, Parquet export; `core.lineage_events` (hiện chỉ dịch vụ ingest cảm biến ghi) |
| OT | NGSI-LD, timeseries, cảm biến, phiếu kiểm tra |
| Pháp lý | 50 văn bản, 24 trích dẫn, thẩm quyền, định danh, phí, lưu trữ, chia sẻ |
| UI | workspace, modal hồ sơ, dashboard, legal library, DSAR |
| Bảo mật | SSO/MFA, RLS, PII, DSAR, break-glass |

### 1.4. Khoảng trống

| Mảng | Thiếu |
|---|---|
| MDM | Chưa có mã chuẩn/liên kết công dân ↔ thửa đất ↔ công trình ↔ hồ sơ ↔ giấy phép |
| DQ | Chưa có rule, score, issue workflow |
| Catalog | Chưa có asset owner, classification, retention |
| Lineage | Chỉ `services/ingest` gọi `record_lineage_event`; chưa phủ hồ sơ, giấy phép, metrics |
| 360 | Chưa có view tổng hợp và search toàn cục |
| OCR | Chưa có extraction/auto-classify |
| Autofill | Chưa có điền lại/thông minh |
| PWA | Chưa có tác nghiệp hiện trường offline |
| H metrics | Chưa đo thao tác thủ công/thời gian tiết kiệm; audit `flow.task_completed` chỉ có `task_id`, không gắn được với hồ sơ |
| External | Chưa có external_refs/adapters |

### 1.5. Không làm trong kế hoạch này

- Không làm Agentic AI/autonomous action.
- Không làm full lakehouse/Iceberg.
- Không kết nối CSDL quốc gia thật.
- Không làm WebGIS toàn thành phố.
- Không OCR tất cả giấy tờ.
- Không thay core/workflow hiện có.
- Không làm lại các mảng đã có: quy hoạch, thiết kế, nghiệm thu, pháp lý, hậu kiểm.

### 1.6. Tiêu chí thành công

| Nhóm | Tiêu chí |
|---|---|
| D | DQ score ≥ 85 (phase 1), ≥ 95 (phase 2); duplicate ≤ 2% → 1%; 100% asset chính có owner; lineage 100% luồng chính |
| H | Giảm 20–40% thao tác thủ công/hồ sơ; giảm 25–50% thời gian kiểm tra giấy tờ; giảm 10–25% rework; tăng 20–40% self-service |
| Chi phí | Có baseline TCO/chi phí hồ sơ; chỉ claim tiết kiệm sau khi đo |
| Chất lượng | Không tăng lỗi; mọi automation có human review + audit |

### 1.7. Tuân thủ dữ liệu

- Phân loại PII: CCCD, họ tên, điện thoại, địa chỉ, tệp đính kèm.
- CCCD trong lớp MDM chỉ lưu `cccd_hmac` = HMAC-SHA256 với khóa bí mật `secrets/mdm-hmac.key`
  (sinh bởi `dx init`). Không dùng hash trần: CCCD chỉ có 10¹² giá trị, SHA-256 trần dò ngược được.
- MDM không chép họ tên/điện thoại sang bảng mới; golden view đọc từ bản ghi nguồn. Bảng MDM nào
  có dữ liệu cá nhân phải nằm trong phạm vi xuất/xóa của DSAR.
- Mask khi log/dashboard; RLS theo tenant; audit mọi truy cập.
- Retention theo nhóm hồ sơ; DSAR đã có.
- Không copy PII sang mock/fixture; dùng dữ liệu giả.
- Data quality job không trả PII trong sample; chỉ trả ID/masked.

---

## 2. Nguyên tắc chia việc

| # | Nguyên tắc | Diễn giải |
|---|---|---|
| 1 | **Contract-first** | API/schema chốt trước; mock trước; code sau |
| 2 | **File ownership** | Mỗi file có một owner; người kia đề xuất qua PR nhỏ |
| 3 | **D trước H tự động** | Không tự động hóa trên dữ liệu bẩn |
| 4 | **Human-in-the-loop** | OCR/AI chỉ đề xuất; cán bộ xác nhận |
| 5 | **Không ghi đè nguồn** | MDM là lớp liên kết/golden record |
| 6 | **Đo trước, sửa sau** | Baseline H/D trước khi cải thiện |
| 7 | **Không big-bang** | Từng work package nhỏ, có flag |
| 8 | **Không phá core** | Tận dụng Postgres/PostgREST/RLS/files/audit/metrics |
| 9 | **Test thuộc owner** | A backend/integration; B UI/E2E |
| 10 | **Không mock kéo dài** | Gate 2 phải chuyển API thật |
| 11 | **Mốc đo trên v1.1** | Đo baseline H/D trên tag `v1.1` trước Gate 1, lưu `docs/data/baseline-v1.1.md` |

---

## 3. Mô hình 2 track

### 3.1. Track D — Người A

**Sở hữu**
- `core/postgres/20-data-governance.sql`
- `core/postgres/21-mdm.sql`
- `core/postgres/22-data-quality.sql`
- `core/postgres/23-catalog-lineage.sql`
- `core/postgres/24-external-refs.sql`
- `apps/cap-phep/db/migrations/20-dh-ocr.sql`
- `services/construction/routers/mdm.py`
- `services/construction/routers/data_quality.py`
- `services/construction/routers/catalog.py`
- `services/construction/routers/lineage.py`
- `services/construction/routers/search.py`
- `services/construction/routers/automation_metrics.py`
- `services/ocr/*`
- `scripts/data_quality_worker.py`
- `scripts/mdm_backfill.py`
- `scripts/seed_mdm.py`
- `contracts/dh/*`
- `core/apisix/routes/dh.yaml` (route của các API D)
- `compose.yaml` phần dịch vụ backend mới (`ocr`), `dx.ps1`/`dx.sh` phần migration
- `services/dxos_core/user_sync.py` phần vai mới (`dx:data-steward`)
- `services/flow` phần ghi audit (gắn `ho_so_id` vào `flow.task_completed`)
- `scripts/dh_baseline.py`
- `apps/bang-dieu-hanh/web/src/components/data/*`
- `tests/integration/test_dh_*`
- `tests/unit/test_data_*`

**API sở hữu**
- `/api/v1/mdm/*`
- `/api/v1/data-quality/*`
- `/api/v1/catalog/*`
- `/api/v1/lineage/*`
- `/api/v1/search`
- `/api/v1/automation/metrics`
- `/api/v1/ocr/*`

**Không sửa**
- UI workspace/modal/home của B.
- `apps/bang-dieu-hanh/web/src/App.vue`.
- `tests/e2e-ui/*`.
- `apps/cap-phep/web/src/features/*`.

### 3.2. Track H — Người B

**Sở hữu**
- `apps/cap-phep/web/src/views/*`
- `apps/cap-phep/web/src/components/*`
- `apps/cap-phep/web/src/features/*`
- `apps/cap-phep/web/src/api/*` (B tự sinh type/client từ `contracts/dh`)
- `apps/bang-dieu-hanh/web/src/App.vue`
- `apps/bang-dieu-hanh/web/src/components/automation/*`
- `apps/bang-dieu-hanh/web/src/components/ocr/*`
- `apps/cap-phep/web/src/components/ChonTep.vue` (đã có)
- `tests/e2e-ui/*`
- `apps/*/web/tests/*`

**API tiêu thụ**
- MDM 360/search, DQ, catalog, lineage, automation metrics, OCR.

**Không sửa**
- `core/postgres/*`.
- `services/*` backend của A.
- `contracts/dh/*` (chỉ review).

### 3.3. Điểm giao nhau

| File/khu vực | Owner | Quy tắc |
|---|---|---|
| `contracts/dh/*` | A | B review; đổi breaking phải bump version |
| `apps/cap-phep/app.yaml` | B | A đề xuất; B merge |
| `compose.yaml`, `dx.ps1`, `dx.sh` | A | Phần dịch vụ backend/migration do A sửa; B đề xuất phần build web qua PR nhỏ |
| `features/registry.ts` | B | A không sửa |
| `apps/bang-dieu-hanh/web/src/App.vue` | B | A tạo component; B thêm tab |
| `apps/cap-phep/web/src/api/index.ts` | B | A chỉ cung cấp contract + mock, không viết client |
| `core/apisix/routes/dh.yaml` | A | Mỗi nhóm route một tệp fragment, không sửa `apisix.template.yaml` |
| Vai trong realm (`user_sync.py`) | A | Vai mới khai báo ở đây để `dx up` đồng bộ cả stack cũ |
| `tests/e2e-ui/*` | B | A cung cấp seed/fixture |
| `docs/data/*` | A | `docs/ux/*` B |
| `README` | B | A cập nhật mục data qua PR nhỏ |

### 3.4. Contract-first

A viết trước:
- `contracts/dh/mdm.yaml`
- `contracts/dh/data-quality.yaml`
- `contracts/dh/catalog.yaml`
- `contracts/dh/lineage.yaml`
- `contracts/dh/ocr.yaml`
- `contracts/dh/automation.yaml`
- `contracts/dh/search.yaml`
- `contracts/dh/mocks/*.json`

Quy ước:
- `tenant` lấy từ JWT, không nhận body.
- Lỗi: `{code, message, details}`.
- Pagination: `page`, `page_size`, `total`.
- Idempotency key cho POST quan trọng.
- Audit event cho mọi mutation.
- Version `v1`; breaking → `v2`.

### 3.5. Feature flags

| Flag | Owner | Tác dụng |
|---|---|---|
| `DH_MDM` | A | Bật MDM/360 API |
| `DH_DQ` | A | Bật DQ worker/dashboard |
| `DH_CATALOG` | A | Bật catalog/lineage |
| `DH_OCR` | A/B | Bật OCR backend/UI; mặc định tắt, dịch vụ `ocr` ở profile riêng |
| `DH_PWA` | B | Bật PWA |
| `DH_H_METRICS` | A/B | Bật dashboard H |
| `VITE_API_MOCK` | B | UI dùng mock |

---

## 4. Phase 0 — Nền tảng cho 2 người độc lập

> Mục tiêu: sau Phase 0, A và B làm song song mà gần như không sửa cùng file.
> Gate: DB → API → UI → CI chạy “hello world” xuyên suốt.

### P0-01 — Ownership & branch

**Việc**
- Tạo `OWNERSHIP.md` ở gốc repo.
- Nhánh: `feat/data-foundation` (A), `feat/human-workspace` (B).
- Quy tắc:
  - Rebase/merge `develop` trước PR.
  - PR nhỏ theo work package.
  - CI xanh mới merge.
  - Shared file chỉ owner sửa.
- Không commit trực tiếp `develop`.

**Done khi**
- Cả hai đọc và thống nhất ownership.
- Mỗi người có nhánh riêng.

### P0-02 — Migration & namespace

**Việc**
- D migrations:
  - `20-data-governance.sql`
  - `21-mdm.sql`
  - `22-data-quality.sql`
  - `23-catalog-lineage.sql`
  - `24-external-refs.sql`
- App migration:
  - `20-dh-ocr.sql`
- Tất cả idempotent: `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `DO $$`.
- Không sửa migration cũ.
- D chạy `py -3 scripts/migrate.py`; app migration chạy qua `dx up`/`app-install`.

**Done khi**
- DB sạch và DB hiện có đều migrate thành công.
- Không mất dữ liệu.

### P0-03 — API contract

**Việc**
- A tạo `contracts/dh/*.yaml` + JSON Schema.
- B review, chốt type.
- Sinh TypeScript type (`openapi-typescript`) hoặc viết tay theo schema.
- Mock JSON trong `contracts/dh/mocks/`.

**Done khi**
- B import được type.
- Mock server trả đúng schema.

### P0-04 — Mock & fixtures

**Việc**
- Mock 360: 1 hồ sơ, 1 công dân, 1 thửa đất, 1 công trình, 1 giấy phép.
- Mock DQ: 1 summary, 5 issue.
- Mock catalog: 5 asset.
- Mock OCR: 1 extraction.
- Mock H metrics: 1 bộ số.
- Dùng MSW/JSON server; flag `VITE_API_MOCK=1`.

**Done khi**
- B dựng được toàn bộ UI bằng mock.

### P0-05 — Test harness & CI

**Việc**
- A: `pytest tests/integration/test_dh_*`, contract test.
- B: Vitest, Playwright, axe.
- CI: type-check, build, unit, integration data, E2E smoke.
- Seed/fixture dùng chung, không PII thật.

**Done khi**
- PR nào cũng chạy test của owner.
- Không test nào phụ thuộc thứ tự.

### P0-06 — Seed & backfill

**Việc**
- `scripts/mdm_backfill.py`: map dữ liệu hiện có vào MDM.
- `scripts/seed_mdm.py`: seed demo.
- `scripts/data_quality_worker.py`: chạy rule.
- Không sửa dữ liệu gốc; chỉ insert/update bảng MDM/DQ.

**Done khi**
- Chạy lại nhiều lần không tạo trùng.
- Có báo cáo số bản ghi map được.

### P0-07 — Data admin shell

**Việc**
- A tạo `apps/bang-dieu-hanh/web/src/components/data/DataQualityPanel.vue`, `CatalogPanel.vue`.
- B thêm tab “Dữ liệu” vào `App.vue` sau khi component có mock.
- Chỉ B sửa `App.vue`.

**Done khi**
- Tab hiển thị component của A; không conflict.

---

## 5. Track D — Chi tiết

### 5.1. D-GOV — Data governance

#### D-GOV-01 — Inventory & ownership

| Việc | Chi tiết |
|---|---|
| Domain | Công dân, thửa đất, hồ sơ, giấy phép, công trình, giấy tờ, kiểm tra, tài chính, audit |
| Bảng | `core.data_assets`, `core.data_owners` |
| Cột | `asset`, `schema`, `domain`, `owner`, `steward`, `classification`, `retention`, `freshness`, `version` |
| UI | Danh sách asset, filter domain, owner |

**Done khi**
- 9 domain có owner.
- Asset chính có mô tả/classification.

#### D-GOV-02 — PII & retention

| Việc | Chi tiết |
|---|---|
| Phân loại | Public / Internal / PII / Sensitive |
| Cột PII | `cccd`, `ho_ten`, `dien_thoai`, `dia_chi`, tệp đính kèm |
| Retention | Theo nhóm hồ sơ; cấu hình `core.data_retention` |
| Mask | View/log không trả full CCCD |
| Audit | Mọi đọc PII ghi audit |

**Done khi**
- Catalog hiển thị classification.
- Không có PII trong mock/log.

### 5.2. D-MDM — Master Data Management nhẹ

#### D-MDM-01 — Schema

**Bảng**
| Bảng | Cột chính |
|---|---|
| `core.mdm_subject` | `subject_id`, `tenant`, `cccd_hmac`, `source`, `confidence`, `merged_into`, `created_at` (họ tên, điện thoại đọc từ nguồn qua view) |
| `core.mdm_parcel` | `parcel_id`, `tenant`, `ma_dinh_danh_dia_diem`, `so_thua`, `to_ban_do`, `dien_tich_m2`, `geom`, `source` |
| `core.mdm_construction` | `construction_id`, `tenant`, `ma_cong_trinh`, `parcel_id`, `dia_chi_chuan`, `source` |
| `core.mdm_dossier_link` | `dossier_id`, `tenant`, `subject_id`, `parcel_id`, `construction_id`, `permit_id`, `confidence` |
| `core.mdm_organization` | `org_id`, `tenant`, `ten`, `mst`, `loai`, `source` |
| `core.external_refs` | `system`, `entity_type`, `entity_id`, `external_id`, `confidence`, `last_synced_at` |

**Index**
- `(tenant, cccd_hmac)`, `(tenant, ma_dinh_danh_dia_diem)`, `(tenant, ma_cong_trinh)`, `(tenant, dossier_id)`.
- Unique `(tenant, system, entity_type, external_id)` cho external_refs.

**RLS**
- `tenant = core.jwt_tenant()` hoặc platform-admin.
- `merged_into IS NULL` cho view golden.

**Done khi**
- Migration chạy; seed/backfill chạy; không trùng.

#### D-MDM-02 — Matching

**Exact**
- `cccd_hmac + tenant`.
- `ma_ho_so`.
- `ma_cong_trinh`.
- `ma_dinh_danh_dia_diem`.
- `public_code`/`so_giay_phep`.

**Fuzzy (phase 2)**
- Tên + điện thoại + địa chỉ.
- Confidence 0–1.
- Dưới ngưỡng: tạo `mdm_link_candidate`, không auto-link.
- Merge thủ công, có audit, có undo.

**Done khi**
- Backfill map ≥ 90% hồ sơ có subject/parcel.
- Không auto-merge ngoài ngưỡng.

#### D-MDM-03 — Golden views

- `v_mdm_subject_golden`
- `v_mdm_parcel_golden`
- `v_mdm_construction_golden`
- `v_mdm_dossier_360`
- `v_mdm_permit_360`

**Done khi**
- View trả đúng tenant; không lộ PII thừa.

#### D-MDM-04 — API

| Endpoint | Mô tả |
|---|---|
| `GET /api/v1/mdm/dossiers/{id}/links` | Liên kết subject/parcel/construction/permit |
| `GET /api/v1/mdm/search?q=&type=` | Tìm thực thể |
| `POST /api/v1/mdm/links` | Tạo liên kết thủ công |
| `POST /api/v1/mdm/merge` | Gộp (admin) |
| `GET /api/v1/mdm/entities/{type}/{id}` | Chi tiết thực thể |
| `GET /api/v1/mdm/candidates?entity_type=&entity_id=` | Ứng viên trùng |

**Bảo mật**
- Cán bộ (`app:cap-phep:*` trừ chủ đầu tư), `dx:auditor`, `dx:tenant-admin` đọc; merge chỉ `dx:tenant-admin` hoặc vai mới `dx:data-steward`.
- Audit mọi mutation.

**Done khi**
- OpenAPI + integration test tenant isolation.
- B dùng được mock/real.

#### D-MDM-05 — Admin UI

- Component `MdmLinksPanel.vue` trong `components/data/*`.
- Hiển thị liên kết, confidence, issue, nút gộp.
- B thêm vào tab Dữ liệu.

**Done khi**
- Admin gộp được 2 bản ghi; có audit; undo.

### 5.3. D-DQ — Data quality

#### D-DQ-01 — Rule catalog

**20–30 rule**, nhóm:
- Completeness: hồ sơ thiếu CCCD/địa chỉ/thửa đất.
- Validity: CCCD 12 số, số tầng > 0, diện tích > 0.
- Uniqueness: `ma_ho_so`, `ma_cong_trinh`, `public_code`.
- Consistency: giấy phép phải có signed_doc; nghiệm thu phải có hồ sơ.
- Timeliness: dữ liệu quá cũ; chưa đồng bộ.
- Referential: `ho_so_tep.file_id` tồn tại; `moc_nghiem_thu` đúng thứ tự.
- Security: audit chain valid; PII không lộ.

**Schema**
- `core.data_quality_rules`: `code`, `domain`, `severity`, `sql`, `owner`, `enabled`.
- `core.data_quality_runs`: `id`, `started_at`, `finished_at`, `status`.
- `core.data_quality_results`: `run_id`, `rule_code`, `total`, `failed`, `score`, `sample_ids`.
- `core.data_quality_issues`: `id`, `rule_code`, `entity_type`, `entity_id`, `field`, `severity`, `status`, `assigned_to`, `note`.

- Rule chỉ được khai báo trong migration của repo; `web_user` không có quyền ghi `core.data_quality_rules`
  (cột `sql` là câu lệnh chạy thật). Worker chạy bằng vai chỉ đọc, mỗi rule có `statement_timeout`.

**Done khi**
- Rule có test; chạy được trên DB sạch/hiện có.

#### D-DQ-02 — Worker

- `scripts/data_quality_worker.py`:
  - Chạy theo lịch/trigger.
  - Mỗi rule trong transaction/savepoint.
  - Không làm sập toàn bộ khi 1 rule lỗi.
  - Ghi run/result/issue.
- Có chế độ `--dry-run`, `--rule`, `--domain`.

**Done khi**
- Chạy tay + định kỳ; có log; không trả PII.

#### D-DQ-03 — Issue workflow

- Giao issue cho owner.
- Trạng thái: `open`, `in_progress`, `resolved`, `ignored`.
- Ghi chú, audit.
- Notification qua `core.notifications`.

**Done khi**
- Issue có vòng đời; dashboard thấy trạng thái.

#### D-DQ-04 — Dashboard API/UI

| Endpoint | Mô tả |
|---|---|
| `GET /api/v1/data-quality/summary` | Điểm theo domain |
| `GET /api/v1/data-quality/rules` | Danh sách rule |
| `GET /api/v1/data-quality/issues` | Danh sách issue |
| `POST /api/v1/data-quality/issues/{id}/assign` | Giao xử lý |
| `POST /api/v1/data-quality/issues/{id}/resolve` | Đóng |

UI A: `DataQualityPanel.vue`; B thêm tab.

**Done khi**
- Dashboard có score, top rule fail, drill-down; filter domain/severity.

### 5.4. D-CAT — Catalog & lineage

#### D-CAT-01 — Catalog

- `core.data_assets`: asset, schema, owner, classification, freshness, retention.
- `core.data_contracts`: asset, version, JSON Schema, SLA, consumer.
- API `GET /api/v1/catalog/assets`, `/contracts`.
- UI `CatalogPanel.vue` (A), B thêm tab.

**Done khi**
- 100% asset chính có owner/classification.

#### D-CAT-02 — Lineage

Mở rộng `record_lineage_event` cho:
- nộp hồ sơ → tệp
- kiểm tra quy hoạch → kết quả
- cấp giấy phép → signed doc
- nghiệm thu → as-built
- metrics job

API `GET /api/v1/lineage/{entity_type}/{id}`.

**Done khi**
- 100% luồng chính có ít nhất 1 event.
- UI lineage filter theo hồ sơ/giấy phép.

### 5.5. D-360 — 360 view & search

#### D-360-01 — Views

- `v_dossier_360`: hồ sơ + chủ đầu tư + thửa đất + công trình + giấy phép + kiểm tra + tài chính + audit.
- `v_permit_360`: giấy phép + signed doc + public code + hồ sơ + công trình.
- `v_construction_360`: công trình + hồ sơ + phiếu kiểm tra + cảm biến.

**Done khi**
- View trả đúng tenant; B dùng được.

#### D-360-02 — Search

- API `GET /api/v1/search?q=`.
- Tìm: mã hồ sơ, CCCD (hash/mask), tên, điện thoại, địa chỉ, mã công trình, số giấy phép, public code.
- Ranking: exact > prefix > fuzzy.
- Không trả PII thừa.

**Done khi**
- Search 1 từ khóa trả nhóm kết quả; có test.

### 5.6. D-MART — Analytics marts

- 3–5 mart:
  - `mart_dossier_status`
  - `mart_processing_time`
  - `mart_overdue`
  - `mart_acceptance`
  - `mart_dq_score`
- Mỗi mart có: định nghĩa, owner, freshness, lineage.
- API `GET /api/v1/automation/metrics` + dashboard.

**Done khi**
- Số liệu khớp nguồn; có thời điểm tính.

### 5.7. D-OCR — OCR backend

- Service `services/ocr` (A):
  - `POST /api/v1/ocr/extract` (file_id, doc_type)
  - `GET /api/v1/ocr/{id}`
  - `POST /api/v1/ocr/{id}/confirm`
- Pipeline:
  - files service → ClamAV → OCR (Tesseract `vie` trước; PaddleOCR chỉ khi Tesseract không đủ, vì image > 1 GB) → extract fields → confidence → queue.
- Bảng `app_cap_phep.ocr_extractions`:
  - `id`, `tenant`, `file_id`, `doc_type`, `fields jsonb`, `confidence`, `status`, `reviewed_by`, `reviewed_at`, `audit_id`.
- Không auto-commit; H review.

**Done khi**
- 3 loại giấy tờ extract được; confidence; audit.

### 5.8. D-GIS — GIS/địa chỉ (phase sau)

- PostGIS point/geometry; chuẩn hóa địa chỉ; đối chiếu thửa đất.
- Chỉ làm khi có dữ liệu thật.

### 5.9. D-TEST — Test

- Unit: matching, DQ rules, lineage.
- Integration: MDM/DQ/catalog/360/search/OCR.
- Contract: OpenAPI schema.
- Tenant isolation, PII, idempotency.

---

## 6. Track H — Chi tiết

### 6.1. H-WORK — Workspace 360

#### H-WORK-01 — Shell & mock

- Tạo client mock từ `contracts/dh`.
- Flag `VITE_API_MOCK`.
- UI shell giữ nguyên header/tab/palette/glass.

**Done khi**
- UI chạy với mock, không cần backend.

#### H-WORK-02 — 360 view

- Panel/tab 360 trong chi tiết hồ sơ:
  - Chủ đầu tư
  - Thửa đất
  - Công trình
  - Giấy phép
  - Kiểm tra
  - Tài chính
  - Audit
- Cảnh báo DQ/MDM issue.

**Done khi**
- Không phải mở nhiều màn hình; có link chéo.

#### H-WORK-03 — Global search

- Command palette (`Ctrl/Cmd+K`):
  - mã hồ sơ, CCCD, tên, điện thoại, địa chỉ, mã công trình, số giấy phép.
- Nhóm kết quả; keyboard nav.
- Không lộ PII.

**Done khi**
- Tìm được 1 hồ sơ trong ≤ 3 thao tác.

#### H-WORK-04 — Saved filters & bulk actions

- Lưu bộ lọc; bulk assign/remind/export.
- Chọn nhiều, thao tác có xác nhận.
- Empty/loading/error states.

**Done khi**
- Giảm thao tác lặp; audit.

### 6.2. H-AUTO — Autofill & validation

#### H-AUTO-01 — Autofill

- Nguồn: hồ sơ cũ, tài khoản công dân, OCR.
- Điền: họ tên, CCCD, điện thoại, địa chỉ, thửa đất, diện tích, số tầng.
- Human confirm; không ghi đè dữ liệu đã nhập nếu không xác nhận.

**Done khi**
- Giảm nhập lại; có log nguồn.

#### H-AUTO-02 — Validation & draft

- Validate CCCD, điện thoại, diện tích, số tầng, mã địa điểm.
- Draft autosave; reload không mất.
- Cảnh báo trùng.

**Done khi**
- Form không mất dữ liệu; lỗi hiển thị tại chỗ.

### 6.3. H-OCR — Review queue

- Danh sách extraction: file, doc_type, confidence, status.
- So sánh ảnh/PDF với field extract.
- Sửa field; confirm/reject; audit.
- Filter confidence thấp.

**Done khi**
- 100% extraction qua human review; không auto-commit.

### 6.4. H-FIELD — PWA hiện trường

- PWA cho cán bộ kiểm tra:
  - Offline draft
  - Ảnh, GPS
  - Checklist
  - Chữ ký
  - Sync khi có mạng
- Xung đột có thông báo.

**Done khi**
- Tạo 1 phiếu offline, sync thành công.

### 6.5. H-LINK — External lookup UI

- Adapter mock dân cư/đất đai/thuế/PCCC.
- Kết quả lookup cạnh hồ sơ; cán bộ xác nhận.
- Không lưu PII thừa.

**Done khi**
- 1 lookup mock end-to-end; audit.

### 6.6. H-SELF — Self-service công dân

- Theo dõi tiến độ, bổ sung, tải kết quả, QR, đặt lịch, thanh toán (nếu có).
- Trạng thái rõ; thông báo.

**Done khi**
- Công dân tự làm được 1 luồng không cần cán bộ.

### 6.7. H-FLOW — Workflow assistance

- Gợi ý phân công theo tải việc/kỹ năng.
- Cảnh báo SLA, nhắc việc, escalation.
- Nháp thông báo/quyết định từ template + dữ liệu hồ sơ.

**Done khi**
- Giảm thao tác soạn thông báo; cán bộ vẫn duyệt.

### 6.8. H-METRIC — H dashboard

- Tab “Hiệu quả vận hành”:
  - Thao tác thủ công/hồ sơ
  - Handoff
  - Rework
  - Cycle time
  - Self-service
  - Auto-extraction
- So sánh baseline vs hiện tại.

**Done khi**
- Số liệu lấy từ audit/task, không nhập tay.

### 6.9. H-UX — Accessibility & help

- Keyboard, focus, contrast, ARIA.
- Help/tooltip/guided tour ngắn.
- Responsive/mobile.
- Performance.

**Done khi**
- Axe 0 serious/critical; E2E a11y pass.

### 6.10. H-TEST — Test

- Vitest component/composable.
- Playwright role/E2E.
- Visual baseline.
- Không phụ thuộc thứ tự; seed riêng.

---

## 7. Ma trận bao phủ D/H

| Yêu cầu | Task D | Task H | Ghi chú |
|---|---|---|---|
| Mã chuẩn công dân/thửa đất/công trình | D-MDM-01..04 | H-WORK-02 | 360 dùng MDM |
| Chất lượng dữ liệu | D-DQ-01..04 | H-WORK-02, H-METRIC | Cảnh báo + dashboard |
| Catalog/lineage | D-CAT-01..02 | H-WORK-02 | Link từ 360 |
| 360 view | D-360-01 | H-WORK-02 | API + UI |
| Search toàn cục | D-360-02 | H-WORK-03 | API + palette |
| Autofill | D-MDM-04, D-OCR | H-AUTO-01 | Human confirm |
| OCR | D-OCR | H-OCR | Review queue |
| PWA hiện trường | — | H-FIELD | Offline |
| External lookup | D-360-02 (external_refs) | H-LINK | Mock trước |
| Self-service | — | H-SELF | Công dân |
| H metrics | D-MART, D-OCR | H-METRIC | Dashboard |
| A11y/help | — | H-UX | UI |

---

## 8. Thiết kế dữ liệu & API

### 8.1. Bảng chính

#### `core.mdm_subject`
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `subject_id` | uuid PK | |
| `tenant` | text | RLS |
| `cccd_hmac` | text | HMAC-SHA256 với khóa `secrets/mdm-hmac.key`, không plaintext, không hash trần |
| `source` | text | `ho_so`, `ocr`, `import` |
| `confidence` | numeric | 0–1 |
| `merged_into` | uuid | trỏ bản ghi gốc |
| `created_at` | timestamptz | |

#### `core.mdm_parcel`
`parcel_id`, `tenant`, `ma_dinh_danh_dia_diem`, `so_thua`, `to_ban_do`, `dien_tich_m2`, `geom jsonb`, `source`, `confidence`.

#### `core.mdm_construction`
`construction_id`, `tenant`, `ma_cong_trinh`, `parcel_id`, `dia_chi_chuan`, `source`, `confidence`.

#### `core.mdm_dossier_link`
`dossier_id`, `tenant`, `subject_id`, `parcel_id`, `construction_id`, `permit_id`, `confidence`.

#### `core.external_refs`
`tenant`, `system`, `entity_type`, `entity_id`, `external_id`, `confidence`, `last_synced_at`, unique `(tenant, system, entity_type, external_id)`.

#### `core.data_quality_rules`
`code`, `domain`, `severity`, `sql`, `owner`, `enabled`, `created_at`.

#### `core.data_quality_runs`
`id`, `started_at`, `finished_at`, `status`, `triggered_by`.

#### `core.data_quality_results`
`run_id`, `rule_code`, `total`, `failed`, `score`, `sample_ids jsonb`.

#### `core.data_quality_issues`
`id`, `rule_code`, `entity_type`, `entity_id`, `field`, `severity`, `status`, `assigned_to`, `note`, `created_at`, `resolved_at`.

#### `app_cap_phep.ocr_extractions`
`id`, `tenant`, `file_id`, `doc_type`, `fields jsonb`, `confidence`, `status`, `reviewed_by`, `reviewed_at`, `audit_id`.

### 8.2. API tóm tắt

| Method | Endpoint | Auth | Mô tả |
|---|---|---|---|
| GET | `/api/v1/mdm/dossiers/{id}/links` | staff/auditor/admin | 360 links |
| GET | `/api/v1/mdm/search` | staff | tìm entity |
| POST | `/api/v1/mdm/links` | staff/admin | tạo link |
| POST | `/api/v1/mdm/merge` | `dx:tenant-admin`/`dx:data-steward` | gộp |
| GET | `/api/v1/data-quality/summary` | admin/staff | điểm DQ |
| GET | `/api/v1/data-quality/issues` | admin/staff | issue |
| POST | `/api/v1/data-quality/issues/{id}/assign` | admin | giao |
| GET | `/api/v1/catalog/assets` | admin | catalog |
| GET | `/api/v1/catalog/contracts` | admin | contract |
| GET | `/api/v1/lineage/{type}/{id}` | staff/admin | lineage |
| GET | `/api/v1/search` | staff | search |
| GET | `/api/v1/automation/metrics` | lãnh đạo (`app:cap-phep:lanh-dao`)/admin | H metrics |
| POST | `/api/v1/ocr/extract` | staff | OCR |
| POST | `/api/v1/ocr/{id}/confirm` | staff | confirm |

**Lỗi chuẩn**
```json
{"code":"DQ_RULE_FAILED","message":"...","details":{"rule":"..."}}
```

### 8.3. Event/outbox

| Event | Khi nào | Consumer |
|---|---|---|
| `mdm.entity.linked` | link mới | audit, 360 cache |
| `mdm.entity.merged` | gộp | audit, notification |
| `dq.issue.created` | rule fail | notification, dashboard |
| `dq.issue.resolved` | đóng issue | dashboard |
| `ocr.extracted` | OCR xong | review queue |
| `ocr.confirmed` | cán bộ xác nhận | autofill/audit |
| `dossier.autofilled` | autofill | audit |

### 8.4. Feature flags

- Backend: `DH_MDM`, `DH_DQ`, `DH_CATALOG`, `DH_OCR`, `DH_H_METRICS`.
- Frontend: `VITE_DH_MDM`, `VITE_DH_DQ`, `VITE_DH_OCR`, `VITE_DH_PWA`, `VITE_API_MOCK`.

---

## 9. UI/UX blueprint

### 9.1. Screen inventory

| Màn | Owner | Nội dung |
|---|---|---|
| Workspace 360 | B | 360 panel, cảnh báo, link |
| Global search | B | Command palette |
| DQ dashboard | A component + B tab | Score, issue |
| Catalog | A component + B tab | Asset, owner |
| OCR review | B | Extraction + confirm |
| PWA inspection | B | Offline draft |
| Self-service | B | Tiến độ, bổ sung, QR |
| H dashboard | B | Metrics |
| Data admin | A | Link/merge/issue |

### 9.2. Trạng thái UI

- Loading skeleton.
- Empty state có CTA.
- Error state có retry + mã lỗi.
- Warning DQ/MDM.
- Không hiển thị PII đầy đủ.

### 9.3. Role

| Role | 360 | DQ | Catalog | OCR | PWA | H metrics |
|---|---|---|---|---|---|---|
| Công dân | Hồ sơ của mình | — | — | — | — | — |
| Một cửa | Có | Cảnh báo | — | Review | — | — |
| Thẩm định | Có | Cảnh báo | — | Review | — | — |
| Lãnh đạo | Có | Dashboard | — | Review | — | Có |
| Trật tự | Có | Cảnh báo | — | — | Có | — |
| Auditor | Đọc | Đọc | Đọc | — | — | Đọc |
| Admin | Có | Có | Có | Có | — | Có |

---

## 10. Demo & đo lường

### 10.1. Demo flows

1. **360 + MDM:** tìm hồ sơ bằng CCCD → 360 → thấy liên kết công dân/thửa đất/công trình/giấy phép.
2. **DQ:** dashboard score 82 → drill-down rule “thiếu CCCD” → giao issue → sửa → score tăng.
3. **OCR + autofill:** upload đơn → extract → review → autofill form → giảm nhập tay.
4. **PWA:** kiểm tra offline → sync → phiếu xuất hiện trên workspace.
5. **H dashboard:** so sánh baseline vs hiện tại: thao tác/hồ sơ, handoff, rework.

### 10.2. D metrics

- Completeness, validity, uniqueness, consistency, timeliness.
- DQ score theo domain.
- Catalog coverage, lineage coverage.
- Số issue mở/đóng.

### 10.3. H metrics

- Manual actions/hồ sơ (audit `actor_type=user`; thao tác trên task chỉ tính được khi `flow.task_completed` có `ho_so_id`, xem D-MET-00).
- Handoffs/hồ sơ.
- Rework rate.
- Cycle time.
- Self-service ratio.
- Auto-extraction ratio.
- Cost/hồ sơ (TCO).

### 10.4. Cost/TCO

- Baseline: hạ tầng + nhân sự + giấy/scan/lưu trữ + thời gian xử lý.
- Sau: đo lại các chỉ số.
- Chỉ công bố tiết kiệm khi có số.

---

## 11. Testing/QA

### 11.1. Backend

- Unit: matching, DQ rule, lineage.
- Integration: API + DB + RLS.
- Contract: OpenAPI schema + mock.
- Security: tenant isolation, PII, auth.

### 11.2. Frontend

- Vitest: component/composable.
- Playwright: 360, search, DQ, OCR, PWA, self-service.
- Axe: 0 serious/critical.
- Visual: baseline cho màn mới.

### 11.3. CI gates

- Type-check, build.
- Unit + integration.
- E2E smoke.
- Contract test.
- Không merge nếu fail.

---

## 12. Rủi ro

| Rủi ro | Giảm |
|---|---|
| Contract lệch | OpenAPI + mock + contract test |
| B block vì chờ API | Mock + flag |
| Cùng sửa `App.vue` | B owner; A tạo component |
| Migration xung đột | A owner toàn bộ SQL |
| MDM gộp sai | Confidence + manual review + undo |
| DQ false-positive | Warn trước; block rule critical |
| OCR sai | Human review + confidence |
| PII lộ | Mask + RLS + audit |
| Mock kéo dài | Gate 2 bắt buộc API thật |
| Dashboard sai | Mart có owner + lineage + test |
| Scope creep | Không lakehouse/agentic/GIS full |

---

## 13. Gates & thứ tự ghép

### Gate 0 — Contract & ownership
- Đo baseline H/D trên v1.1 (`scripts/dh_baseline.py`).
- A có OpenAPI + mock.
- B review, chốt type.
- `OWNERSHIP.md` xong.

### Gate 1 — Skeleton
- A có migration + API empty/mock.
- B có shell + mock UI.
- CI chạy.

### Gate 2 — Data thật
- A có MDM/DQ/360/search chạy DB.
- B chuyển 360/search/autofill sang API thật.
- Integration test.

### Gate 3 — Automation
- A có OCR/H metrics.
- B có OCR review/PWA/H dashboard.
- E2E.

### Gate 4 — Hoàn thiện
- A có catalog/lineage/data contract.
- B có self-service/a11y/help.
- Đo baseline H/D, TCO.

---

## 14. Definition of Done

### 14.1. Task
- [ ] Code + test.
- [ ] API/contract cập nhật.
- [ ] Audit/PII/RLS.
- [ ] UI state đủ.
- [ ] Docs ngắn.
- [ ] Demo được.

### 14.2. Track D
- [ ] Migration DB sạch/hiện có.
- [ ] DQ score có baseline.
- [ ] 360/search API ổn định.
- [ ] Catalog/lineage có owner.
- [ ] Contract test pass.

### 14.3. Track H
- [ ] UI dùng API thật ở Gate 2.
- [ ] Không tăng thao tác.
- [ ] Human review cho OCR.
- [ ] E2E/axe pass.
- [ ] H metrics dashboard.

### 14.4. Project
- [ ] `dx up` pass.
- [ ] CI xanh.
- [ ] Không PII trong mock/log.
- [ ] Demo 5 flows.
- [ ] TCO baseline.

---

## 15. Việc khởi động ngay

### 15.1. Người A — 10 việc đầu

1. D-GOV-01 inventory 9 domain.
2. D-GOV-02 PII/retention.
3. D-MDM-01 schema migration.
4. D-MDM-02 matching exact.
5. D-MDM-03 backfill script.
6. D-DQ-01 20 rule.
7. D-DQ-02 worker.
8. D-360-01 view 360.
9. P0-03 OpenAPI + mock.
10. D-TEST-01 integration test.
11. D-MET-00 gắn `ho_so_id` vào audit `flow.task_completed`.

### 15.2. Người B — 10 việc đầu

1. P0-04 mock client.
2. H-WORK-01 shell/flag.
3. H-WORK-02 360 UI mock.
4. H-WORK-03 search/palette mock.
5. H-AUTO-01 autofill mock.
6. H-AUTO-02 validation/draft.
7. H-OCR-01 review queue mock.
8. H-FIELD-01 PWA skeleton.
9. H-METRIC-01 dashboard mock.
10. H-UX-01 a11y/help.

---

## 16. Phụ lục

### A. File ownership map

| Khu vực | Owner |
|---|---|
| `core/postgres/20-*` → `24-*` | A |
| `apps/cap-phep/db/migrations/20-dh-ocr.sql` | A |
| `services/construction/routers/{mdm,data_quality,catalog,lineage,search,automation_metrics}.py` | A |
| `services/ocr/*` | A |
| `scripts/{data_quality_worker,mdm_backfill,seed_mdm}.py` | A |
| `contracts/dh/*` | A |
| `apps/bang-dieu-hanh/web/src/components/data/*` | A |
| `core/apisix/routes/dh.yaml` | A |
| `compose.yaml`, `dx.ps1`, `dx.sh` | A |
| `scripts/dh_baseline.py` | A |
| `apps/cap-phep/web/src/views/*` | B |
| `apps/cap-phep/web/src/components/*` (trừ data) | B |
| `apps/cap-phep/web/src/features/*` | B |
| `apps/cap-phep/web/src/api/*` (trừ data client) | B |
| `apps/bang-dieu-hanh/web/src/App.vue` | B |
| `apps/bang-dieu-hanh/web/src/components/{automation,ocr}/*` | B |
| `tests/e2e-ui/*` | B |
| `apps/*/web/tests/*` | B |
| `docs/data/*` | A |
| `docs/ux/*` | B |

### B. Branch & PR

- `feat/data-foundation` (A)
- `feat/human-workspace` (B)
- PR nhỏ theo work package.
- Rebase/merge `develop` trước PR.
- Không merge khi CI đỏ.
- Shared file: owner merge.

### C. Commit convention

```
feat(data): ...
fix(data): ...
test(data): ...
docs(data): ...

feat(ux): ...
fix(ux): ...
test(ux): ...
docs(ux): ...
```

### D. Lệnh kiểm tra

```powershell
# Backend
py -3 -m pytest tests/integration/test_dh_*.py -q
py -3 scripts/data_quality_worker.py --dry-run

# Web cấp phép
cd apps/cap-phep/web
npm run type-check
npm test
npm run build

# Dashboard
cd apps/bang-dieu-hanh/web
npm run type-check
npm test
npm run build

# E2E
py -3 -m pytest tests/e2e-ui -q
```

### E. Tài liệu tham khảo

- `ke_hoach_cai_thien_D_H.md`
- `ke_hoach_cai_thien_toan_dien_2_nguoi.md`
- `cac_mang_xay_dung_co_the_them.md`
- `ke_hoach_chuan_hoa_module_adapter.md`
- `OLP_PMNM_2026_Cam_nang_Mentor.pdf.txt`
- `de-thi-phan-mem-nguon-mo-olp-2026.txt`

---

## 17. Kết luận

**Có, 2 người làm độc lập được** nếu:

1. A làm **D + backend/OCR**.
2. B làm **H + UI/automation**.
3. Contract chốt trước; mock trước; API thật sau.
4. Không ai sửa file của người kia.
5. Merge theo Gate; Gate 2 bắt buộc chuyển API thật.
6. Đo baseline trước khi claim giảm H/tiết kiệm chi phí.

**Thứ tự đúng:**
- Gate 0: contract + ownership.
- Gate 1: skeleton + mock.
- Gate 2: MDM/DQ/360/search thật.
- Gate 3: OCR/PWA/H metrics.
- Gate 4: catalog/lineage/self-service/đo TCO.

**Không làm lúc này:** Agentic AI, full lakehouse, CSDL quốc gia thật, WebGIS toàn thành phố, OCR tất cả giấy tờ.

---

## 18. Thay đổi so với bản đầu (rà soát 2026-11-21)

| # | Chỗ đổi | Lý do |
|---|---|---|
| 1 | `cccd_hash` → `cccd_hmac` (HMAC-SHA256, khóa trong `secrets/`) | CCCD 12 chữ số chỉ có 10¹² giá trị; hash trần dò ngược được trong vài giờ |
| 2 | `core.mdm_subject` bỏ `ho_ten`, `dien_thoai`; MDM vào phạm vi DSAR | Không tạo bản PII thứ hai mà DSAR bỏ sót |
| 3 | Route API D ở `core/apisix/routes/dh.yaml`, owner A | Bản đầu không nhắc APISIX; mỗi nhóm route là một fragment riêng |
| 4 | `compose.yaml`, `dx.*` về A; bỏ ngoại lệ `components/data/*` ở mục 3.2; `api/*` hoàn toàn của B | Bản đầu tự mâu thuẫn (A thêm dịch vụ `ocr` nhưng B giữ compose; `components/data/*` nằm ở bảng điều hành) |
| 5 | Vai dùng tên thật của realm; thêm `dx:data-steward` qua `user_sync.py` | "leader", "data-steward" chưa có trong realm |
| 6 | Rule DQ chỉ khai báo bằng migration, worker chạy vai chỉ đọc | Cột `sql` là câu lệnh chạy thật |
| 7 | OCR bắt đầu bằng Tesseract `vie`, `DH_OCR` mặc định tắt | PaddleOCR làm image > 1 GB, `dx up` chậm |
| 8 | Lineage hiện chỉ có ở ingest; thêm D-MET-00 | Đúng hiện trạng mã; không gắn audit task với hồ sơ thì không đo được thao tác/hồ sơ |
| 9 | Unique `external_refs` thống nhất `(tenant, system, entity_type, external_id)` | Mục 5.2 và 8.1 ghi khác nhau |
| 10 | Đo baseline trên v1.1 trước Gate 1 | Đổi mã trước khi đo thì mất mốc so sánh |
