# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Regression test for V3-12:
- Backup snapshots OpenBao KMS storage cleanly without failing.
- Backup staging directory is always cleaned up in finally (no unencrypted data exposed).
- Backup volume contains only encrypted restic repository; no plaintext files.
- Disaster recovery restore restores PostgreSQL, S3, OpenBao KMS, and doc-sign.
- Previously signed permits remain 'Hop_le' and audit chain verification passes.
"""

import subprocess
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parent.parent.parent


def test_backup_and_staging_cleanup():
    # 1. Run backup via tools container
    res_bk = subprocess.run(
        ["docker", "compose", "run", "--rm", "tools", "python", "scripts/backup.py"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
    )
    assert res_bk.returncode == 0, f"Backup failed:\nStdout:\n{res_bk.stdout}\nStderr:\n{res_bk.stderr}"
    assert "Đã xuất snapshot OpenBao storage" in res_bk.stdout
    assert "Đã mã hóa và đồng bộ thành công vào kho Restic" in res_bk.stdout

    # 2. Verify no unencrypted staging directory remains in /var/backups/dxos
    res_ls = subprocess.run(
        ["docker", "compose", "run", "--rm", "tools", "sh", "-c", "ls -1 /var/backups/dxos"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=30,
    )
    assert res_ls.returncode == 0
    items = [line.strip() for line in res_ls.stdout.strip().splitlines() if line.strip()]
    staging_items = [it for it in items if it.startswith("staging_")]
    assert len(staging_items) == 0, f"Unencrypted staging directories left in backup volume: {staging_items}"
    assert "restic_repo" in items, f"restic_repo missing in backup volume: {items}"


def test_restore_and_permit_validity():
    # 1. Run restore via tools container
    res_rst = subprocess.run(
        ["docker", "compose", "run", "--rm", "tools", "python", "scripts/restore.py"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
    )
    assert res_rst.returncode == 0, f"Restore failed:\nStdout:\n{res_rst.stdout}\nStderr:\n{res_rst.stderr}"
    assert "PHỤC HỒI THẢM HỌA HOÀN TẤT THÀNH CÔNG" in res_rst.stdout
    assert "OpenBao KMS đã được phục hồi" in res_rst.stdout

    # Khởi động lại doc-sign sau khi OpenBao KMS phục hồi để làm mới kết nối
    subprocess.run(["docker", "restart", "dxos-doc-sign"], capture_output=True, timeout=30)

    # 2. Verify audit chain verification passes
    res_vrf = subprocess.run(
        ["docker", "compose", "run", "--rm", "tools", "python", "scripts/verify_audit.py"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=60,
    )
    assert res_vrf.returncode == 0, f"Audit verify failed:\n{res_vrf.stdout}\n{res_vrf.stderr}"

    # 3. Check public license verification
    res_code = subprocess.run(
        [
            "docker",
            "exec",
            "dxos-postgres",
            "psql",
            "-U",
            "postgres",
            "-d",
            "dxos",
            "-t",
            "-A",
            "-c",
            "SELECT public_code FROM core.signed_docs WHERE status = 'valid' ORDER BY issued_at DESC LIMIT 1;",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert res_code.returncode == 0, f"Query public code failed: {res_code.stderr}"
    pub_code = res_code.stdout.strip()
    assert pub_code.startswith("DOC-"), f"Invalid public code: {pub_code}"

    with httpx.Client(base_url="http://localhost:8080", timeout=10.0) as client:
        resp = client.get(f"/kiem-tra/{pub_code}")
        assert resp.status_code == 200, f"Public verify returned {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("trang_thai") == "Hop_le"
        assert data.get("public_code") == pub_code
