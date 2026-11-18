# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""V3-02: tài khoản dịch vụ không có đặc quyền thừa: không superuser, không CREATE, không sửa bảng của app."""

import subprocess

from tests.integration.conftest import run_sql

TAI_KHOAN_DICH_VU = ["dxos_svc", "svc", "authenticator", "web_user"]


def psql_as(user: str, sql: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "exec", "dxos-postgres", "psql", "-U", user, "-d", "dxos", "-v", "ON_ERROR_STOP=1", "-c", sql],
        capture_output=True, text=True, encoding="utf-8",
    )


def test_V3_02_tai_khoan_dich_vu_khong_phai_superuser():
    for role in TAI_KHOAN_DICH_VU:
        row = run_sql(
            f"SELECT rolsuper::text || '|' || rolcreaterole::text || '|' || rolcreatedb::text || '|' || rolbypassrls::text "
            f"FROM pg_roles WHERE rolname = '{role}';"
        )
        if role == "dxos_svc":
            assert row, "Thiếu role dxos_svc"
        if row:
            assert row == "false|false|false|false", f"{role} có đặc quyền thừa (super|createrole|createdb|bypassrls = {row})"


def test_V3_02_dxos_svc_cannot_create_schema_or_alter_app_tables():
    assert run_sql("SELECT has_database_privilege('dxos_svc', 'dxos', 'CREATE');") == "f", "dxos_svc còn quyền CREATE trên dxos"
    r = psql_as("dxos_svc", "CREATE SCHEMA qa_x_test;")
    assert r.returncode != 0 and "permission denied" in r.stderr.lower(), f"dxos_svc tạo được schema: {r.stdout} {r.stderr}"
    r = psql_as("dxos_svc", "ALTER TABLE app_cap_phep.ho_so ADD COLUMN qa_x int;")
    assert r.returncode != 0, "dxos_svc sửa được cấu trúc bảng của app"
    assert run_sql(
        "SELECT count(*) FROM information_schema.columns WHERE table_schema = 'app_cap_phep' AND table_name = 'ho_so' AND column_name = 'qa_x';"
    ) == "0"
