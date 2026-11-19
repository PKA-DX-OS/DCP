# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""V2-05: phân công cán bộ động (lãnh đạo chọn thẩm định viên) và khởi động quy trình truy cập khẩn."""

from tests.integration._ho_so import complete_task, get_token, start_process, sub_of, wait_task


def test_phan_cong_tham_dinh_200():
    tok = {u: get_token(u) for u in ("cdt.minh", "mc.thu", "ld.hoa", "td.binh", "td.cuong")}
    proc_id = start_process(tok["cdt.minh"], "cap-phep", {
        "chu_dau_tu_sub": sub_of(tok["cdt.minh"]),
        "dien_tich_san_m2": 150.0,
        "khu_quan_ly_kien_truc": True,
    })

    # 1. Một cửa tiếp nhận
    t = wait_task(tok["mc.thu"], proc_id, "taskKiemTraHopLe")
    r = complete_task(tok["mc.thu"], t["id"], {"hoSoHopLe": True})
    assert r.status_code == 200, r.text

    # 2. Lãnh đạo chọn thẩm định viên lúc chạy (biến nguoiThamDinh)
    t = wait_task(tok["ld.hoa"], proc_id, "taskPhanCong")
    r = complete_task(tok["ld.hoa"], t["id"], {"nguoiThamDinh": sub_of(tok["td.cuong"]), "lanhDaoPhanCong": sub_of(tok["ld.hoa"])})
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "success"

    # 3. Việc thẩm định giao đúng người được chọn
    viec = wait_task(tok["td.cuong"], proc_id, "taskThamDinh")
    assert viec.get("assignee") == sub_of(tok["td.cuong"]), f"Sai người được giao: {viec.get('assignee')}"


def test_khoi_tao_truy_cap_khan_200():
    token_ld = get_token("ld.hoa")
    proc_id = start_process(token_ld, "truy-cap-khan", {"lyDo": "Xu ly su co mat dien khan cap"})
    assert proc_id
