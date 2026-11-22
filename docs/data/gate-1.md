<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Track D — Gate 1

Trạng thái theo mục 13 của [kế hoạch D & H](ke-hoach-dh.md): migration và API theo
[contracts/dh](../../contracts/dh/README.md) chạy qua APISIX tới DB, có RLS, không còn 404.
Dữ liệu là dữ liệu thật của stack; phần chưa có dữ liệu trả rỗng hoặc null đúng hợp đồng.

## Đã có

| Gói | Thành phần | Ghi chú |
| :--- | :--- | :--- |
| D-GOV-01/02 | `core/postgres/20-data-governance.sql`, `apps/cap-phep/db/migrations/24-dh-danh-muc.sql` | 9 miền có chủ quản; tài sản lõi và tài sản cấp phép có phân loại, thời hạn lưu trữ, cột cá nhân |
| D-MDM-01 | `core/postgres/21-mdm.sql`, `24-external-refs.sql` | CCCD chỉ lưu HMAC (khóa `secrets/mdm-hmac.key`, `scripts/dh_khoa.py` sinh khi `dx up`) |
| D-MDM-02 | `services/construction/dh_mdm.py`, `scripts/mdm_backfill.py` | Khớp đúng theo HMAC CCCD, mã định danh địa điểm hoặc số thửa/tờ, mã công trình; backfill tự động khi `dx up`; khớp gần đúng tạo ứng viên trùng; không ghi đè liên kết thủ công |
| D-MDM-04, D-360-01 | `routers/mdm.py` | Liên kết, 360, tìm thực thể, chi tiết, ứng viên trùng, tạo liên kết, gộp, hoàn tác (Idempotency-Key) |
| D-360-02 | `routers/search.py` | Nhóm hồ sơ, chủ đầu tư, thửa đất, công trình, giấy phép; CCCD đủ 12 số, điện thoại từ 9 số; audit chỉ ghi độ dài chuỗi |
| D-DQ-01..04 | `core/postgres/22-data-quality.sql`, `scripts/data_quality_worker.py`, `routers/data_quality.py`, `components/data/DataQualityPanel.vue` | 22 rule; worker chạy giao dịch chỉ đọc từng rule, `dx up` chạy một lần; vấn đề có vòng đời mở, đang xử lý, đã đóng, bỏ qua; dashboard điểm/vấn đề, data admin đóng/bỏ qua |
| D-CAT-01/02 | `core/postgres/23-catalog-lineage.sql`, `apps/cap-phep/db/migrations/25-lineage-nghiep-vu.sql`, `routers/catalog.py`, `routers/lineage.py`, `components/data/CatalogPanel.vue` | Danh mục, cột, hợp đồng dữ liệu; dashboard chỉ đọc cho kiểm toán/quản trị, lọc miền/phân loại, xem cột và hợp đồng; phả hệ theo `facets.entity` (nộp hồ sơ, kiểm tra quy hoạch, cấp giấy phép, nghiệm thu) và theo job |
| D-MART | `routers/automation_metrics.py`, `scripts/dh_baseline.py --save` | Cùng định nghĩa với `dh_baseline.py`; mốc đọc từ `core.h_baseline`; đã lưu v1.1 cho `phuong-a`/`phuong-b` ngày 2026-11-22 |
| D-OCR | `services/ocr`, `apps/cap-phep/db/migrations/26-ocr-extractions.sql` | Dịch vụ OCR và hàng chờ duyệt (`/api/v1/ocr/*`, bật bằng `DH_OCR`); trích xuất 3 loại giấy tờ, RLS cách ly theo phường, không ghi PII vào audit log |

Route: `core/apisix/routes/dh.yaml`. Lỗi trả `{code, message, details}` như hợp đồng (lỗi quyền
do DB từ chối vẫn trả 403 dạng chung của lõi).

## Chạy tay

```bash
docker compose --profile tools run --rm tools scripts/data_quality_worker.py            # chấm lại DQ
docker compose --profile tools run --rm tools scripts/data_quality_worker.py --dry-run  # chỉ đếm
python scripts/dh_baseline.py --tenant phuong-a --save v1.1                              # lưu mốc H (chạy trên bản v1.1)
```

## Chưa có (Gate sau)

- Kiểm toán viên chưa xem được 360 hồ sơ vì RLS của `app_cap_phep.ho_so` không cho vai này; cần quyết
  định chính sách trước khi mở.
- Mốc H v1.1 đã lưu cho `phuong-a`/`phuong-b`; cần đo lại khi dữ liệu hoặc quy trình thay đổi.
