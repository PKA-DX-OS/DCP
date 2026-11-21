#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Nạp dữ liệu bịa phục vụ kiểm thử và demo dữ liệu chủ MDM (D-MDM-02).

- Chỉ dùng dữ liệu bịa / giả lập hoàn toàn (không chứa dữ liệu cá nhân thật).
- Tạo các thực thể mẫu và ứng viên trùng (core.mdm_link_candidate) để demo chức năng
  xem ứng viên trùng, gộp bản ghi và hoàn tác gộp trên Bàn làm việc.
- Idempotent: chạy lại nhiều lần không tạo trùng lặp.

Chạy:
    python scripts/seed_mdm.py
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from uuid import UUID

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent

try:
    import asyncpg
except ImportError:
    pass


def _env(ten: str, mac_dinh: str = "") -> str:
    gia_tri = os.getenv(ten)
    if gia_tri:
        return gia_tri
    env_file = ROOT / ".env"
    if env_file.exists():
        for dong in env_file.read_text(encoding="utf-8").splitlines():
            if dong.startswith(ten + "="):
                return dong.split("=", 1)[1].strip()
    return mac_dinh


def dsn_mac_dinh() -> str:
    user = _env("DB_USER", "postgres")
    pw = _env("DB_PASSWORD", "dxos_postgres_2026")
    host = _env("POSTGRES_HOST", "localhost")
    if host in ("postgres", "dxos-postgres"):
        import socket
        try:
            socket.gethostbyname(host)
        except OSError:
            host = "localhost"
    port = _env("POSTGRES_PORT", "5432")
    db = _env("POSTGRES_DB", "dxos")
    return f"postgresql://{user}:{pw}@{host}:{port}/{db}"


# Dữ liệu bịa hoàn toàn phục vụ demo
SEED_SUBJECTS = [
    {
        "subject_id": UUID("00000000-0000-4000-8000-000000000201"),
        "tenant": "phuong-a",
        "source": "import",
        "source_ref": "REF-SEED-01",
        "confidence": 1.0,
    },
    {
        "subject_id": UUID("00000000-0000-4000-8000-000000000202"),
        "tenant": "phuong-a",
        "source": "import",
        "source_ref": "REF-SEED-02",
        "confidence": 1.0,
    },
]

SEED_PARCELS = [
    {
        "parcel_id": UUID("00000000-0000-4000-8000-000000000301"),
        "tenant": "phuong-a",
        "ma_dinh_danh_dia_diem": "790100000125",
        "so_thua": "125",
        "to_ban_do": "18",
        "source": "import",
        "source_ref": "REF-SEED-P01",
        "confidence": 1.0,
    },
    {
        "parcel_id": UUID("00000000-0000-4000-8000-000000000302"),
        "tenant": "phuong-a",
        "ma_dinh_danh_dia_diem": None,
        "so_thua": "125",
        "to_ban_do": "18a",
        "source": "import",
        "source_ref": "REF-SEED-P02",
        "confidence": 1.0,
    },
]

SEED_CANDIDATES = [
    {
        "tenant": "phuong-a",
        "entity_type": "subject",
        "entity_id": UUID("00000000-0000-4000-8000-000000000201"),
        "candidate_id": UUID("00000000-0000-4000-8000-000000000202"),
        "confidence": 0.885,
        "ly_do": ["ho_ten", "dien_thoai"],
        "status": "open",
    },
    {
        "tenant": "phuong-a",
        "entity_type": "parcel",
        "entity_id": UUID("00000000-0000-4000-8000-000000000301"),
        "candidate_id": UUID("00000000-0000-4000-8000-000000000302"),
        "confidence": 0.820,
        "ly_do": ["thua_dat", "dia_chi"],
        "status": "open",
    },
]


async def seed_mdm(dsn: str) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        # 1. Nạp chủ thể bịa
        for s in SEED_SUBJECTS:
            await conn.execute(
                """
                INSERT INTO core.mdm_subject (subject_id, tenant, source, source_ref, confidence)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (subject_id) DO NOTHING
                """,
                s["subject_id"], s["tenant"], s["source"], s["source_ref"], s["confidence"],
            )

        # 2. Nạp thửa đất bịa
        for p in SEED_PARCELS:
            await conn.execute(
                """
                INSERT INTO core.mdm_parcel (parcel_id, tenant, ma_dinh_danh_dia_diem, so_thua, to_ban_do, source, source_ref, confidence)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (parcel_id) DO NOTHING
                """,
                p["parcel_id"], p["tenant"], p["ma_dinh_danh_dia_diem"], p["so_thua"], p["to_ban_do"],
                p["source"], p["source_ref"], p["confidence"],
            )

        # 3. Nạp ứng viên trùng bịa
        for c in SEED_CANDIDATES:
            await conn.execute(
                """
                INSERT INTO core.mdm_link_candidate (tenant, entity_type, entity_id, candidate_id, confidence, ly_do, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (tenant, entity_type, entity_id, candidate_id) DO NOTHING
                """,
                c["tenant"], c["entity_type"], c["entity_id"], c["candidate_id"],
                c["confidence"], c["ly_do"], c["status"],
            )

        print("[OK] Đã nạp dữ liệu bịa MDM thành công (chủ thể, thửa đất và ứng viên trùng mẫu).")
    finally:
        await conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Nạp dữ liệu bịa MDM (D-MDM-02)")
    parser.add_argument("--dsn", default=None, help="PostgreSQL DSN")
    args = parser.parse_args()

    dsn = args.dsn or dsn_mac_dinh()
    try:
        asyncio.run(seed_mdm(dsn))
        return 0
    except Exception as e:
        print(f"[LỖI] seed_mdm: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
