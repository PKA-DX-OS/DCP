#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Migration runner cho PostgreSQL lõi (P0-03).

- Đọc core/postgres/*.sql theo thứ tự tên tệp.
- Ghi phiên bản đã chạy vào core.schema_migrations(version, checksum, applied_at).
- Chỉ chạy tệp chưa có hoặc có checksum khác (mặc định dừng khi checksum khác).
- Chạy được trên DB đang có dữ liệu; các tệp SQL phải idempotent.

Ví dụ:
    py -3 scripts/migrate.py --status
    py -3 scripts/migrate.py
    py -3 scripts/migrate.py --dry-run
    py -3 scripts/migrate.py --no-docker --psql "C:\\Program Files\\PostgreSQL\\16\\bin\\psql.exe"
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, Exception):
        pass

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "core" / "postgres"
SKIP_PREFIXES = ("00-",)


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def psql_base(args: argparse.Namespace) -> list[str]:
    if args.no_docker:
        psql = args.psql or shutil.which("psql")
        if not psql:
            raise SystemExit("Không tìm thấy psql. Truyền --psql hoặc bỏ --no-docker.")
        return [psql, "-U", args.user, "-d", args.database, "-v", "ON_ERROR_STOP=1"]
    return [
        "docker", "exec", "-i", args.container,
        "psql", "-U", args.user, "-d", args.database, "-v", "ON_ERROR_STOP=1",
    ]


def run_psql(args: argparse.Namespace, sql: str, single_transaction: bool = False) -> subprocess.CompletedProcess:
    cmd = psql_base(args)
    if single_transaction:
        cmd.append("--single-transaction")
    cmd += ["-f", "-"]
    return subprocess.run(cmd, input=sql, capture_output=True, text=True, encoding="utf-8")


def ensure_table(args: argparse.Namespace) -> None:
    sql = """
CREATE SCHEMA IF NOT EXISTS core;
CREATE TABLE IF NOT EXISTS core.schema_migrations (
    version text PRIMARY KEY,
    checksum text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);
"""
    res = run_psql(args, sql, single_transaction=True)
    if res.returncode != 0:
        raise SystemExit(f"Không tạo được core.schema_migrations:\n{res.stderr or res.stdout}")


def load_applied(args: argparse.Namespace) -> dict[str, str]:
    sql = "SELECT version || '|' || checksum FROM core.schema_migrations ORDER BY version;"
    res = run_psql(args, sql)
    if res.returncode != 0:
        raise SystemExit(f"Không đọc được core.schema_migrations:\n{res.stderr or res.stdout}")
    applied: dict[str, str] = {}
    for line in res.stdout.splitlines():
        line = line.strip()
        if "|" in line:
            version, digest = line.split("|", 1)
            applied[version] = digest
    return applied


def migration_files() -> list[Path]:
    files = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name.startswith(SKIP_PREFIXES):
            continue
        files.append(path)
    return files


def apply_file(args: argparse.Namespace, path: Path, digest: str) -> None:
    sql = path.read_text(encoding="utf-8")
    res = run_psql(args, sql, single_transaction=True)
    if res.returncode != 0:
        raise SystemExit(f"[FAIL] {path.name}:\n{res.stderr or res.stdout}")
    record = (
        "INSERT INTO core.schema_migrations (version, checksum) VALUES "
        f"('{path.name}', '{digest}') "
        "ON CONFLICT (version) DO UPDATE SET checksum = EXCLUDED.checksum, applied_at = now();"
    )
    res = run_psql(args, record, single_transaction=True)
    if res.returncode != 0:
        raise SystemExit(f"[FAIL] Không ghi nhận migration {path.name}:\n{res.stderr or res.stdout}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Chạy migration PostgreSQL lõi DCP")
    parser.add_argument("--status", action="store_true", help="Chỉ in trạng thái, không chạy")
    parser.add_argument("--dry-run", action="store_true", help="In các tệp sẽ chạy")
    parser.add_argument("--no-docker", action="store_true", help="Dùng psql trên máy thay vì docker exec")
    parser.add_argument("--psql", help="Đường dẫn psql khi dùng --no-docker")
    parser.add_argument("--container", default="dxos-postgres")
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--database", default="dxos")
    parser.add_argument("--allow-checksum-change", action="store_true", help="Cho phép chạy lại tệp đã đổi checksum")
    args = parser.parse_args(argv)

    ensure_table(args)
    applied = load_applied(args)
    files = migration_files()

    pending: list[tuple[Path, str]] = []
    changed: list[tuple[Path, str]] = []
    for path in files:
        digest = checksum(path)
        if path.name not in applied:
            pending.append((path, digest))
        elif applied[path.name] != digest:
            changed.append((path, digest))

    if args.status or args.dry_run:
        print("Trạng thái migration (core/postgres):")
        for path in files:
            digest = checksum(path)
            if path.name not in applied:
                state = "CHƯA CHẠY"
            elif applied[path.name] != digest:
                state = "ĐÃ ĐỔI"
            else:
                state = "OK"
            print(f"  [{state:9}] {path.name}")
        if changed:
            print("\nCảnh báo: tệp đã chạy nhưng nội dung đã đổi:")
            for path, _ in changed:
                print(f"  - {path.name}")
        return 0

    if changed and not args.allow_checksum_change:
        raise SystemExit(
            "Có tệp migration đã chạy nhưng checksum thay đổi. "
            "Tạo tệp migration mới thay vì sửa tệp cũ, hoặc dùng --allow-checksum-change "
            "khi thực sự muốn chạy lại."
        )

    if not pending and not (changed and args.allow_checksum_change):
        print("[OK] Không có migration mới.")
        return 0

    for path, digest in pending:
        print(f"--> Áp dụng {path.name} ...")
        apply_file(args, path, digest)
        print(f"    [PASS] {path.name}")

    if changed and args.allow_checksum_change:
        for path, digest in changed:
            print(f"--> Chạy lại (checksum đổi) {path.name} ...")
            apply_file(args, path, digest)
            print(f"    [PASS] {path.name}")

    run_psql(args, "NOTIFY pgrst, 'reload schema';")
    print("[PASS] Migration hoàn tất.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
