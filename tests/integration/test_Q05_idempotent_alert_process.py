# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy cho lỗi Q-05:
- Outbox-relay mở quy trình Flowable cho cảnh báo với businessKey = <phieu_id>.
- Trước khi gọi Flowable mở mới: hỏi Flowable xem đã có quy trình nào có businessKey đó chưa.
- Khi on_process_started ném lỗi ở lần giao đầu tiên (TEST_FAIL_ON_PROCESS_STARTED=1):
  thông điệp được giao lại (redelivered) và Flowable chỉ có DUY NHẤT 1 quy trình cho phieu_id.
"""

import json
from pathlib import Path
import subprocess
import time
import uuid
import httpx
from tests.integration.conftest import GATEWAY_URL
from tests.integration.test_Z05_ingest_auth import get_sensor_token


def run_sql(sql: str) -> str:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", sql]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def get_flowable_instances_by_phieu(phieu_id: str):
    cmd = [
        "docker", "exec", "dxos-flow", "sh", "-c",
        f'curl -s -u "$FLOWABLE_USER:$FLOWABLE_PASSWORD" "$FLOWABLE_URL/service/runtime/process-instances?businessKey={phieu_id}"'
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        try:
            data = json.loads(res.stdout.strip())
            return data.get("data", [])
        except Exception:
            return []
    return []


def test_Q05_idempotent_alert_process_on_retry():
    token = get_sensor_token("phuong-a")
    site_id = f"CT-Q05-{uuid.uuid4().hex[:8]}"
    entity_id = f"urn:ngsi-ld:Site:{site_id}"

    # 1. Tạo công trình giám sát
    run_sql(f"""
    INSERT INTO app_cap_phep.cong_trinh (tenant, ma_cong_trinh, entity_id, dia_chi)
    VALUES ('phuong-a', '{site_id}', '{entity_id}', 'Số 5 Phố Q05')
    ON CONFLICT (ma_cong_trinh) DO NOTHING;
    """)

    # 2. Cấu hình container outbox-relay chạy với TEST_FAIL_ON_PROCESS_STARTED=1 và ALERT_RETRY_DELAY=2
    # Dùng docker exec hoặc khởi động lại container outbox-relay với biến môi trường thử nghiệm
    env_file = Path(".env")
    assert env_file.exists(), "Tệp .env phải tồn tại để chạy kiểm thử"

    # Gửi cảnh báo vượt ngưỡng qua Ingest API
    url = f"{GATEWAY_URL}/api/v1/ingest"
    payload = {
        "tenant": "phuong-a",
        "site_id": site_id,
        "device_id": "DEV-Q05",
        "metrics": {"laeq_dba": 89.5},
    }

    try:
        # Bật cờ kiểm thử giả lập lỗi on_process_started trong dxos-outbox-relay (Q-05)
        subprocess.run(["docker", "exec", "dxos-outbox-relay", "touch", "/tmp/test_fail_on_process_started"], check=True)

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 201, f"Ingest cảnh báo phải trả về 201 Created: {resp.status_code}"

        # Chờ phiếu kiểm tra được tạo trong CSDL
        phieu_id = None
        for _ in range(20):
            val = run_sql(f"""
            SELECT pk.id::text
            FROM app_cap_phep.phieu_kiem_tra pk
            JOIN app_cap_phep.cong_trinh ct ON ct.id = pk.cong_trinh_id
            WHERE ct.ma_cong_trinh = '{site_id}';
            """)
            if val:
                phieu_id = val.strip()
                break
            time.sleep(1)

        assert phieu_id, f"Phải tạo được phiếu kiểm tra cho công trình {site_id}"

        # Chờ quy trình được gán process_instance_id sau khi retry thành công (tối đa 30 giây)
        proc_inst_id = None
        for _ in range(30):
            val = run_sql(f"SELECT process_instance_id FROM app_cap_phep.phieu_kiem_tra WHERE id = '{phieu_id}';")
            if val and val.strip():
                proc_inst_id = val.strip()
                break
            time.sleep(1)

        assert proc_inst_id, f"Phiếu {phieu_id} phải được gán process_instance_id sau khi thử lại"

        # 3. YÊU CẦU CỐT LÕI Q-05: Flowable chỉ có DUY NHẤT MỘT quy trình với businessKey = phieu_id
        instances = get_flowable_instances_by_phieu(phieu_id)
        assert len(instances) == 1, (
            f"Kỳ vọng Flowable chỉ có duy nhất 1 process instance cho phieu_id {phieu_id}, "
            f"thực tế nhận {len(instances)}: {[i.get('id') for i in instances]}"
        )
        assert instances[0]["id"] == proc_inst_id, (
            f"ID quy trình trong Flowable ({instances[0]['id']}) phải khớp với phiếu kiểm tra ({proc_inst_id})"
        )

    finally:
        # Tắt cờ kiểm thử
        subprocess.run(["docker", "exec", "dxos-outbox-relay", "rm", "-f", "/tmp/test_fail_on_process_started"], check=False)

        # Dọn dẹp dữ liệu kiểm thử
        run_sql(f"""
        DELETE FROM app_cap_phep.phieu_kiem_tra WHERE cong_trinh_id IN (SELECT id FROM app_cap_phep.cong_trinh WHERE ma_cong_trinh = '{site_id}');
        DELETE FROM app_cap_phep.cong_trinh WHERE ma_cong_trinh = '{site_id}';
        """)
