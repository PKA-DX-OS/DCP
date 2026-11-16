# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import base64
import json
import subprocess
import time
import httpx
from tests.integration.conftest import GATEWAY_URL, get_token, submit_dossier


def parse_sub(tok: str) -> str:
    raw = tok.split(".")[1]
    raw += "=" * (-len(raw) % 4)
    return json.loads(base64.urlsafe_b64decode(raw))["sub"]


def run_sql(sql: str) -> str:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", sql]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout.strip()


def test_N03_hook_failure_and_retry():
    cdt_token = get_token("cdt.minh")
    mc_token = get_token("mc.thu")
    ld_token = get_token("ld.hoa")
    td_token = get_token("td.binh")
    binh_sub = parse_sub(td_token)
    hoa_sub = parse_sub(ld_token)

    # 1. Nộp hồ sơ
    with httpx.Client(timeout=10.0) as client:
        resp = submit_dossier(cdt_token, {
                "ho_ten": "Hoang Thi N03",
                "cccd": "001200000033",
                "dien_thoai": "0911223344",
                "dia_chi_cong_trinh": "789 Duong N03 Phuong A",
                "thua_dat": "Thua 3 To 3",
                "so_tang": 3,
                "dien_tich_san_m2": 150.0,
                "khu_quan_ly_kien_truc": True,
            }, tag_prefix="N03_hook_failure", client=client)
        assert resp.status_code == 200, f"Nộp hồ sơ thất bại: {resp.text}"
        hs_data = resp.json()
        hs_id = hs_data["id"]
        ma_hs = hs_data["ma_ho_so"]
        proc_id = hs_data.get("process_instance_id")

    if not proc_id:
        with httpx.Client(timeout=10.0) as client:
            wf_resp = client.post(
                f"{GATEWAY_URL}/api/v1/flow/processes/start",
                headers={"Authorization": f"Bearer {cdt_token}"},
                json={
                    "process_key": "cap-phep",
                    "business_key": ma_hs,
                    "variables": {
                        "ho_so_id": hs_id,
                        "object_id": hs_id,
                        "p_object_id": hs_id,
                        "cdt_sub": "cdt.minh",
                        "tenant": "phuong-a",
                    },
                },
            )
            assert wf_resp.status_code == 200, f"Khởi động quy trình thất bại: {wf_resp.text}"
            proc_id = wf_resp.json()["process_id"]

    def get_task_id(user_token: str, task_def: str) -> str:
        for _ in range(10):
            with httpx.Client(timeout=5.0) as cl:
                r = cl.get(f"{GATEWAY_URL}/api/v1/flow/tasks", headers={"Authorization": f"Bearer {user_token}"})
                if r.status_code == 200:
                    data = r.json()
                    task_list = data.get("tasks", []) if isinstance(data, dict) else data
                    for t in task_list:
                        if t.get("processInstanceId") == proc_id and t.get("taskDefinitionKey") == task_def:
                            return t["id"]
            time.sleep(1)
        raise RuntimeError(f"Không tìm thấy nhiệm vụ {task_def} cho quy trình {proc_id}")

    # 2. Tiếp nhận một cửa
    t1_id = get_task_id(mc_token, "taskKiemTraHopLe")
    with httpx.Client(timeout=5.0) as client:
        r = client.post(
            f"{GATEWAY_URL}/api/v1/flow/tasks/{t1_id}/complete",
            headers={"Authorization": f"Bearer {mc_token}"},
            json={"variables": {"hoSoHopLe": True}},
        )
        assert r.status_code == 200

    # 3. Lãnh đạo phân công
    t2_id = get_task_id(ld_token, "taskPhanCong")
    with httpx.Client(timeout=5.0) as client:
        r = client.post(
            f"{GATEWAY_URL}/api/v1/flow/tasks/{t2_id}/complete",
            headers={"Authorization": f"Bearer {ld_token}"},
            json={"variables": {"nguoiThamDinh": binh_sub, "lanhDaoPhanCong": hoa_sub}},
        )
        assert r.status_code == 200

    # 4. Thẩm định viên thẩm định
    t3_id = get_task_id(td_token, "taskThamDinh")
    with httpx.Client(timeout=5.0) as client:
        r = client.post(
            f"{GATEWAY_URL}/api/v1/flow/tasks/{t3_id}/complete",
            headers={"Authorization": f"Bearer {td_token}"},
            json={"variables": {"ketQuaThamDinh": "DAT", "noiDungThamDinh": "Bản vẽ đạt chuẩn"}},
        )
        assert r.status_code == 200

    # 5. Dừng dịch vụ doc-sign để giả lập sự cố kết nối/ký số
    subprocess.run(["docker", "stop", "dxos-doc-sign"], check=True)

    try:
        t4_id = get_task_id(ld_token, "taskDuyetCapPhep")
        with httpx.Client(timeout=10.0) as client:
            r_duyet = client.post(
                f"{GATEWAY_URL}/api/v1/flow/tasks/{t4_id}/complete",
                headers={"Authorization": f"Bearer {ld_token}"},
                json={"variables": {"dongYCapPhep": True, "pheDuyet": True, "yKienPheDuyet": "Duyet cap phep"}},
            )
            # Kỳ vọng flow trả về lỗi HTTP 502 do doc-sign không kết nối được
            assert r_duyet.status_code == 502, f"Kỳ vọng 502 khi doc-sign lỗi nhưng nhận {r_duyet.status_code}: {r_duyet.text}"

        # Kiểm tra bảng core.hook_runs đã ghi nhận trạng thái FAILED
        hook_status = run_sql(
            f"SELECT status FROM core.hook_runs WHERE process_instance_id = '{proc_id}' AND task_def = 'taskDuyetCapPhep' ORDER BY created_at DESC LIMIT 1;"
        )
        assert hook_status == "FAILED", f"Kỳ vọng hook_runs lưu status FAILED, thực tế: '{hook_status}'"

        # 6. Người không có vai trò lãnh đạo gọi retry -> phải bị chặn 403
        with httpx.Client(timeout=5.0) as client:
            r_unauth = client.post(
                f"{GATEWAY_URL}/api/v1/flow/hooks/retry",
                headers={"Authorization": f"Bearer {td_token}"},
                json={"process_instance_id": proc_id, "task_def": "taskDuyetCapPhep"},
            )
            assert r_unauth.status_code == 403, f"Thẩm định viên gọi retry phải nhận 403, nhận: {r_unauth.status_code}"

    finally:
        # 7. Khôi phục lại container doc-sign
        subprocess.run(["docker", "start", "dxos-doc-sign"], check=True)
        # Chờ doc-sign sẵn sàng
        for _ in range(15):
            time.sleep(1)
            res_ping = subprocess.run(["docker", "inspect", "dxos-doc-sign", "--format", "{{.State.Health.Status}}"], capture_output=True, text=True)
            if res_ping.stdout.strip() == "healthy":
                break

    # 8. Lãnh đạo gọi retry
    with httpx.Client(timeout=15.0) as client:
        r_retry = client.post(
            f"{GATEWAY_URL}/api/v1/flow/hooks/retry",
            headers={"Authorization": f"Bearer {ld_token}"},
            json={"process_instance_id": proc_id, "task_def": "taskDuyetCapPhep"},
        )
        assert r_retry.status_code == 200, f"Retry lãnh đạo thất bại: {r_retry.text}"
        data = r_retry.json()
        assert data.get("status") == "success"
        assert data.get("signed_doc_id"), "Phải có signed_doc_id sau khi retry"

    # 9. Kiểm tra kết quả trong CSDL:
    # 9a. hook_runs chuyển sang COMPLETED
    hook_status_after = run_sql(
        f"SELECT status FROM core.hook_runs WHERE process_instance_id = '{proc_id}' AND task_def = 'taskDuyetCapPhep' ORDER BY created_at DESC LIMIT 1;"
    )
    assert hook_status_after == "COMPLETED", f"Kỳ vọng hook_runs chuyển sang COMPLETED, thực tế: '{hook_status_after}'"

    # 9b. Giấy phép được tạo thành công
    gp_count = int(run_sql(f"SELECT count(*) FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}';") or "0")
    assert gp_count == 1, f"Kỳ vọng có 1 giấy phép được tạo sau khi retry, thực tế: {gp_count}"

    # 9c. Hồ sơ chuyển sang DA_CAP
    hs_status = run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{hs_id}';")
    assert hs_status == "DA_CAP", f"Kỳ vọng hồ sơ chuyển sang DA_CAP, thực tế: '{hs_status}'"
