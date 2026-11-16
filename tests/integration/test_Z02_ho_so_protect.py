# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import subprocess
import uuid


def run_psql(sql: str, user: str = "authenticator") -> subprocess.CompletedProcess:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", user, "-d", "dxos", "-v", "ON_ERROR_STOP=1", "-c", sql]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_Z02_ho_so_protect_columns_and_rls():
    hs_id = str(uuid.uuid4())
    claims = json.dumps({"sub": "cdt_test_z02", "tenant": "phuong-a", "roles": ["app:cap-phep:chu-dau-tu"]})

    # 1. Setup hồ sơ bằng postgres
    setup_sql = f"""
    INSERT INTO app_cap_phep.ho_so (id, tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai, dia_chi_cong_trinh, thua_dat, trang_thai, han_tong_at)
    VALUES ('{hs_id}', 'phuong-a', 'HS-Z02', 'cdt_test_z02', 'Nguyen Van Z02', '001200000002', '0912345678', '123 Test', 'Thua 1', 'CHO_DUYET', now() + interval '15 days');
    """
    res = run_psql(setup_sql, user="postgres")
    assert res.returncode == 0, f"Setup hồ sơ thất bại: {res.stderr}"

    try:
        # 2. Hồ sơ CHO_DUYET: chủ đầu tư UPDATE so_tang -> sửa 0 dòng hoặc lỗi 42501
        update_cho_duyet = f"""
        BEGIN;
        SET LOCAL ROLE web_user;
        SELECT set_config('request.jwt.claims', '{claims}', true);
        UPDATE app_cap_phep.ho_so SET so_tang = 5 WHERE id = '{hs_id}';
        COMMIT;
        """
        res = run_psql(update_cho_duyet, user="authenticator")
        if res.returncode == 0:
            assert "UPDATE 0" in res.stdout, f"Không được sửa hồ sơ CHO_DUYET: {res.stdout}"
        else:
            assert "42501" in res.stderr or "CAN_BO_SUNG" in res.stderr

        # 3. Hồ sơ DA_CAP: đổi sang DA_CAP bằng postgres, chủ đầu tư thử sửa dien_tich, dia_chi -> sửa 0 dòng hoặc lỗi 42501
        run_psql(f"UPDATE app_cap_phep.ho_so SET trang_thai = 'DA_CAP' WHERE id = '{hs_id}';", user="postgres")
        update_da_cap = f"""
        BEGIN;
        SET LOCAL ROLE web_user;
        SELECT set_config('request.jwt.claims', '{claims}', true);
        UPDATE app_cap_phep.ho_so SET dien_tich_san_m2 = 999.0, dia_chi_cong_trinh = 'Hack' WHERE id = '{hs_id}';
        COMMIT;
        """
        res = run_psql(update_da_cap, user="authenticator")
        if res.returncode == 0:
            assert "UPDATE 0" in res.stdout, f"Không được sửa hồ sơ DA_CAP: {res.stdout}"
        else:
            assert "42501" in res.stderr or "CAN_BO_SUNG" in res.stderr

        # 4. Hồ sơ CAN_BO_SUNG: đổi sang CAN_BO_SUNG bằng postgres
        run_psql(f"UPDATE app_cap_phep.ho_so SET trang_thai = 'CAN_BO_SUNG' WHERE id = '{hs_id}';", user="postgres")
        # 4a. Sửa so_tang thành công
        update_can_bo_sung = f"""
        BEGIN;
        SET LOCAL ROLE web_user;
        SELECT set_config('request.jwt.claims', '{claims}', true);
        UPDATE app_cap_phep.ho_so SET so_tang = 3 WHERE id = '{hs_id}';
        COMMIT;
        """
        res = run_psql(update_can_bo_sung, user="authenticator")
        assert res.returncode == 0, f"Hồ sơ CAN_BO_SUNG phải cho phép chủ đầu tư cập nhật: {res.stderr}"
        assert "UPDATE 1" in res.stdout

        # 4b. Đổi trang_thai trực tiếp qua REST thì lỗi 42501
        update_trang_thai = f"""
        BEGIN;
        SET LOCAL ROLE web_user;
        SELECT set_config('request.jwt.claims', '{claims}', true);
        UPDATE app_cap_phep.ho_so SET trang_thai = 'DA_CAP' WHERE id = '{hs_id}';
        COMMIT;
        """
        res = run_psql(update_trang_thai, user="authenticator")
        assert res.returncode != 0, "Không được tự ý đổi trang_thai qua REST API!"
        assert "42501" in res.stderr or "quy trình BPMN" in res.stderr or "permission denied" in res.stderr

        # 5. RPC bo_sung_ho_so(...) vẫn hoạt động đúng với hồ sơ CAN_BO_SUNG
        bo_sung_rpc = f"""
        BEGIN;
        SET LOCAL ROLE web_user;
        SELECT set_config('request.jwt.claims', '{claims}', true);
        SELECT app_cap_phep.bo_sung_ho_so('{hs_id}'::uuid, 'Dia chi moi', 'Thua 2', 4, 150.0, false);
        COMMIT;
        """
        res = run_psql(bo_sung_rpc, user="authenticator")
        assert res.returncode == 0, f"RPC bo_sung_ho_so phải thành công: {res.stderr}"
        assert "success" in res.stdout

    finally:
        run_psql(f"DELETE FROM app_cap_phep.ho_so WHERE id = '{hs_id}';", user="postgres")
