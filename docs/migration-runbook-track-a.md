<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Runbook migration & dữ liệu demo Track A

## 1. Migration lõi

`core/postgres/` được mount vào `/docker-entrypoint-initdb.d` nên volume trống
tự chạy toàn bộ. Với DB đang chạy, dùng migration runner:

```powershell
cd D:\PMNM\DCP
py -3 scripts/migrate.py --status
py -3 scripts/migrate.py
```

Runner ghi `core.schema_migrations(version, checksum, applied_at)`.
Không sửa tệp đã chạy; tạo tệp mới. Nếu buộc phải chạy lại:

```powershell
py -3 scripts/migrate.py --allow-checksum-change
```

Thứ tự Track A:

| Tệp | Nội dung |
|---|---|
| `10-planning-schema.sql` | Legal refs, thửa đất, vùng, chỉ tiêu, kết quả kiểm tra, định danh địa điểm, log chia sẻ |
| `11-acceptance-schema.sql` | Mốc nghiệm thu, biên bản, bản vẽ hoàn công |
| `12-legal-backend-schema.sql` | Thẩm quyền, phí/lệ phí, lưu trữ |
| `13-construction-seed.sql` | 3 thửa + 2 vùng phuong-a, 1 thửa phuong-b, ma trận thẩm quyền, phí/lưu trữ |
| `14-legal-backend-fix.sql` | Wrapper thẩm quyền cho `web_user` |
| `15-fix-share-citation.sql` | Sửa căn cứ chia sẻ sang NĐ 278/2025 |

## 2. Migration ứng dụng cấp phép

`apps/cap-phep/db/migrations/03-legal-alignment.sql` bổ sung:

- cột `cap_hanh_chinh`, `doi_tuong`, `loai_cong_trinh`, `cap_cong_trinh`,
  `trong_kcn`, `ma_dinh_danh_dia_diem`, `loai_dat`, `quy_hoach_pass`;
- manifest Điều 60: cam kết an toàn công trình liền kề, giấy tờ đất theo Điều 55,
  không đòi quyết định dự án/tổng mặt bằng;
- validation 4 lớp có `severity`: số tầng >5 và diện tích >500 m² chỉ là cảnh báo;
- RPC cập nhật mã định danh địa điểm và kiểm tra thẩm quyền.

Chạy lại toàn bộ gói ứng dụng (idempotent):

```powershell
docker compose exec -T -e DXOS_OWNER_PASSWORD=<secret> construction `
  python /app/scripts/app_manager.py install cap-phep
```

## 3. Seed pháp lý và demo

```powershell
py -3 scripts/seed_legal.py          # 50 văn bản + 24 trích dẫn + RAG chunks
py -3 scripts/seed_hero.py           # CP-HERO-2026-001 và CP-HERO-ACC-2026-001
```

`seed_legal.py` dùng `docker exec` mặc định; thêm `--no-docker` nếu chạy psql trực tiếp.

## 4. APISIX route fragment

```powershell
py -3 scripts/build_apisix.py --csp "http://localhost:8080 http://localhost:8080/auth"
docker compose restart apisix
```

Thêm route mới: tạo `core/apisix/routes/<ten>.yaml` với danh sách `routes:`.
Builder ghép vào `apisix.yaml`, giữ `#END` cho chế độ standalone.

## 5. Kiểm tra sau migration

```powershell
$env:PYTHONPATH="D:\PMNM\DCP\services;D:\PMNM\DCP"
py -3 -m pytest tests/unit -q
py -3 -m pytest tests/integration/test_A01_legal_api.py tests/integration/test_A02_planning_api.py `
  tests/integration/test_A03_acceptance_api.py tests/integration/test_A04_legal_alignment.py `
  tests/integration/test_A05_data_export_audit.py tests/integration/test_A06_flow_lifecycle.py -q
docker compose ps construction
curl http://localhost:8080/api/v1/planning/legal/documents -H "Authorization: Bearer <token>"
```

## 6. Kịch bản demo quy hoạch (60–90 giây)

1. Mở hồ sơ `CP-HERO-2026-001` (5 tầng, 600 m², thửa `TD-A-01`).
2. Tab **Quy hoạch** → `Kiểm tra quy hoạch` với chiều cao 16 m, FAR 2.4.
3. Kết quả: R03–R08 không đạt; bảng hiển thị căn cứ Luật Quy hoạch 47/2024.
4. Sửa số tầng 3, chiều cao 11 m, FAR 1.8, khoảng lùi 3.5/1.2/1.2 → **Đạt**.
5. Mở tab **Nghiệm thu** trên `CP-HERO-ACC-2026-001`: móng v1 không đạt,
   v2 đạt; nộp biên bản; nộp bản vẽ hoàn công.
6. Bàn làm việc hiển thị mã hồ sơ, địa chỉ, hạn, badge quá hạn/sắp hạn.
7. Tab chi tiết có nút **Phê duyệt / Từ chối / Yêu cầu bổ sung** theo đúng việc
   đang chờ và đúng người được giao.

## 7. Xử lý sự cố thường gặp

| Hiện tượng | Nguyên nhân | Xử lý |
|---|---|---|
| `permission denied for schema app_construction_private` | thiếu wrapper public | chạy `14-legal-backend-fix.sql` |
| APISIX 404 toàn bộ | `apisix.yaml` thiếu `#END` | chạy lại `build_apisix.py` |
| `migrate.py` báo checksum đổi | sửa tệp đã chạy | tạo tệp mới hoặc `--allow-checksum-change` |
| Planning 404 thửa đất | hồ sơ dùng số thửa tự do | gắn `TD-A-01`/`TD-A-02` hoặc chọn thửa trong panel |
| Thiếu trích dẫn RAG | `app_manager` xóa chunks khi cài lại | chạy `seed_legal.py` hoặc mount `core/legal` |
