# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""V3-12: sao lưu trên stack thật.

- Sao lưu chạy hết, có snapshot OpenBao, mã hóa restic, có manifest mã băm.
- Không còn thư mục tạm (staging_*) trong container sau khi sao lưu; volume sao lưu chỉ có kho restic
  và manifest, không có dữ liệu rõ.
- Bản sao lưu giải mã được và khớp manifest (restore --chi-kiem, không ghi đè dữ liệu đang chạy).
- Không bí mật nào (mật khẩu restic, mật khẩu CSDL) xuất hiện trong log.
"""

import subprocess

from tests.integration.conftest import ROOT


def tools(*args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "--profile", "tools", "run", "--rm", "-T", "--entrypoint", "sh", "tools", "-c", " ".join(args)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=timeout,
    )


def bi_mat() -> list[str]:
    ds = []
    f = ROOT / "secrets" / "restic-password.txt"
    if f.exists():
        ds.append(f.read_text(encoding="utf-8").strip())
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if ("PASSWORD" in k or "SECRET" in k) and len(v.strip()) >= 8:
                ds.append(v.strip())
    return ds


def test_backup_and_staging_cleanup():
    # Cùng một container: sao lưu rồi liệt kê /tmp và volume sao lưu
    r = tools("python3 scripts/backup.py && echo ---TMP && ls -1 /tmp && echo ---VOL && ls -1 /var/backups/dxos")
    out = r.stdout
    assert r.returncode == 0, f"Sao lưu thất bại:\n{out[-2000:]}\n{r.stderr[-1000:]}"
    assert "Đã xuất snapshot OpenBao storage" in out
    assert "Đã mã hóa vào kho Restic" in out
    assert "manifest tại" in out
    tmp = out.split("---TMP", 1)[1].split("---VOL", 1)[0].split()
    vol = out.split("---VOL", 1)[1].split()
    assert not [x for x in tmp if x.startswith("staging_")], f"Còn thư mục tạm chưa dọn: {tmp}"
    assert set(vol) <= {"restic_repo", "manifests"} and "restic_repo" in vol, f"Volume sao lưu có dữ liệu rõ: {vol}"
    lo = [s for s in bi_mat() if s in out or s in r.stderr]
    assert not lo, "Log sao lưu lộ bí mật"


def test_restore_chi_kiem_ma_bam():
    r = tools("python3 scripts/restore.py --chi-kiem && ls -1 /tmp")
    assert r.returncode == 0, f"Giải mã hoặc kiểm mã băm thất bại:\n{r.stdout[-2000:]}\n{r.stderr[-1000:]}"
    assert "Mã băm mọi tệp khớp manifest" in r.stdout
    assert "dxos_restored_" not in r.stdout, "Thư mục giải mã tạm chưa được dọn"
    lo = [s for s in bi_mat() if s in r.stdout or s in r.stderr]
    assert not lo, "Log phục hồi lộ bí mật"
