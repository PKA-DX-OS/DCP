#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Nạp hồ sơ "hero" phục vụ demo Track A (A-PLAN-08, A-ACC-05).

- CP-HERO-2026-001: hồ sơ 5 tầng tại TD-A-01 để demo quy hoạch fail → sửa 3 tầng pass.
- CP-HERO-ACC-2026-001: hồ sơ đã cấp phép, có mốc móng fail → khắc phục → đạt.
- Idempotent theo mã hồ sơ; không xóa dữ liệu khác.

Chạy:
    py -3 scripts/seed_hero.py
    py -3 scripts/seed_hero.py --no-docker --psql "C:\\...\\psql.exe"
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

-- 1. Hồ sơ hero quy hoạch: 5 tầng, 600 m2, tại TD-A-01.
INSERT INTO app_cap_phep.ho_so
    (tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai, dia_chi_cong_trinh,
     thua_dat, so_tang, dien_tich_san_m2, khu_quan_ly_kien_truc, trang_thai, buoc,
     han_tong_at, doi_tuong, loai_cong_trinh, ma_dinh_danh_dia_diem, loai_dat)
SELECT
    'phuong-a', 'CP-HERO-2026-001', u.id, 'Nguyễn Văn Minh', '001099000001', '0901234567',
    'Số 18 Đường Hòa Bình, phường A', 'TD-A-01', 5, 600.0, false, 'TIEP_NHAN', 'tham_dinh',
    now() + interval '7 days', 'ho_gia_dinh_ca_nhan', 'nha_o_rieng_le', '790101000001', 'dat_o'
FROM core.users_directory u
WHERE u.tenant = 'phuong-a' AND u.username = 'cdt.minh'
ON CONFLICT (ma_ho_so) DO UPDATE
SET ho_ten = EXCLUDED.ho_ten, dia_chi_cong_trinh = EXCLUDED.dia_chi_cong_trinh,
    thua_dat = EXCLUDED.thua_dat, so_tang = EXCLUDED.so_tang,
    dien_tich_san_m2 = EXCLUDED.dien_tich_san_m2, trang_thai = EXCLUDED.trang_thai,
    buoc = EXCLUDED.buoc, doi_tuong = EXCLUDED.doi_tuong,
    loai_cong_trinh = EXCLUDED.loai_cong_trinh,
    ma_dinh_danh_dia_diem = EXCLUDED.ma_dinh_danh_dia_diem,
    loai_dat = EXCLUDED.loai_dat, updated_at = now();

-- 2. Hồ sơ hero nghiệm thu: đã cấp phép.
INSERT INTO app_cap_phep.ho_so
    (tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai, dia_chi_cong_trinh,
     thua_dat, so_tang, dien_tich_san_m2, khu_quan_ly_kien_truc, trang_thai, buoc,
     han_tong_at, doi_tuong, loai_cong_trinh, ma_dinh_danh_dia_diem, loai_dat)
SELECT
    'phuong-a', 'CP-HERO-ACC-2026-001', u.id, 'Trần Thị Hồng', '001099000002', '0902345678',
    'Số 20 Đường Hòa Bình, phường A', 'TD-A-02', 3, 420.0, true, 'DA_CAP', 'da_cap',
    now() + interval '7 days', 'ho_gia_dinh_ca_nhan', 'nha_o_rieng_le', '790101000002', 'dat_o'
FROM core.users_directory u
WHERE u.tenant = 'phuong-a' AND u.username = 'cdt.minh'
ON CONFLICT (ma_ho_so) DO UPDATE
SET ho_ten = EXCLUDED.ho_ten, dia_chi_cong_trinh = EXCLUDED.dia_chi_cong_trinh,
    thua_dat = EXCLUDED.thua_dat, so_tang = EXCLUDED.so_tang,
    dien_tich_san_m2 = EXCLUDED.dien_tich_san_m2, trang_thai = EXCLUDED.trang_thai,
    buoc = EXCLUDED.buoc, ma_dinh_danh_dia_diem = EXCLUDED.ma_dinh_danh_dia_diem,
    updated_at = now();

-- 3. Mốc nghiệm thu hero: móng fail (v1) → đạt (v2), kết cấu đạt.
WITH h AS (SELECT id FROM app_cap_phep.ho_so WHERE ma_ho_so = 'CP-HERO-ACC-2026-001')
INSERT INTO app_construction.moc_nghiem_thu
    (tenant, ho_so_id, loai_moc, version, ngay_nghiem_thu, ket_qua, nguoi_thuc_hien, ghi_chu, created_by)
SELECT 'phuong-a', h.id, v.loai, v.version, v.ngay::date, v.ket_qua, 'td.binh', v.ghi_chu, 'seed'
FROM h, (VALUES
    ('mong', 1, '2026-10-01', 'khong_dat', 'Cao độ đáy móng thấp hơn thiết kế 12 cm'),
    ('mong', 2, '2026-10-05', 'dat', 'Đã khắc phục và nghiệm thu lại'),
    ('ket_cau', 1, '2026-10-20', 'dat', 'Kết cấu đạt yêu cầu')
) AS v(loai, version, ngay, ket_qua, ghi_chu)
ON CONFLICT (tenant, ho_so_id, loai_moc, version) DO UPDATE
SET ket_qua = EXCLUDED.ket_qua, ghi_chu = EXCLUDED.ghi_chu, updated_at = now();

INSERT INTO app_construction.bien_ban_nghiem_thu
    (tenant, moc_id, so_bien_ban, ket_luan, nguoi_ky, created_by)
SELECT 'phuong-a', m.id, 'BB-HERO-MONG-01', 'Yêu cầu khắc phục cao độ móng', 'td.binh', 'seed'
FROM app_construction.moc_nghiem_thu m
JOIN app_cap_phep.ho_so h ON h.id = m.ho_so_id
WHERE h.ma_ho_so = 'CP-HERO-ACC-2026-001' AND m.loai_moc = 'mong' AND m.version = 1
ON CONFLICT (tenant, so_bien_ban) DO UPDATE SET ket_luan = EXCLUDED.ket_luan;

INSERT INTO app_construction.bien_ban_nghiem_thu
    (tenant, moc_id, so_bien_ban, ket_luan, nguoi_ky, created_by)
SELECT 'phuong-a', m.id, 'BB-HERO-MONG-02', 'Móng đạt yêu cầu sau khắc phục', 'td.binh', 'seed'
FROM app_construction.moc_nghiem_thu m
JOIN app_cap_phep.ho_so h ON h.id = m.ho_so_id
WHERE h.ma_ho_so = 'CP-HERO-ACC-2026-001' AND m.loai_moc = 'mong' AND m.version = 2
ON CONFLICT (tenant, so_bien_ban) DO UPDATE SET ket_luan = EXCLUDED.ket_luan;

COMMIT;
"""


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Nạp hồ sơ hero Track A")
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
    print("[PASS] Đã nạp hồ sơ hero: CP-HERO-2026-001 (5 tầng) và CP-HERO-ACC-2026-001 (nghiệm thu).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
