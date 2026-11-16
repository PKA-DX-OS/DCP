# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import subprocess
import httpx
from tests.integration.conftest import GATEWAY_URL, get_token, ROOT


def get_sensor_token(tenant: str = "phuong-a") -> str:
    secret_file = ROOT / "secrets" / f"sensor-{tenant}-secret.txt"
    if secret_file.exists():
        secret = secret_file.read_text(encoding="utf-8").strip()
    else:
        secret = "dxos_dev_sensor_phuong_a_secret_2026" if tenant == "phuong-a" else "dxos_dev_sensor_phuong_b_secret_2026"

    token_url = f"{GATEWAY_URL}/auth/realms/dxos/protocol/openid-connect/token"
    client_id = f"dxos-sensor-{tenant}"
    with httpx.Client(timeout=5.0) as client:
        resp = client.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": secret,
            },
        )
        assert resp.status_code == 200, f"Lỗi lấy token sensor {client_id}: {resp.text}"
        return resp.json()["access_token"]


def count_timeseries(tenant: str, site_id: str) -> int:
    cmd = [
        "docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c",
        f"SELECT count(*) FROM core.timeseries WHERE tenant = '{tenant}' AND entity_id = 'urn:ngsi-ld:Site:{site_id}';"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return int(res.stdout.strip()) if res.stdout.strip().isdigit() else 0


def test_Z05_ingest_no_token_returns_401():
    url = f"{GATEWAY_URL}/api/v1/ingest"
    payload = {
        "tenant": "phuong-a",
        "site_id": "SITE-TEST-401",
        "device_id": "DEV-401",
        "metrics": {"laeq_dba": 60.0},
    }
    with httpx.Client(timeout=5.0) as client:
        resp = client.post(url, json=payload)
        assert resp.status_code == 401, f"Không có token phải bị từ chối 401 tại gateway, nhận được: {resp.status_code}"


def test_Z05_ingest_cdt_token_returns_403():
    cdt_token = get_token("cdt.minh")
    url = f"{GATEWAY_URL}/api/v1/ingest"
    payload = {
        "tenant": "phuong-a",
        "site_id": "SITE-TEST-CDT",
        "device_id": "DEV-CDT",
        "metrics": {"laeq_dba": 60.0},
    }
    with httpx.Client(timeout=5.0) as client:
        resp = client.post(url, json=payload, headers={"Authorization": f"Bearer {cdt_token}"})
        assert resp.status_code == 403, f"Token chủ đầu tư (không có dx:device/dx:service) phải bị từ chối 403, nhận được: {resp.status_code}"


def test_Z05_ingest_tenant_spoofing_returns_403_and_no_data():
    sensor_a_token = get_sensor_token("phuong-a")
    site_b = "SITE-SPOOF-B"
    before_b = count_timeseries("phuong-b", site_b)

    url = f"{GATEWAY_URL}/api/v1/ingest"
    payload = {
        "tenant": "phuong-b",  # Giả mạo gửi cho tenant B
        "site_id": site_b,
        "device_id": "DEV-SPOOF",
        "metrics": {"laeq_dba": 60.0},
    }
    with httpx.Client(timeout=5.0) as client:
        resp = client.post(url, json=payload, headers={"Authorization": f"Bearer {sensor_a_token}"})
        assert resp.status_code == 403, f"Gửi sai tenant phải bị từ chối 403, nhận được: {resp.status_code}"

    after_b = count_timeseries("phuong-b", site_b)
    assert after_b == before_b, "Dữ liệu giả mạo tenant không được phép lọt vào core.timeseries!"


def test_Z05_ingest_valid_sensor_token_returns_201():
    sensor_a_token = get_sensor_token("phuong-a")
    site_a = "SITE-VALID-A"
    before_a = count_timeseries("phuong-a", site_a)

    url = f"{GATEWAY_URL}/api/v1/ingest"
    payload = {
        "tenant": "phuong-a",
        "site_id": site_a,
        "device_id": "DEV-VALID",
        "metrics": {"laeq_dba": 60.0, "pm10": 35.0},
    }
    with httpx.Client(timeout=5.0) as client:
        resp = client.post(url, json=payload, headers={"Authorization": f"Bearer {sensor_a_token}"})
        assert resp.status_code == 201, f"Token sensor hợp lệ phải được ghi nhận 201: {resp.text}"

    after_a = count_timeseries("phuong-a", site_a)
    assert after_a >= before_a + 2, "Phải ghi nhận đủ 2 bản ghi metrics mới vào core.timeseries"
