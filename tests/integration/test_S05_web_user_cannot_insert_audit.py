# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import subprocess


def test_S05_web_user_cannot_insert_audit():
    # Thử INSERT trực tiếp vào core.audit_log dưới vai trò web_user
    sql = "SET ROLE web_user; INSERT INTO core.audit_log (tenant, actor_type, action, prev_hash, hash) VALUES ('phuong-a', 'user', 'hacked', '\\x00', '\\x00');"
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "dxos_svc", "-d", "dxos", "-c", sql]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    assert proc.returncode != 0
    err = proc.stderr.lower() + proc.stdout.lower()
    assert "permission denied" in err or "từ chối quyền" in err
