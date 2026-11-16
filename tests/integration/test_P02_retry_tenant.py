# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import subprocess
import uuid
import httpx
from tests.integration.conftest import GATEWAY_URL, get_token


def run_sql(sql: str) -> str:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", sql]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout.strip()


def test_P02_P07_retry_tenant_isolation_and_idempotence():
    token_ld_a = get_token("ld.hoa")
    token_ld_b = get_token("ld.phuongb")

    proc_id_a = f"proc-test-{uuid.uuid4().hex[:8]}"
    hs_id_a = str(uuid.uuid4())
    ma_hs_a = f"CP-TEST-{uuid.uuid4().hex[:6]}"

    # Setup hồ sơ phường A ở trạng thái CHO_KY
    run_sql(f"""
    INSERT INTO app_cap_phep.ho_so (id, tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai, dia_chi_cong_trinh, thua_dat, trang_thai, process_instance_id, han_tong_at)
    VALUES ('{hs_id_a}', 'phuong-a', '{ma_hs_a}', 'cdt_test', 'Nguyen Van A', '001200000022', '0901222', 'Dia chi A', 'Thua A', 'CHO_KY', '{proc_id_a}', now() + interval '10 days');
    INSERT INTO core.hook_runs (tenant, process_instance_id, task_def, status)
    VALUES ('phuong-a', '{proc_id_a}', 'taskDuyetCapPhep', 'FAILED');
    """)

    try:
        with httpx.Client(base_url=GATEWAY_URL, timeout=10.0) as client:
            signed_docs_count_before = int(run_sql("SELECT count(*) FROM core.signed_docs;"))

            # 1. Lãnh đạo phường B gọi retry cho hồ sơ phường A -> Phải bị từ chối 403 Forbidden
            resp_b = client.post(
                "/api/v1/flow/hooks/retry",
                headers={"Authorization": f"Bearer {token_ld_b}"},
                json={"process_instance_id": proc_id_a, "task_def": "taskDuyetCapPhep"},
            )
            assert resp_b.status_code == 403, f"Lãnh đạo phường B gọi retry hồ sơ phường A phải 403 nhưng ra {resp_b.status_code}: {resp_b.text}"

            # Kiểm tra CSDL: hồ sơ vẫn CHO_KY, chưa có giấy phép, không có signed_docs mới
            status_after_b = run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{hs_id_a}';")
            assert status_after_b == "CHO_KY"
            gp_count_b = run_sql(f"SELECT count(*) FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id_a}';")
            assert int(gp_count_b) == 0
            signed_docs_count_after = int(run_sql("SELECT count(*) FROM core.signed_docs;"))
            assert signed_docs_count_after == signed_docs_count_before, "Không được sinh signed_docs mới khi bị 403"

            # 1b. Lãnh đạo phường A gọi retry cho quy trình chưa từng chạy hook -> 404 Not Found
            resp_404 = client.post(
                "/api/v1/flow/hooks/retry",
                headers={"Authorization": f"Bearer {token_ld_a}"},
                json={"process_instance_id": "proc-non-existent-9999", "task_def": "taskDuyetCapPhep"},
            )
            assert resp_404.status_code == 404, f"Gọi retry quy trình không tồn tại phải 404 nhưng ra {resp_404.status_code}"

            # 2. Lãnh đạo phường A gọi retry hợp lệ -> Thành công DA_CAP
            resp_a = client.post(
                "/api/v1/flow/hooks/retry",
                headers={"Authorization": f"Bearer {token_ld_a}"},
                json={"process_instance_id": proc_id_a, "task_def": "taskDuyetCapPhep"},
            )
            assert resp_a.status_code == 200, f"Lãnh đạo phường A gọi retry phải 200: {resp_a.status_code} {resp_a.text}"
            res_data_a = resp_a.json()
            code_first = res_data_a.get("public_code")
            assert code_first, "Phải có public_code sau khi ký"

            status_after_a = run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{hs_id_a}';")
            assert status_after_a == "DA_CAP"

            # 3. Lãnh đạo phường A gọi retry cho hồ sơ đã DA_CAP -> Phải ra 409 Conflict
            resp_again = client.post(
                "/api/v1/flow/hooks/retry",
                headers={"Authorization": f"Bearer {token_ld_a}"},
                json={"process_instance_id": proc_id_a, "task_def": "taskDuyetCapPhep"},
            )
            assert resp_again.status_code == 409, f"Gọi retry khi hồ sơ đã DA_CAP phải 409 Conflict nhưng ra {resp_again.status_code}"

            # 4. P-07: Kiểm tra hàm cap_giay_phep khi idempotent=true thì public_code không đổi
            doc_id_orig = run_sql(f"SELECT signed_doc_id FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id_a}';")
            idemp_res = run_sql(f"SELECT app_cap_phep_private.cap_giay_phep('{proc_id_a}', '{doc_id_orig}', 'NEW-FAKE-CODE-999', 'phuong-a');")
            assert "NEW-FAKE-CODE-999" not in idemp_res, f"cap_giay_phep khi idempotent phai tra public_code cu, khong duoc tra ma moi: {idemp_res}"

    finally:
        run_sql(f"""
        DELETE FROM core.hook_runs WHERE process_instance_id = '{proc_id_a}';
        DELETE FROM app_cap_phep.cong_trinh WHERE giay_phep_id IN (SELECT id FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id_a}');
        DELETE FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id_a}';
        DELETE FROM app_cap_phep.ho_so WHERE id = '{hs_id_a}';
        """)
