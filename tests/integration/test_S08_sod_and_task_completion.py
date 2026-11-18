# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""S-08: ai được hoàn thành việc nào, và tách biệt nhiệm vụ (SoD) ở bước phê duyệt.

Mỗi test tự khởi động một quy trình cap-phep mới ở phường A.
"""

from tests.integration._ho_so import complete_task, flowable, get_token, run_sql, start_process, sub_of, wait_task


def _quy_trinh_moi(tok: dict) -> str:
    return start_process(tok["cdt.minh"], "cap-phep", {
        "chu_dau_tu_sub": sub_of(tok["cdt.minh"]),
        "dien_tich_san_m2": 150.0,
        "khu_quan_ly_kien_truc": True,
    })


def _den_tham_dinh(tok: dict, proc_id: str) -> dict:
    t = wait_task(tok["mc.thu"], proc_id, "taskKiemTraHopLe")
    assert complete_task(tok["mc.thu"], t["id"], {"hoSoHopLe": True}).status_code == 200
    t = wait_task(tok["ld.hoa"], proc_id, "taskPhanCong")
    r = complete_task(tok["ld.hoa"], t["id"], {"nguoiThamDinh": sub_of(tok["td.binh"]), "lanhDaoPhanCong": sub_of(tok["ld.hoa"])})
    assert r.status_code == 200, r.text
    return wait_task(tok["td.binh"], proc_id, "taskThamDinh")


def _tokens(*users: str) -> dict:
    return {u: get_token(u) for u in users}


def test_S08_citizen_cannot_complete_workflow_tasks():
    tok = _tokens("cdt.minh", "mc.thu")
    proc_id = _quy_trinh_moi(tok)
    task = wait_task(tok["mc.thu"], proc_id, "taskKiemTraHopLe")

    r = complete_task(tok["cdt.minh"], task["id"], {"hoSoHopLe": True})
    assert r.status_code == 403, f"Chủ đầu tư hoàn thành việc của một cửa phải 403, nhận {r.status_code}: {r.text}"


def test_S08_unassigned_reviewer_cannot_complete_assigned_task():
    tok = _tokens("cdt.minh", "mc.thu", "ld.hoa", "td.binh", "td.cuong")
    task = _den_tham_dinh(tok, _quy_trinh_moi(tok))

    r = complete_task(tok["td.cuong"], task["id"], {"ketQuaThamDinh": "DAT"})
    assert r.status_code == 403, f"td.cuong hoàn thành việc giao td.binh phải 403, nhận {r.status_code}: {r.text}"


def test_S08_sod_blocks_self_approval_and_allows_valid_assignment():
    tok = _tokens("cdt.minh", "mc.thu", "ld.hoa", "td.binh")
    proc_id = _quy_trinh_moi(tok)
    task = _den_tham_dinh(tok, proc_id)
    r = complete_task(tok["td.binh"], task["id"], {"ketQuaThamDinh": "DAT", "noiDungThamDinh": "Đạt"})
    assert r.status_code == 200, r.text
    duyet = wait_task(tok["ld.hoa"], proc_id, "taskDuyetCapPhep")
    hoa_sub, binh_sub = sub_of(tok["ld.hoa"]), sub_of(tok["td.binh"])

    def dat_nguoi_tham_dinh(sub: str) -> None:
        with flowable() as fl:
            res = fl.put(f"/service/runtime/process-instances/{proc_id}/variables",
                         json=[{"name": "nguoiThamDinh", "type": "string", "value": sub}])
            assert res.status_code in (200, 201), f"Không đặt được nguoiThamDinh: {res.status_code} {res.text}"

    # 1. Cấu hình vi phạm: người thẩm định trùng người phê duyệt -> chặn 403, ghi audit
    dat_nguoi_tham_dinh(hoa_sub)
    r = complete_task(tok["ld.hoa"], duyet["id"], {"dongYCapPhep": False, "yKienPheDuyet": "Thử tự duyệt"})
    assert r.status_code == 403, f"SoD phải chặn người thẩm định tự phê duyệt, nhận {r.status_code}: {r.text}"
    assert "phân tách nhiệm vụ" in r.text
    so_audit = run_sql(
        "SELECT count(*) FROM core.audit_log "
        f"WHERE action = 'sod.violation_prevented' AND object_id = '{duyet['id']}';"
    )
    assert int(so_audit) >= 1, "Phải ghi audit sod.violation_prevented"
    wait_task(tok["ld.hoa"], proc_id, "taskDuyetCapPhep", tries=2)

    # 2. Cấu hình hợp lệ: người thẩm định khác người phê duyệt -> hoàn thành được.
    #    Chọn từ chối để không gọi ký số, quy trình kết thúc ở endTuChoi.
    dat_nguoi_tham_dinh(binh_sub)
    r = complete_task(tok["ld.hoa"], duyet["id"], {"dongYCapPhep": False, "yKienPheDuyet": "Từ chối thử"})
    assert r.status_code == 200, f"Phân công hợp lệ phải hoàn thành được, nhận {r.status_code}: {r.text}"
    with flowable() as fl:
        hist = fl.get(f"/service/history/historic-process-instances/{proc_id}").json()
    assert hist.get("endActivityId") == "endTuChoi", f"Quy trình phải kết thúc ở endTuChoi: {hist}"
