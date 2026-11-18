# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""N-04: chống trùng cảnh báo nằm ở CSDL, không ở RAM của ingest: khởi động lại ingest vẫn chỉ một phiếu.

Test khởi động lại container dxos-ingest.
"""

import subprocess
import time

from tests.integration._iot import cho, don_iot, get_sensor_token, gui_so_do, ma_site, phieu_cua, so_quy_trinh, tao_cong_trinh


def _cho_ingest_san_sang() -> None:
    """Chờ healthcheck của dxos-ingest về healthy (gọi qua gateway không đo được: APISIX trả 401 trước khi tới dịch vụ)."""
    for _ in range(60):
        r = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", "dxos-ingest"],
            capture_output=True, text=True,
        )
        if r.stdout.strip() == "healthy":
            return
        time.sleep(1)
    raise AssertionError("dxos-ingest không về healthy trong 60 giây sau khi khởi động lại")


def test_N04_alert_deduplication_persistent_and_database_level():
    token = get_sensor_token("phuong-a")
    site_id = ma_site("CT-N04")
    tao_cong_trinh(site_id)
    try:
        for _ in range(2):
            r = gui_so_do(token, site_id, {"laeq_dba": 88.0}, device_id="DEV-N04")
            assert r.status_code == 201, r.text
        assert cho(lambda: len(phieu_cua(site_id)) >= 1), "Cảnh báo phải sinh phiếu kiểm tra"
        time.sleep(3)
        assert len(phieu_cua(site_id)) == 1, f"2 cảnh báo liên tiếp chỉ được 1 phiếu, thực tế {len(phieu_cua(site_id))}"

        subprocess.run(["docker", "restart", "dxos-ingest"], check=True, capture_output=True)
        _cho_ingest_san_sang()

        r = gui_so_do(token, site_id, {"laeq_dba": 88.0}, device_id="DEV-N04")
        assert r.status_code == 201, r.text
        time.sleep(5)
        phieu = phieu_cua(site_id)
        assert len(phieu) == 1, f"Sau khi khởi động lại ingest vẫn chỉ được 1 phiếu, thực tế {len(phieu)}"
        assert so_quy_trinh(phieu[0]) == 1, "Đúng một quy trình hậu kiểm cho phiếu"
    finally:
        don_iot(site_id)
