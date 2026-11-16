# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy cho lỗi Q-04:
- Trong luồng complete_task (services/flow/main.py):
  + Khi guard_sql ném lỗi: phải trả HTTP 500 và TUYỆT ĐỐI KHÔNG ký duyệt (không sinh signed_docs).
  + Khi guard_sql trả tenant rỗng hoặc không khớp: phải trả HTTP 403 Forbidden.
  + Khi guard_sql trả trang_thai != 'CHO_KY': phải trả HTTP 409 Conflict.
"""

import json
import subprocess
import time
import uuid
import httpx
from tests.integration.conftest import GATEWAY_URL, get_token


def run_sql(sql: str) -> str:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", sql]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def test_Q04_guard_sql_failure_aborts_signing():
    mc_token = get_token("mc.thu")
    ld_token = get_token("ld.hoa")
    td_token = get_token("td.binh")

    hoa_sub = run_sql("SELECT id::text FROM core.users_directory WHERE username = 'ld.hoa';")
    binh_sub = run_sql("SELECT id::text FROM core.users_directory WHERE username = 'td.binh';")
    minh_sub = run_sql("SELECT id::text FROM core.users_directory WHERE username = 'cdt.minh';")

    unique_code = f"CP-Q04-{uuid.uuid4().hex[:6].upper()}"
    dossier_id = str(uuid.uuid4())

    # 1. Nộp hồ sơ và khởi tạo quy trình
    run_sql(f"""
    INSERT INTO app_cap_phep.ho_so (
        id, tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai,
        dia_chi_cong_trinh, thua_dat, so_tang, dien_tich_san_m2,
        khu_quan_ly_kien_truc, trang_thai, buoc, han_tong_at
    ) VALUES (
        '{dossier_id}'::uuid, 'phuong-a', '{unique_code}', '{minh_sub}', 'Trần Văn Minh',
        '001099001234', '0901234567', 'Số 4 Phố Q04', 'Thửa 4 Tờ 4', 3, 150.0,
        true, 'DA_NOP', 'tiep_nhan', now() + interval '30 days'
    );
    """)

    with httpx.Client(base_url=GATEWAY_URL, timeout=10.0) as client:
        r_start = client.post(
            "/api/v1/flow/processes/start",
            headers={"Authorization": f"Bearer {mc_token}"},
            json={"process_key": "cap-phep", "variables": {"ma_ho_so": unique_code, "dossierId": dossier_id}},
        )
        assert r_start.status_code == 200, f"Start process thất bại: {r_start.text}"
        proc_id = r_start.json()["process_id"]

    run_sql(f"UPDATE app_cap_phep.ho_so SET process_instance_id = '{proc_id}' WHERE id = '{dossier_id}';")

    def get_task_id(tok, task_def):
        for _ in range(15):
            with httpx.Client(base_url=GATEWAY_URL, timeout=5.0) as client:
                r = client.get("/api/v1/flow/tasks", headers={"Authorization": f"Bearer {tok}"})
                if r.status_code == 200:
                    task_list = r.json().get("tasks", []) if isinstance(r.json(), dict) else r.json()
                    for t in task_list:
                        if t.get("processInstanceId") == proc_id and t.get("taskDefinitionKey") == task_def:
                            return t["id"]
            time.sleep(1)
        raise RuntimeError(f"Không tìm thấy nhiệm vụ {task_def} cho quy trình {proc_id}")

    # Bước 1: Tiếp nhận
    t1_id = get_task_id(mc_token, "taskKiemTraHopLe")
    with httpx.Client(base_url=GATEWAY_URL, timeout=5.0) as client:
        r1 = client.post(
            f"/api/v1/flow/tasks/{t1_id}/complete",
            headers={"Authorization": f"Bearer {mc_token}"},
            json={"variables": {"hoSoHopLe": True}},
        )
        assert r1.status_code == 200

    # Bước 2: Phân công
    t2_id = get_task_id(ld_token, "taskPhanCong")
    with httpx.Client(base_url=GATEWAY_URL, timeout=5.0) as client:
        r2 = client.post(
            f"/api/v1/flow/tasks/{t2_id}/complete",
            headers={"Authorization": f"Bearer {ld_token}"},
            json={"variables": {"nguoiThamDinh": binh_sub, "lanhDaoPhanCong": hoa_sub}},
        )
        assert r2.status_code == 200

    # Bước 3: Thẩm định
    t3_id = get_task_id(td_token, "taskThamDinh")
    with httpx.Client(base_url=GATEWAY_URL, timeout=5.0) as client:
        r3 = client.post(
            f"/api/v1/flow/tasks/{t3_id}/complete",
            headers={"Authorization": f"Bearer {td_token}"},
            json={"variables": {"ketQuaThamDinh": "DAT", "noiDungThamDinh": "Đạt chuẩn Q04"}},
        )
        assert r3.status_code == 200

    # Bây giờ quy trình đang ở nhiệm vụ taskDuyetCapPhep
    t4_id = get_task_id(ld_token, "taskDuyetCapPhep")

    # Tạo hàm guard_sql ném ngoại lệ
    run_sql("""
    CREATE OR REPLACE FUNCTION app_cap_phep_private.kiem_tra_hook_ky_error(p_proc text)
    RETURNS text AS $$
    BEGIN
        RAISE EXCEPTION 'Lỗi cố tình kiểm tra guard_sql (Q-04)';
    END;
    $$ LANGUAGE plpgsql;
    GRANT EXECUTE ON FUNCTION app_cap_phep_private.kiem_tra_hook_ky_error(text) TO svc, dxos_svc, dxos_owner;
    """)

    # Lưu lại cấu hình flow_policies cũ
    raw_policy = run_sql("SELECT policy_data FROM core.app_policies WHERE app_code = 'cap-phep' AND policy_type = 'flow_policies';")
    orig_policy = json.loads(raw_policy)

    # Đổi guard_sql của taskDuyetCapPhep sang hàm ném lỗi
    tampered_policy = json.loads(raw_policy)
    tampered_policy["on_task_complete"]["taskDuyetCapPhep"]["guard_sql"] = "app_cap_phep_private.kiem_tra_hook_ky_error"

    signed_docs_before = int(run_sql("SELECT count(*) FROM core.signed_docs;"))

    try:
        run_sql(f"""
        UPDATE core.app_policies
        SET policy_data = '{json.dumps(tampered_policy)}'
        WHERE app_code = 'cap-phep' AND policy_type = 'flow_policies';
        """)

        # Gọi complete taskDuyetCapPhep
        with httpx.Client(base_url=GATEWAY_URL, timeout=10.0) as client:
            r_duyet = client.post(
                f"/api/v1/flow/tasks/{t4_id}/complete",
                headers={"Authorization": f"Bearer {ld_token}"},
                json={"variables": {"dongYCapPhep": True, "pheDuyet": True, "yKienPheDuyet": "Duyet cap phep"}},
            )

            # Yêu cầu Q-04: Gặp lỗi guard_sql phải trả về HTTP 500 và TUYỆT ĐỐI KHÔNG KÝ
            assert r_duyet.status_code == 500, f"Kỳ vọng HTTP 500 khi guard_sql ném lỗi, nhận: {r_duyet.status_code} ({r_duyet.text})"

        # Kiểm tra không có văn bản ký số nào mới được tạo
        signed_docs_after = int(run_sql("SELECT count(*) FROM core.signed_docs;"))
        assert signed_docs_after == signed_docs_before, "Không được sinh bản ghi signed_docs mới khi guard_sql bị lỗi"

    finally:
        # Khôi phục cấu hình policy ban đầu
        run_sql(f"""
        UPDATE core.app_policies
        SET policy_data = '{json.dumps(orig_policy)}'
        WHERE app_code = 'cap-phep' AND policy_type = 'flow_policies';
        """)
        run_sql(f"""
        DELETE FROM core.hook_runs WHERE process_instance_id = '{proc_id}';
        DELETE FROM app_cap_phep.cong_trinh WHERE giay_phep_id IN (SELECT id FROM app_cap_phep.giay_phep WHERE ho_so_id = '{dossier_id}');
        DELETE FROM app_cap_phep.giay_phep WHERE ho_so_id = '{dossier_id}';
        DELETE FROM app_cap_phep.ho_so WHERE id = '{dossier_id}';
        """)
