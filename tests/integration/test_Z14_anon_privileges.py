# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import subprocess


def run_psql(sql: str, user: str = "postgres") -> subprocess.CompletedProcess:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", user, "-d", "dxos", "-v", "ON_ERROR_STOP=1", "-c", sql]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_Z14_no_anon_function_privileges():
    # 1. Truy vấn kiểm tra không hàm nào trong app_cap_phep hoặc core_api cho phép anon thực thi
    sql = """
    SELECT n.nspname||'.'||p.proname||'('||pg_get_function_identity_arguments(p.oid)||')' as f
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname IN ('app_cap_phep', 'core_api')
      AND has_function_privilege('anon', p.oid, 'EXECUTE');
    """
    res = run_psql(sql)
    assert res.returncode == 0, f"Lỗi truy vấn pg_proc: {res.stderr}"
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip() and not line.startswith("-") and not line.startswith("(")]
    # Dòng đầu là header 'f', nếu trả 0 dòng thì chỉ có header và count
    funcs = [fn for fn in lines if fn != "f" and not fn.startswith("(0 rows)")]
    assert len(funcs) == 0, f"Các hàm sau vẫn cấp quyền EXECUTE cho anon: {funcs}"


def test_Z14_security_definer_functions_have_search_path():
    # 2. Không còn hàm SECURITY DEFINER nào thiếu search_path trong proconfig
    sql = """
    SELECT n.nspname||'.'||p.proname||'('||pg_get_function_identity_arguments(p.oid)||')' as f
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname IN ('app_cap_phep', 'core_api')
      AND p.prosecdef = true
      AND (p.proconfig IS NULL OR NOT (array_to_string(p.proconfig, ',') LIKE '%search_path%'));
    """
    res = run_psql(sql)
    assert res.returncode == 0, f"Lỗi truy vấn proconfig: {res.stderr}"
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip() and not line.startswith("-") and not line.startswith("(")]
    funcs = [fn for fn in lines if fn != "f" and not fn.startswith("(0 rows)")]
    assert len(funcs) == 0, f"Các hàm SECURITY DEFINER sau thiếu search_path: {funcs}"


def test_Z14_empty_claims_rejected_with_42501():
    # 3. Gọi RPC với claims '{}' -> phải báo lỗi 42501
    sql = """
    BEGIN;
    SET LOCAL ROLE web_user;
    SELECT set_config('request.jwt.claims', '{}', true);
    SELECT core_api.gui_yeu_cau_dsar('access', 'test');
    COMMIT;
    """
    res = run_psql(sql, user="authenticator")
    assert res.returncode != 0, "Gọi RPC với claims rỗng không được thành công!"
    assert "42501" in res.stderr or "Chưa xác thực danh tính" in res.stderr
