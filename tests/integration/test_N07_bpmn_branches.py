# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy cho lỗi N-07:
- BPMN cap-phep có các gateway xử lý bổ sung hồ sơ và từ chối cấp phép.
- hoSoHopLe=false -> nhiệm vụ chuyển sang taskChoBoSung, không sinh taskPhanCong, hồ sơ CAN_BO_SUNG.
- Chủ đầu tư hoàn tất bổ sung -> quy trình quay lại taskKiemTraHopLe.
- Lãnh đạo từ chối (dongYCapPhep=false) -> quy trình kết thúc tại endTuChoi, hồ sơ TU_CHOI, không sinh giấy phép.
"""

import os
from pathlib import Path
import subprocess
import uuid
import httpx
from tests.integration.conftest import get_token


def run_psql(sql: str) -> str:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", sql]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def get_flowable_creds():
    user = os.getenv("FLOWABLE_USER", "rest-admin")
    pw = os.getenv("FLOWABLE_PASSWORD")
    env_file = Path(".env")
    if (not pw or not user) and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("FLOWABLE_PASSWORD="):
                pw = line.split("=", 1)[1].strip()
            elif line.startswith("FLOWABLE_USER="):
                user = line.split("=", 1)[1].strip()
    return user or "rest-admin", pw or "dxos_dev_flowable_password_2026"


def test_N07_bpmn_bo_sung_and_tu_choi_branches():
    token_mc = get_token("mc.thu")
    token_cdt = get_token("cdt.minh")
    token_binh = get_token("td.binh")
    token_hoa = get_token("ld.hoa")

    h_mc = {"Authorization": f"Bearer {token_mc}", "Content-Type": "application/json"}
    h_cdt = {"Authorization": f"Bearer {token_cdt}", "Content-Type": "application/json"}
    h_binh = {"Authorization": f"Bearer {token_binh}", "Content-Type": "application/json"}
    h_hoa = {"Authorization": f"Bearer {token_hoa}", "Content-Type": "application/json"}

    fl_user, fl_pw = get_flowable_creds()
    flowable_auth = (fl_user, fl_pw)
    flowable_base = "http://localhost:8082/flowable-rest"

    # Lấy sub của cdt.minh và ld.hoa
    cdt_sub = run_psql("SELECT id::text FROM core.users_directory WHERE username = 'cdt.minh';")
    hoa_sub = run_psql("SELECT id::text FROM core.users_directory WHERE username = 'ld.hoa';")
    binh_sub = run_psql("SELECT id::text FROM core.users_directory WHERE username = 'td.binh';")

    unique_code = f"CP-N07-{uuid.uuid4().hex[:6].upper()}"
    dossier_id = str(uuid.uuid4())

    with httpx.Client(base_url="http://localhost:8080", timeout=15.0) as client:
        # 1. Tạo hồ sơ trong DB
        with httpx.Client(base_url=flowable_base, auth=flowable_auth, timeout=15.0) as fl_client:
            # Khởi động process instance
            start_res = fl_client.post(
                "/service/runtime/process-instances",
                json={
                    "processDefinitionKey": "cap-phep",
                    "businessKey": unique_code,
                    "tenantId": "phuong-a",
                    "variables": [
                        {"name": "ma_ho_so", "value": unique_code},
                        {"name": "ho_so_id", "value": dossier_id},
                        {"name": "chu_dau_tu_sub", "value": cdt_sub},
                        {"name": "cdt_sub", "value": cdt_sub},
                        {"name": "tenant", "value": "phuong-a"},
                        {"name": "dien_tich_san_m2", "value": 150.0},
                        {"name": "khu_quan_ly_kien_truc", "value": True},
                    ],
                },
            )
            assert start_res.status_code in (200, 201), f"Lỗi khởi chạy quy trình Flowable: {start_res.text}"
            proc_id = start_res.json()["id"]

        # Chèn hồ sơ vào DB
        run_psql(f"""
            INSERT INTO app_cap_phep.ho_so (
                id, tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai,
                dia_chi_cong_trinh, thua_dat, so_tang, dien_tich_san_m2,
                khu_quan_ly_kien_truc, trang_thai, buoc, process_instance_id, han_tong_at
            ) VALUES (
                '{dossier_id}'::uuid, 'phuong-a', '{unique_code}', '{cdt_sub}', 'Trần Văn Minh',
                '001099001234', '0901234567', 'Số 10 Phố Test N07', 'Thửa 1 Tờ 1', 3, 150.0,
                true, 'DA_NOP', 'tiep_nhan', '{proc_id}', now() + interval '15 days'
            );
        """)

        # 2. Bước 1: Một cửa kiểm tra tính hợp lệ -> Trả về KHÔNG HỢP LỆ (hoSoHopLe = false)
        with httpx.Client(base_url=flowable_base, auth=flowable_auth, timeout=15.0) as fl_client:
            tasks_res = fl_client.get(f"/service/runtime/tasks?processInstanceId={proc_id}")
            tasks = tasks_res.json().get("data", [])
            task_hop_le = next((t for t in tasks if t["taskDefinitionKey"] == "taskKiemTraHopLe"), None)
            assert task_hop_le, f"Không tìm thấy taskKiemTraHopLe: {tasks}"

        # Cán bộ một cửa hoàn thành taskKiemTraHopLe với hoSoHopLe=false
        res_hl = client.post(
            f"/api/v1/flow/tasks/{task_hop_le['id']}/complete",
            headers=h_mc,
            json={"variables": {"hoSoHopLe": False, "lyDoTra": "Thiếu hồ sơ thiết kế móng"}},
        )
        assert res_hl.status_code == 200, f"Hoàn tất taskKiemTraHopLe thất bại: {res_hl.status_code} - {res_hl.text}"

        # Kiểm tra BPMN: Nhiệm vụ đang mở là taskChoBoSung, KHÔNG CÓ taskPhanCong!
        with httpx.Client(base_url=flowable_base, auth=flowable_auth, timeout=15.0) as fl_client:
            tasks_after_hl = fl_client.get(f"/service/runtime/tasks?processInstanceId={proc_id}").json().get("data", [])
            task_defs = [t["taskDefinitionKey"] for t in tasks_after_hl]
            assert "taskChoBoSung" in task_defs, f"Thiếu taskChoBoSung sau khi trả hồ sơ: {task_defs}"
            assert "taskPhanCong" not in task_defs, f"LỖI: Xuất hiện taskPhanCong khi hồ sơ chưa hợp lệ: {task_defs}"

        # Kiểm tra DB: trạng thái hồ sơ phải là CAN_BO_SUNG
        hs_status = run_psql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{dossier_id}';")
        assert hs_status == "CAN_BO_SUNG", f"Trạng thái hồ sơ phải là CAN_BO_SUNG, thực tế là: {hs_status}"

        # 3. Chủ đầu tư hoàn thành taskChoBoSung
        task_bo_sung = next(t for t in tasks_after_hl if t["taskDefinitionKey"] == "taskChoBoSung")
        res_bs = client.post(
            f"/api/v1/flow/tasks/{task_bo_sung['id']}/complete",
            headers=h_cdt,
            json={"variables": {"noiDungBoSung": "Đã bổ sung bản vẽ thiết kế móng đầy đủ"}},
        )
        assert res_bs.status_code == 200, f"Chủ đầu tư hoàn tất taskChoBoSung thất bại: {res_bs.status_code} - {res_bs.text}"

        # Kiểm tra BPMN: Sau khi bổ sung, quy trình QUAY LẠI taskKiemTraHopLe
        with httpx.Client(base_url=flowable_base, auth=flowable_auth, timeout=15.0) as fl_client:
            tasks_after_bs = fl_client.get(f"/service/runtime/tasks?processInstanceId={proc_id}").json().get("data", [])
            task_defs_bs = [t["taskDefinitionKey"] for t in tasks_after_bs]
            assert "taskKiemTraHopLe" in task_defs_bs, f"Quy trình phải quay lại taskKiemTraHopLe: {task_defs_bs}"

        # 4. Một cửa kiểm tra lại -> Lần này ĐẠT (hoSoHopLe = true)
        task_hl_2 = next(t for t in tasks_after_bs if t["taskDefinitionKey"] == "taskKiemTraHopLe")
        res_hl_2 = client.post(
            f"/api/v1/flow/tasks/{task_hl_2['id']}/complete",
            headers=h_mc,
            json={"variables": {"hoSoHopLe": True}},
        )
        assert res_hl_2.status_code == 200

        # Kiểm tra: Đến taskPhanCong
        with httpx.Client(base_url=flowable_base, auth=flowable_auth, timeout=15.0) as fl_client:
            task_pc = fl_client.get(f"/service/runtime/tasks?processInstanceId={proc_id}").json().get("data", [])[0]
            assert task_pc["taskDefinitionKey"] == "taskPhanCong"

        # 5. Lãnh đạo phân công thẩm định cho td.binh
        res_pc = client.post(
            f"/api/v1/flow/tasks/{task_pc['id']}/complete",
            headers=h_hoa,
            json={"variables": {"nguoiThamDinh": binh_sub, "lanhDaoPhanCong": hoa_sub}},
        )
        assert res_pc.status_code == 200

        # Kiểm tra: Đến taskThamDinh
        with httpx.Client(base_url=flowable_base, auth=flowable_auth, timeout=15.0) as fl_client:
            task_td = fl_client.get(f"/service/runtime/tasks?processInstanceId={proc_id}").json().get("data", [])[0]
            assert "taskThamDinh" in task_td["taskDefinitionKey"]

        # 6. Thẩm định viên hoàn tất thẩm định kỹ thuật
        res_td = client.post(
            f"/api/v1/flow/tasks/{task_td['id']}/complete",
            headers=h_binh,
            json={"variables": {"ketQuaThamDinh": "DAT", "noiDungThamDinh": "Bản vẽ đạt tiêu chuẩn xây dựng"}},
        )
        assert res_td.status_code == 200

        # Kiểm tra: Đến taskDuyetCapPhep
        with httpx.Client(base_url=flowable_base, auth=flowable_auth, timeout=15.0) as fl_client:
            task_duyet = fl_client.get(f"/service/runtime/tasks?processInstanceId={proc_id}").json().get("data", [])[0]
            assert task_duyet["taskDefinitionKey"] == "taskDuyetCapPhep"

        # 7. Lãnh đạo TỪ CHỐI cấp phép (dongYCapPhep = false)
        res_duyet = client.post(
            f"/api/v1/flow/tasks/{task_duyet['id']}/complete",
            headers=h_hoa,
            json={"variables": {"dongYCapPhep": False, "yKienPheDuyet": "Từ chối cấp phép do vướng chỉ giới quy hoạch mở rộng hè phố"}},
        )
        assert res_duyet.status_code == 200

        # 8. Kiểm tra kết quả sau từ chối:
        with httpx.Client(base_url=flowable_base, auth=flowable_auth, timeout=15.0) as fl_client:
            # Quy trình đã hoàn thành, không còn runtime tasks
            active_tasks = fl_client.get(f"/service/runtime/tasks?processInstanceId={proc_id}").json().get("data", [])
            assert len(active_tasks) == 0, f"Quy trình đã kết thúc nhưng vẫn còn task: {active_tasks}"

            # Kiểm tra historic process instance có endActivityId == endTuChoi
            hist_res = fl_client.get(f"/service/history/historic-process-instances/{proc_id}")
            assert hist_res.status_code == 200, f"Không lấy được lịch sử quy trình: {hist_res.text}"
            hist_data = hist_res.json()
            assert hist_data.get("endActivityId") == "endTuChoi", f"endActivityId phải là endTuChoi: {hist_data}"

        # Kiểm tra DB: Hồ sơ có trạng thái TU_CHOI
        final_status = run_psql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{dossier_id}';")
        assert final_status == "TU_CHOI", f"Trạng thái hồ sơ trong DB phải là TU_CHOI: {final_status}"

        # Kiểm tra DB: KHÔNG có giấy phép nào được cấp
        gp_count = int(run_psql(f"SELECT count(*) FROM app_cap_phep.giay_phep WHERE ho_so_id = '{dossier_id}';"))
        assert gp_count == 0, f"Từ chối cấp phép nhưng lại sinh giấy phép trong CSDL: {gp_count}"
