# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-DATA-01/02: dữ liệu biểu đồ và tải việc cho dashboard lãnh đạo."""

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from dxos_core.db import get_db_connection
from dxos_core.jwt import verify_jwt_token

from construction.deps import yeu_cau_can_bo

router = APIRouter(prefix="/api/v1/metrics", tags=["Số liệu Track A"])


def _thang(month: Optional[str]) -> date:
    if not month:
        return datetime.now(timezone.utc).date().replace(day=1)
    try:
        return datetime.strptime(month[:7], "%Y-%m").date().replace(day=1)
    except ValueError:
        raise HTTPException(status_code=422, detail={"loi": "month phải có dạng YYYY-MM"})


@router.get("/status-breakdown")
async def status_breakdown(month: Optional[str] = Query(default=None), authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    thang = _thang(month)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT trang_thai, count(*) AS so_luong
            FROM app_cap_phep.ho_so
            WHERE tenant = core.jwt_tenant()
              AND date_trunc('month', created_at)::date = $1::date
            GROUP BY trang_thai
            ORDER BY so_luong DESC
            """,
            thang,
        )
    return {"tenant": claims.tenant, "month": thang, "items": [dict(r) for r in rows]}


@router.get("/trend")
async def trend(months: int = Query(default=12, ge=1, le=24), authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            WITH m AS (
                SELECT generate_series(
                    date_trunc('month', now()) - ($1 - 1) * interval '1 month',
                    date_trunc('month', now()),
                    interval '1 month'
                )::date AS thang
            )
            SELECT to_char(m.thang, 'YYYY-MM') AS thang,
                   count(h.id) AS so_ho_so,
                   count(h.id) FILTER (WHERE h.trang_thai = 'DA_CAP') AS da_cap,
                   count(h.id) FILTER (WHERE h.qua_han = true) AS qua_han
            FROM m
            LEFT JOIN app_cap_phep.ho_so h
              ON h.tenant = core.jwt_tenant()
             AND date_trunc('month', h.created_at)::date = m.thang
            GROUP BY m.thang
            ORDER BY m.thang
            """,
            months,
        )
    return {"tenant": claims.tenant, "months": months, "items": [dict(r) for r in rows]}


@router.get("/workload")
async def workload(authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT a.user_sub,
                   COALESCE(u.full_name, a.user_sub) AS ho_ten,
                   count(DISTINCT a.object_id) AS so_ho_so_duoc_giao,
                   count(DISTINCT a.object_id) FILTER (
                       WHERE h.trang_thai NOT IN ('DA_CAP', 'TU_CHOI')
                   ) AS dang_xu_ly
            FROM core.assignments a
            LEFT JOIN core.users_directory u
              ON u.tenant = a.tenant AND (u.id::text = a.user_sub OR u.username = a.user_sub)
            LEFT JOIN app_cap_phep.ho_so h
              ON h.id = a.object_id AND h.tenant = a.tenant
            WHERE a.tenant = core.jwt_tenant()
              AND a.object_type = 'ho_so'
              AND a.active = true
            GROUP BY a.user_sub, u.full_name
            ORDER BY so_ho_so_duoc_giao DESC
            """
        )
    return {"tenant": claims.tenant, "items": [dict(r) for r in rows]}


@router.get("/planning-fail")
async def planning_fail(month: Optional[str] = Query(default=None), authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    thang = _thang(month)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT z.ma_zone, z.ten, count(*) AS so_lan_fail
            FROM app_construction.ket_qua_kiem_tra_quy_hoach k
            LEFT JOIN app_construction.quy_hoach_zone z ON z.id = k.zone_id
            WHERE k.tenant = core.jwt_tenant()
              AND k.pass = false
              AND date_trunc('month', k.created_at)::date = $1::date
            GROUP BY z.ma_zone, z.ten
            ORDER BY so_lan_fail DESC
            """,
            thang,
        )
    return {"tenant": claims.tenant, "month": thang, "items": [dict(r) for r in rows]}


@router.get("/acceptance-progress")
async def acceptance_progress(month: Optional[str] = Query(default=None), authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    thang = _thang(month)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT loai_moc, ket_qua, count(*) AS so_luong
            FROM app_construction.moc_nghiem_thu
            WHERE tenant = core.jwt_tenant()
              AND date_trunc('month', created_at)::date = $1::date
            GROUP BY loai_moc, ket_qua
            ORDER BY loai_moc, ket_qua
            """,
            thang,
        )
    return {"tenant": claims.tenant, "month": thang, "items": [dict(r) for r in rows]}


@router.get("/on-time")
async def on_time(months: int = Query(default=12, ge=1, le=24), authorization: str = Header(...)):
    """Tỷ lệ hồ sơ DA_CAP đúng hạn theo từng tháng của địa bàn."""
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            WITH m AS (
                SELECT generate_series(
                    date_trunc('month', now()) - ($1 - 1) * interval '1 month',
                    date_trunc('month', now()),
                    interval '1 month'
                )::date AS thang
            )
            SELECT to_char(m.thang, 'YYYY-MM') AS thang,
                   count(h.id) AS da_cap,
                   count(h.id) FILTER (WHERE h.updated_at <= h.han_tong_at) AS dung_han,
                   COALESCE(round(100.0 * count(h.id) FILTER (WHERE h.updated_at <= h.han_tong_at) / NULLIF(count(h.id), 0), 1), 0) AS ty_le
            FROM m
            LEFT JOIN app_cap_phep.ho_so h
              ON h.tenant = core.jwt_tenant()
             AND h.trang_thai = 'DA_CAP'
             AND date_trunc('month', h.updated_at)::date = m.thang
            GROUP BY m.thang
            ORDER BY m.thang
            """,
            months,
        )
    return {"tenant": claims.tenant, "months": months, "items": [dict(r) for r in rows]}
