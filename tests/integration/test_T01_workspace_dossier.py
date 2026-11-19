# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""T-01: bàn làm việc cán bộ mở hồ sơ, tải tệp đính kèm và đọc danh sách việc."""

import urllib.error
import urllib.request

import httpx

from tests.integration._ho_so import GATEWAY_URL, get_token, run_sql, start_cap_phep, submit_dossier, wait_task


def test_T01_file_download_access_control_and_audit():
    """
    T-01: Kiểm tra API tải tệp qua service files:
    - Cán bộ một cửa (mc.thu) có quyền đọc hồ sơ -> tải được tệp (200) và ghi audit 'file.read'.
    - Thẩm định viên chưa phân công (td.cuong) -> bị từ chối 403 và ghi audit 'access.denied'.
    """
    token_mc = get_token("mc.thu")
    token_cuong = get_token("td.cuong")
    token_cdt = get_token("cdt.minh")

    # 1. Nộp hồ sơ và tải lên 1 tệp đính kèm
    with httpx.Client(timeout=60.0) as client:
        # Nộp hồ sơ
        hs_res = submit_dossier(token_cdt, {
                "ho_ten": "Nguyen Van T01",
                "cccd": "001099123456",
                "dien_thoai": "0912345678",
                "dia_chi_cong_trinh": "123 Pho T01",
                "thua_dat": "Thua 101",
                "so_tang": 3,
                "dien_tich_san_m2": 150.0,
                "khu_quan_ly_kien_truc": True,
            }, tag_prefix="T01_workspace_dossie", client=client)
        assert hs_res.status_code == 200, f"Lỗi nộp hồ sơ: {hs_res.text}"
        hs_data = hs_res.json()
        hs_id = hs_data["id"]

        # Tải tệp bản vẽ
        dummy_pdf = b"%PDF-1.4 test T01 content drawing"
        files = {"file": ("ban_ve_t01.pdf", dummy_pdf, "application/pdf")}
        data = {"object_type": "ho_so", "object_id": hs_id}
        upload_res = client.post(
            f"{GATEWAY_URL}/api/v1/files",
            headers={"Authorization": f"Bearer {token_cdt}"},
            files=files,
            data=data,
        )
        assert upload_res.status_code == 201, f"Lỗi upload: {upload_res.text}"
        file_id = upload_res.json()["file_id"]

        # Đính kèm tệp vào hồ sơ
        link_res = client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/dinh_kem_tep",
            headers={"Authorization": f"Bearer {token_cdt}"},
            json={"p_ho_so_id": hs_id, "p_file_id": file_id, "p_loai": "ban_ve_mat_bang"},
        )
        assert link_res.status_code == 200, f"Lỗi liên kết tệp: {link_res.text}"

    # 2. td.cuong (chưa phân công) gọi tải tệp -> Phải bị 403
    download_url = f"{GATEWAY_URL}/api/v1/files/{file_id}/download"
    req_cuong = urllib.request.Request(download_url, headers={"Authorization": f"Bearer {token_cuong}"})
    status_cuong = None
    try:
        with urllib.request.urlopen(req_cuong, timeout=5) as resp:
            status_cuong = resp.status
    except urllib.error.HTTPError as e:
        status_cuong = e.code

    assert status_cuong == 403, f"td.cuong chưa phân công tải tệp phải nhận 403, nhận được: {status_cuong}"

    # Kiểm tra audit access.denied
    denied_audit = run_sql(
        f"SELECT count(*) FROM core.audit_log WHERE action = 'access.denied' AND object_id = '{file_id}';"
    )
    assert int(denied_audit) > 0, "Phải ghi audit access.denied khi td.cuong bị từ chối tải tệp"

    # 3. mc.thu (cán bộ một cửa cùng phường) gọi tải tệp -> Phải 200 và nội dung đúng
    req_mc = urllib.request.Request(download_url, headers={"Authorization": f"Bearer {token_mc}"})
    with urllib.request.urlopen(req_mc, timeout=5) as resp_mc:
        assert resp_mc.status == 200, f"mc.thu phải tải được tệp (200), nhận được: {resp_mc.status}"
        content = resp_mc.read()
        assert content == dummy_pdf, "Nội dung tải về phải trùng khớp với tệp đã tải lên"

    # Kiểm tra audit file.read
    read_audit = run_sql(
        f"SELECT count(*) FROM core.audit_log WHERE action = 'file.read' AND object_id = '{file_id}';"
    )
    assert int(read_audit) > 0, "Phải ghi audit file.read khi mc.thu tải tệp thành công"

    # 4. mc.thu truy vấn danh sách tệp đính kèm qua v_ho_so_tep
    with httpx.Client(timeout=10.0) as client:
        v_files_res = client.get(
            f"{GATEWAY_URL}/api/v1/rest/v_ho_so_tep?ho_so_id=eq.{hs_id}",
            headers={"Authorization": f"Bearer {token_mc}"},
        )
        assert v_files_res.status_code == 200, f"Lỗi truy vấn v_ho_so_tep: {v_files_res.text}"
        v_files = v_files_res.json()
        assert len(v_files) >= 1, "Phải tìm thấy ít nhất 1 tệp đính kèm trong v_ho_so_tep"
        assert v_files[0]["status"] == "clean", "Trạng thái tệp phải là clean sau quét ClamAV"


def test_T01_flow_tasks_include_variables():
    """
    T-01: /api/v1/flow/tasks trả kèm biến quy trình (ho_so_id, ma_ho_so) để
    bàn làm việc liên kết đúng task với hồ sơ.
    """
    token_cdt = get_token("cdt.minh")
    token_mc = get_token("mc.thu")

    res = submit_dossier(token_cdt, {
        "ho_ten": "Nguyen Van T01",
        "cccd": "001099123457",
        "dien_thoai": "0912345678",
        "dia_chi_cong_trinh": "125 Pho T01",
        "thua_dat": "Thua 102",
        "so_tang": 2,
        "dien_tich_san_m2": 110.0,
        "khu_quan_ly_kien_truc": False,
    }, tag_prefix="T01_flow_vars")
    assert res.status_code == 200, f"Lỗi nộp hồ sơ: {res.text}"
    ho_so = res.json()
    proc_id = start_cap_phep(token_cdt, ho_so)

    task = wait_task(token_mc, proc_id, "taskKiemTraHopLe")
    assert isinstance(task.get("variables"), list), "'variables' phải là mảng biến từ Flowable"
    bien = {v.get("name"): v.get("value") for v in task["variables"]}
    assert bien.get("ho_so_id") == ho_so["id"], f"Thiếu hoặc sai ho_so_id: {bien}"
    assert bien.get("ma_ho_so") == ho_so["ma_ho_so"], f"Thiếu hoặc sai ma_ho_so: {bien}"
