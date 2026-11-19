# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-LEGAL-04..07: thẩm quyền, định danh địa điểm, chia sẻ dữ liệu, phí và lưu trữ."""

import json
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from dxos_core.audit import log_audit_event
from dxos_core.db import get_db_connection
from dxos_core.jwt import verify_jwt_token

from construction.deps import yeu_cau_can_bo, yeu_cau_kiem_tra

router = APIRouter(prefix="/api/v1/planning", tags=["Pháp lý nền"])


class AuthorityCheck(BaseModel):
    loai_cong_trinh: str = "nha_o_rieng_le"
    cap_cong_trinh: Optional[str] = None
    doi_tuong: str = "ho_gia_dinh_ca_nhan"
    trong_kcn: bool = False
    cap_hanh_chinh: Optional[str] = None


class LocationUpdate(BaseModel):
    ma_dinh_danh: str = Field(pattern="^[0-9]{12}$")


class ShareRequest(BaseModel):
    loai_du_lieu: str = Field(default="ho_so", max_length=64)
    ho_so_id: Optional[str] = None
    ma_dinh_danh_dia_diem: Optional[str] = Field(default=None, pattern="^[0-9]{12}$")
    ben_nhan: str = Field(min_length=1, max_length=200)


class ArchiveRequest(BaseModel):
    nhom_ho_so: str = Field(default="cap_phep_xay_dung", max_length=100)
    file_id: Optional[str] = None
    ghi_chu: Optional[str] = Field(default=None, max_length=1000)


def _row(r) -> dict:
    data = dict(r)
    for key in ("chi_tiet", "ket_qua"):
        if key in data and isinstance(data[key], str):
            try:
                data[key] = json.loads(data[key])
            except ValueError:
                pass
    return data


@router.get("/authority/{ho_so_id}")
async def kiem_tra_tham_quyen_ho_so(ho_so_id: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        raw = await conn.fetchval("SELECT app_cap_phep.kiem_tra_tham_quyen_ho_so($1::uuid)", ho_so_id)
    if isinstance(raw, str):
        raw = json.loads(raw)
    return raw or {"xac_dinh_duoc": False}


@router.post("/authority/check")
async def kiem_tra_tham_quyen(body: AuthorityCheck, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        raw = await conn.fetchval(
            """
            SELECT app_construction.xac_dinh_tham_quyen(
                $1, $2, $3, $4, $5
            )
            """,
            body.loai_cong_trinh,
            body.cap_cong_trinh,
            body.doi_tuong,
            body.trong_kcn,
            body.cap_hanh_chinh,
        )
    if isinstance(raw, str):
        raw = json.loads(raw)
    return raw or {"xac_dinh_duoc": False}


@router.get("/location/{ma_dinh_danh}")
async def tra_cuu_dia_diem(ma_dinh_danh: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    if not ma_dinh_danh.isdigit() or len(ma_dinh_danh) != 12:
        raise HTTPException(status_code=422, detail={"loi": "Mã định danh địa điểm phải gồm đúng 12 chữ số"})
    async with get_db_connection(claims) as conn:
        row = await conn.fetchrow(
            """
            SELECT ma_dinh_danh_dia_diem, dia_chi, so_thua, to_ban_do, dien_tich_m2,
                   loai_dat, nguon, da_kiem_chung, created_at
            FROM app_construction.dia_diem_dinh_danh
            WHERE ma_dinh_danh_dia_diem = $1 AND tenant = core.jwt_tenant()
            """,
            ma_dinh_danh,
        )
    await log_audit_event(
        tenant=claims.tenant,
        action="location.lookup",
        actor_sub=claims.sub,
        object_type="dia_diem",
        object_id=ma_dinh_danh,
        detail={"found": row is not None, "nguon": row["nguon"] if row else None},
    )
    if row is None:
        return {
            "found": False,
            "ma_dinh_danh": ma_dinh_danh,
            "can_reuse": False,
            "message": "Không tìm thấy trong CSDL định danh địa điểm của địa bàn (dữ liệu demo).",
        }
    return {
        "found": True,
        "ma_dinh_danh": ma_dinh_danh,
        "can_reuse": True,
        "source": row["nguon"],
        "da_kiem_chung": row["da_kiem_chung"],
        "data": _row(row),
        "message": "Đã có dữ liệu địa điểm; không yêu cầu người dân nộp lại thông tin đã có.",
    }


@router.post("/location/ho-so/{ho_so_id}")
async def cap_nhat_dia_diem_ho_so(ho_so_id: str, body: LocationUpdate, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    async with get_db_connection(claims) as conn:
        raw = await conn.fetchval(
            "SELECT app_cap_phep.cap_nhat_dinh_danh_dia_diem($1::uuid, $2)",
            ho_so_id,
            body.ma_dinh_danh,
        )
    if isinstance(raw, str):
        raw = json.loads(raw)
    await log_audit_event(
        tenant=claims.tenant,
        action="location.attached",
        actor_sub=claims.sub,
        object_type="ho_so",
        object_id=ho_so_id,
        detail={"ma_dinh_danh": body.ma_dinh_danh},
    )
    return raw or {"status": "success"}


@router.post("/share/export")
async def chia_se_du_lieu(body: ShareRequest, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_kiem_tra(claims)
    if not body.ho_so_id and not body.ma_dinh_danh_dia_diem:
        raise HTTPException(status_code=422, detail={"loi": "Cần ho_so_id hoặc mã định danh địa điểm"})
    async with get_db_connection(claims) as conn:
        if body.ho_so_id:
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM app_cap_phep.ho_so WHERE id = $1::uuid AND tenant = core.jwt_tenant())",
                body.ho_so_id,
            )
            if not exists:
                raise HTTPException(status_code=404, detail={"loi": "Không tìm thấy hồ sơ trong địa bàn"})
        row = await conn.fetchrow(
            """
            INSERT INTO app_construction.chia_se_du_lieu_log
                (tenant, loai_du_lieu, ma_dinh_danh_dia_diem, ho_so_id, ben_nhan,
                 can_cu_phap_ly, trang_thai, chi_tiet, created_by)
            VALUES (core.jwt_tenant(), $1, $2, $3::uuid, $4, 'ND-278/2025/ND-CP', 'cho_ket_noi', $5::jsonb, core.jwt_sub())
            RETURNING id, tenant, loai_du_lieu, ma_dinh_danh_dia_diem, ho_so_id, ben_nhan,
                      can_cu_phap_ly, trang_thai, created_at
            """,
            body.loai_du_lieu,
            body.ma_dinh_danh_dia_diem,
            body.ho_so_id,
            body.ben_nhan,
            json.dumps({"ghi_chu": "Chưa kết nối Nền tảng chia sẻ dữ liệu thật; bản ghi phục vụ thiết kế API."}, ensure_ascii=False),
        )
    await log_audit_event(
        tenant=claims.tenant,
        action="data.share_export",
        actor_sub=claims.sub,
        object_type="chia_se_du_lieu",
        object_id=str(row["id"]),
        detail={"ben_nhan": body.ben_nhan, "loai_du_lieu": body.loai_du_lieu},
    )
    return _row(row)


@router.get("/share/logs")
async def nhat_ky_chia_se(limit: int = Query(default=100, ge=1, le=500), authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT id, loai_du_lieu, ma_dinh_danh_dia_diem, ho_so_id, ben_nhan,
                   can_cu_phap_ly, trang_thai, chi_tiet, created_by, created_at
            FROM app_construction.chia_se_du_lieu_log
            WHERE tenant = core.jwt_tenant()
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [_row(r) for r in rows]


@router.get("/fees")
async def bang_phi(authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT id, ten_thu_tuc, don_vi_tinh, muc_phi, don_vi_tien, can_cu,
                   hieu_luc_tu, hieu_luc_den, status
            FROM app_construction.bieu_phi_dia_phuong
            WHERE tenant = core.jwt_tenant()
            ORDER BY ten_thu_tuc, hieu_luc_tu DESC NULLS LAST
            """
        )
    return [_row(r) for r in rows]


@router.get("/bien-lai")
async def bien_lai(authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT id, ho_so_id, so_bien_lai, so_tien, don_vi_tien, trang_thai,
                   ngay_thu, nguoi_thu, ma_tham_chieu, ghi_chu, created_at
            FROM app_construction.bien_lai_phi
            WHERE tenant = core.jwt_tenant()
            ORDER BY created_at DESC
            LIMIT 500
            """
        )
    return [_row(r) for r in rows]


@router.get("/archive")
async def danh_sach_luu_tru(authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT l.id, l.ho_so_id, h.ma_ho_so, l.nhom_ho_so, l.thoi_han_den,
                   l.trang_thai, l.file_id, l.ghi_chu, l.created_at
            FROM app_construction.luu_tru_ho_so l
            LEFT JOIN app_cap_phep.ho_so h ON h.id = l.ho_so_id
            WHERE l.tenant = core.jwt_tenant()
            ORDER BY l.created_at DESC
            LIMIT 500
            """
        )
    return [_row(r) for r in rows]


@router.post("/archive/{ho_so_id}")
async def tao_luu_tru(ho_so_id: str, body: ArchiveRequest, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_kiem_tra(claims)
    async with get_db_connection(claims) as conn:
        ho_so = await conn.fetchrow(
            "SELECT id, ma_ho_so FROM app_cap_phep.ho_so WHERE id = $1::uuid AND tenant = core.jwt_tenant()",
            ho_so_id,
        )
        if ho_so is None:
            raise HTTPException(status_code=404, detail={"loi": "Không tìm thấy hồ sơ trong địa bàn"})
        row = await conn.fetchrow(
            """
            INSERT INTO app_construction.luu_tru_ho_so
                (tenant, ho_so_id, nhom_ho_so, trang_thai, file_id, ghi_chu)
            VALUES (core.jwt_tenant(), $1::uuid, $2, 'dang_luu_tru', $3::uuid, $4)
            ON CONFLICT (tenant, ho_so_id, nhom_ho_so) DO UPDATE
            SET file_id = EXCLUDED.file_id, ghi_chu = EXCLUDED.ghi_chu, updated_at = now()
            RETURNING id, ho_so_id, nhom_ho_so, thoi_han_den, trang_thai, file_id, ghi_chu, created_at
            """,
            ho_so_id,
            body.nhom_ho_so,
            body.file_id,
            body.ghi_chu,
        )
    await log_audit_event(
        tenant=claims.tenant,
        action="archive.created",
        actor_sub=claims.sub,
        object_type="ho_so",
        object_id=ho_so_id,
        detail={"nhom_ho_so": body.nhom_ho_so, "file_id": body.file_id},
    )
    return _row(row)
