# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import subprocess
import urllib.request
from tests.integration.conftest import get_token, GATEWAY_URL


def test_S04_audit_tamper_detected():
    token = get_token("kt.an")

    # 1. Lấy thông tin detail ban đầu của bản ghi id 6
    get_orig = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", "SELECT detail::text FROM core.audit_log WHERE id = 6;"]
    orig_detail = subprocess.run(get_orig, capture_output=True, text=True, check=True).stdout.strip()

    try:
        # 2. Sửa lén bản ghi id 6 bằng superuser postgres (tạm thời tắt trigger để giả lập tấn công can thiệp DB cấp thấp)
        tamper_cmd = [
            "docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-c",
            "ALTER TABLE core.audit_log DISABLE TRIGGER trg_audit_log_immutable; "
            "UPDATE core.audit_log SET detail=jsonb_build_object('tampered', true) WHERE id = 6; "
            "ALTER TABLE core.audit_log ENABLE TRIGGER trg_audit_log_immutable;"
        ]
        subprocess.run(tamper_cmd, check=True)

        # 3. Gọi API /api/v1/audit/verify -> Phải trả valid = False và tampered_id = 6
        req = urllib.request.Request(
            f"{GATEWAY_URL}/api/v1/audit/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            assert data.get("valid") is False
            assert data.get("tampered_id") == 6

        # 4. Kiểm tra CLI dx verify thoát mã khác 0
        verify_proc = subprocess.run(
            ["docker", "compose", "run", "--rm", "tools", "python", "scripts/verify_audit.py"],
            capture_output=True,
            text=True,
        )
        assert verify_proc.returncode != 0
        assert "PHÁT HIỆN GIAN LẬN" in verify_proc.stdout or "CAN THIỆP" in verify_proc.stdout

    finally:
        # 5. Phục hồi lại dữ liệu gốc của id 6 để bảo đảm chuỗi toàn vẹn
        restore_cmd = [
            "docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-c",
            "ALTER TABLE core.audit_log DISABLE TRIGGER trg_audit_log_immutable; "
            f"UPDATE core.audit_log SET detail='{orig_detail}'::jsonb WHERE id = 6; "
            "ALTER TABLE core.audit_log ENABLE TRIGGER trg_audit_log_immutable;"
        ]
        subprocess.run(restore_cmd, check=True)

        # Xác minh chuỗi đã khôi phục hợp lệ
        req = urllib.request.Request(
            f"{GATEWAY_URL}/api/v1/audit/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            assert data.get("valid") is True
