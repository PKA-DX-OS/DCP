# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import httpx

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8080")
ROOT = Path(__file__).resolve().parents[2]


def get_sensor_token(tenant: str = "phuong-a") -> str:
    """Lấy token client_credentials cho cảm biến.

    Giữ cục bộ trong test A08 để commit không phụ thuộc vào conftest (C14)
    và test_Z05 (C13) chưa có ở thời điểm này.
    """
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


def run_sql(sql: str) -> str:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", sql]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout.strip()


def get_flowable_instances(business_key: str):
    cmd = [
        "docker", "exec", "dxos-flow", "sh", "-c",
        f'curl -s -u "$FLOWABLE_USER:$FLOWABLE_PASSWORD" "$FLOWABLE_URL/service/runtime/process-instances?businessKey={business_key}"'
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        try:
            data = json.loads(res.stdout.strip())
            return data.get("data", [])
        except Exception:
            return []
    return []


def get_flowable_tasks(business_key: str):
    cmd = [
        "docker", "exec", "dxos-flow", "sh", "-c",
        f'curl -s -u "$FLOWABLE_USER:$FLOWABLE_PASSWORD" "$FLOWABLE_URL/service/runtime/tasks?processInstanceBusinessKey={business_key}"'
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        try:
            data = json.loads(res.stdout.strip())
            return data.get("data", [])
        except Exception:
            return []
    return []


def test_P03_alert_flowable_recovery_and_dead_letter():
    token = get_sensor_token("phuong-a")
    site_id = f"CT-P03-{uuid.uuid4().hex[:8]}"
    entity_id = f"urn:ngsi-ld:Site:{site_id}"

    # Setup công trình hợp lệ
    run_sql(f"""
    INSERT INTO app_cap_phep.cong_trinh (tenant, ma_cong_trinh, entity_id, dia_chi)
    VALUES ('phuong-a', '{site_id}', '{entity_id}', 'So 3 Pho P03')
    ON CONFLICT (ma_cong_trinh) DO NOTHING;
    """)

    url = f"{GATEWAY_URL}/api/v1/ingest"
    payload = {
        "tenant": "phuong-a",
        "site_id": site_id,
        "device_id": "DEV-P03",
        "metrics": {"laeq_dba": 88.0},
    }

    try:
        # 1. Dừng flowable, gửi 1 cảnh báo vượt ngưỡng
        subprocess.run(["docker", "stop", "dxos-flowable"], check=True)
        time.sleep(2)

        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 201, f"Ingest cảnh báo phải 201: {resp.status_code}"

        # Chờ outbox relay gọi on_alert và gặp lỗi khi gọi flowable
        time.sleep(5)

        # Kiểm tra: Có phiếu kiểm tra nhưng chưa có quy trình (process_instance_id IS NULL)
        phieu_row = run_sql(f"""
        SELECT pk.id, pk.process_instance_id
        FROM app_cap_phep.phieu_kiem_tra pk
        JOIN app_cap_phep.cong_trinh ct ON ct.id = pk.cong_trinh_id
        WHERE ct.ma_cong_trinh = '{site_id}';
        """)
        assert phieu_row, f"Phải có phiếu kiểm tra được tạo cho {site_id}"
        phieu_parts = phieu_row.split("|")
        phieu_id = phieu_parts[0]
        proc_inst_id = phieu_parts[1] if len(phieu_parts) > 1 else ""
        assert not proc_inst_id, f"Khi Flowable down, phiếu chưa được có quy trình: {proc_inst_id}"

        # 2. Khởi động lại Flowable, chờ tối đa 120s để outbox relay thử lại (nak retry)
        subprocess.run(["docker", "start", "dxos-flowable"], check=True)

        # Chờ Flowable container sẵn sàng phục vụ
        time.sleep(10)

        # Polling tối đa 120s chờ phiếu có process_instance_id
        start_time = time.time()
        final_proc_id = ""
        while time.time() - start_time < 120:
            val = run_sql(f"SELECT process_instance_id FROM app_cap_phep.phieu_kiem_tra WHERE id = '{phieu_id}';")
            if val:
                final_proc_id = val
                break
            time.sleep(3)

        assert final_proc_id, f"Sau khi Flowable khôi phục trong 120s, phiếu {phieu_id} phải được gán process_instance_id"

        # Kiểm tra: đúng 1 quy trình hau-kiem (Q-05: businessKey = phieu_id)
        instances = get_flowable_instances(str(phieu_id)) or get_flowable_instances(site_id)
        assert len(instances) == 1, f"Kỳ vọng đúng 1 process instance hau-kiem, thực tế: {len(instances)}"
        assert instances[0].get("processDefinitionKey") == "hau-kiem" or "hau-kiem" in instances[0].get("processDefinitionId", "")

        # Kiểm tra: đúng 1 nhiệm vụ taskKiemTraHienTruong
        tasks = get_flowable_tasks(str(phieu_id)) or get_flowable_tasks(site_id)
        assert len(tasks) == 1, f"Kỳ vọng đúng 1 user task mở, thực tế: {len(tasks)}"
        assert tasks[0].get("taskDefinitionKey") == "taskKiemTraHienTruong"

        # 3. Thử nghiệm Dead-Letter: khi Flowable lỗi suốt 5 lần giao -> có audit alert.dead_letter
        site_dl = f"CT-DL-{uuid.uuid4().hex[:8]}"
        entity_dl = f"urn:ngsi-ld:Site:{site_dl}"
        run_sql(f"""
        INSERT INTO app_cap_phep.cong_trinh (tenant, ma_cong_trinh, entity_id, dia_chi)
        VALUES ('phuong-a', '{site_dl}', '{entity_dl}', 'So 3 DL Pho')
        ON CONFLICT (ma_cong_trinh) DO NOTHING;
        """)

        # Dừng Flowable để gây lỗi liên tục
        subprocess.run(["docker", "stop", "dxos-flowable"], check=True)
        time.sleep(2)

        with httpx.Client(timeout=5.0) as client:
            resp_dl = client.post(
                url,
                json={"tenant": "phuong-a", "site_id": site_dl, "device_id": "DEV-DL", "metrics": {"laeq_dba": 95.0}},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp_dl.status_code == 201

        # Chờ relay giao đủ 5 lần và ghi audit alert.dead_letter (tối đa 150s)
        dl_start = time.time()
        found_dead_letter = False
        while time.time() - dl_start < 150:
            dl_count = run_sql(f"SELECT count(*) FROM core.audit_log WHERE action = 'alert.dead_letter' AND object_id = '{site_dl}';")
            if int(dl_count or "0") > 0:
                found_dead_letter = True
                break
            time.sleep(5)

        assert found_dead_letter, f"Kỳ vọng có audit alert.dead_letter cho site {site_dl} sau 5 lần giao thất bại"

    finally:
        subprocess.run(["docker", "start", "dxos-flowable"])
        for _ in range(30):
            try:
                with httpx.Client(timeout=2.0) as fl_c:
                    r = fl_c.get("http://localhost:8082/flowable-rest/actuator/health")
                    if r.status_code == 200:
                        break
            except Exception:
                pass
            time.sleep(1)
        run_sql(f"""
        DELETE FROM app_cap_phep.phieu_kiem_tra WHERE cong_trinh_id IN (SELECT id FROM app_cap_phep.cong_trinh WHERE ma_cong_trinh IN ('{site_id}', '{site_dl if "site_dl" in locals() else ""}'));
        DELETE FROM app_cap_phep.cong_trinh WHERE ma_cong_trinh IN ('{site_id}', '{site_dl if "site_dl" in locals() else ""}');
        """)
