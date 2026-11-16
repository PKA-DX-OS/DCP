# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
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


def get_flowable_instances_count(business_key: str) -> int:
    cmd = [
        "docker", "exec", "dxos-flow", "sh", "-c",
        f'curl -s -u "$FLOWABLE_USER:$FLOWABLE_PASSWORD" "$FLOWABLE_URL/service/runtime/process-instances?businessKey={business_key}"'
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        data = json.loads(res.stdout.strip())
        return len(data.get("data", []))
    return 0


def test_N04_alert_deduplication_persistent_and_database_level():
    token = get_sensor_token("phuong-a")
    site_id = f"CT-N04-{uuid.uuid4().hex[:8]}"
    entity_id = f"urn:ngsi-ld:Site:{site_id}"

    # 1. Tạo công trình hợp lệ trong CSDL
    run_sql(f"""
    INSERT INTO app_cap_phep.cong_trinh (tenant, ma_cong_trinh, entity_id, dia_chi)
    VALUES ('phuong-a', '{site_id}', '{entity_id}', 'So 4 Pho N04')
    ON CONFLICT (ma_cong_trinh) DO NOTHING;
    """)

    url = f"{GATEWAY_URL}/api/v1/ingest"
    payload = {
        "tenant": "phuong-a",
        "site_id": site_id,
        "device_id": "DEV-N04",
        "metrics": {"laeq_dba": 88.0},
    }

    # 2. Bắn 2 sự kiện cảnh báo giống nhau liên tiếp (trong 1 giây)
    with httpx.Client(timeout=5.0) as client:
        r1 = client.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
        assert r1.status_code == 201
        r2 = client.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 201

    # Chờ outbox-relay xử lý
    time.sleep(4)

    # 3. Kiểm tra đúng 1 phiếu kiểm tra được sinh
    count1 = int(run_sql(
        f"SELECT count(*) FROM app_cap_phep.phieu_kiem_tra pk JOIN app_cap_phep.cong_trinh ct ON ct.id = pk.cong_trinh_id WHERE ct.ma_cong_trinh = '{site_id}';"
    ) or "0")
    assert count1 == 1, f"Kỳ vọng đúng 1 phiếu kiểm tra sau 2 cảnh báo, thực tế: {count1}"

    # 4. Restart dịch vụ ingest để chứng minh không phụ thuộc RAM của ingest
    subprocess.run(["docker", "restart", "dxos-ingest"], check=True)
    time.sleep(3)

    # 5. Bắn tiếp cảnh báo thứ 3 ngay sau đó
    with httpx.Client(timeout=5.0) as client:
        r3 = client.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
        assert r3.status_code == 201

    time.sleep(4)

    # 6. Kiểm tra CSDL vẫn chỉ có đúng 1 phiếu kiểm tra duy nhất
    count2 = int(run_sql(
        f"SELECT count(*) FROM app_cap_phep.phieu_kiem_tra pk JOIN app_cap_phep.cong_trinh ct ON ct.id = pk.cong_trinh_id WHERE ct.ma_cong_trinh = '{site_id}';"
    ) or "0")
    assert count2 == 1, f"Kỳ vọng vẫn chỉ 1 phiếu kiểm tra sau khi restart ingest, thực tế: {count2}"

    # 7. Kiểm tra số process instance trong Flowable ứng với businessKey: đúng 1 instance
    # Q-05: businessKey được đặt theo phieu_id
    phieu_id = run_sql(
        f"SELECT pk.id FROM app_cap_phep.phieu_kiem_tra pk JOIN app_cap_phep.cong_trinh ct ON ct.id = pk.cong_trinh_id WHERE ct.ma_cong_trinh = '{site_id}';"
    )
    flow_instances = get_flowable_instances_count(str(phieu_id)) or get_flowable_instances_count(site_id)
    assert flow_instances == 1, f"Kỳ vọng đúng 1 process instance Flowable cho {site_id} / phieu {phieu_id}, thực tế: {flow_instances}"
