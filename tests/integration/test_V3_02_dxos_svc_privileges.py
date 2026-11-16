# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import subprocess


def test_V3_02_dxos_svc_cannot_create_schema_or_alter_app_tables():
    # 1. Kiểm tra quyền CREATE trên database dxos của dxos_svc
    query_priv = "SELECT has_database_privilege('dxos_svc', 'dxos', 'CREATE');"
    cmd_priv = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", query_priv]
    proc_priv = subprocess.run(cmd_priv, capture_output=True, text=True, check=True)
    has_create = proc_priv.stdout.strip().lower() == "t"
    assert not has_create, f"dxos_svc vẫn có quyền CREATE trên cơ sở dữ liệu dxos: {proc_priv.stdout.strip()}"

    # 2. Thử chạy CREATE SCHEMA qa_x bằng dxos_svc
    script = (
        "import asyncio, asyncpg, os\n"
        "async def run():\n"
        "    u = os.getenv('DB_USER', 'dxos_svc')\n"
        "    p = os.getenv('DB_PASSWORD')\n"
        "    h = os.getenv('POSTGRES_HOST', 'postgres')\n"
        "    conn = await asyncpg.connect(f'postgresql://{u}:{p}@{h}:5432/dxos')\n"
        "    try:\n"
        "        await conn.execute('CREATE SCHEMA qa_x_test;')\n"
        "        print('SUCCESS')\n"
        "    except Exception as e:\n"
        "        print('REJECTED:', e)\n"
        "    finally:\n"
        "        await conn.close()\n"
        "asyncio.run(run())\n"
    )
    cmd_schema = ["docker", "exec", "dxos-files", "python", "-c", script]
    proc_schema = subprocess.run(cmd_schema, capture_output=True, text=True)
    out = proc_schema.stdout.strip() + " " + proc_schema.stderr.strip()
    assert "REJECTED" in out and "permission denied" in out, f"dxos_svc vẫn tạo được schema hoặc lỗi: {out}"
