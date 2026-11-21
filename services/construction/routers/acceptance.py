# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-ACC-02: API nghiệm thu, biên bản và bản vẽ hoàn công."""

import json
from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from dxos_core.audit import log_audit_event
from dxos_core.db import get_db_connection
from dxos_core.jwt import verify_jwt_token

from construction.deps import la_can_bo, yeu_cau_nghiem_thu

router = APIRouter(prefix="/api/v1/acceptance", tags=["Nghiệm thu"])

MILESTONES = ("mong", "ket_cau", "hoan_thien", "hoan_cong")
MILESTONE_LABEL = {
    "mong": "Nghiệm thu móng",
    "ket_cau": "Nghiệm thu kết cấu",
    "hoan_thien": "Nghiệm thu hoàn thiện",
    "hoan_cong": "Hoàn công",
}


class MilestoneRequest(BaseModel):
    loai_moc: str
    ngay_nghiem_thu: Optional[str] = None
    ket_qua: str = Field(default="cho_nghiem_thu", pattern="^(cho_nghiem_thu|dat|khong_dat)$")
    ghi_chu: Optional[str] = Field(default=None, max_length=2000)
    file_id: Optional[str] = None


class RecordRequest(BaseModel):
    so_bien_ban: str = Field(min_length=1, max_length=100)
    ket_luan: str = Field(min_length=1, max_length=4000)
    ket_qua: Optional[str] = Field(default=None, pattern="^(dat|khong_dat)$")
    file_id: Optional[str] = None
    chu_ky: Optional[str] = Field(default=None, max_length=20000)
    ngay_ky: Optional[str] = None
    nguoi_ky: Optional[str] = Field(default=None, max_length=200)
    ghi_chu: Optional[str] = Field(default=None, max_length=2000)


class AsBuiltRequest(BaseModel):
    file_id: str
    ghi_chu: Optional[str] = Field(default=None, max_length=2000)


def _row(r) -> dict:
    data = dict(r)
    for key in ("ghi_chu",):
        if key in data and isinstance(data[key], str):
            try:
                parsed = json.loads(data[key])
                if isinstance(parsed, (dict, list)):
                    data[key] = parsed
            except ValueError:
                pass
    return data


def _dt(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        raise HTTPException(status_code=422, detail={"loi": f"Ngày không hợp lệ: {value}"})


def _ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=422, detail={"loi": f"Thời điểm không hợp lệ: {value}"})


async def _ho_so(conn, ho_so_id: str):
    row = await conn.fetchrow(
        """
        SELECT id, tenant, ma_ho_so, ho_ten, dia_chi_cong_trinh, thua_dat, so_tang,
               dien_tich_san_m2, trang_thai, buoc, chu_dau_tu_sub
        FROM app_cap_phep.ho_so
        WHERE id = $1::uuid AND tenant = core.jwt_tenant()
        """,
        ho_so_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail={"loi": "Không tìm thấy hồ sơ trong địa bàn"})
    return row


async def _file_hop_le(conn, file_id: Optional[str]) -> Optional[str]:
    if not file_id:
        return None
    row = await conn.fetchrow(
        "SELECT id FROM core.files WHERE id = $1::uuid AND tenant = core.jwt_tenant() AND status = 'clean'",
        file_id,
    )
    if row is None:
        raise HTTPException(status_code=422, detail={"loi": "Tệp không tồn tại, không thuộc địa bàn hoặc chưa sạch"})
    return str(row["id"])


@router.get("/{ho_so_id}")
async def tong_quan_nghiem_thu(ho_so_id: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    async with get_db_connection(claims) as conn:
        hs = await _ho_so(conn, ho_so_id)
        mocs = await conn.fetch(
            """
            SELECT id, ho_so_id, loai_moc, version, ngay_nghiem_thu, ket_qua, nguoi_thuc_hien,
                   ghi_chu, file_id, created_at, updated_at
            FROM app_construction.moc_nghiem_thu
            WHERE tenant = core.jwt_tenant() AND ho_so_id = $1::uuid
            ORDER BY created_at
            """,
            ho_so_id,
        )
        records = await conn.fetch(
            """
            SELECT b.id, b.moc_id, b.so_bien_ban, b.ket_luan, b.file_id, b.chu_ky,
                   b.ngay_ky, b.nguoi_ky, b.created_at
            FROM app_construction.bien_ban_nghiem_thu b
            JOIN app_construction.moc_nghiem_thu m ON m.id = b.moc_id
            WHERE m.tenant = core.jwt_tenant() AND m.ho_so_id = $1::uuid
            ORDER BY b.created_at
            """,
            ho_so_id,
        )
        as_built = await conn.fetch(
            """
            SELECT id, ho_so_id, file_id, version, ngay_nop, nguoi_nop, trang_thai, ghi_chu, created_at
            FROM app_construction.ban_ve_hoan_cong
            WHERE tenant = core.jwt_tenant() AND ho_so_id = $1::uuid
            ORDER BY version DESC
            """,
            ho_so_id,
        )
    record_by_moc: dict[str, list] = {}
    for r in records:
        record_by_moc.setdefault(str(r["moc_id"]), []).append(_row(r))
    data_mocs = []
    for m in mocs:
        item = _row(m)
        item["bien_ban"] = record_by_moc.get(str(m["id"]), [])
        data_mocs.append(item)
    done = {m["loai_moc"] for m in data_mocs if m["ket_qua"] == "dat"}
    next_milestone = next((m for m in MILESTONES if m not in done), None)
    return {
        "ho_so": _row(hs),
        "milestones": data_mocs,
        "as_built": [_row(a) for a in as_built],
        "tien_do": {"da_dat": len(done), "tong": len(MILESTONES), "phan_tram": round(len(done) * 100 / len(MILESTONES))},
        "moc_tiep_theo": next_milestone,
        "moc_tiep_theo_ten": MILESTONE_LABEL.get(next_milestone or "", "Đã hoàn công"),
        "legal_refs": [
            {
                "citation_key": "ND207-TOANVAN",
                "document_code": "207/2026/NĐ-CP",
                "summary": "Nghị định 207/2026/NĐ-CP quy định quản lý chất lượng, thi công xây dựng và bảo trì công trình.",
            }
        ],
    }


@router.post("/{ho_so_id}/milestones")
async def tao_moc_nghiem_thu(ho_so_id: str, body: MilestoneRequest, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_nghiem_thu(claims)
    if body.loai_moc not in MILESTONES:
        raise HTTPException(status_code=422, detail={"loi": "Loại mốc nghiệm thu không hợp lệ"})
    async with get_db_connection(claims) as conn:
        await _ho_so(conn, ho_so_id)
        file_id = await _file_hop_le(conn, body.file_id)
        version = await conn.fetchval(
            """
            SELECT COALESCE(max(version), 0) + 1
            FROM app_construction.moc_nghiem_thu
            WHERE tenant = core.jwt_tenant() AND ho_so_id = $1::uuid AND loai_moc = $2
            """,
            ho_so_id,
            body.loai_moc,
        )
        row = await conn.fetchrow(
            """
            INSERT INTO app_construction.moc_nghiem_thu
                (tenant, ho_so_id, loai_moc, version, ngay_nghiem_thu, ket_qua, nguoi_thuc_hien,
                 ghi_chu, file_id, created_by)
            VALUES (core.jwt_tenant(), $1::uuid, $2, $3, $4, $5, core.jwt_sub(), $6, $7::uuid, core.jwt_sub())
            RETURNING id, loai_moc, version, ket_qua, created_at
            """,
            ho_so_id,
            body.loai_moc,
            version,
            _dt(body.ngay_nghiem_thu),
            body.ket_qua,
            body.ghi_chu,
            file_id,
        )
    await log_audit_event(
        tenant=claims.tenant,
        action="acceptance.milestone_created",
        actor_sub=claims.sub,
        object_type="ho_so",
        object_id=ho_so_id,
        detail={"moc_id": str(row["id"]), "loai_moc": body.loai_moc, "version": version, "ket_qua": body.ket_qua},
    )
    return _row(row)


@router.post("/milestones/{moc_id}/records")
async def nop_bien_ban(moc_id: str, body: RecordRequest, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_nghiem_thu(claims)
    async with get_db_connection(claims) as conn:
        moc = await conn.fetchrow(
            """
            SELECT id, tenant, ho_so_id, loai_moc FROM app_construction.moc_nghiem_thu
            WHERE id = $1::uuid AND tenant = core.jwt_tenant()
            """,
            moc_id,
        )
        if moc is None:
            raise HTTPException(status_code=404, detail={"loi": "Không tìm thấy mốc nghiệm thu"})
        file_id = await _file_hop_le(conn, body.file_id)
        row = await conn.fetchrow(
            """
            INSERT INTO app_construction.bien_ban_nghiem_thu
                (tenant, moc_id, so_bien_ban, ket_luan, file_id, chu_ky, ngay_ky, nguoi_ky, created_by)
            VALUES (core.jwt_tenant(), $1::uuid, $2, $3, $4::uuid, $5, $6, $7, core.jwt_sub())
            RETURNING id, so_bien_ban, ket_luan, created_at
            """,
            moc_id,
            body.so_bien_ban,
            body.ket_luan,
            file_id,
            body.chu_ky,
            _ts(body.ngay_ky),
            body.nguoi_ky or claims.sub,
        )
        if body.ket_qua:
            await conn.execute(
                """
                UPDATE app_construction.moc_nghiem_thu
                SET ket_qua = $2, updated_at = now()
                WHERE id = $1::uuid
                """,
                moc_id,
                body.ket_qua,
            )
    await log_audit_event(
        tenant=claims.tenant,
        action="acceptance.record_submitted",
        actor_sub=claims.sub,
        object_type="ho_so",
        object_id=str(moc["ho_so_id"]),
        detail={"moc_id": moc_id, "so_bien_ban": body.so_bien_ban, "ket_qua": body.ket_qua},
    )
    return _row(row)


@router.post("/{ho_so_id}/as-built")
async def nop_ban_ve_hoan_cong(ho_so_id: str, body: AsBuiltRequest, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_nghiem_thu(claims)
    async with get_db_connection(claims) as conn:
        await _ho_so(conn, ho_so_id)
        file_id = await _file_hop_le(conn, body.file_id)
        version = await conn.fetchval(
            """
            SELECT COALESCE(max(version), 0) + 1
            FROM app_construction.ban_ve_hoan_cong
            WHERE tenant = core.jwt_tenant() AND ho_so_id = $1::uuid
            """,
            ho_so_id,
        )
        row = await conn.fetchrow(
            """
            INSERT INTO app_construction.ban_ve_hoan_cong
                (tenant, ho_so_id, file_id, version, nguoi_nop, ghi_chu)
            VALUES (core.jwt_tenant(), $1::uuid, $2::uuid, $3, core.jwt_sub(), $4)
            RETURNING id, ho_so_id, file_id, version, ngay_nop, trang_thai
            """,
            ho_so_id,
            file_id,
            version,
            body.ghi_chu,
        )
    await log_audit_event(
        tenant=claims.tenant,
        action="acceptance.as_built_submitted",
        actor_sub=claims.sub,
        object_type="ho_so",
        object_id=ho_so_id,
        detail={"as_built_id": str(row["id"]), "version": version},
    )
    return _row(row)


@router.get("/{ho_so_id}/history")
async def lich_su_nghiem_thu(ho_so_id: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    async with get_db_connection(claims) as conn:
        await _ho_so(conn, ho_so_id)
        rows = await conn.fetch(
            """
            SELECT 'moc' AS loai, id::text AS id, loai_moc AS su_kien, ket_qua AS trang_thai,
                   ghi_chu AS noi_dung, created_at
            FROM app_construction.moc_nghiem_thu
            WHERE tenant = core.jwt_tenant() AND ho_so_id = $1::uuid
            UNION ALL
            SELECT 'bien_ban', b.id::text, 'bien_ban', b.so_bien_ban, b.ket_luan, b.created_at
            FROM app_construction.bien_ban_nghiem_thu b
            JOIN app_construction.moc_nghiem_thu m ON m.id = b.moc_id
            WHERE m.tenant = core.jwt_tenant() AND m.ho_so_id = $1::uuid
            UNION ALL
            SELECT 'ban_ve', a.id::text, 'ban_ve_hoan_cong', a.trang_thai, a.ghi_chu, a.created_at
            FROM app_construction.ban_ve_hoan_cong a
            WHERE a.tenant = core.jwt_tenant() AND a.ho_so_id = $1::uuid
            ORDER BY created_at
            """,
            ho_so_id,
        )
    return [_row(r) for r in rows]
