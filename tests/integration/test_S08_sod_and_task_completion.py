# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import urllib.request
import urllib.error
from tests.integration.conftest import get_token, GATEWAY_URL


def test_S08_citizen_cannot_complete_workflow_tasks():
    token_minh = get_token("cdt.minh")
    token_hoa = get_token("ld.hoa")

    # 1. Lấy một task đang chờ của lãnh đạo (taskDuyetCapPhep hoặc taskPhanCong)
    req = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/flow/tasks",
        headers={"Authorization": f"Bearer {token_hoa}"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        tasks = json.loads(resp.read().decode()).get("tasks", [])
        assert len(tasks) > 0
        task_id = tasks[0]["id"]

    # 2. cdt.minh cố gắng hoàn thành task của lãnh đạo
    complete_req = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/flow/tasks/{task_id}/complete",
        data=json.dumps({"variables": {"pheDuyet": True}}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token_minh}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(complete_req, timeout=5) as resp:
            raise AssertionError(f"Mong đợi bị từ chối 403 nhưng trả {resp.status}")
    except urllib.error.HTTPError as e:
        assert e.code == 403, f"Mong đợi HTTP 403 nhưng nhận được HTTP {e.code}"


def test_S08_unassigned_reviewer_cannot_complete_assigned_task():
    token_binh = get_token("td.binh")
    token_cuong = get_token("td.cuong")

    # Lấy task được giao cho td.binh
    req = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/flow/tasks",
        headers={"Authorization": f"Bearer {token_binh}"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        tasks = json.loads(resp.read().decode()).get("tasks", [])
        assert len(tasks) > 0
        binh_task_id = tasks[0]["id"]

    # td.cuong cố gắng hoàn thành task đã giao cho td.binh
    complete_req = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/flow/tasks/{binh_task_id}/complete",
        data=json.dumps({"variables": {"ketQuaThamDinh": "DAT"}}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token_cuong}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(complete_req, timeout=5) as resp:
            raise AssertionError(f"Mong đợi bị từ chối 403 nhưng trả {resp.status}")
    except urllib.error.HTTPError as e:
        assert e.code == 403, f"Mong đợi HTTP 403 nhưng nhận được HTTP {e.code}"
