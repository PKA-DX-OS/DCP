# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import subprocess
import time
import uuid
import httpx
from tests.integration.conftest import GATEWAY_URL
from tests.integration.test_Z05_ingest_auth import get_sensor_token


def run_sql(sql: str) -> str:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", sql]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout.strip()


def test_Z06_no_hardcoded_thresholds_in_services():
    # grep -rnE "70\.0|55\.0|100\.0|50\.0" services/
    cmd = ["grep", "-rnE", "70\\.0|55\\.0|100\\.0|50\\.0", "services/"]
    res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    # Loại trừ tính toán phần trăm trong metrics-api nếu có
    lines = [
        ln for ln in res.stdout.strip().splitlines()
        if ln and "metrics-api" not in ln and "#" not in ln
    ]
    assert len(lines) == 0, f"Vẫn còn số ngưỡng hardcode trong services: {lines}"


def test_Z06_iot_sensor_spike_triggers_hau_kiem():
    token = get_sensor_token("phuong-a")
    suffix = uuid.uuid4().hex[:8]
    site_id = f"CT-TEST-HK-{suffix}"
    entity_id = f"urn:ngsi-ld:Site:{site_id}"

    # Setup công trình mẫu
    run_sql(f"""
    INSERT INTO app_cap_phep.cong_trinh (tenant, ma_cong_trinh, entity_id, dia_chi)
    VALUES ('phuong-a', '{site_id}', '{entity_id}', 'So 100 Pho Test')
    ON CONFLICT (ma_cong_trinh) DO NOTHING;
    """)

    url = f"{GATEWAY_URL}/api/v1/ingest"
    payload = {
        "tenant": "phuong-a",
        "site_id": site_id,
        "device_id": "DEV-NOISE-85",
        "metrics": {"laeq_dba": 85.0},
    }

    # Gửi 5 lần vượt ngưỡng liên tiếp
    for _ in range(5):
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 201

    # Chờ outbox relay và consumer xử lý trong tối đa 15 giây
    time.sleep(4)

    # 1. Kiểm tra có sự kiện alert.threshold trong outbox
    outbox_count = int(run_sql("SELECT count(*) FROM core.outbox WHERE tenant='phuong-a' AND topic='alert.threshold';") or "0")
    assert outbox_count >= 1, "Phải có sự kiện alert.threshold trong core.outbox"

    # 2. Kiểm tra chỉ có ĐÚNG 1 phiếu kiểm tra được tạo (chống trùng)
    phieu_count = int(run_sql(f"SELECT count(*) FROM app_cap_phep.phieu_kiem_tra pk JOIN app_cap_phep.cong_trinh ct ON ct.id = pk.cong_trinh_id WHERE ct.ma_cong_trinh = '{site_id}';") or "0")
    assert phieu_count == 1, f"Kỳ vọng đúng 1 phiếu kiểm tra cho 5 lần gửi liên tiếp, thực tế: {phieu_count}"

    # 3. Kiểm tra thông tin phiếu kiểm tra
    phieu_info = run_sql(f"SELECT chi_so || '|' || nguong FROM app_cap_phep.phieu_kiem_tra pk JOIN app_cap_phep.cong_trinh ct ON ct.id = pk.cong_trinh_id WHERE ct.ma_cong_trinh = '{site_id}' LIMIT 1;")
    assert "laeq_dba|70" in phieu_info or "laeq_dba|55" in phieu_info
