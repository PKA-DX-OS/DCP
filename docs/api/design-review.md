<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# API thẩm định thiết kế đa bộ môn (5.2)

Bổ sung cho hợp đồng [`contracts/design-review.yaml`](../../contracts/design-review.yaml).
Nghiệp vụ nằm ở lớp app (ADR-005): bảng, RLS và hàm SQL trong
`apps/cap-phep/db/migrations/10-tham-dinh-thiet-ke.sql`, gọi qua PostgREST dưới
`/api/v1/rest/...`; không có dịch vụ riêng.

## Quy ước

- `tenant`, `sub` và vai lấy từ JWT; thân yêu cầu không có trường `tenant`.
- Lỗi PostgREST: `42501` → 403, `22023` → 400, `PT404` → 404, `PT409` → 409.
- Tạo phiên bản/bản vẽ/nhận xét nhận `p_idempotency_key`; gọi lại cùng khóa trả bản ghi cũ.
- Tệp phải được tải trước qua `POST /api/v1/files` với `object_type=ho_so` (hoặc
  `draft.ho_so`) và `object_id` đúng hồ sơ; chỉ nhận tệp `clean`, RPC tự lấy SHA-256/kích thước.
- Mọi thao tác ghi tạo audit và sự kiện outbox `design_review.*`.

## Vai

| Thao tác | Vai |
|---|---|
| Tạo phiên bản, thêm bản vẽ | chủ hồ sơ (`app:cap-phep:chu-dau-tu`) |
| Đánh giá bản vẽ, nhận xét | `app:cap-phep:tham-dinh` |
| Đánh dấu nhận xét đã xử lý | chủ hồ sơ hoặc `app:cap-phep:tham-dinh` |
| Đọc | các vai trên, `app:cap-phep:lanh-dao`, `app:cap-phep:mot-cua`, `app:cap-phep:trat-tu-xd`, `dx:auditor` |

## Endpoint

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/api/v1/rest/bo_mon_thiet_ke` | Danh mục 4 bộ môn, sắp theo `thu_tu` |
| POST | `/api/v1/rest/rpc/tao_phien_ban` | Tạo phiên bản mới; số phiên bản tăng từ 1 |
| POST | `/api/v1/rest/rpc/them_ban_ve` | Thêm bản vẽ vào phiên bản đang soạn |
| POST | `/api/v1/rest/rpc/ds_ban_ve` | Bản vẽ nhóm theo bộ môn; bỏ `p_phien_ban_id` lấy bản mới nhất |
| POST | `/api/v1/rest/rpc/ds_phien_ban` | Các phiên bản kèm bản vẽ để so sánh |
| POST | `/api/v1/rest/rpc/danh_gia_ban_ve` | Thẩm định viên đánh giá `dat`/`khong_dat` |
| POST | `/api/v1/rest/rpc/them_nhan_xet` | Nhận xét theo bộ môn, mức độ `loi`/`canh_bao`/`gop_y` |
| POST | `/api/v1/rest/rpc/xu_ly_nhan_xet` | Đánh dấu nhận xét đã xử lý |
| POST | `/api/v1/rest/rpc/ds_nhan_xet` | Danh sách nhận xét, mới nhất trước, lọc theo bộ môn/mức độ/trạng thái |
| POST | `/api/v1/rest/rpc/trang_thai_tham_dinh` | Tổng hợp trạng thái thiết kế của hồ sơ |

## Trạng thái

- Phiên bản: `dang_soan` → `dang_tham_dinh` → `dat` / `khong_dat`.
- Bản vẽ: `cho_tham_dinh` → `dat` / `khong_dat`.
- Nhận xét: `mo` → `da_xu_ly`.
- Kết luận tổng hợp (`trang_thai_tham_dinh`):
  - `chua_nop`: chưa có phiên bản.
  - `khong_dat`: thiếu bộ môn bắt buộc hoặc có bản vẽ `khong_dat`.
  - `dang_tham_dinh`: còn bản vẽ chờ hoặc còn nhận xét mở.
  - `dat`: đủ bộ môn bắt buộc, mọi bản vẽ đạt, không còn nhận xét mở.

`PCCC` là bộ môn không bắt buộc; ba bộ môn `kien_truc`, `ket_cau`, `mep` bắt buộc.

## Quy trình BPMN

`apps/cap-phep/bpmn/tham-dinh-thiet-ke.bpmn20.xml`:

1. `taskThamDinhBoMon` multi-instance song song theo `bo_mon_can_tham_dinh`.
2. `taskTongHopThietKe` cho lãnh đạo kết luận.
3. Gateway `gwThietKe`: đạt → kết thúc; không đạt → `taskBoSungThietKe` → quay lại
   bước thẩm định cho phiên bản mới.

Biến mặc định `bo_mon_can_tham_dinh` khai báo trong `apps/cap-phep/app.yaml`
(`flow_policies.default_process_variables`).

## Kiểm thử

```powershell
$env:PYTHONPATH="D:\PMNM\DCP\services;D:\PMNM\DCP"
py -3 -m pytest tests/unit/test_design_review_bpmn.py tests/unit/test_design_review_contract.py -q
py -3 -m pytest tests/integration/test_TD01_design_review_rpc.py -q
```
