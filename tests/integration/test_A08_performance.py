# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-TEST-04: performance DB/API với 1000 hồ sơ và 100 vùng quy hoạch."""

import time

import httpx

from tests.integration._auth import GATEWAY_URL, get_token
from tests.integration._ho_so import run_sql


def test_A08_1000_ho_so_100_vung_hieu_nang():
    token = get_token("td.binh")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        run_sql(
            """
            DELETE FROM app_construction.quy_hoach_zone
            WHERE tenant = 'phuong-a' AND ma_zone LIKE 'PERF-Z-%';
            """
        )
        run_sql(
            """
            DELETE FROM app_cap_phep.ho_so
            WHERE tenant = 'phuong-a' AND ma_ho_so LIKE 'PERF-A-%';
            """
        )
        run_sql(
            """
            INSERT INTO app_construction.quy_hoach_zone
                (tenant, ma_zone, ten, loai_zone, geom, status, created_by)
            SELECT 'phuong-a', 'PERF-Z-' || g, 'Vùng hiệu năng ' || g, 'o_do_thi',
                   '{"type":"Polygon","coordinates":[[[106.70,10.77],[106.7001,10.77],[106.7001,10.7701],[106.70,10.7701],[106.70,10.77]]]}'::jsonb,
                   'hieu_luc', 'perf'
            FROM generate_series(1, 100) g;
            """
        )
        run_sql(
            """
            INSERT INTO app_cap_phep.ho_so
                (tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai,
                 dia_chi_cong_trinh, thua_dat, so_tang, dien_tich_san_m2,
                 khu_quan_ly_kien_truc, trang_thai, buoc, han_tong_at)
            SELECT 'phuong-a', 'PERF-A-' || g, 'perf-sub', 'Hiệu năng ' || g,
                   '001099000000', '0900000000', 'Địa chỉ hiệu năng ' || g,
                   'TD-A-01', 2, 120.0, false, 'DA_NOP', 'tiep_nhan', now() + interval '7 days'
            FROM generate_series(1, 1000) g;
            """
        )

        started = time.perf_counter()
        metric = httpx.get(
            f"{GATEWAY_URL}/api/v1/metrics/status-breakdown",
            headers=headers,
            timeout=30.0,
        )
        metric_seconds = time.perf_counter() - started
        assert metric.status_code == 200, metric.text
        assert metric_seconds < 3.0, f"Metric 1000 hồ sơ quá chậm: {metric_seconds:.2f}s"

        started = time.perf_counter()
        check = httpx.post(
            f"{GATEWAY_URL}/api/v1/planning/check",
            headers=headers,
            json={"thua_dat_id": "TD-A-01", "proposal": {"so_tang": 2, "loai_dat": "dat_o"}},
            timeout=30.0,
        )
        check_seconds = time.perf_counter() - started
        assert check.status_code == 200, check.text
        assert check_seconds < 5.0, f"Check 100 vùng quá chậm: {check_seconds:.2f}s"
    finally:
        run_sql(
            """
            DELETE FROM app_construction.quy_hoach_zone
            WHERE tenant = 'phuong-a' AND ma_zone LIKE 'PERF-Z-%';
            """
        )
        run_sql(
            """
            DELETE FROM app_cap_phep.ho_so
            WHERE tenant = 'phuong-a' AND ma_ho_so LIKE 'PERF-A-%';
            """
        )
