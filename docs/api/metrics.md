<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# API Track A — Số liệu, xuất báo cáo, kiểm toán

Các endpoint dưới `/api/v1/metrics/*` cho Track A do dịch vụ `construction`
phục vụ (APISIX ưu tiên 35 cho các đường dẫn chuyên biệt); danh sách metric
tổng hợp chung vẫn do `metrics-api` phục vụ tại `/api/v1/metrics`.

| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/metrics/status-breakdown?month=YYYY-MM` | cán bộ, auditor | Số hồ sơ theo trạng thái trong tháng |
| GET | `/api/v1/metrics/trend?months=12` | cán bộ, auditor | Chuỗi tháng: mới, đã cấp, quá hạn |
| GET | `/api/v1/metrics/workload` | cán bộ, auditor | Tải việc theo cán bộ (assignment) |
| GET | `/api/v1/metrics/planning-fail?month=` | cán bộ, auditor | Số lần fail quy hoạch theo vùng |
| GET | `/api/v1/metrics/acceptance-progress?month=` | cán bộ, auditor | Mốc nghiệm thu theo loại/kết quả |
| GET | `/api/v1/metrics/on-time?months=12` | cán bộ, auditor | Tỷ lệ hồ sơ đã cấp đúng hạn theo tháng |
| GET | `/api/v1/export/dossiers.xlsx` | cán bộ | Xuất hồ sơ |
| GET | `/api/v1/export/metrics.pdf` | cán bộ | Xuất báo cáo tổng hợp |
| GET | `/api/v1/export/audit.xlsx` | `dx:auditor` | Xuất nhật ký kiểm toán |
| GET | `/api/v1/audit/chain?entity=&id=` | `dx:auditor` | Chuỗi băm theo đối tượng |
| POST | `/api/v1/audit/verify` | `dx:auditor` | Xác minh toàn chuỗi tenant |

Mọi lần export ghi audit `export.*`; mọi lần xem chuỗi không ghi audit (chỉ đọc).
Dữ liệu trả về là tổng hợp, không chứa CCCD hay chi tiết tệp.
