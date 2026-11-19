# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""V3-06: hạn xác nhận và hạn xử lý DSAR tính theo ngày làm việc (core.add_business_days)."""

import httpx
import pytest

from tests.integration.conftest import GATEWAY_URL, run_psql, run_sql


@pytest.mark.parametrize("loai, ngay_xu_ly", [("access", 10), ("rectify", 10), ("withdraw", 15), ("restrict", 15), ("erase", 20)])
def test_V3_06_dsar_due_dates_calculation(token, don_dep, loai, ngay_xu_ly):
    r = httpx.post(f"{GATEWAY_URL}/api/v1/rest/rpc/gui_yeu_cau_dsar",
                   headers={"Authorization": f"Bearer {token('cdt.minh')}"},
                   json={"p_type": loai, "p_legal_basis_note": "Kiểm thử V3-06"}, timeout=10.0)
    assert r.status_code == 200, r.text
    data = r.json()
    don_dep(lambda: run_psql(f"DELETE FROM core.dsar_requests WHERE id = '{data['id']}';"))

    exp = run_sql(
        "SELECT to_char(core.add_business_days(received_at, 2), 'YYYY-MM-DD') || '|' || "
        f"to_char(core.add_business_days(received_at, {ngay_xu_ly}), 'YYYY-MM-DD') "
        f"FROM core.dsar_requests WHERE id = '{data['id']}';"
    )
    exp_ack, exp_due = exp.split("|")
    assert str(data["ack_due_at"])[:10] == exp_ack, f"{loai}: hạn xác nhận phải +2 ngày làm việc ({exp_ack}), nhận {data['ack_due_at']}"
    assert str(data["due_at"])[:10] == exp_due, f"{loai}: hạn xử lý phải +{ngay_xu_ly} ngày làm việc ({exp_due}), nhận {data['due_at']}"


def test_V3_06_loai_khong_hop_le_bi_tu_choi(token):
    r = httpx.post(f"{GATEWAY_URL}/api/v1/rest/rpc/gui_yeu_cau_dsar",
                   headers={"Authorization": f"Bearer {token('cdt.minh')}"}, json={"p_type": "erasure"}, timeout=10.0)
    assert r.status_code == 400, f"Loại DSAR lạ phải 400 (22023), nhận {r.status_code}"
