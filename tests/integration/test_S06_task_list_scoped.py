# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import urllib.request
from tests.integration.conftest import get_token, GATEWAY_URL


def test_S06_task_list_scoped():
    token_minh = get_token("cdt.minh")
    token_phuongb = get_token("mc.phuongb")
    token_binh = get_token("td.binh")
    token_cuong = get_token("td.cuong")

    def fetch_tasks(token: str) -> list:
        req = urllib.request.Request(
            f"{GATEWAY_URL}/api/v1/flow/tasks",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data.get("tasks", [])

    # 1. cdt.minh (chủ đầu tư) không có nhiệm vụ nội bộ nào của cán bộ
    tasks_minh = fetch_tasks(token_minh)
    internal_task_keys = {"taskKiemTraHopLe", "taskPhanCong", "taskThamDinh", "taskDuyetCapPhep", "taskKiemTraHienTruong", "taskXuLyViPham"}
    internal_tasks_minh = [t for t in tasks_minh if t.get("taskDefinitionKey") in internal_task_keys]
    assert len(internal_tasks_minh) == 0, f"cdt.minh không được có nhiệm vụ nội bộ cán bộ: {internal_tasks_minh}"

    # 2. mc.phuongb (phường B) chỉ thấy nhiệm vụ thuộc tenant phuong-b
    tasks_phuongb = fetch_tasks(token_phuongb)
    for t in tasks_phuongb:
        assert t.get("tenantId") == "phuong-b"

    # 3. td.binh và td.cuong không thấy nhiệm vụ đã phân công cho người kia
    tasks_binh = fetch_tasks(token_binh)
    tasks_cuong = fetch_tasks(token_cuong)

    binh_task_ids = {t["id"] for t in tasks_binh}
    cuong_task_ids = {t["id"] for t in tasks_cuong}

    # Hai tập nhiệm vụ được phân công riêng biệt không được trùng lặp
    assert binh_task_ids.isdisjoint(cuong_task_ids)
