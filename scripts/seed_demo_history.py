#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Nạp 12 tháng dữ liệu hồ sơ demo cho dashboard (B-UX-08/B-UX-01).

- Chỉ tạo/xóa các mã `CP-DEMO-HIST-*` của phường A; không đụng dữ liệu khác.
- Phân bố trạng thái để donut/line/bar có dữ liệu; gán việc cho td.binh/td.cuong/mc.thu.
- Idempotent: chạy lại xóa bộ cũ rồi nạp lại.

Chạy:
    py -3 scripts/seed_demo_history.py
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, Exception):
        pass

ROOT = Path(__file__).resolve().parent.parent

SQL = """
BEGIN;

DELETE FROM core.assignments
WHERE tenant = 'phuong-a'
  AND object_type = 'ho_so'
  AND object_id IN (
      SELECT id FROM app_cap_phep.ho_so WHERE ma_ho_so LIKE 'CP-DEMO-HIST-%'
  );
DELETE FROM app_cap_phep.ho_so WHERE ma_ho_so LIKE 'CP-DEMO-HIST-%';

WITH nguoi AS (
    SELECT username,
           (SELECT id FROM core.users_directory u WHERE u.tenant = 'phuong-a' AND u.username = x.username) AS sub
    FROM (VALUES ('cdt.minh'), ('cdt.lan')) AS x(username)
), thang AS (
    SELECT g AS offset_thang FROM generate_series(0, 11) g
), ho_ten AS (
    SELECT * FROM (VALUES
        (1, 'Nguyễn Văn An'),
        (2, 'Trần Thị Bích'),
        (3, 'Lê Quang Huy'),
        (4, 'Phạm Thu Hà'),
        (5, 'Hoàng Đức Long'),
        (6, 'Vũ Minh Ngọc')
    ) AS x(idx, ten)
), dong AS (
    SELECT t.offset_thang, h.idx, h.ten,
           CASE h.idx
               WHEN 1 THEN 'DA_CAP'
               WHEN 2 THEN 'DA_CAP'
               WHEN 3 THEN 'DANG_THAM_DINH'
               WHEN 4 THEN 'DA_NOP'
               WHEN 5 THEN 'CAN_BO_SUNG'
               ELSE 'TU_CHOI'
           END AS trang_thai,
           CASE h.idx
               WHEN 1 THEN 'hoan_thanh'
               WHEN 2 THEN 'hoan_thanh'
               WHEN 3 THEN 'tham_dinh'
               WHEN 4 THEN 'tiep_nhan'
               WHEN 5 THEN 'bo_sung'
               ELSE 'tu_choi'
           END AS buoc
    FROM thang t CROSS JOIN ho_ten h
)
INSERT INTO app_cap_phep.ho_so
    (tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai,
     dia_chi_cong_trinh, thua_dat, so_tang, dien_tich_san_m2,
     khu_quan_ly_kien_truc, trang_thai, buoc, created_at, updated_at,
     han_tong_at, qua_han, doi_tuong, loai_cong_trinh, loai_dat)
SELECT
    'phuong-a',
    'CP-DEMO-HIST-' || d.offset_thang || '-' || d.idx,
    n.sub,
    d.ten,
    '001099' || lpad((d.offset_thang * 10 + d.idx)::text, 6, '0'),
    '090' || lpad((d.offset_thang * 10 + d.idx)::text, 7, '0'),
    'Số ' || d.idx || ' Đường ' || (ARRAY['Hòa Bình', 'Trần Phú', 'Lê Lợi', 'Nguyễn Trãi', 'Hai Bà Trưng', 'Lý Thường Kiệt'])[d.idx] || ', phường A',
    'TD-HIST-' || d.offset_thang || '-' || d.idx,
    2 + (d.idx % 4),
    90.0 + d.idx * 18,
    d.idx IN (1, 2),
    d.trang_thai,
    d.buoc,
    date_trunc('month', now()) - (d.offset_thang || ' months')::interval + (d.idx || ' days')::interval,
    date_trunc('month', now()) - (d.offset_thang || ' months')::interval + (d.idx || ' days')::interval,
    date_trunc('month', now()) - (d.offset_thang || ' months')::interval + (d.idx + 30 || ' days')::interval,
    (d.offset_thang > 1 AND d.idx IN (3, 5)),
    'ho_gia_dinh_ca_nhan',
    'nha_o_rieng_le',
    'dat_o'
FROM dong d
JOIN nguoi n ON n.username = CASE WHEN d.idx % 2 = 0 THEN 'cdt.lan' ELSE 'cdt.minh' END;

INSERT INTO core.assignments (tenant, object_type, object_id, user_sub, role, active)
SELECT 'phuong-a', 'ho_so', h.id,
       CASE (row_number() OVER (ORDER BY h.created_at)) % 3
           WHEN 0 THEN (SELECT id::text FROM core.users_directory WHERE tenant = 'phuong-a' AND username = 'td.binh')
           WHEN 1 THEN (SELECT id::text FROM core.users_directory WHERE tenant = 'phuong-a' AND username = 'td.cuong')
           ELSE (SELECT id::text FROM core.users_directory WHERE tenant = 'phuong-a' AND username = 'mc.thu')
       END,
       'tham_dinh', true
FROM app_cap_phep.ho_so h
WHERE h.ma_ho_so LIKE 'CP-DEMO-HIST-%'
  AND h.trang_thai NOT IN ('DA_CAP', 'TU_CHOI');

COMMIT;
"""


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Nạp 12 tháng dữ liệu hồ sơ demo")
    parser.add_argument("--no-docker", action="store_true")
    parser.add_argument("--psql")
    parser.add_argument("--container", default="dxos-postgres")
    parser.add_argument("--user", default="dxos_owner")
    parser.add_argument("--database", default="dxos")
    args = parser.parse_args(argv)

    if args.no_docker:
        psql = args.psql or shutil.which("psql")
        if not psql:
            raise SystemExit("Không tìm thấy psql.")
        cmd = [psql, "-U", args.user, "-d", args.database, "-v", "ON_ERROR_STOP=1", "-f", "-"]
    else:
        cmd = ["docker", "exec", "-i", args.container, "psql", "-U", args.user, "-d", args.database, "-v", "ON_ERROR_STOP=1", "-f", "-"]

    res = subprocess.run(cmd, input=SQL, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        print(res.stderr or res.stdout, file=sys.stderr)
        return 1
    print("[PASS] Đã nạp 72 hồ sơ demo 12 tháng (CP-DEMO-HIST-*) và assignments.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
