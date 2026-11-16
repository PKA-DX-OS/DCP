# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import subprocess
import time
import base64
import json
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


def test_Z04_permit_auto_generation_and_signing():
    cdt_token = get_token("cdt.minh")
    mc_token = get_token("mc.thu")
    ld_token = get_token("ld.hoa")
    td_token = get_token("td.binh")
    binh_sub = parse_sub(td_token)
    hoa_sub = parse_sub(ld_token)

    # 1. Nộp hồ sơ
    with httpx.Client(timeout=10.0) as client:
        resp = submit_dossier(cdt_token, {
                "ho_ten": "Tran Thi Z04",
                "cccd": "001200000044",
                "dien_thoai": "0988776655",
                "dia_chi_cong_trinh": "123 Duong Z04 Phuong A",
                "thua_dat": "Thua 4 To 4",
                "so_tang": 2,
                "dien_tich_san_m2": 120.0,
                "khu_quan_ly_kien_truc": True,
            }, tag_prefix="Z04_cap_giay_phep", client=client)
        assert resp.status_code == 200, f"Nộp hồ sơ thất bại: {resp.text}"
        hs_data = resp.json()
        hs_id = hs_data["id"]
        ma_hs = hs_data["ma_ho_so"]
        assert ma_hs, "Hồ sơ phải có mã hồ sơ"
        proc_id = hs_data.get("process_instance_id")

    # Nếu process_instance_id chưa có trong response, khởi động quy trình Flowable cho hồ sơ
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
    assert proc_id, "Hồ sơ phải có process_instance_id"

    # Helper tìm task theo candidateGroup hoặc assignee
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

    # 2. Tiếp nhận một cửa: taskKiemTraHopLe
    t1_id = get_task_id(mc_token, "taskKiemTraHopLe")
    with httpx.Client(timeout=5.0) as client:
        r = client.post(
            f"{GATEWAY_URL}/api/v1/flow/tasks/{t1_id}/complete",
            headers={"Authorization": f"Bearer {mc_token}"},
            json={"variables": {"hoSoHopLe": True}},
        )
        assert r.status_code == 200, f"Hoàn thành taskKiemTraHopLe thất bại: {r.text}"

    # 3. Lãnh đạo phân công: taskPhanCong
    t2_id = get_task_id(ld_token, "taskPhanCong")
    with httpx.Client(timeout=5.0) as client:
        r = client.post(
            f"{GATEWAY_URL}/api/v1/flow/tasks/{t2_id}/complete",
            headers={"Authorization": f"Bearer {ld_token}"},
            json={"variables": {"nguoiThamDinh": binh_sub, "lanhDaoPhanCong": hoa_sub}},
        )
        assert r.status_code == 200, f"Hoàn thành taskPhanCong thất bại: {r.text}"

    # 4. Thẩm định viên: taskThamDinh
    t3_id = get_task_id(td_token, "taskThamDinh")
    with httpx.Client(timeout=5.0) as client:
        r = client.post(
            f"{GATEWAY_URL}/api/v1/flow/tasks/{t3_id}/complete",
            headers={"Authorization": f"Bearer {td_token}"},
            json={"variables": {"ketQuaThamDinh": "DAT", "noiDungThamDinh": "Bản vẽ đạt chuẩn"}},
        )
        assert r.status_code == 200, f"Hoàn thành taskThamDinh thất bại: {r.text}"

    # 5. Lãnh đạo phê duyệt: taskDuyetCapPhep -> kích hoạt hook tự động ký số và cấp phép
    t4_id = get_task_id(ld_token, "taskDuyetCapPhep")
    with httpx.Client(timeout=10.0) as client:
        r = client.post(
            f"{GATEWAY_URL}/api/v1/flow/tasks/{t4_id}/complete",
            headers={"Authorization": f"Bearer {ld_token}"},
            json={"variables": {"dongYCapPhep": True, "pheDuyet": True, "yKienPheDuyet": "Đồng ý cấp phép"}},
        )
        assert r.status_code == 200, f"Lãnh đạo duyệt cấp phép thất bại: {r.text}"

    # Chờ 2 giây để giao dịch hoàn tất
    time.sleep(2)

    # 6. Kiểm tra các kết quả bắt buộc:
    # 6a. Đúng 1 dòng trong app_cap_phep.giay_phep
    gp_count = int(run_sql(f"SELECT count(*) FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}';") or "0")
    assert gp_count == 1, f"Kỳ vọng đúng 1 giấy phép được sinh ra, thực tế: {gp_count}"

    so_gp = run_sql(f"SELECT so_giay_phep FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}';")
    assert so_gp.startswith("GPXD-phuong-a-"), f"Số giấy phép phải đúng định dạng GPXD-tenant-yyyy-seq: {so_gp}"

    signed_doc_id = run_sql(f"SELECT signed_doc_id FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}';")
    assert signed_doc_id, "Giấy phép phải gắn với signed_doc_id"

    # 6b. Đúng 1 dòng trong core.signed_docs có status 'valid'
    doc_status = run_sql(f"SELECT status FROM core.signed_docs WHERE id = '{signed_doc_id}';")
    assert doc_status == "valid", f"Trạng thái văn bản ký số phải là 'valid', thực tế: {doc_status}"

    public_code = run_sql(f"SELECT public_code FROM core.signed_docs WHERE id = '{signed_doc_id}';")
    assert public_code, "Văn bản phải có public_code"

    # 6c. Đúng 1 dòng trong app_cap_phep.cong_trinh
    ct_count = int(run_sql(f"SELECT count(*) FROM app_cap_phep.cong_trinh WHERE giay_phep_id = (SELECT id FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}');") or "0")
    assert ct_count == 1, f"Kỳ vọng đúng 1 công trình gắn với giấy phép, thực tế: {ct_count}"

    # 6d. Hồ sơ ở trạng thái DA_CAP
    hs_status = run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{hs_id}';")
    assert hs_status == "DA_CAP", f"Trạng thái hồ sơ phải là DA_CAP, thực tế: {hs_status}"

    # 6e. GET /kiem-tra/<public_code> trả 200 kèm số giấy phép
    with httpx.Client(timeout=5.0) as client:
        chk_resp = client.get(f"{GATEWAY_URL}/api/v1/docs/verify/{public_code}")
        if chk_resp.status_code != 200:
            chk_resp = client.get(f"{GATEWAY_URL}/kiem-tra/{public_code}")
        assert chk_resp.status_code == 200, f"Tra cứu công khai /kiem-tra/{public_code} phải trả 200: {chk_resp.status_code}"
