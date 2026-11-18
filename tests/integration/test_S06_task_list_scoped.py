# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""S-06: danh sách việc chỉ gồm việc của chính người dùng, đúng địa bàn."""

import httpx

from tests.integration._ho_so import GATEWAY_URL, complete_task, get_token, start_process, sub_of, wait_task

VIEC_NOI_BO = {
    "taskKiemTraHopLe", "taskPhanCong", "taskThamDinh", "taskThamDinhNhanh",
    "taskDuyetCapPhep", "taskKiemTraHienTruong", "taskXuLyViPham",
}


def _tasks(token: str) -> list:
    resp = httpx.get(f"{GATEWAY_URL}/api/v1/flow/tasks", headers={"Authorization": f"Bearer {token}"}, timeout=10.0)
    assert resp.status_code == 200, f"Lấy danh sách việc thất bại: {resp.status_code} {resp.text}"
    return resp.json().get("tasks", [])


def test_S06_task_list_scoped():
    tok = {u: get_token(u) for u in ("cdt.minh", "mc.thu", "ld.hoa", "td.binh", "td.cuong", "mc.phuongb")}

    # Tự tạo một quy trình ở phường A và đưa tới bước thẩm định giao cho td.binh
    proc_id = start_process(tok["cdt.minh"], "cap-phep", {
        "chu_dau_tu_sub": sub_of(tok["cdt.minh"]),
        "dien_tich_san_m2": 150.0,
        "khu_quan_ly_kien_truc": True,
    })
    t = wait_task(tok["mc.thu"], proc_id, "taskKiemTraHopLe")
    assert complete_task(tok["mc.thu"], t["id"], {"hoSoHopLe": True}).status_code == 200
    t = wait_task(tok["ld.hoa"], proc_id, "taskPhanCong")
    assert complete_task(tok["ld.hoa"], t["id"], {"nguoiThamDinh": sub_of(tok["td.binh"])}).status_code == 200
    viec_binh = wait_task(tok["td.binh"], proc_id, "taskThamDinh")

    # 1. Chủ đầu tư không thấy việc nội bộ của cán bộ
    noi_bo = [x for x in _tasks(tok["cdt.minh"]) if x.get("taskDefinitionKey") in VIEC_NOI_BO]
    assert noi_bo == [], f"cdt.minh không được có nhiệm vụ nội bộ cán bộ: {noi_bo}"

    # 2. Cán bộ phường B chỉ thấy việc của phường B, không thấy quy trình vừa tạo
    viec_b = _tasks(tok["mc.phuongb"])
    assert all(x.get("tenantId") == "phuong-b" for x in viec_b), f"Lộ việc tenant khác: {viec_b}"
    assert all(x.get("processInstanceId") != proc_id for x in viec_b)

    # 3. td.cuong không thấy việc đã giao cho td.binh
    assert viec_binh["id"] not in {x["id"] for x in _tasks(tok["td.cuong"])}, "td.cuong thấy việc của td.binh"
