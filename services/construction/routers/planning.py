# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-PLAN-03: API kiểm tra quy hoạch, thửa đất, vùng và kết quả."""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger("dxos.construction.planning")

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from dxos_core.audit import log_audit_event
from dxos_core.db import get_db_connection
from dxos_core.jwt import UserClaims, verify_jwt_token
from dxos_core.lineage import record_lineage_event

from construction.deps import la_can_bo, yeu_cau_can_bo, yeu_cau_kiem_tra
from construction.rules.planning_engine import check_planning, overall_pass

router = APIRouter(prefix="/api/v1/planning", tags=["Quy hoạch"])


class CheckRequest(BaseModel):
    ho_so_id: Optional[str] = Field(default=None, max_length=64)
    thua_dat_id: Optional[str] = Field(default=None, max_length=64)
    proposal: dict[str, Any] = Field(default_factory=dict)


class WarningConfirmRequest(BaseModel):
    ghi_chu: Optional[str] = Field(default=None, max_length=2000)


def _json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _row(r) -> dict:
    data = dict(r)
    for key in ("geom", "proposal", "ket_qua", "tags"):
        if key in data:
            data[key] = _json(data[key])
    return data


def _bbox_intersects(geom: Any, bbox: tuple[float, float, float, float]) -> bool:
    minx, miny, maxx, maxy = bbox
    coords: list[tuple[float, float]] = []

    def walk(node: Any) -> None:
        if isinstance(node, (list, tuple)):
            if len(node) >= 2 and all(isinstance(x, (int, float)) for x in node[:2]):
                coords.append((float(node[0]), float(node[1])))
            else:
                for child in node:
                    walk(child)

    g = _json(geom)
    if isinstance(g, dict):
        if g.get("type") == "Feature":
            g = g.get("geometry") or {}
        walk(g.get("coordinates"))
    if not coords:
        return True
    gx1 = min(c[0] for c in coords)
    gx2 = max(c[0] for c in coords)
    gy1 = min(c[1] for c in coords)
    gy2 = max(c[1] for c in coords)
    return not (gx2 < minx or gx1 > maxx or gy2 < miny or gy1 > maxy)


def _parse_bbox(bbox: Optional[str]) -> Optional[tuple[float, float, float, float]]:
    if not bbox:
        return None
    parts = bbox.split(",")
    if len(parts) != 4:
        raise HTTPException(status_code=422, detail={"loi": "bbox phải có dạng minx,miny,maxx,maxy"})
    try:
        return tuple(float(p) for p in parts)  # type: ignore[return-value]
    except ValueError:
        raise HTTPException(status_code=422, detail={"loi": "bbox không hợp lệ"})


async def _enrich_citations(conn, results: list[dict]) -> list[dict]:
    keys = sorted({r.get("citation_key") for r in results if r.get("citation_key")})
    if not keys:
        return results
    rows = await conn.fetch(
        """
        SELECT c.citation_key, c.document_id, d.code AS document_code, d.title AS document_title,
               c.article, c.clause, c.point, c.topic, c.summary, c.effective_date, c.status,
               c.source_url, c.sha256, c.can_doi_chieu
        FROM app_construction.legal_citations c
        JOIN app_construction.legal_refs d ON d.document_id = c.document_id
        WHERE c.citation_key = ANY($1::text[])
        """,
        keys,
    )
    by_key = {r["citation_key"]: _row(r) for r in rows}
    for result in results:
        result["citation"] = by_key.get(result.get("citation_key"))
    return results


async def _load_parcel(conn, thua_dat_id: str) -> Optional[dict]:
    row = await conn.fetchrow(
        """
        SELECT id, tenant, ma_thua_dat, so_thua, to_ban_do, dia_chi, dien_tich_m2, loai_dat,
               ma_dinh_danh_dia_diem, geom, status
        FROM app_construction.thua_dat
        WHERE tenant = core.jwt_tenant()
          AND (id::text = $1 OR ma_thua_dat = $1)
          AND status = 'hieu_luc'
        """,
        thua_dat_id,
    )
    return _row(row) if row else None


@router.get("/parcels")
async def danh_sach_thua_dat(
    bbox: Optional[str] = Query(default=None),
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    box = _parse_bbox(bbox)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT id, tenant, ma_thua_dat, so_thua, to_ban_do, dia_chi, dien_tich_m2, loai_dat,
                   ma_dinh_danh_dia_diem, geom, status
            FROM app_construction.thua_dat
            WHERE tenant = core.jwt_tenant() AND status = 'hieu_luc'
            ORDER BY ma_thua_dat
            """
        )
    data = [_row(r) for r in rows]
    if box:
        data = [r for r in data if _bbox_intersects(r.get("geom"), box)]
    return data


@router.get("/parcels/{parcel_id}")
async def chi_tiet_thua_dat(parcel_id: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        parcel = await _load_parcel(conn, parcel_id)
    if parcel is None:
        raise HTTPException(status_code=404, detail={"loi": "Không tìm thấy thửa đất"})
    return parcel


@router.get("/zones")
async def danh_sach_vung(
    bbox: Optional[str] = Query(default=None),
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    box = _parse_bbox(bbox)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT id, tenant, ma_zone, ten, loai_zone, mo_ta, dien_tich_ha, geom, status
            FROM app_construction.quy_hoach_zone
            WHERE tenant = core.jwt_tenant() AND status = 'hieu_luc'
            ORDER BY ma_zone
            """
        )
    data = [_row(r) for r in rows]
    if box:
        data = [r for r in data if _bbox_intersects(r.get("geom"), box)]
    return data


@router.get("/documents")
async def danh_sach_van_ban_quy_hoach(authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT v.id, v.tenant, v.ma_van_ban, v.ten, v.co_quan_ban_hanh, v.ngay_ban_hanh,
                   v.ngay_hieu_luc, v.file_url, v.legal_document_id, v.status,
                   d.code AS legal_document_code, d.title AS legal_document_title,
                   d.source_url, d.sha256
            FROM app_construction.quy_hoach_van_ban v
            LEFT JOIN app_construction.legal_refs d ON d.document_id = v.legal_document_id
            WHERE v.tenant = core.jwt_tenant()
            ORDER BY v.ngay_ban_hanh DESC
            """
        )
    return [_row(r) for r in rows]


@router.get("/documents/{document_id}")
async def chi_tiet_van_ban_quy_hoach(document_id: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        row = await conn.fetchrow(
            """
            SELECT v.id, v.tenant, v.ma_van_ban, v.ten, v.co_quan_ban_hanh, v.ngay_ban_hanh,
                   v.ngay_hieu_luc, v.file_url, v.legal_document_id, v.status,
                   d.code AS legal_document_code, d.title AS legal_document_title,
                   d.source_url, d.sha256
            FROM app_construction.quy_hoach_van_ban v
            LEFT JOIN app_construction.legal_refs d ON d.document_id = v.legal_document_id
            WHERE v.tenant = core.jwt_tenant() AND (v.id::text = $1 OR v.ma_van_ban = $1)
            """,
            document_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail={"loi": "Không tìm thấy văn bản quy hoạch" })
        quotas = await conn.fetch(
            """
            SELECT q.zone_id, z.ma_zone, q.chi_tieu, q.ten, q.gia_tri_min, q.gia_tri_max,
                   q.don_vi, q.bat_buoc, q.legal_citation_key
            FROM app_construction.chi_tieu_quy_hoach q
            JOIN app_construction.quy_hoach_zone z ON z.id = q.zone_id
            WHERE q.tenant = core.jwt_tenant() AND z.tenant = core.jwt_tenant()
            ORDER BY z.ma_zone, q.chi_tieu
            """
        )
    data = _row(row)
    data["chi_tieu"] = [_row(q) for q in quotas]
    return data


@router.post("/check")
async def kiem_tra_quy_hoach(body: CheckRequest, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_kiem_tra(claims)
    if not body.ho_so_id and not body.thua_dat_id:
        raise HTTPException(status_code=422, detail={"loi": "Cần ho_so_id hoặc thua_dat_id"})

    async with get_db_connection(claims) as conn:
        ho_so = None
        if body.ho_so_id:
            ho_so = await conn.fetchrow(
                """
                SELECT id, tenant, ma_ho_so, thua_dat, so_tang, dien_tich_san_m2, loai_dat,
                       ma_dinh_danh_dia_diem, chu_dau_tu_sub
                FROM app_cap_phep.ho_so
                WHERE id = $1::uuid AND tenant = core.jwt_tenant()
                """,
                body.ho_so_id,
            )
            if ho_so is None:
                raise HTTPException(status_code=404, detail={"loi": "Không tìm thấy hồ sơ trong địa bàn"})
            if not la_can_bo(claims) and ho_so["chu_dau_tu_sub"] != claims.sub:
                raise HTTPException(status_code=403, detail={"loi": "Bạn không có quyền kiểm tra hồ sơ này"})

        thua_dat_ref = body.thua_dat_id or (ho_so["thua_dat"] if ho_so else None)
        if not thua_dat_ref:
            raise HTTPException(status_code=422, detail={"loi": "Hồ sơ chưa có thông tin thửa đất"})

        parcel = await _load_parcel(conn, str(thua_dat_ref))
        if parcel is None:
            # Hồ sơ demo có thể dùng số thửa tự do; trả lỗi rõ thay vì đoán.
            raise HTTPException(
                status_code=404,
                detail={"loi": "Không tìm thấy thửa đất trong dữ liệu quy hoạch", "thua_dat": str(thua_dat_ref)},
            )

        zones = [
            _row(r)
            for r in await conn.fetch(
                """
                SELECT id, tenant, ma_zone, ten, loai_zone, mo_ta, dien_tich_ha, geom, status
                FROM app_construction.quy_hoach_zone
                WHERE tenant = core.jwt_tenant() AND status = 'hieu_luc'
                """
            )
        ]
        quotas = [
            _row(r)
            for r in await conn.fetch(
                """
                SELECT id, tenant, zone_id, chi_tieu, ten, gia_tri_min, gia_tri_max, don_vi,
                       bat_buoc, legal_citation_key, status
                FROM app_construction.chi_tieu_quy_hoach
                WHERE tenant = core.jwt_tenant() AND status = 'hieu_luc'
                """
            )
        ]

        proposal = dict(body.proposal or {})
        if ho_so:
            proposal.setdefault("so_tang", ho_so["so_tang"])
            proposal.setdefault("dien_tich_san_m2", ho_so["dien_tich_san_m2"])
            if ho_so.get("loai_dat"):
                proposal.setdefault("loai_dat", ho_so["loai_dat"])
            if ho_so.get("ma_dinh_danh_dia_diem"):
                proposal.setdefault("ma_dinh_danh_dia_diem", ho_so["ma_dinh_danh_dia_diem"])

        results = check_planning(parcel, zones, quotas, proposal)
        passed = overall_pass(results)
        results = await _enrich_citations(conn, results)
        zone = next((z for z in zones if any(r["rule_id"] == "R01" and r["passed"] and r["value"] == z.get("ma_zone") for r in results)), None)

        so_loi = sum(1 for r in results if r["severity"] == "error")
        so_canh_bao = sum(1 for r in results if r["severity"] == "warning")
        row = await conn.fetchrow(
            """
            INSERT INTO app_construction.ket_qua_kiem_tra_quy_hoach
                (tenant, ho_so_id, thua_dat_id, zone_id, proposal, ket_qua, pass, so_loi, so_canh_bao, nguoi_kiem_tra)
            VALUES (core.jwt_tenant(), $1, $2, $3, $4::jsonb, $5::jsonb, $6, $7, $8, core.jwt_sub())
            RETURNING id, created_at
            """,
            ho_so["id"] if ho_so else None,
            parcel["id"],
            zone["id"] if zone else None,
            json.dumps(proposal, ensure_ascii=False),
            json.dumps(results, ensure_ascii=False, default=str),
            passed,
            so_loi,
            so_canh_bao,
        )
        await conn.execute(
            """
            INSERT INTO core.outbox (tenant, topic, payload)
            VALUES (core.jwt_tenant(), 'planning.checked', $1::jsonb)
            """,
            json.dumps(
                {
                    "ho_so_id": body.ho_so_id,
                    "thua_dat_id": str(parcel["id"]),
                    "pass": passed,
                    "so_loi": so_loi,
                    "so_canh_bao": so_canh_bao,
                    "ket_qua_id": str(row["id"]),
                },
                ensure_ascii=False,
            ),
        )

        if ho_so:
            try:
                await record_lineage_event(
                    job="quy_hoach.kiem_tra",
                    inputs=[{"name": "app_cap_phep.ho_so"}, {"name": "app_construction.thua_dat"}],
                    outputs=[{"name": "app_construction.ket_qua_kiem_tra_quy_hoach"}],
                    facets={
                        "tenant": claims.tenant,
                        "entity": {"type": "ho_so", "id": str(ho_so["id"])},
                        "pass": passed,
                    },
                )
            except Exception as e:
                logger.warning(f"Lỗi ghi lineage: {e}", exc_info=True)

    await log_audit_event(
        tenant=claims.tenant,
        action="planning.checked",
        actor_sub=claims.sub,
        object_type="ho_so" if body.ho_so_id else "thua_dat",
        object_id=body.ho_so_id or str(parcel["id"]),
        detail={"pass": passed, "so_loi": so_loi, "so_canh_bao": so_canh_bao, "ket_qua_id": str(row["id"])},
    )

    return {
        "id": str(row["id"]),
        "created_at": row["created_at"].isoformat(),
        "pass": passed,
        "so_loi": so_loi,
        "so_canh_bao": so_canh_bao,
        "ho_so_id": body.ho_so_id,
        "thua_dat": parcel,
        "zone": zone,
        "proposal": proposal,
        "results": results,
    }


@router.get("/validation/{ho_so_id}")
async def danh_sach_canh_bao(ho_so_id: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    async with get_db_connection(claims) as conn:
        raw = await conn.fetchval("SELECT app_cap_phep.danh_sach_canh_bao_ho_so($1::uuid)", ho_so_id)
    if isinstance(raw, str):
        raw = json.loads(raw)
    return raw or {"items": [], "so_canh_bao": 0, "so_loi": 0}


@router.post("/validation/{ho_so_id}/confirm")
async def xac_nhan_canh_bao(ho_so_id: str, body: WarningConfirmRequest, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_kiem_tra(claims)
    async with get_db_connection(claims) as conn:
        raw = await conn.fetchval(
            "SELECT app_cap_phep.xac_nhan_canh_bao_ho_so($1::uuid, $2)",
            ho_so_id,
            body.ghi_chu,
        )
    if isinstance(raw, str):
        raw = json.loads(raw)
    return raw or {"items": []}


@router.get("/results/{ho_so_id}")
async def ket_qua_da_luu(ho_so_id: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT id, tenant, ho_so_id, thua_dat_id, zone_id, proposal, ket_qua, pass,
                   so_loi, so_canh_bao, nguoi_kiem_tra, created_at
            FROM app_construction.ket_qua_kiem_tra_quy_hoach
            WHERE tenant = core.jwt_tenant() AND ho_so_id = $1::uuid
            ORDER BY created_at DESC
            LIMIT 20
            """,
            ho_so_id,
        )
        data = []
        for r in rows:
            item = _row(r)
            item["ket_qua"] = await _enrich_citations(conn, item.get("ket_qua") or [])
            data.append(item)
    return data
