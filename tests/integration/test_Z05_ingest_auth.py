# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Z-05: xác thực ingest: không token 401, sai vai 403, giả mạo tenant 403 không ghi dữ liệu, cảm biến hợp lệ 201."""

import httpx

from tests.integration._auth import GATEWAY_URL, get_token
from tests.integration._ho_so import run_sql
from tests.integration._iot import don_iot, get_sensor_token, gui_so_do, ma_site


def dem_so_do(tenant: str, site_id: str) -> int:
    return int(run_sql(
        f"SELECT count(*) FROM core.timeseries WHERE tenant = '{tenant}' AND entity_id = 'urn:ngsi-ld:Site:{site_id}';"
    ) or "0")


def test_Z05_ingest_no_token_returns_401():
    resp = httpx.post(
        f"{GATEWAY_URL}/api/v1/ingest",
        json={"tenant": "phuong-a", "site_id": "SITE-401", "device_id": "DEV-401", "metrics": {"laeq_dba": 60.0}},
        timeout=10.0,
    )
    assert resp.status_code == 401, f"Không token phải 401, nhận {resp.status_code}"


def test_Z05_ingest_cdt_token_returns_403():
    resp = gui_so_do(get_token("cdt.minh"), "SITE-CDT", {"laeq_dba": 60.0})
    assert resp.status_code == 403, f"Token chủ đầu tư phải 403, nhận {resp.status_code}"


def test_Z05_ingest_tenant_spoofing_returns_403_and_no_data():
    site_b = ma_site("SITE-SPOOF-B")
    try:
        resp = gui_so_do(get_sensor_token("phuong-a"), site_b, {"laeq_dba": 60.0}, tenant="phuong-b")
        assert resp.status_code == 403, f"Gửi sai tenant phải 403, nhận {resp.status_code}"
        assert dem_so_do("phuong-b", site_b) == 0, "Dữ liệu giả mạo tenant không được lọt vào core.timeseries"
        audit = run_sql(
            "SELECT count(*) FROM core.audit_log WHERE action = 'ingest.tenant_mismatch' "
            "AND detail->>'site_id' = '" + site_b + "';"
        )
        assert int(audit or "0") >= 1, "Phải ghi audit ingest.tenant_mismatch"
    finally:
        don_iot(site_b, tenant="phuong-b")


def test_Z05_ingest_valid_sensor_token_returns_201():
    site_a = ma_site("SITE-VALID-A")
    try:
        # 50 dBA dưới cả ngưỡng ban đêm (55) lẫn ban ngày (70): test chạy giờ nào cũng không sinh cảnh báo
        resp = gui_so_do(get_sensor_token("phuong-a"), site_a, {"laeq_dba": 50.0, "pm10": 35.0})
        assert resp.status_code == 201, f"Cảm biến hợp lệ phải 201: {resp.status_code} {resp.text}"
        assert resp.json()["alerts"] == [], "Số đo trong ngưỡng không được tạo cảnh báo"
        assert dem_so_do("phuong-a", site_a) == 2, "Phải ghi đủ 2 số đo vào core.timeseries"
        state = run_sql(
            f"SELECT attrs->'laeq_dba'->>'value' FROM core.entity_state WHERE entity_id = 'urn:ngsi-ld:Site:{site_a}';"
        )
        assert state == "50.0", f"core.entity_state phải cập nhật số đo mới nhất, nhận {state!r}"
    finally:
        don_iot(site_a)
