# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import time
import subprocess
import httpx
from tests.integration.conftest import GATEWAY_URL, get_token, submit_dossier


def run_sql(sql: str) -> str:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", sql]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout.strip()


def test_T07_supplement_dossier_workflow():
    """
    T-07: Quy trình bổ sung hồ sơ và hoàn thành taskChoBoSung qua flow:
    1. cdt.minh nộp hồ sơ mới.
    2. mc.thu từ chối hợp lệ và yêu cầu bổ sung kèm lý do.
    3. cdt.lan cố gắng bổ sung hồ sơ của cdt.minh -> 403 Forbidden.
    4. cdt.minh gọi RPC bo_sung_ho_so theo đúng payload UI gửi -> 200 OK.
    5. cdt.minh hoàn thành task taskChoBoSung qua services/flow.
    6. mc.thu nhận lại task taskKiemTraHopLe trong danh sách công việc.
    7. Kiểm tra audit log có bản ghi ho_so.bo_sung.
    """
    token_minh = get_token("cdt.minh")
    token_thu = get_token("mc.thu")
    token_lan = get_token("cdt.lan")

    with httpx.Client(timeout=10.0) as client:
        # 1. cdt.minh nộp hồ sơ mới
        res_nop = submit_dossier(token_minh, {
                "ho_ten": "Trần Văn Minh",
                "cccd": "001090000001",
                "dien_thoai": "0901234567",
                "dia_chi_cong_trinh": "123 Đường Test T07, Phường A",
                "thua_dat": "T07-1",
                "so_tang": 2,
                "dien_tich_san_m2": 100.0,
                "khu_quan_ly_kien_truc": False,
            }, tag_prefix="T07_bo_sung_ui", client=client)
        assert res_nop.status_code == 200, f"Nộp hồ sơ thất bại: {res_nop.text}"
        ho_so_data = res_nop.json()
        ho_so_id = ho_so_data.get("id") or ho_so_data.get("p_id")
        ma_hs = ho_so_data.get("ma_ho_so")
        assert ho_so_id, "Không có ho_so_id"

        # Khởi động quy trình BPMN như UI làm
        wf_res = client.post(
            f"{GATEWAY_URL}/api/v1/flow/processes/start",
            headers={"Authorization": f"Bearer {token_minh}"},
            json={
                "process_key": "cap-phep",
                "business_key": ma_hs,
                "variables": {
                    "ho_so_id": ho_so_id,
                    "ma_ho_so": ma_hs,
                    "dia_chi_cong_trinh": "123 Đường Test T07, Phường A",
                    "thua_dat": "T07-1",
                    "so_tang": 2,
                    "dien_tich_san_m2": 100.0,
                    "khu_quan_ly_kien_truc": False,
                },
            },
        )
        assert wf_res.status_code in (200, 201), f"Khởi động quy trình thất bại: {wf_res.text}"

        # Đợi Flowable khởi tạo taskKiemTraHopLe
        task_tiep_nhan = None
        for _ in range(10):
            tasks_thu_res = client.get(
                f"{GATEWAY_URL}/api/v1/flow/tasks",
                headers={"Authorization": f"Bearer {token_thu}"},
            ).json()
            tasks_thu = tasks_thu_res.get("tasks", []) if isinstance(tasks_thu_res, dict) else tasks_thu_res
            for t in tasks_thu:
                if t.get("taskDefinitionKey") == "taskKiemTraHopLe":
                    # Kiểm tra biến hồ sơ
                    vars_dict = {v["name"]: v["value"] for v in t.get("variables", [])}
                    if vars_dict.get("ho_so_id") == str(ho_so_id) or vars_dict.get("business_key") == ho_so_data.get("ma_ho_so"):
                        task_tiep_nhan = t
                        break
            if task_tiep_nhan:
                break
            time.sleep(1)

        assert task_tiep_nhan, "mc.thu phải nhận được taskKiemTraHopLe sau khi nộp hồ sơ"

        # 2. mc.thu yêu cầu bổ sung hồ sơ kèm lý do
        ly_do = "Cần bổ sung bản vẽ chi tiết kết cấu móng và sơ đồ cấp thoát nước"
        res_tra = client.post(
            f"{GATEWAY_URL}/api/v1/flow/tasks/{task_tiep_nhan['id']}/complete",
            headers={"Authorization": f"Bearer {token_thu}"},
            json={"variables": {"hoSoHopLe": False, "lyDoBoSung": ly_do, "lyDoTra": ly_do}},
        )
        assert res_tra.status_code == 200, f"Yêu cầu bổ sung thất bại: {res_tra.text}"

        # Kiểm tra hồ sơ ở trạng thái CAN_BO_SUNG trong CSDL
        trang_thai = run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{ho_so_id}'")
        assert trang_thai == "CAN_BO_SUNG", f"Trạng thái hồ sơ phải là CAN_BO_SUNG, nhận: {trang_thai}"

        # 3. cdt.lan cố tình bổ sung hồ sơ của cdt.minh -> 403 Forbidden
        res_unauth = client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/bo_sung_ho_so",
            headers={"Authorization": f"Bearer {token_lan}"},
            json={
                "p_ho_so_id": ho_so_id,
                "p_dia_chi_cong_trinh": "Địa chỉ giả mạo của người khác",
            },
        )
        assert res_unauth.status_code == 403, f"cdt.lan bổ sung hồ sơ của cdt.minh phải bị từ chối 403, nhận: {res_unauth.status_code}"

        # 4. cdt.minh bổ sung hồ sơ với đúng payload UI gửi
        payload_ui = {
            "p_ho_so_id": ho_so_id,
            "p_dia_chi_cong_trinh": "123 Đường Test T07 Đã Bổ Sung, Phường A",
            "p_thua_dat": "T07-1",
            "p_so_tang": 3,
            "p_dien_tich_san_m2": 150.0,
            "p_khu_quan_ly_kien_truc": False,
        }
        res_bo_sung = client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/bo_sung_ho_so",
            headers={"Authorization": f"Bearer {token_minh}"},
            json=payload_ui,
        )
        assert res_bo_sung.status_code == 200, f"cdt.minh bổ sung hồ sơ phải 200, nhận: {res_bo_sung.status_code} - {res_bo_sung.text}"

        # U-06: RPC chỉ cập nhật dữ liệu, trạng thái chưa đổi khi task chưa hoàn thành
        tt_sau_rpc = run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{ho_so_id}'")
        assert tt_sau_rpc == "CAN_BO_SUNG", f"RPC bổ sung không được tự đổi trạng thái, nhận: {tt_sau_rpc}"

        # 5. cdt.minh tìm và hoàn thành task taskChoBoSung qua flow
        task_bo_sung = None
        for _ in range(10):
            tasks_minh_res = client.get(
                f"{GATEWAY_URL}/api/v1/flow/tasks",
                headers={"Authorization": f"Bearer {token_minh}"},
            ).json()
            tasks_minh = tasks_minh_res.get("tasks", []) if isinstance(tasks_minh_res, dict) else tasks_minh_res
            for t in tasks_minh:
                if t.get("taskDefinitionKey") == "taskChoBoSung":
                    vars_dict = {v["name"]: v["value"] for v in t.get("variables", [])}
                    if vars_dict.get("ho_so_id") == str(ho_so_id) or vars_dict.get("business_key") == ho_so_data.get("ma_ho_so"):
                        task_bo_sung = t
                        break
            if task_bo_sung:
                break
            time.sleep(1)

        assert task_bo_sung, "cdt.minh phải có taskChoBoSung trong danh sách nhiệm vụ"

        res_complete_bs = client.post(
            f"{GATEWAY_URL}/api/v1/flow/tasks/{task_bo_sung['id']}/complete",
            headers={"Authorization": f"Bearer {token_minh}"},
            json={"variables": {"noiDungBoSung": "Đã bổ sung bản vẽ móng và sơ đồ thoát nước"}},
        )
        assert res_complete_bs.status_code == 200, f"Hoàn thành taskChoBoSung thất bại: {res_complete_bs.text}"

        # 6. mc.thu nhận lại task taskKiemTraHopLe
        task_lai = None
        for _ in range(10):
            tasks_thu_res = client.get(
                f"{GATEWAY_URL}/api/v1/flow/tasks",
                headers={"Authorization": f"Bearer {token_thu}"},
            ).json()
            tasks_thu = tasks_thu_res.get("tasks", []) if isinstance(tasks_thu_res, dict) else tasks_thu_res
            for t in tasks_thu:
                if t.get("taskDefinitionKey") == "taskKiemTraHopLe":
                    vars_dict = {v["name"]: v["value"] for v in t.get("variables", [])}
                    if vars_dict.get("ho_so_id") == str(ho_so_id) or vars_dict.get("business_key") == ho_so_data.get("ma_ho_so"):
                        task_lai = t
                        break
            if task_lai:
                break
            time.sleep(1)

        assert task_lai, "Sau khi bổ sung, mc.thu phải nhận lại taskKiemTraHopLe để thẩm tra lại"

        # 7. Kiểm tra audit log
        audit_count = run_sql(f"SELECT count(*) FROM core.audit_log WHERE object_id = '{ho_so_id}' AND action = 'ho_so.bo_sung'")
        assert int(audit_count) >= 1, "Phải có ít nhất 1 bản ghi audit log ho_so.bo_sung"
