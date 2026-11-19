#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Đưa dữ liệu demo Track A về trạng thái ban đầu (A-DATA-05).

- Xóa kết quả kiểm tra quy hoạch, mốc/biên bản/bản vẽ của hai hồ sơ hero.
- Xóa assignment của hồ sơ hero.
- Chạy lại seed_hero.py để tạo mốc móng fail → đạt và hồ sơ 5 tầng.

Không xóa hồ sơ/dữ liệu khác. Dùng `dx reset` nếu muốn xóa toàn bộ stack.

Chạy:
    py -3 scripts/demo_reset.py --yes
"""

import argparse
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

SQL = """
BEGIN;
WITH h AS (
    SELECT id FROM app_cap_phep.ho_so
    WHERE ma_ho_so IN ('CP-HERO-2026-001', 'CP-HERO-ACC-2026-001')
)
DELETE FROM app_construction.bien_ban_nghiem_thu b
USING app_construction.moc_nghiem_thu m, h
WHERE b.moc_id = m.id AND m.ho_so_id = h.id;

WITH h AS (
    SELECT id FROM app_cap_phep.ho_so
    WHERE ma_ho_so IN ('CP-HERO-2026-001', 'CP-HERO-ACC-2026-001')
)
DELETE FROM app_construction.moc_nghiem_thu m USING h WHERE m.ho_so_id = h.id;

WITH h AS (
    SELECT id FROM app_cap_phep.ho_so
    WHERE ma_ho_so IN ('CP-HERO-2026-001', 'CP-HERO-ACC-2026-001')
)
DELETE FROM app_construction.ban_ve_hoan_cong a USING h WHERE a.ho_so_id = h.id;

WITH h AS (
    SELECT id FROM app_cap_phep.ho_so
    WHERE ma_ho_so IN ('CP-HERO-2026-001', 'CP-HERO-ACC-2026-001')
)
DELETE FROM app_construction.ket_qua_kiem_tra_quy_hoach k USING h WHERE k.ho_so_id = h.id;

WITH h AS (
    SELECT id FROM app_cap_phep.ho_so
    WHERE ma_ho_so IN ('CP-HERO-2026-001', 'CP-HERO-ACC-2026-001')
)
DELETE FROM core.assignments a USING h
WHERE a.object_type = 'ho_so' AND a.object_id = h.id;

DELETE FROM app_construction.luu_tru_ho_so l
USING app_cap_phep.ho_so h
WHERE l.ho_so_id = h.id AND h.ma_ho_so IN ('CP-HERO-2026-001', 'CP-HERO-ACC-2026-001');

COMMIT;
"""


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Reset dữ liệu demo Track A")
    parser.add_argument("--yes", action="store_true", help="Xác nhận chạy")
    parser.add_argument("--no-docker", action="store_true")
    parser.add_argument("--psql")
    parser.add_argument("--container", default="dxos-postgres")
    parser.add_argument("--user", default="dxos_owner")
    parser.add_argument("--database", default="dxos")
    args = parser.parse_args(argv)
    if not args.yes:
        print("Dùng --yes để xác nhận reset dữ liệu hero (không xóa hồ sơ khác).")
        return 2

    if args.no_docker:
        import shutil
        psql = args.psql or shutil.which("psql")
        if not psql:
            raise SystemExit("Không tìm thấy psql.")
        cmd = [psql, "-U", args.user, "-d", args.database, "-v", "ON_ERROR_STOP=1", "-f", "-"]
    else:
        cmd = ["docker", "exec", "-i", args.container, "psql", "-U", args.user, "-d", args.database, "-v", "ON_ERROR_STOP=1", "-f", "-"]

    res = subprocess.run(cmd, input=SQL, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        print(res.stderr or res.stdout, file=sys.stderr)
        return 1
    print("[PASS] Đã xóa dữ liệu nghiệm thu/quy hoạch của hồ sơ hero.")
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "seed_hero.py")] + (["--no-docker"] if args.no_docker else []))


if __name__ == "__main__":
    raise SystemExit(main())
