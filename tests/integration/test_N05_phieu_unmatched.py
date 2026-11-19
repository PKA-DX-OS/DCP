# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""N-05: cảnh báo từ vị trí không có công trình không sinh phiếu mồ côi hay quy trình, chỉ ghi audit."""

from tests.integration._ho_so import run_sql
from tests.integration._iot import cho, don_iot, get_sensor_token, gui_so_do, ma_site, so_quy_trinh


def test_N05_unmatched_site_does_not_create_orphaned_ticket_or_process():
    site_ma = ma_site("CONG-TRINH-MA")
    try:
        r = gui_so_do(get_sensor_token("phuong-a"), site_ma, {"laeq_dba": 95.0}, device_id="DEV-NOISE-MA")
        assert r.status_code == 201, r.text

        assert cho(lambda: int(run_sql(
            f"SELECT count(*) FROM core.audit_log WHERE action = 'alert.unmatched_site' AND object_id = '{site_ma}';"
        ) or "0") >= 1), f"Phải ghi audit alert.unmatched_site cho {site_ma}"

        mo_coi = run_sql(
            "SELECT count(*) FROM app_cap_phep.phieu_kiem_tra "
            "WHERE cong_trinh_id IS NULL AND created_at >= now() - interval '2 minutes';"
        )
        assert int(mo_coi or "0") == 0, f"Không được tạo phiếu không gắn công trình, thực tế {mo_coi}"
        assert so_quy_trinh(site_ma) == 0, "Không được tạo quy trình hậu kiểm cho vị trí không có công trình"
    finally:
        don_iot(site_ma)
