# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Helper cho test IoT -> cảnh báo -> hậu kiểm (C13).

Token cảm biến lấy bằng client_credentials của client `dxos-sensor-<tenant>`; secret đọc từ
secrets/sensor-<tenant>-secret.txt do `dx init` sinh. Thiếu tệp thì test fail rõ ràng, không
dùng giá trị mặc định.
"""

import time
import uuid
from typing import Callable

import httpx

from tests.integration._auth import GATEWAY_URL, ROOT
from tests.integration._ho_so import flowable, run_psql, run_sql


def get_sensor_token(tenant: str = "phuong-a") -> str:
    secret_file = ROOT / "secrets" / f"sensor-{tenant}-secret.txt"
    assert secret_file.exists(), f"Thiếu {secret_file.relative_to(ROOT)} (chạy `dx init`)"
    resp = httpx.post(
        f"{GATEWAY_URL}/auth/realms/dxos/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": f"dxos-sensor-{tenant}",
            "client_secret": secret_file.read_text(encoding="utf-8").strip(),
        },
        timeout=10.0,
    )
    assert resp.status_code == 200, f"Không lấy được token cảm biến {tenant}: {resp.status_code}"
    return resp.json()["access_token"]


def gui_so_do(token: str, site_id: str, metrics: dict, tenant: str = "phuong-a", device_id: str = "DEV-TEST") -> httpx.Response:
    return httpx.post(
        f"{GATEWAY_URL}/api/v1/ingest",
        json={"tenant": tenant, "site_id": site_id, "device_id": device_id, "metrics": metrics},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )


def cho(dieu_kien: Callable[[], bool], timeout: float = 20.0, buoc: float = 1.0) -> bool:
    """Chờ tới khi điều kiện đúng hoặc hết giờ (outbox-relay xử lý bất đồng bộ)."""
    het = time.time() + timeout
    while time.time() < het:
        if dieu_kien():
            return True
        time.sleep(buoc)
    return dieu_kien()


def ma_site(tien_to: str) -> str:
    return f"{tien_to}-{uuid.uuid4().hex[:8]}"


def tao_cong_trinh(site_id: str, tenant: str = "phuong-a") -> None:
    run_sql(
        "INSERT INTO app_cap_phep.cong_trinh (tenant, ma_cong_trinh, entity_id, dia_chi) "
        f"VALUES ('{tenant}', '{site_id}', 'urn:ngsi-ld:Site:{site_id}', 'Công trình kiểm thử {site_id}') "
        "ON CONFLICT (ma_cong_trinh) DO NOTHING;"
    )


def phieu_cua(site_id: str) -> list[str]:
    out = run_sql(
        "SELECT pk.id FROM app_cap_phep.phieu_kiem_tra pk "
        "JOIN app_cap_phep.cong_trinh ct ON ct.id = pk.cong_trinh_id "
        f"WHERE ct.ma_cong_trinh = '{site_id}' ORDER BY pk.created_at;"
    )
    return [x for x in out.splitlines() if x.strip()]


def so_quy_trinh(business_key: str) -> int:
    with flowable() as fl:
        r = fl.get("/service/runtime/process-instances", params={"businessKey": business_key})
        assert r.status_code == 200, f"Flowable lỗi {r.status_code}"
        return len(r.json().get("data", []))


def don_iot(site_id: str, tenant: str = "phuong-a") -> None:
    """Dọn dữ liệu test của một công trình: quy trình hậu kiểm, phiếu, công trình, số đo."""
    for pid in phieu_cua(site_id):
        try:
            with flowable() as fl:
                for p in fl.get("/service/runtime/process-instances", params={"businessKey": pid}).json().get("data", []):
                    fl.delete(f"/service/runtime/process-instances/{p['id']}")
        except Exception:
            pass
    entity = f"urn:ngsi-ld:Site:{site_id}"
    run_psql(
        "DELETE FROM app_cap_phep.phieu_kiem_tra WHERE cong_trinh_id IN "
        f"(SELECT id FROM app_cap_phep.cong_trinh WHERE ma_cong_trinh = '{site_id}');"
        f"DELETE FROM app_cap_phep.cong_trinh WHERE ma_cong_trinh = '{site_id}';"
        f"DELETE FROM core.timeseries WHERE tenant = '{tenant}' AND entity_id = '{entity}';"
        f"DELETE FROM core.entity_state WHERE tenant = '{tenant}' AND entity_id = '{entity}';"
    )
