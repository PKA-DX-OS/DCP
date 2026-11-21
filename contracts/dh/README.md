<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Hợp đồng API D & H (v1)

Hợp đồng giữa Track D (backend, Duy Anh) và Track H (giao diện, Hoàng) theo
[docs/data/ke-hoach-dh.md](../../docs/data/ke-hoach-dh.md). Track D viết và giữ các tệp này;
Track H duyệt rồi sinh type/client từ đây và dựng giao diện bằng mock trong khi chờ API thật.

| Tệp | Đường dẫn | Gói việc |
| :--- | :--- | :--- |
| `mdm.yaml` | `/api/v1/mdm/*` (liên kết, 360 hồ sơ, gộp) | D-MDM-04, D-360-01 / H-WORK-02 |
| `search.yaml` | `/api/v1/search` | D-360-02 / H-WORK-03 |
| `data-quality.yaml` | `/api/v1/data-quality/*` | D-DQ-04 / H-WORK-02, H-METRIC |
| `catalog.yaml` | `/api/v1/catalog/*` | D-CAT-01 |
| `lineage.yaml` | `/api/v1/lineage/*` | D-CAT-02 |
| `ocr.yaml` | `/api/v1/ocr/*` | D-OCR / H-OCR |
| `automation.yaml` | `/api/v1/automation/metrics` | D-MART / H-METRIC |

## Quy ước chung

- Địa bàn (`tenant`), người gọi (`sub`) và vai lấy từ JWT; thân yêu cầu không có trường tenant.
- Lỗi: `{code, message, details}` (schema `Loi`). Mã HTTP: 400 tham số sai, 401 chưa đăng nhập,
  403 sai vai, 404 không thấy (kể cả khi thuộc phường khác), 409 trạng thái không cho phép, 422 dữ liệu
  không hợp lệ.
- Danh sách dài phân trang bằng `page` (từ 1) và `page_size` (mặc định 20, tối đa 100); kết quả có
  `items`, `page`, `page_size`, `total`.
- POST tạo hoặc đổi trạng thái nhận header `Idempotency-Key`: gọi lại cùng khóa trả kết quả cũ.
- Mọi thao tác ghi tạo dòng audit.
- Dữ liệu cá nhân trả theo dạng che: `cccd_mask` (`0012******90`), `dien_thoai_mask` (`090****567`).
  CCCD đầy đủ không bao giờ có trong phản hồi; tìm theo CCCD so khớp bằng HMAC ở máy chủ.
- Đổi không tương thích ngược thì tăng `/api/v2`; thêm trường tùy chọn thì giữ v1.

## Mock

`mocks/<tệp>.json` có một mục cho mỗi `operationId`: `{"status": <mã>, "body": <phản hồi>}`.
Toàn bộ là dữ liệu bịa, không có thông tin của người thật. `tests/unit/test_dh_contracts.py` kiểm
mỗi mock khớp schema phản hồi và mỗi thao tác đều có mock.
