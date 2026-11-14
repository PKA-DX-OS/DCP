# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import subprocess


def run_psql(sql: str, user: str = "postgres") -> subprocess.CompletedProcess:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", user, "-d", "dxos", "-v", "ON_ERROR_STOP=1", "-c", sql]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_Z01_audit_worm_table_privileges():
    roles = ["dxos_svc", "svc", "dxos_owner", "web_user"]
    privs = ["insert", "update", "delete", "truncate"]
    for r in roles:
        for p in privs:
            sql = f"SELECT has_table_privilege('{r}', 'core.audit_log', '{p}');"
            res = run_psql(sql)
            assert res.returncode == 0, f"Lỗi truy vấn privilege {r} {p}: {res.stderr}"
            assert "f" in res.stdout.strip().splitlines()[-2], f"Vai {r} không được có quyền {p} trên core.audit_log!"


def test_Z01_audit_worm_direct_mutations_blocked():
    roles = ["dxos_svc", "svc", "dxos_owner", "web_user"]
    for r in roles:
        # UPDATE
        res = run_psql(f"SET ROLE {r}; UPDATE core.audit_log SET detail='{{}}' WHERE id = 1;", user="postgres")
        assert res.returncode != 0, f"Vai {r} UPDATE core.audit_log không bị chặn!"
        assert "42501" in res.stderr or "permission denied" in res.stderr.lower() or "bất biến" in res.stderr.lower()

        # DELETE
        res = run_psql(f"SET ROLE {r}; DELETE FROM core.audit_log WHERE id = 1;", user="postgres")
        assert res.returncode != 0, f"Vai {r} DELETE core.audit_log không bị chặn!"
        assert "42501" in res.stderr or "permission denied" in res.stderr.lower() or "bất biến" in res.stderr.lower()

        # TRUNCATE
        res = run_psql(f"SET ROLE {r}; TRUNCATE core.audit_log;", user="postgres")
        assert res.returncode != 0, f"Vai {r} TRUNCATE core.audit_log không bị chặn!"
        assert "42501" in res.stderr or "permission denied" in res.stderr.lower() or "bất biến" in res.stderr.lower()

        # Direct INSERT
        res = run_psql(
            f"SET ROLE {r}; INSERT INTO core.audit_log (tenant, actor_type, action, prev_hash, hash) VALUES ('phuong-a', 'user', 'hack', '\\x00', '\\x00');",
            user="postgres",
        )
        assert res.returncode != 0, f"Vai {r} direct INSERT core.audit_log không bị chặn!"
        assert "42501" in res.stderr or "permission denied" in res.stderr.lower() or "bất biến" in res.stderr.lower()


def test_Z01_audit_seal_worm_mutations_blocked():
    roles = ["dxos_svc", "svc", "dxos_owner", "web_user"]
    for r in roles:
        # UPDATE
        res = run_psql(f"SET ROLE {r}; UPDATE core.audit_seal SET head_hash='\\x00' WHERE id = 1;", user="postgres")
        assert res.returncode != 0, f"Vai {r} UPDATE core.audit_seal không bị chặn!"

        # DELETE
        res = run_psql(f"SET ROLE {r}; DELETE FROM core.audit_seal WHERE id = 1;", user="postgres")
        assert res.returncode != 0, f"Vai {r} DELETE core.audit_seal không bị chặn!"

        # TRUNCATE
        res = run_psql(f"SET ROLE {r}; TRUNCATE core.audit_seal;", user="postgres")
        assert res.returncode != 0, f"Vai {r} TRUNCATE core.audit_seal không bị chặn!"

    # web_user cannot direct INSERT audit_seal
    res = run_psql(
        "SET ROLE web_user; INSERT INTO core.audit_seal (tenant, last_audit_id, head_hash, object_key) VALUES ('phuong-a', 1, '\\x00', 'fake');",
        user="postgres",
    )
    assert res.returncode != 0, "web_user không được INSERT core.audit_seal!"


def test_Z01_record_audit_execution_permissions():
    # dxos_svc can execute core.record_audit
    res = run_psql(
        "SET ROLE dxos_svc; SELECT core.record_audit('phuong-a', 'svc_test', 'service', 'test.audit', 'test', '1', '{\"ok\":true}'::jsonb);",
        user="postgres",
    )
    assert res.returncode == 0, f"dxos_svc phải gọi được core.record_audit: {res.stderr}"

    # web_user CANNOT execute core.record_audit
    res = run_psql(
        "SET ROLE web_user; SELECT core.record_audit('phuong-a', 'web_test', 'user', 'fake.audit', 'test', '1', '{\"ok\":true}'::jsonb);",
        user="postgres",
    )
    assert res.returncode != 0, "web_user không được phép gọi core.record_audit!"
    assert "42501" in res.stderr or "permission denied" in res.stderr.lower()
