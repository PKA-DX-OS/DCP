<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Quyền sở hữu tệp — đợt cải thiện D & H

Áp dụng cho đợt làm theo [docs/data/ke-hoach-dh.md](docs/data/ke-hoach-dh.md). Mỗi tệp có một
owner. Người còn lại cần đổi tệp đó thì mở PR nhỏ để owner duyệt, không sửa thẳng trên nhánh của mình.

| Track | Người | Nhánh | Tiền tố commit |
| :--- | :--- | :--- | :--- |
| D — Data Foundation | Duy Anh (`caduoiduianh`) | `feat/data-foundation` | `feat(data)`, `fix(data)`, `test(data)`, `docs(data)` |
| H — Human Workspace | Hoàng (`5coinin1`) | `feat/human-workspace` | `feat(ux)`, `fix(ux)`, `test(ux)`, `docs(ux)` |

## Track D (Duy Anh)

| Khu vực | Ghi chú |
| :--- | :--- |
| `core/postgres/20-*` đến `24-*` | Migration mới; không sửa migration cũ |
| `apps/cap-phep/db/migrations/20-dh-*.sql` | Bảng OCR của app |
| `services/construction/routers/{mdm,data_quality,catalog,lineage,search,automation_metrics}.py` | API D |
| `services/ocr/*` | Dịch vụ OCR |
| `services/flow` (phần ghi audit) | Gắn `ho_so_id` vào `flow.task_completed` (D-MET-00) |
| `services/dxos_core/user_sync.py` (phần vai) | Vai mới, ví dụ `dx:data-steward` |
| `core/apisix/routes/dh.yaml` | Route của API D |
| `compose.yaml`, `dx.ps1`, `dx.sh` | Dịch vụ backend, migration |
| `scripts/{dh_baseline,data_quality_worker,mdm_backfill,seed_mdm}.py` | |
| `contracts/dh/*` | Hợp đồng API và mock; H duyệt, đổi phá vỡ thì tăng phiên bản |
| `apps/bang-dieu-hanh/web/src/components/data/*` | Panel dữ liệu; H gắn vào tab |
| `docs/data/*` | |
| `tests/integration/test_dh_*`, `tests/unit/test_dh_*`, `tests/unit/test_data_*` | |

## Track H (Hoàng)

| Khu vực | Ghi chú |
| :--- | :--- |
| `apps/cap-phep/web/src/{views,components,features,api,composables}/*` | Client API sinh từ `contracts/dh` |
| `apps/cap-phep/web/src/features/registry.ts` | |
| `apps/bang-dieu-hanh/web/src/App.vue` | Thêm tab cho panel của D |
| `apps/bang-dieu-hanh/web/src/components/{automation,ocr}/*` | |
| `apps/cap-phep/app.yaml` | D đề xuất qua PR |
| `apps/*/web/tests/*`, `tests/e2e-ui/*` | D cung cấp seed/fixture |
| `docs/ux/*` | |

## Tệp dùng chung

| Tệp | Owner | Quy tắc |
| :--- | :--- | :--- |
| `README.md` | H | D cập nhật mục dữ liệu qua PR nhỏ |
| `CHANGELOG.md` | Người phát hành | Mỗi PR thêm dòng vào `[Chưa phát hành]` |
| `.github/workflows/*` | D | H đề xuất qua PR |

## Quy tắc

1. Nhánh làm việc tạo từ `develop`; cập nhật `develop` trước khi mở PR.
2. PR nhỏ theo gói việc, ghi `Refs: <mã gói>` trong commit; CI xanh mới merge.
3. Không commit thẳng vào `develop` hoặc `main`.
4. Không đưa dữ liệu cá nhân thật vào mock, fixture, log.
5. Ghép theo cổng (Gate 0 → 4) như mục 13 của kế hoạch.
