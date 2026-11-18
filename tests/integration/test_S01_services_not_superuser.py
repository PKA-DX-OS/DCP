# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import subprocess


def test_S01_services_not_superuser():
    query = """
    SELECT count(*)
    FROM pg_stat_activity
    WHERE datname = 'dxos'
      AND usename = 'postgres'
      AND client_addr IS NOT NULL
      AND application_name NOT LIKE '%psql%';
    """
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", query]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    count = int(proc.stdout.strip())
    assert count == 0, f"Có {count} kết nối từ các dịch vụ sử dụng tài khoản superuser postgres trong CSDL dxos!"
