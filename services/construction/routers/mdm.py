# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""API dữ liệu chủ và xem 360 hồ sơ — contracts/dh/mdm.yaml (D-MDM-04, D-360-01)."""

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from dxos_core.audit import log_audit_event
from dxos_core.db import get_db_connection
from dxos_core.jwt import verify_jwt_token

from construction.dh import (
    VAI_DOC_DH, VAI_DSAR_XUAT, VAI_DSAR_XU_LY, VAI_GOP, VAI_LIEN_KET, LoiDH, can_vai, che_cccd, che_dien_thoai,
    cccd_hmac, idempotent, kiem_khoa_idempotency, la_chu_dau_tu, trang,
)
from construction.dh_mdm import BANG, COT_LIEN_KET, lien_ket_ho_so, lien_ket_tu_ho_so, tom_tat, vang

logger = logging.getLogger("dxos.mdm")
router = APIRouter(prefix="/api/v1/mdm", tags=["mdm"])

LOAI = ("subject", "parcel", "construction", "permit", "organization")
NHAN_MOC = {"mong": "Nghiệm thu móng", "ket_cau": "Nghiệm thu kết cấu",
            "hoan_thien": "Nghiệm thu hoàn thiện", "hoan_cong": "Hoàn công"}


class TaoLienKet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dossier_id: UUID
    entity_type: str = Field(pattern="^(subject|parcel|construction|permit)$")
    entity_id: UUID
    ghi_chu: Optional[str] = Field(default=None, max_length=500)


class GopThucThe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_type: str = Field(pattern="^(subject|parcel|construction|organization)$")
    giu_id: UUID
    gop_ids: List[UUID] = Field(min_length=1, max_length=10)
    ly_do: str = Field(min_length=5, max_length=500)


class XoaDsarMDM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_sub: Optional[str] = None
    so_dinh_danh: Optional[str] = None
    cccd: Optional[str] = None
    reason: Optional[str] = Field(default="Yêu cầu xóa dữ liệu cá nhân theo DSAR", max_length=500)


def _uuid(v: str, ten: str = "id") -> UUID:
    try:
        return UUID(str(v))
    except ValueError:
        raise LoiDH(400, "BAD_REQUEST", f"{ten} không phải UUID")


async def _ho_so_thay_duoc(conn, dossier_id: UUID) -> Dict[str, Any]:
    """Hồ sơ người gọi thấy được (RLS + phường trong token); không thấy thì 404 như không tồn tại."""
    hs = await conn.fetchrow(
        """
        SELECT id, ma_ho_so, trang_thai, buoc, created_at, han_tong_at, qua_han, ho_ten, cccd, dien_thoai
        FROM app_cap_phep.ho_so WHERE id = $1 AND tenant = core.jwt_tenant()
        """,
        dossier_id,
    )
    if hs is None:
        raise LoiDH(404, "MDM_NOT_FOUND", "Không tìm thấy hồ sơ trong phường của bạn")
    return dict(hs)


async def _dong_bo(tenant: str, dossier_id: UUID) -> Optional[Dict[str, Any]]:
    """Khớp đúng thực thể cho hồ sơ bằng kết nối dịch vụ (người gọi đã được kiểm thấy hồ sơ)."""
    async with get_db_connection() as svc:
        return await lien_ket_tu_ho_so(svc, tenant, str(dossier_id))


@router.get("/dossiers/{dossier_id}/links")
async def lay_lien_ket_ho_so(dossier_id: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_DOC_DH)
    did = _uuid(dossier_id, "dossier_id")
    async with get_db_connection(claims) as conn:
        await _ho_so_thay_duoc(conn, did)
    link = await _dong_bo(claims.tenant, did)
    async with get_db_connection(claims) as conn:
        return await lien_ket_ho_so(conn, did, link)


async def _an_toan(conn, sql: str, *args) -> List[Any]:
    """Phần 360 người gọi không có quyền đọc (RLS) thì để trống thay vì làm hỏng cả trang."""
    try:
        async with conn.transaction():
            return list(await conn.fetch(sql, *args))
    except Exception as exc:  # quyền hoặc bảng chưa có
        logger.info("Bỏ qua một phần 360: %s", type(exc).__name__)
        return []


def _ket_qua_moc(kq: Optional[str]) -> str:
    return kq if kq in ("dat", "khong_dat") else "cho_xu_ly"


@router.get("/dossiers/{dossier_id}/360")
async def xem_360_ho_so(dossier_id: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    chu_dau_tu = la_chu_dau_tu(claims)
    if not chu_dau_tu:
        can_vai(claims, VAI_DOC_DH)
    did = _uuid(dossier_id, "dossier_id")
    async with get_db_connection(claims) as conn:
        hs = await _ho_so_thay_duoc(conn, did)
    link = await _dong_bo(claims.tenant, did) or {}

    async with get_db_connection(claims) as conn:
        # Đọc thông tin tổng hợp từ view 360 (D-MDM-03)
        row_360 = await conn.fetchrow(
            """
            SELECT ho_so, chu_dau_tu, thua_dat, cong_trinh, giay_phep
            FROM core.v_dossier_360
            WHERE dossier_id = $1
            """,
            did,
        )
        if row_360:
            def _pj(v):
                return json.loads(v) if isinstance(v, str) else v
            ho_so_val = _pj(row_360["ho_so"])
            nguoi = _pj(row_360["chu_dau_tu"])
            thua = _pj(row_360["thua_dat"])
            cong_trinh = _pj(row_360["cong_trinh"])
            giay_phep = _pj(row_360["giay_phep"])
        else:
            ho_so_val = {k: hs[k] for k in ("id", "ma_ho_so", "trang_thai", "buoc", "created_at", "han_tong_at")} | {"qua_han": bool(hs["qua_han"])}
            nguoi = None
            thua = None
            cong_trinh = None
            giay_phep = None

        subject_id = link.get("subject_id")

        gp_rows = await _an_toan(
            conn,
            """
            SELECT g.id, c.id AS cong_trinh_app_id
            FROM app_cap_phep.giay_phep g
            LEFT JOIN app_cap_phep.cong_trinh c ON c.giay_phep_id = g.id
            WHERE g.ho_so_id = $1
            ORDER BY (g.trang_thai = 'hieu_luc') DESC, g.ngay_cap DESC LIMIT 1
            """,
            did,
        )
        gp = gp_rows[0] if gp_rows else None

        kiem_tra: List[Dict[str, Any]] = []
        for r in await _an_toan(
            conn,
            "SELECT pass, so_loi, created_at FROM app_construction.ket_qua_kiem_tra_quy_hoach WHERE ho_so_id = $1 ORDER BY created_at",
            did,
        ):
            kiem_tra.append({"loai": "quy_hoach", "ket_qua": "dat" if r["pass"] else "khong_dat", "thoi_diem": r["created_at"],
                             "mo_ta": "Kiểm tra quy hoạch" + (f", {r['so_loi']} lỗi" if r["so_loi"] else "")})
        for r in await _an_toan(
            conn,
            "SELECT loai_moc, ket_qua, created_at, version FROM app_construction.moc_nghiem_thu WHERE ho_so_id = $1 ORDER BY created_at",
            did,
        ):
            kiem_tra.append({"loai": "nghiem_thu", "ket_qua": _ket_qua_moc(r["ket_qua"]), "thoi_diem": r["created_at"],
                             "mo_ta": f"{NHAN_MOC.get(r['loai_moc'], r['loai_moc'])}, lần {r['version']}"})
        if gp and gp["cong_trinh_app_id"]:
            for r in await _an_toan(
                conn,
                "SELECT trang_thai, ket_luan, created_at FROM app_cap_phep.phieu_kiem_tra WHERE cong_trinh_id = $1 ORDER BY created_at",
                gp["cong_trinh_app_id"],
            ):
                kq = "cho_xu_ly" if r["trang_thai"] != "DA_XU_LY" else ("dat" if (r["ket_luan"] or "").startswith("Đạt") else "khong_dat")
                kiem_tra.append({"loai": "hien_truong", "ket_qua": kq, "thoi_diem": r["created_at"], "mo_ta": r["ket_luan"]})
        kiem_tra.sort(key=lambda k: k["thoi_diem"])

        tai_chinh = [
            {"loai": "Lệ phí cấp giấy phép xây dựng", "so_tien": int(r["so_tien"] or 0),
             "trang_thai": "da_thu" if r["trang_thai"] == "da_doi_soat" else ("mien" if r["trang_thai"] == "hoan_phi" else "chua_thu")}
            for r in await _an_toan(
                conn,
                "SELECT so_tien, trang_thai FROM app_construction.bien_lai_phi WHERE ho_so_id = $1 AND trang_thai <> 'huy' ORDER BY created_at",
                did,
            )
        ]

        canh_bao: List[Dict[str, Any]] = []
        if not chu_dau_tu:
            for r in await _an_toan(
                conn,
                """
                SELECT i.rule_code, i.severity, i.field, r.description
                FROM core.data_quality_issues i JOIN core.data_quality_rules r ON r.code = i.rule_code
                WHERE i.tenant = core.jwt_tenant() AND i.dossier_id = $1 AND i.status IN ('open', 'in_progress')
                ORDER BY CASE i.severity WHEN 'critical' THEN 0 WHEN 'warn' THEN 1 ELSE 2 END, i.created_at DESC
                """,
                did,
            ):
                canh_bao.append({"nguon": "dq", "code": r["rule_code"], "severity": r["severity"],
                                 "message": r["description"], "field": r["field"]})
            if not subject_id:
                canh_bao.append({"nguon": "mdm", "code": "MDM_SUBJECT_MISSING", "severity": "info",
                                 "message": "Chưa liên kết được chủ đầu tư (CCCD sai dạng hoặc chưa khớp)", "field": "cccd"})

        audit_rows = await _an_toan(
            conn,
            "SELECT count(*) AS n, max(at) AS gan_nhat FROM core.audit_log WHERE object_type = 'ho_so' AND object_id = $1",
            str(did),
        )
        audit = {"so_su_kien": int(audit_rows[0]["n"]) if audit_rows else 0,
                 "gan_nhat": audit_rows[0]["gan_nhat"] if audit_rows else None}

    return {
        "ho_so": ho_so_val,
        "chu_dau_tu": nguoi,
        "thua_dat": thua,
        "cong_trinh": cong_trinh,
        "giay_phep": giay_phep,
        "kiem_tra": kiem_tra,
        "tai_chinh": tai_chinh,
        "canh_bao": canh_bao,
        "audit": audit,
    }


@router.get("/search")
async def tim_thuc_the(
    q: str = Query(min_length=2, max_length=100),
    type: str = Query(pattern="^(subject|parcel|construction|permit|organization)$"),
    page: int = 1,
    page_size: int = 20,
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_DOC_DH)
    page, page_size, offset = trang(page, page_size)
    mau = q.strip().lower()
    async with get_db_connection(claims) as conn:
        if type == "subject":
            sql = """
                SELECT DISTINCT ON (l.subject_id) l.subject_id AS id,
                       CASE WHEN lower(h.ho_ten) = $1 THEN 1.0 WHEN lower(h.ho_ten) LIKE $1 || '%' THEN 0.8 ELSE 0.5 END AS diem
                FROM core.mdm_dossier_link l JOIN app_cap_phep.ho_so h ON h.id = l.dossier_id
                JOIN core.mdm_subject s ON s.subject_id = l.subject_id AND s.merged_into IS NULL
                WHERE l.tenant = core.jwt_tenant() AND lower(h.ho_ten) LIKE '%' || $1 || '%'
                ORDER BY l.subject_id, diem DESC"""
        elif type == "parcel":
            sql = """
                SELECT parcel_id AS id,
                       CASE WHEN ma_dinh_danh_dia_diem = $1 OR so_thua = $1 THEN 1.0
                            WHEN coalesce(ma_dinh_danh_dia_diem, '') LIKE $1 || '%' OR so_thua LIKE $1 || '%' THEN 0.8 ELSE 0.5 END AS diem
                FROM core.mdm_parcel
                WHERE tenant = core.jwt_tenant() AND merged_into IS NULL
                  AND (coalesce(ma_dinh_danh_dia_diem, '') LIKE $1 || '%' OR coalesce(so_thua, '') LIKE '%' || $1 || '%'
                       OR coalesce(so_thua || '/' || to_ban_do, '') = $1)"""
        elif type == "construction":
            sql = """
                SELECT construction_id AS id,
                       CASE WHEN lower(ma_cong_trinh) = $1 THEN 1.0 WHEN lower(ma_cong_trinh) LIKE $1 || '%' THEN 0.8 ELSE 0.5 END AS diem
                FROM core.mdm_construction
                WHERE tenant = core.jwt_tenant() AND merged_into IS NULL
                  AND (lower(coalesce(ma_cong_trinh, '')) LIKE '%' || $1 || '%' OR lower(coalesce(dia_chi_chuan, '')) LIKE '%' || $1 || '%')"""
        elif type == "permit":
            sql = """
                SELECT id, CASE WHEN lower(so_giay_phep) = $1 THEN 1.0 WHEN lower(so_giay_phep) LIKE $1 || '%' THEN 0.8 ELSE 0.5 END AS diem
                FROM app_cap_phep.giay_phep
                WHERE tenant = core.jwt_tenant() AND lower(so_giay_phep) LIKE '%' || $1 || '%'"""
        else:
            sql = """
                SELECT org_id AS id, CASE WHEN lower(ten) = $1 OR mst = $1 THEN 1.0 WHEN lower(ten) LIKE $1 || '%' THEN 0.8 ELSE 0.5 END AS diem
                FROM core.mdm_organization
                WHERE tenant = core.jwt_tenant() AND merged_into IS NULL AND (lower(ten) LIKE '%' || $1 || '%' OR mst = $1)"""
        tong = await conn.fetchval(f"SELECT count(*) FROM ({sql}) x", mau)
        rows = await conn.fetch(f"SELECT * FROM ({sql}) x ORDER BY diem DESC, id LIMIT $2 OFFSET $3", mau, page_size, offset)
        items = [t for t in [await tom_tat(conn, type, r["id"]) for r in rows] if t]
    return {"items": items, "page": page, "page_size": page_size, "total": int(tong or 0)}


@router.get("/entities/{type}/{id}")
async def lay_thuc_the(type: str, id: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_DOC_DH)
    if type not in LOAI:
        raise LoiDH(400, "BAD_REQUEST", "Loại thực thể không hợp lệ")
    eid = _uuid(id)
    async with get_db_connection(claims) as conn:
        tt = await tom_tat(conn, type, eid)
        if tt is None:
            raise LoiDH(404, "MDM_NOT_FOUND", "Không tìm thấy thực thể trong phường của bạn")
        merged_into = None
        thuoc_tinh: Dict[str, Any] = {}
        if type in BANG:
            bang, khoa = BANG[type]
            r = await conn.fetchrow(f"SELECT * FROM {bang} WHERE {khoa} = $1", eid)
            merged_into = r["merged_into"]
            an = {"tenant", "cccd_hmac", "source_ref", khoa, "merged_into", "confidence", "source", "geom"}
            thuoc_tinh = {k: (float(v) if k == "dien_tich_m2" and v is not None else v) for k, v in dict(r).items() if k not in an}
        cot = COT_LIEN_KET.get(type)
        ho_so = []
        if cot:
            ho_so = [dict(r) for r in await conn.fetch(
                f"""
                SELECT h.id AS dossier_id, h.ma_ho_so, h.trang_thai
                FROM core.mdm_dossier_link l JOIN app_cap_phep.ho_so h ON h.id = l.dossier_id
                WHERE l.tenant = core.jwt_tenant() AND l.{cot} = $1 ORDER BY h.created_at DESC
                """,
                eid,
            )]
        refs = [dict(r) | {"confidence": float(r["confidence"])} for r in await conn.fetch(
            """
            SELECT system, external_id, confidence, last_synced_at FROM core.external_refs
            WHERE tenant = core.jwt_tenant() AND entity_type = $1 AND entity_id = $2 ORDER BY system
            """,
            type, eid,
        )]
    return tt | {"merged_into": merged_into, "thuoc_tinh": thuoc_tinh, "ho_so": ho_so, "external_refs": refs}


@router.get("/candidates")
async def ds_ung_vien_trung(entity_type: str, entity_id: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_DOC_DH)
    if entity_type not in LOAI:
        raise LoiDH(400, "BAD_REQUEST", "Loại thực thể không hợp lệ")
    eid = _uuid(entity_id, "entity_id")
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT candidate_id, confidence, ly_do FROM core.mdm_link_candidate
            WHERE tenant = core.jwt_tenant() AND entity_type = $1 AND entity_id = $2 AND status = 'open'
            ORDER BY confidence DESC
            """,
            entity_type, eid,
        )
        kq = []
        for r in rows:
            uv = await tom_tat(conn, entity_type, r["candidate_id"])
            if uv:
                kq.append({"ung_vien": uv, "confidence": float(r["confidence"]), "ly_do": list(r["ly_do"])})
    return kq


@router.post("/links", status_code=201)
async def tao_lien_ket(body: TaoLienKet, authorization: str = Header(...),
                       idempotency_key: Optional[str] = Header(default=None)):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_LIEN_KET)
    khoa = kiem_khoa_idempotency(idempotency_key)

    async with get_db_connection(claims) as conn:
        async def lam():
            await _ho_so_thay_duoc(conn, body.dossier_id)
            if await tom_tat(conn, body.entity_type, body.entity_id) is None:
                raise LoiDH(422, "MDM_ENTITY_NOT_FOUND", "Không có thực thể này trong phường")
            if body.entity_type in BANG:
                bang, khoa_bang = BANG[body.entity_type]
                if await conn.fetchval(f"SELECT merged_into FROM {bang} WHERE {khoa_bang} = $1", body.entity_id):
                    raise LoiDH(409, "MDM_ENTITY_MERGED", "Thực thể đã bị gộp, hãy liên kết với bản ghi gốc")
            cot = COT_LIEN_KET[body.entity_type]
            await conn.execute(
                f"""
                INSERT INTO core.mdm_dossier_link (tenant, dossier_id, {cot}, source, updated_by)
                VALUES (core.jwt_tenant(), $1, $2, 'thu_cong', core.jwt_sub())
                ON CONFLICT (tenant, dossier_id) DO UPDATE
                SET {cot} = EXCLUDED.{cot}, source = 'thu_cong', updated_by = EXCLUDED.updated_by, updated_at = now()
                """,
                body.dossier_id, body.entity_id,
            )
            link = await conn.fetchrow(
                "SELECT * FROM core.mdm_dossier_link WHERE tenant = core.jwt_tenant() AND dossier_id = $1", body.dossier_id,
            )
            await conn.execute(
                "INSERT INTO core.outbox (tenant, topic, payload) VALUES (core.jwt_tenant(), 'mdm.entity.linked', $1::jsonb)",
                json.dumps({"dossier_id": str(body.dossier_id), "entity_type": body.entity_type, "entity_id": str(body.entity_id)}),
            )
            return 201, await lien_ket_ho_so(conn, body.dossier_id, dict(link))

        ma, kq = await idempotent(conn, claims, "mdm.links", khoa, lam)
    await log_audit_event(tenant=claims.tenant, action="mdm.entity.linked", actor_sub=claims.sub, object_type="ho_so",
                          object_id=str(body.dossier_id), detail={"entity_type": body.entity_type, "entity_id": str(body.entity_id)})
    return JSONResponse(status_code=ma, content=kq)


def _ket_qua_gop(r) -> Dict[str, Any]:
    return {"merge_id": str(r["merge_id"]), "entity_type": r["entity_type"], "giu_id": str(r["giu_id"]),
            "gop_ids": [str(x) for x in r["gop_ids"]], "trang_thai": r["trang_thai"],
            "thuc_hien_luc": (r["hoan_tac_luc"] or r["thuc_hien_luc"]).isoformat()}


@router.post("/merge")
async def gop_thuc_the(body: GopThucThe, authorization: str = Header(...),
                       idempotency_key: Optional[str] = Header(default=None)):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_GOP, "Chỉ quản trị phường hoặc người quản lý dữ liệu được gộp bản ghi")
    khoa = kiem_khoa_idempotency(idempotency_key)
    if body.giu_id in body.gop_ids:
        raise LoiDH(409, "MDM_MERGE_SELF", "Bản ghi giữ lại không được nằm trong danh sách gộp")
    bang, khoa_bang = BANG[body.entity_type]
    cot = COT_LIEN_KET.get(body.entity_type)

    async with get_db_connection(claims) as conn:
        async def lam():
            ids = [body.giu_id, *body.gop_ids]
            rows = await conn.fetch(f"SELECT {khoa_bang} AS id, merged_into FROM {bang} WHERE {khoa_bang} = ANY($1::uuid[])", ids)
            if len(rows) != len(set(ids)):
                raise LoiDH(404, "MDM_NOT_FOUND", "Có bản ghi không tồn tại trong phường của bạn")
            if any(r["merged_into"] for r in rows):
                raise LoiDH(409, "MDM_ALREADY_MERGED", "Có bản ghi đã bị gộp trước đó")
            await conn.execute(f"UPDATE {bang} SET merged_into = $1 WHERE {khoa_bang} = ANY($2::uuid[])", body.giu_id, body.gop_ids)
            await conn.execute(
                "UPDATE core.mdm_link_candidate SET status = 'merged' WHERE tenant = core.jwt_tenant() AND entity_type = $1 "
                "AND ((entity_id = $2 AND candidate_id = ANY($3::uuid[])) OR (candidate_id = $2 AND entity_id = ANY($3::uuid[])))",
                body.entity_type, body.giu_id, body.gop_ids,
            )
            r = await conn.fetchrow(
                """
                INSERT INTO core.mdm_merge_log (tenant, entity_type, giu_id, gop_ids, ly_do, thuc_hien_boi)
                VALUES (core.jwt_tenant(), $1, $2, $3::uuid[], $4, core.jwt_sub()) RETURNING *
                """,
                body.entity_type, body.giu_id, body.gop_ids, body.ly_do,
            )
            return 200, _ket_qua_gop(r)

        ma, kq = await idempotent(conn, claims, "mdm.merge", khoa, lam)
    await log_audit_event(tenant=claims.tenant, action="mdm.entity.merged", actor_sub=claims.sub, object_type="mdm_" + body.entity_type,
                          object_id=str(body.giu_id), detail={"merge_id": kq["merge_id"], "so_ban_ghi_gop": len(body.gop_ids),
                                                              "lien_ket_theo": cot})
    return JSONResponse(status_code=ma, content=kq)


@router.post("/merge/{merge_id}/undo")
async def hoan_tac_gop(merge_id: str, authorization: str = Header(...),
                       idempotency_key: Optional[str] = Header(default=None)):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_GOP, "Chỉ quản trị phường hoặc người quản lý dữ liệu được hoàn tác gộp")
    khoa = kiem_khoa_idempotency(idempotency_key)
    mid = _uuid(merge_id, "merge_id")

    async with get_db_connection(claims) as conn:
        async def lam():
            m = await conn.fetchrow("SELECT * FROM core.mdm_merge_log WHERE merge_id = $1 FOR UPDATE", mid)
            if m is None:
                raise LoiDH(404, "MDM_NOT_FOUND", "Không có lần gộp này trong phường của bạn")
            if m["trang_thai"] != "da_gop":
                raise LoiDH(409, "MDM_MERGE_UNDONE", "Lần gộp này đã được hoàn tác")
            bang, khoa_bang = BANG[m["entity_type"]]
            await conn.execute(
                f"UPDATE {bang} SET merged_into = NULL WHERE {khoa_bang} = ANY($1::uuid[]) AND merged_into = $2",
                m["gop_ids"], m["giu_id"],
            )
            r = await conn.fetchrow(
                """
                UPDATE core.mdm_merge_log SET trang_thai = 'da_hoan_tac', hoan_tac_luc = now(), hoan_tac_boi = core.jwt_sub()
                WHERE merge_id = $1 RETURNING *
                """,
                mid,
            )
            return 200, _ket_qua_gop(r)

        ma, kq = await idempotent(conn, claims, "mdm.merge.undo", khoa, lam)
    await log_audit_event(tenant=claims.tenant, action="mdm.entity.merge_undone", actor_sub=claims.sub,
                          object_type="mdm_merge", object_id=str(mid), detail={})
    return JSONResponse(status_code=ma, content=kq)


@router.get("/dsar/export")
async def dsar_xuat_mdm(
    subject_sub: Optional[str] = Query(default=None),
    so_dinh_danh: Optional[str] = Query(default=None),
    cccd: Optional[str] = Query(default=None),
    authorization: str = Header(...),
):
    """Xuất dữ liệu MDM phục vụ yêu cầu DSAR (D-GOV-02); không trả HMAC thô."""
    claims = verify_jwt_token(authorization)
    target_sub = claims.sub
    if la_chu_dau_tu(claims):
        target_sub = claims.sub
    else:
        can_vai(claims, VAI_DSAR_XUAT, "Chỉ cán bộ hoặc chính chủ thể được xuất dữ liệu DSAR")
        if subject_sub:
            target_sub = subject_sub

    async with get_db_connection(claims) as conn:
        ma = None
        cccd_in = so_dinh_danh or cccd
        if cccd_in:
            ma = cccd_hmac(cccd_in)
        if not ma:
            so_cccd = await conn.fetchval(
                "SELECT cccd FROM app_cap_phep.ho_so WHERE tenant = core.jwt_tenant() "
                "AND chu_dau_tu_sub = $1 AND cccd IS NOT NULL ORDER BY created_at DESC LIMIT 1",
                target_sub,
            )
            if so_cccd:
                ma = cccd_hmac(so_cccd)

        if not ma:
            return {
                "tenant": claims.tenant,
                "subject": None,
                "dossier_links": [],
                "external_refs": [],
            }

        res_json = await conn.fetchval(
            "SELECT core_api.dsar_mdm_export(core.jwt_tenant(), $1)",
            ma,
        )
        if not res_json:
            return {
                "tenant": claims.tenant,
                "subject": None,
                "dossier_links": [],
                "external_refs": [],
            }

        kq = json.loads(res_json) if isinstance(res_json, str) else res_json

    subj_id = (kq.get("subject") or {}).get("subject_id")
    await log_audit_event(
        tenant=claims.tenant,
        action="dsar.mdm.exported",
        actor_sub=claims.sub,
        object_type="mdm_subject",
        object_id=str(subj_id) if subj_id else "unknown",
        detail={"subject_sub": target_sub},
    )
    return kq


@router.post("/dsar/erase")
async def dsar_xoa_mdm(
    body: XoaDsarMDM,
    authorization: str = Header(...),
    idempotency_key: Optional[str] = Header(default=None),
):
    """Xóa/ẩn danh dữ liệu MDM theo chính sách lưu trữ retention (D-GOV-02); ghi audit."""
    claims = verify_jwt_token(authorization)
    target_sub = claims.sub
    if la_chu_dau_tu(claims):
        target_sub = claims.sub
    else:
        can_vai(claims, VAI_DSAR_XU_LY, "Chỉ cán bộ xử lý DSAR hoặc chính chủ thể được yêu cầu xóa")
        if body.subject_sub:
            target_sub = body.subject_sub

    khoa = kiem_khoa_idempotency(idempotency_key) if idempotency_key else None

    async with get_db_connection(claims) as conn:
        ma = None
        so_dinh_danh = body.so_dinh_danh or body.cccd
        if so_dinh_danh:
            ma = cccd_hmac(so_dinh_danh)
        if not ma:
            so_cccd = await conn.fetchval(
                "SELECT cccd FROM app_cap_phep.ho_so WHERE tenant = core.jwt_tenant() "
                "AND chu_dau_tu_sub = $1 AND cccd IS NOT NULL ORDER BY created_at DESC LIMIT 1",
                target_sub,
            )
            if so_cccd:
                ma = cccd_hmac(so_cccd)

        if not ma:
            raise LoiDH(404, "MDM_SUBJECT_NOT_FOUND", "Không tìm thấy dữ liệu chủ của người yêu cầu trong phường")

        res_json = await conn.fetchval(
            "SELECT core_api.dsar_mdm_erase(core.jwt_tenant(), $1, $2, $3)",
            ma, body.reason, claims.sub,
        )
        kq = json.loads(res_json) if isinstance(res_json, str) else res_json
        if kq.get("status") == "not_found":
            raise LoiDH(404, "MDM_SUBJECT_NOT_FOUND", kq.get("message", "Không tìm thấy"))

    await log_audit_event(
        tenant=claims.tenant,
        action="dsar.mdm.erased",
        actor_sub=claims.sub,
        object_type="mdm_subject",
        object_id=str(kq.get("subject_id")),
        detail={"reason": body.reason, "anonymized": True, "retention_policy": "core.data_assets"},
    )
    return kq
