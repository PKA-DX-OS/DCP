# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FIX-V11-18: trật tự xây dựng xem cảnh báo hồ sơ đã cấp; DB từ chối quyền trả 403 thay vì 503."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
import pytest
from dxos_core import db
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
MIG = ROOT / "apps/cap-phep/db/migrations"


def test_ham_canh_bao_cho_trat_tu_xem_ho_so_da_cap():
    sql = (MIG / "20-trat-tu-xem-canh-bao.sql").read_text(encoding="utf-8")
    assert "CREATE OR REPLACE FUNCTION app_cap_phep.danh_sach_canh_bao_ho_so(p_ho_so_id uuid)" in sql
    assert "core.has_role('app:cap-phep:trat-tu-xd') AND v_hs.trang_thai = 'DA_CAP'" in sql
    assert "GRANT EXECUTE ON FUNCTION app_cap_phep.danh_sach_canh_bao_ho_so(uuid) TO web_user" in sql
    # Phần tính cảnh báo giữ nguyên như bản 08.
    ban_08 = (MIG / "08-warning-function-fix.sql").read_text(encoding="utf-8")
    for doan in ("'so_tang_nguong'", "'dien_tich_nguong'", "'thieu_ma_dinh_danh'", "'thieu_giay_to'"):
        assert doan in sql and doan in ban_08


def test_khong_migration_sau_ghi_de_ham_canh_bao():
    ten = sorted(p.name for p in MIG.glob("*.sql"))
    sau = ten[ten.index("20-trat-tu-xem-canh-bao.sql") + 1:]
    assert all("danh_sach_canh_bao_ho_so" not in (MIG / t).read_text(encoding="utf-8") for t in sau)


class _Conn:
    @asynccontextmanager
    async def transaction(self):
        yield


class _Pool:
    @asynccontextmanager
    async def acquire(self, **_):
        yield _Conn()


async def _chay(loi):
    async def _pool():
        return _Pool()

    db.get_db_pool, cu = _pool, db.get_db_pool
    try:
        async with db.get_db_connection() as _:
            raise loi
    finally:
        db.get_db_pool = cu


def test_tu_choi_quyen_tra_403():
    with pytest.raises(HTTPException) as e:
        asyncio.run(_chay(asyncpg.exceptions.InsufficientPrivilegeError("tu choi")))
    assert e.value.status_code == 403
    assert e.value.detail["ma_loi"] == "FORBIDDEN"


def test_loi_khac_van_503():
    with pytest.raises(HTTPException) as e:
        asyncio.run(_chay(RuntimeError("mat ket noi")))
    assert e.value.status_code == 503
