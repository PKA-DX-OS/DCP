# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import subprocess


def run_psql(sql: str, user: str = "authenticator") -> subprocess.CompletedProcess:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", user, "-d", "dxos", "-v", "ON_ERROR_STOP=1", "-v", "VERBOSITY=verbose", "-c", sql]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_Z03_dsar_workflow_and_security():
    cdt_claims = json.dumps({"sub": "cdt_test_z03", "tenant": "phuong-a", "roles": ["app:cap-phep:chu-dau-tu"]})
    ta_claims = json.dumps({"sub": "ta_test_z03", "tenant": "phuong-a", "roles": ["dx:tenant-admin"]})
    tab_claims = json.dumps({"sub": "tab_test_z03", "tenant": "phuong-b", "roles": ["dx:tenant-admin"]})

    # 1. Chủ đầu tư gửi DSAR
    sql_gui = f"""
    BEGIN;
    SET LOCAL ROLE web_user;
    SELECT set_config('request.jwt.claims', '{cdt_claims}', true);
    SELECT core_api.gui_yeu_cau_dsar('access', 'Yeu cau cung cap ban sao du lieu ca nhan') as res;
    COMMIT;
    """
    res = run_psql(sql_gui)
    assert res.returncode == 0, f"Gửi DSAR thất bại: {res.stderr}"

    # Lấy ID của DSAR vừa tạo
    sql_get_id = """
    SELECT id FROM core.dsar_requests WHERE tenant = 'phuong-a' AND subject_sub = 'cdt_test_z03' ORDER BY received_at DESC LIMIT 1;
    """
    res_id = run_psql(sql_get_id, user="postgres")
    assert res_id.returncode == 0
    dsar_id = res_id.stdout.strip().splitlines()[-2].strip()

    try:
        # 2. Chủ đầu tư tự xử lý DSAR của mình -> 42501
        sql_cdt_xu_ly = f"""
        BEGIN;
        SET LOCAL ROLE web_user;
        SELECT set_config('request.jwt.claims', '{cdt_claims}', true);
        SELECT core_api.xu_ly_dsar('{dsar_id}'::uuid, 'completed', 'Tu dong hoan tat');
        COMMIT;
        """
        res_cdt = run_psql(sql_cdt_xu_ly)
        assert res_cdt.returncode != 0, "Chủ đầu tư không được phép tự xử lý DSAR!"
        assert "42501" in res_cdt.stderr

        # 3. Tenant-admin phường khác xử lý DSAR này -> 42501
        sql_tab_xu_ly = f"""
        BEGIN;
        SET LOCAL ROLE web_user;
        SELECT set_config('request.jwt.claims', '{tab_claims}', true);
        SELECT core_api.xu_ly_dsar('{dsar_id}'::uuid, 'completed', 'Xy ly cheo tenant');
        COMMIT;
        """
        res_tab = run_psql(sql_tab_xu_ly)
        assert res_tab.returncode != 0, "Tenant-admin phường khác không được xử lý DSAR của phuong-a!"
        assert "42501" in res_tab.stderr

        # 4. Tenant-admin cùng phường gọi xu_ly_dsar -> thành công, status=completed, closed_at NOT NULL, result lưu đúng
        sql_ta_xu_ly = f"""
        BEGIN;
        SET LOCAL ROLE web_user;
        SELECT set_config('request.jwt.claims', '{ta_claims}', true);
        SELECT core_api.xu_ly_dsar('{dsar_id}'::uuid, 'completed', 'Da cung cap ban sao day du');
        COMMIT;
        """
        res_ta = run_psql(sql_ta_xu_ly)
        assert res_ta.returncode == 0, f"Tenant-admin xử lý DSAR hợp lệ thất bại: {res_ta.stderr}"

        # Kiểm tra kết quả trong DB
        sql_check = f"""
        SELECT status, closed_at IS NOT NULL as is_closed, result::text FROM core.dsar_requests WHERE id = '{dsar_id}';
        """
        res_chk = run_psql(sql_check, user="postgres")
        assert res_chk.returncode == 0
        out = res_chk.stdout
        assert "completed" in out
        assert "t" in out
        assert "Da cung cap ban sao day du" in out

    finally:
        run_psql(f"DELETE FROM core.dsar_requests WHERE id = '{dsar_id}';", user="postgres")
