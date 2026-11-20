#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Đóng gói phát hành cục bộ (không gồm bí mật và dữ liệu chạy):

    dist/dxos-<version>.tar.gz     mã nguồn
    dist/SHA256SUMS                mã băm gói
    dist/dxos-<version>.json       metadata: phiên bản, commit, thời điểm, số tệp, mã băm

    python scripts/release.py --version 1.0
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception as exc:
        print(f"[release] Không thể chuyển UTF-8: {exc}", file=sys.stderr)

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {".git", "backups", "secrets", "node_modules", "dist", "logs", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", "certs"}
EXCLUDE_FILES = {".env", "apisix.yaml", "jwks.json", "release.env"}
EXCLUDE_SUFFIXES = {".pyc"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="1.1")
    args = parser.parse_args()
    version = args.version.strip().lstrip("v")
    if not version:
        print("[ERROR] Version rỗng", file=sys.stderr)
        return 1

    changelog_file = ROOT / "CHANGELOG.md"
    if changelog_file.exists():
        if version not in changelog_file.read_text(encoding="utf-8"):
            print(f"[ERROR] Không thấy version {version} trong CHANGELOG.md", file=sys.stderr)
            return 1
    else:
        print("[release] Chưa có CHANGELOG.md, bỏ qua bước đối chiếu phiên bản")

    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    archive = dist / f"dxos-{version}.tar.gz"
    so_tep = 0
    with tarfile.open(archive, "w:gz") as tar:
        for path in sorted(ROOT.rglob("*")):
            rel = path.relative_to(ROOT)
            if any(part in EXCLUDE_DIRS for part in rel.parts):
                continue
            if not path.is_file() or path.name in EXCLUDE_FILES or path.suffix in EXCLUDE_SUFFIXES:
                continue
            tar.add(path, arcname=f"dxos-{version}/{rel.as_posix()}")
            so_tep += 1

    checksum = sha256_file(archive)
    (dist / "SHA256SUMS").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
        commit = r.stdout.strip() if r.returncode == 0 else ""
    except FileNotFoundError:
        commit = ""
    meta = {
        "name": "dxos-open-core",
        "version": version,
        "commit": commit or None,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "archive": archive.name,
        "size": archive.stat().st_size,
        "sha256": checksum,
        "files": so_tep,
    }
    meta_file = dist / f"dxos-{version}.json"
    meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[release] Đã tạo {archive} ({archive.stat().st_size} bytes)")
    print(f"[release] SHA256 {checksum}")
    print(f"[release] Đã ghi {dist / 'SHA256SUMS'} và {meta_file.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
