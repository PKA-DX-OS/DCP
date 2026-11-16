# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def test_V3_01_compose_no_app_mount_and_table_owner():
    # 1. Kiểm tra compose.yaml không gắn migration của app vào postgres initdb
    compose_text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "02-app-cap-phep.sql" not in compose_text, "compose.yaml vẫn gắn migration app vào core postgres!"
    assert "01-app-cap-phep.sql" not in compose_text, "compose.yaml vẫn gắn migration app vào core postgres!"

    # 2. Kiểm tra chủ sở hữu các bảng nghiệp vụ trong app_cap_phep phải là dxos_owner
    query = """
    SELECT table_name, tableowner
    FROM information_schema.tables t
    JOIN pg_tables pt ON t.table_name = pt.tablename AND t.table_schema = pt.schemaname
    WHERE t.table_schema = 'app_cap_phep' AND t.table_name = 'ho_so';
    """
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", query]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    out = proc.stdout.strip()
    assert out, "Bảng app_cap_phep.ho_so không tồn tại!"
    parts = out.split("|")
    owner = parts[1] if len(parts) > 1 else ""
    assert owner == "dxos_owner", f"Bảng app_cap_phep.ho_so có chủ sở hữu là '{owner}', mong đợi 'dxos_owner'!"
