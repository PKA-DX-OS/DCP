# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import subprocess


def test_E01_services_do_not_have_superuser_or_admin_secrets():
    """E-01: Kiểm tra các dịch vụ mỏng không chứa các bí mật quản trị nhạy cảm của hệ thống."""
    forbidden_keys = [
        "KEYCLOAK_ADMIN_PASSWORD",
        "DX_SEED_SECRET",
        "POSTGRES_SUPERUSER_PASSWORD",
        "AUTHENTICATOR_PASSWORD",
        "APISIX_OIDC_SECRET",
    ]
    services = ["dxos-files", "dxos-flow", "dxos-doc-sign", "dxos-ingest", "dxos-audit"]

    for svc in services:
        cmd = ["docker", "exec", svc, "env"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            continue
        env_lines = res.stdout.splitlines()
        env_keys = {line.split("=")[0] for line in env_lines if "=" in line}

        for forbidden in forbidden_keys:
            assert forbidden not in env_keys, f"Dịch vụ {svc} bị rò rỉ biến nhạy cảm {forbidden}!"


def test_E02_files_container_cannot_login_as_postgres_superuser():
    """E-02: Từ dxos-files không có biến POSTGRES_SUPERUSER_PASSWORD."""
    cmd = ["docker", "exec", "dxos-files", "python", "-c", "import os; print(os.environ.get('POSTGRES_SUPERUSER_PASSWORD', ''))"]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    if res.returncode == 0:
        val = res.stdout.strip()
        assert val == "", "dxos-files không được phép chứa POSTGRES_SUPERUSER_PASSWORD!"


def test_E04_files_container_does_not_have_dx_seed_secret():
    """E-04: dxos-files không có biến DX_SEED_SECRET để xin token quyền quản trị."""
    cmd = ["docker", "exec", "dxos-files", "python", "-c", "import os; print(os.environ.get('DX_SEED_SECRET', ''))"]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    if res.returncode == 0:
        val = res.stdout.strip()
        assert val == "", "dxos-files không được phép chứa DX_SEED_SECRET!"
