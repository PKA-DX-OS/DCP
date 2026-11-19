<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# API Track A — Quy hoạch, nghiệm thu, pháp lý

Dịch vụ: `construction` (FastAPI), tiền tố qua APISIX:

| Tiền tố | Upstream | Ghi chú |
|---|---|---|
| `/api/v1/planning/*` | `construction:8000` | Quy hoạch, pháp lý, thẩm quyền, chia sẻ dữ liệu, phí/lưu trữ |
| `/api/v1/acceptance/*` | `construction:8000` | Nghiệm thu, biên bản, bản vẽ hoàn công |
| `/api/v1/export/*` | `construction:8000` | Xuất Excel/PDF |

Tất cả endpoint yêu cầu Bearer token Keycloak. Tenant lấy từ JWT, không nhận từ body.

## 1. Quy hoạch

| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| GET | `/parcels?bbox=` | cán bộ, thẩm định, lãnh đạo, auditor | Danh sách thửa đất |
| GET | `/parcels/{id hoặc mã}` | như trên | Chi tiết thửa đất |
| GET | `/zones?bbox=` | như trên | Vùng quy hoạch (GeoJSON) |
| GET | `/documents` | như trên | Văn bản/đồ án quy hoạch |
| GET | `/documents/{id hoặc mã}` | như trên | Chi tiết + chỉ tiêu |
| POST | `/check` | một cửa, thẩm định, lãnh đạo | Chạy 10 rule, lưu kết quả, phát outbox `planning.checked` |
| GET | `/results/{ho_so_id}` | cán bộ hoặc chủ hồ sơ | Lịch sử kiểm tra |

Ví dụ `POST /api/v1/planning/check`:

```json
{
  "ho_so_id": "uuid",
  "thua_dat_id": "TD-A-01",
  "proposal": {
    "so_tang": 3,
    "chieu_cao_m": 11,
    "mat_do_xay_dung_pct": 65,
    "far": 1.8,
    "khoang_lui_truoc_m": 3.5,
    "khoang_lui_hong_m": 1.2,
    "khoang_lui_sau_m": 1.2,
    "loai_dat": "dat_o"
  }
}
```

Kết quả mỗi rule: `rule_id`, `name`, `value`, `limit`, `passed`, `severity`
(`error|warning|info`), `reason`, `citation` (số hiệu, điều, khoản, ngày hiệu lực,
`source_url`, `sha256`).

10 rule: R01 trong vùng; R02 mục đích đất; R03 chiều cao; R04 số tầng;
R05 mật độ; R06 FAR; R07 lùi trước; R08 lùi hông/sau; R09 hành lang giao thông;
R10 vùng cấm xây dựng.

## 2. Pháp lý nền

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/legal/documents?q=` | 50 văn bản (seed từ metadata.json) |
| GET | `/legal/documents/{document_id}` | Chi tiết + trích dẫn |
| GET | `/legal/citations?topic=` | Trích dẫn theo chủ đề |
| GET | `/legal/citations/{citation_key}` | Một trích dẫn |
| GET | `/authority/{ho_so_id}` | Kiểm tra thẩm quyền theo Điều 53 và ghi audit |
| POST | `/authority/check` | Xác định cơ quan cấp theo loại/đối tượng/KCN |
| GET | `/location/{mã 12 số}` | Tra CSDL định danh địa điểm, ghi audit khai thác |
| POST | `/location/ho-so/{id}` | Gắn mã định danh 12 số vào hồ sơ |
| POST | `/share/export` | Ghi log chia sẻ dữ liệu (NĐ 278/2025), trạng thái chờ kết nối |
| GET | `/share/logs` | Nhật ký chia sẻ |
| GET | `/fees` | Bảng phí địa phương (chờ văn bản) |
| GET | `/bien-lai` | Biên lai/đối soát |
| GET | `/archive` | Hồ sơ lưu trữ |
| POST | `/archive/{ho_so_id}` | Tạo bản ghi lưu trữ |

Lưu ý: dữ liệu địa điểm, bảng phí và lưu trữ hiện là **khung demo**; trạng thái
`cho_van_ban_dia_phuong` / `cho_ket_noi` phản ánh chưa có văn bản địa phương hoặc
chưa kết nối nền tảng thật.

## 3. Nghiệm thu

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/api/v1/acceptance/{ho_so_id}` | Tổng quan mốc, biên bản, bản vẽ, tiến độ |
| POST | `/api/v1/acceptance/{ho_so_id}/milestones` | Tạo mốc hoặc nghiệm thu lại (version tăng) |
| POST | `/api/v1/acceptance/milestones/{moc_id}/records` | Nộp biên bản, cập nhật kết quả mốc |
| POST | `/api/v1/acceptance/{ho_so_id}/as-built` | Nộp bản vẽ hoàn công |
| GET | `/api/v1/acceptance/{ho_so_id}/history` | Lịch sử nghiệm thu |

Mốc: `mong`, `ket_cau`, `hoan_thien`, `hoan_cong`. Kết quả: `cho_nghiem_thu`,
`dat`, `khong_dat`. Căn cứ hiển thị: NĐ 207/2026/NĐ-CP.

## 4. Xuất báo cáo

| Method | Đường dẫn | Quyền |
|---|---|---|
| GET | `/api/v1/export/dossiers.xlsx` | cán bộ nghiệp vụ |
| GET | `/api/v1/export/metrics.pdf` | cán bộ nghiệp vụ |
| GET | `/api/v1/export/audit.xlsx` | `dx:auditor` |
| GET | `/api/v1/audit/chain?entity=&id=` | `dx:auditor` |
| POST | `/api/v1/audit/verify` | `dx:auditor` |

Mỗi lần xuất đều ghi `core.audit_log` với action `export.*`.

## 5. Bảo mật

- RLS trên mọi bảng `app_construction`: tenant từ JWT.
- Trigger audit bất biến trên bảng quy hoạch/nghiệm thu/phí/lưu trữ.
- Dịch vụ dùng role `web_user` khi đọc dữ liệu nghiệp vụ; ghi audit qua
  `core.record_audit` bằng kết nối dịch vụ.
- Không trả dữ liệu chi tiết cá nhân qua endpoint công khai.
- Không dùng Điều 57 cho nhà ở riêng lẻ; hồ sơ nhà ở riêng lẻ theo Điều 60
  NĐ 217/2026/NĐ-CP.
