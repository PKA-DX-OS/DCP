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


def test_N05_unmatched_site_does_not_create_orphaned_ticket_or_process():
    token = get_sensor_token("phuong-a")
    ghost_site_id = f"Site:CONG-TRINH-MA-{uuid.uuid4().hex[:8]}"

    # Gửi đo đạc từ thiết bị với site_id không tồn tại trong DB, vượt ngưỡng tiếng ồn
    url = f"{GATEWAY_URL}/api/v1/ingest"
    payload = {
        "tenant": "phuong-a",
        "site_id": ghost_site_id,
        "device_id": "DEV-NOISE-MA",
        "metrics": {"laeq_dba": 95.0},
    }

    with httpx.Client(timeout=5.0) as client:
        resp = client.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 201

    time.sleep(4)

    # 1. Không có dòng mới nào trong app_cap_phep.phieu_kiem_tra có cong_trinh_id IS NULL
    null_phieu_count = int(run_sql(
        "SELECT count(*) FROM app_cap_phep.phieu_kiem_tra WHERE cong_trinh_id IS NULL AND created_at >= now() - interval '1 minute';"
    ) or "0")
    assert null_phieu_count == 0, f"Không được tạo phiếu kiểm tra mồ côi (cong_trinh_id NULL), thực tế có {null_phieu_count}"

    # 2. Không có process instance mới nào được tạo trong Flowable cho site ma
    ghost_instances = get_flowable_instances_count(ghost_site_id)
    assert ghost_instances == 0, f"Không được tạo process Flowable cho site ma, thực tế có {ghost_instances}"

    # 3. Phải có bản ghi audit log với action = 'alert.unmatched_site'
    audit_count = int(run_sql(
        f"SELECT count(*) FROM core.audit_log WHERE action = 'alert.unmatched_site' AND object_id = '{ghost_site_id}';"
    ) or "0")
    assert audit_count >= 1, f"Phải ghi audit log action=alert.unmatched_site cho {ghost_site_id}"
