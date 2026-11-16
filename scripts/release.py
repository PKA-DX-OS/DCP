#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Đóng gói phát hành cục bộ: tar.gz + SHA256SUMS (không gồm secret/runtime data)."""

import argparse
import hashlib
import sys
import tarfile
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception as exc:
        print(f"[release] Không thể chuyển UTF-8: {exc}", file=sys.stderr)

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {".git", "backups", "secrets", "node_modules", "dist", "__pycache__", ".pytest_cache", ".ruff_cache", "certs"}
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
    parser.add_argument("--version", default="1.1.0")
    args = parser.parse_args()
    version = args.version.strip().lstrip("v")
    if not version:
        print("[ERROR] Version rỗng", file=sys.stderr)
        return 1

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if version not in changelog:
        print(f"[ERROR] Không thấy version {version} trong CHANGELOG.md", file=sys.stderr)
        return 1

    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    archive = dist / f"dxos-{version}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for path in sorted(ROOT.rglob("*")):
            rel = path.relative_to(ROOT)
            if any(part in EXCLUDE_DIRS for part in rel.parts):
                continue
            if path.name in EXCLUDE_FILES or path.suffix in EXCLUDE_SUFFIXES:
                continue
            tar.add(path, arcname=f"dxos-{version}/{rel.as_posix()}")

    checksum = sha256_file(archive)
    (dist / "SHA256SUMS").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    print(f"[release] Đã tạo {archive} ({archive.stat().st_size} bytes)")
    print(f"[release] SHA256 {checksum}")
    print(f"[release] Đã ghi {dist / 'SHA256SUMS'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
