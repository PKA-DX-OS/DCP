# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-FLOW-05: vòng đời nộp → quy hoạch → thẩm định → duyệt/từ chối."""

import httpx

from tests.integration._auth import GATEWAY_URL, get_token
from tests.integration._ho_so import cap_phep_den_buoc_duyet, complete_task, run_sql, start_process, sub_of, wait_task


PAYLOAD = {
    "ho_ten": "Nguyễn Văn Vòng Đời",
    "cccd": "001099008888",
    "dien_thoai": "0908888888",
    "dia_chi_cong_trinh": "Số 18 Đường Hòa Bình, phường A",
    "thua_dat": "TD-A-01",
    "so_tang": 3,
    "dien_tich_san_m2": 150.0,
    "khu_quan_ly_kien_truc": True,
}


def test_AFLOW_01_duyet_cap_giay_phep_va_audit():
    ctx = cap_phep_den_buoc_duyet("cdt.minh", PAYLOAD, "AFLOW-ok")
    ho_so = ctx["ho_so"]
    token_td = ctx["tokens"]["td.binh"]

    check = httpx.post(
        f"{GATEWAY_URL}/api/v1/planning/check",
        headers={"Authorization": f"Bearer {token_td}"},
        json={
            "ho_so_id": ho_so["id"],
            "proposal": {
                "chieu_cao_m": 11, "mat_do_xay_dung_pct": 65, "far": 1.8,
                "khoang_lui_truoc_m": 3.5, "khoang_lui_hong_m": 1.2, "khoang_lui_sau_m": 1.2,
            },
        },
        timeout=30.0,
    )
    assert check.status_code == 200, check.text
    assert check.json()["pass"] is True

    duyet = complete_task(
        ctx["tokens"]["ld.hoa"],
        ctx["task"]["id"],
        {"pheDuyet": True, "dongYCapPhep": True, "yKienPheDuyet": "Đồng ý cấp phép"},
    )
    assert duyet.status_code == 200, duyet.text

    trang_thai = run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{ho_so['id']}';")
    assert trang_thai == "DA_CAP", f"Hồ sơ phải được cấp, nhận {trang_thai}"

    audit = run_sql(
        "SELECT count(*) FROM core.audit_log "
        f"WHERE object_type = 'ho_so' AND object_id = '{ho_so['id']}' "
        "AND action IN ('ho_so.nop', 'planning.checked');"
    )
    assert int(audit) >= 2, f"Thiếu audit vòng đời: {audit}"


def test_AFLOW_02_tu_choi_cap_phep():
    ctx = cap_phep_den_buoc_duyet("cdt.minh", PAYLOAD, "AFLOW-reject")
    ho_so = ctx["ho_so"]
    tu_choi = complete_task(
        ctx["tokens"]["ld.hoa"],
        ctx["task"]["id"],
        {"pheDuyet": False, "dongYCapPhep": False, "yKienPheDuyet": "Hồ sơ chưa đủ căn cứ"},
    )
    assert tu_choi.status_code == 200, tu_choi.text
    trang_thai = run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{ho_so['id']}';")
    assert trang_thai == "TU_CHOI", f"Hồ sơ phải bị từ chối, nhận {trang_thai}"


def test_AFLOW_03_work_list_co_ma_ho_so_va_dia_chi():
    # Một hồ sơ mới, dừng ở bước một cửa để kiểm tra dữ liệu work list.
    from tests.integration._ho_so import normalize_payload, start_cap_phep, submit_dossier, wait_task

    from tests.integration._auth import get_token

    token = get_token("cdt.minh")
    resp = submit_dossier(token, PAYLOAD, tag_prefix="AFLOW-work")
    assert resp.status_code == 200, resp.text
    ho_so = resp.json()
    data = normalize_payload(PAYLOAD)
    proc_id = start_cap_phep(token, ho_so, {
        "dien_tich_san_m2": data["dien_tich_san_m2"],
        "khu_quan_ly_kien_truc": bool(data.get("khu_quan_ly_kien_truc")),
        "dia_chi_cong_trinh": PAYLOAD["dia_chi_cong_trinh"],
    })
    task = wait_task(get_token("mc.thu"), proc_id, "taskKiemTraHopLe")
    variables = {v["name"]: v.get("value") for v in task.get("variables", [])}
    assert variables.get("ma_ho_so") == ho_so["ma_ho_so"]
    assert variables.get("dia_chi_cong_trinh") == PAYLOAD["dia_chi_cong_trinh"]
    # Dọn việc: chuyển tiếp để không để task treo ở bước một cửa.
    complete_task(get_token("mc.thu"), task["id"], {"hoSoHopLe": True})


def test_AFLOW_04_quy_hoach_va_nghiem_thu_tao_viec_that():
    import uuid
    tok = get_token("td.binh")
    hid = run_sql("SELECT id FROM app_cap_phep.ho_so WHERE ma_ho_so = 'CP-HERO-2026-001';")
    ma = "CP-HERO-2026-001"
    proc = start_process(tok, "quy-hoach", {
        "ho_so_id": hid,
        "ma_ho_so": ma,
        "dia_chi_cong_trinh": "Số 18 Đường Hòa Bình, phường A",
    }, business_key=f"{ma}-TEST-{uuid.uuid4().hex[:6]}")
    task = wait_task(tok, proc, "taskKiemTraQuyHoach")
    assert complete_task(tok, task["id"], {
        "quy_hoach_pass": True,
        "ket_qua_kiem_tra_id": "test",
        "quy_hoach_fail_rules": "",
    }).status_code == 200
    assert run_sql(f"SELECT quy_hoach_process_id FROM app_cap_phep.ho_so WHERE id = '{hid}';") == proc

    hid2 = run_sql("SELECT id FROM app_cap_phep.ho_so WHERE ma_ho_so = 'CP-HERO-ACC-2026-001';")
    ma2 = "CP-HERO-ACC-2026-001"
    proc2 = start_process(tok, "nghiem-thu", {
        "ho_so_id": hid2,
        "ma_ho_so": ma2,
        "dia_chi_cong_trinh": "Số 20 Đường Hòa Bình, phường A",
    }, business_key=f"{ma2}-TEST-{uuid.uuid4().hex[:6]}")
    task2 = wait_task(tok, proc2, "taskNghiemThuMong")
    assert complete_task(tok, task2["id"], {
        "ket_qua_nghiem_thu": "dat",
        "mong_dat": True,
        "ghi_chu": "Test",
    }).status_code == 200
    assert run_sql(f"SELECT nghiem_thu_process_id FROM app_cap_phep.ho_so WHERE id = '{hid2}';") == proc2


def test_AFLOW_04_escalation_phan_cong_lai_va_nhac_viec():
    tok = get_token("ld.hoa")
    h = {"Authorization": f"Bearer {tok}"}
    esc = httpx.get(f"{GATEWAY_URL}/api/v1/flow/escalations", headers=h, timeout=30.0)
    assert esc.status_code == 200, esc.text
    tasks = httpx.get(f"{GATEWAY_URL}/api/v1/flow/tasks", headers=h, timeout=20.0).json().get("tasks", [])
    task = next((t for t in tasks if t.get("taskDefinitionKey") in ("taskDuyetCapPhep", "taskPheDuyet")), None)
    if task is None:
        return
    assigned = httpx.post(
        f"{GATEWAY_URL}/api/v1/flow/tasks/{task['id']}/assign",
        headers=h,
        json={"user_sub": sub_of(tok), "reason": "Kiểm thử phân công lại"},
        timeout=20.0,
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["assignee"] == sub_of(tok)
    reminded = httpx.post(
        f"{GATEWAY_URL}/api/v1/flow/tasks/{task['id']}/remind",
        headers=h,
        json={"message": "Kiểm thử nhắc việc"},
        timeout=20.0,
    )
    assert reminded.status_code == 200, reminded.text
