# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import urllib.request
from .conftest import get_token, GATEWAY_URL


def test_phan_cong_tham_dinh_200():
    token_mc = get_token("mc.thu")
    token_ld = get_token("ld.hoa")

    # 1. Khởi động quy trình cấp phép
    start_req = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/flow/processes/start",
        data=json.dumps({"process_key": "cap-phep", "variables": {}}).encode(),
        headers={"Authorization": f"Bearer {token_mc}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(start_req, timeout=5) as resp:
        assert resp.status in (200, 201)
        proc_data = json.loads(resp.read().decode())
        proc_id = proc_data.get("process_id")
        assert proc_id is not None

    # 2. mc.thu lấy task tiếp nhận và hoàn thành
    tasks_req = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/flow/tasks",
        headers={"Authorization": f"Bearer {token_mc}"},
    )
    with urllib.request.urlopen(tasks_req, timeout=5) as resp:
        assert resp.status == 200
        tasks = json.loads(resp.read().decode()).get("tasks", [])
        mc_task = next((t for t in tasks if t.get("processInstanceId") == proc_id), None)
        assert mc_task is not None

    complete_mc = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/flow/tasks/{mc_task['id']}/complete",
        data=json.dumps({"variables": {"hoSoHopLe": True}}).encode(),
        headers={"Authorization": f"Bearer {token_mc}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(complete_mc, timeout=5) as resp:
        assert resp.status in (200, 204)

    # 3. ld.hoa lấy task phân công và thực hiện phân công
    ld_tasks_req = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/flow/tasks",
        headers={"Authorization": f"Bearer {token_ld}"},
    )
    with urllib.request.urlopen(ld_tasks_req, timeout=5) as resp:
        assert resp.status == 200
        ld_tasks = json.loads(resp.read().decode()).get("tasks", [])
        phan_cong_task = next((t for t in ld_tasks if t.get("processInstanceId") == proc_id), None)
        assert phan_cong_task is not None

    complete_ld = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/flow/tasks/{phan_cong_task['id']}/complete",
        data=json.dumps({"variables": {"nguoiThamDinh": "td.binh", "lanhDaoPhanCong": "ld.hoa"}}).encode(),
        headers={"Authorization": f"Bearer {token_ld}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(complete_ld, timeout=5) as resp:
        assert resp.status in (200, 204)
        resp_data = json.loads(resp.read().decode())
        assert resp_data.get("status") == "success"


def test_khoi_tao_truy_cap_khan_200():
    token_ld = get_token("ld.hoa")
    start_req = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/flow/processes/start",
        data=json.dumps({"process_key": "truy-cap-khan", "variables": {"lyDo": "Xu ly su co mat dien khan cap"}}).encode(),
        headers={"Authorization": f"Bearer {token_ld}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(start_req, timeout=5) as resp:
        assert resp.status in (200, 201)
        data = json.loads(resp.read().decode())
        assert data.get("status") == "started"
        assert data.get("process_id") is not None
