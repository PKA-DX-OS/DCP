# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tìm kiếm toàn cục — contracts/dh/search.yaml (D-360-02).

Xếp hạng: khớp đúng (1.0) > khớp đầu chuỗi (0.8) > khớp gần đúng (0.5). CCCD chỉ khớp khi đủ 12 số
và so trong máy chủ, không tìm theo một phần; điện thoại từ 9 số. Kết quả theo RLS của người gọi
(chủ đầu tư chỉ thấy hồ sơ của mình). Chuỗi tìm không ghi log; audit chỉ ghi độ dài.
"""

import re
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, Query

from dxos_core.audit import log_audit_event
from dxos_core.db import get_db_connection
from dxos_core.jwt import verify_jwt_token

from construction.dh import LoiDH, che_cccd

router = APIRouter(prefix="/api/v1/search", tags=["search"])

LOAI = ("ho_so", "chu_dau_tu", "thua_dat", "cong_trinh", "giay_phep")
DIEM = "CASE WHEN {cot} = $1 THEN 1.0 WHEN {cot} LIKE $1 || '%' THEN 0.8 ELSE 0.5 END"


def _khop(diem: float) -> str:
    return "exact" if diem >= 1.0 else ("prefix" if diem >= 0.8 else "fuzzy")


def _so(q: str) -> str:
    return re.sub(r"\D", "", q)


def _truy_van(loai: str, q: str) -> Optional[tuple]:
    """(sql, tham_so) trả các cột id, nhan, phu, diem, dossier_id; None nếu loại này không hợp với chuỗi."""
    mau = q.lower()
    so = _so(q)
    if loai == "ho_so":
        dieu_kien = ["lower(h.ma_ho_so) LIKE '%' || $1 || '%'", "lower(h.ho_ten) LIKE '%' || $1 || '%'",
                     "lower(h.dia_chi_cong_trinh) LIKE '%' || $1 || '%'"]
        diem = [DIEM.format(cot="lower(h.ma_ho_so)"),
                "CASE WHEN lower(h.ho_ten) = $1 THEN 1.0 WHEN lower(h.ho_ten) LIKE $1 || '%' THEN 0.8 "
                "WHEN lower(h.ho_ten) LIKE '%' || $1 || '%' THEN 0.5 ELSE 0 END",
                "CASE WHEN lower(h.dia_chi_cong_trinh) LIKE '%' || $1 || '%' THEN 0.5 ELSE 0 END"]
        tham_so: List[Any] = [mau]
        if len(so) == 12 and so == q.strip():
            tham_so.append(so)
            dieu_kien.append(f"h.cccd = ${len(tham_so)}")
            diem.append(f"CASE WHEN h.cccd = ${len(tham_so)} THEN 1.0 ELSE 0 END")
        if len(so) >= 9 and re.fullmatch(r"[\d\s.+-]+", q.strip()):
            tham_so.append(so[-9:])
            dieu_kien.append(f"right(regexp_replace(coalesce(h.dien_thoai, ''), '\\D', '', 'g'), 9) = ${len(tham_so)}")
            diem.append(f"CASE WHEN right(regexp_replace(coalesce(h.dien_thoai, ''), '\\D', '', 'g'), 9) = ${len(tham_so)} THEN 1.0 ELSE 0 END")
        sql = f"""
            SELECT h.id, h.ma_ho_so AS nhan,
                   h.trang_thai || coalesce(' · ' || h.ho_ten, '') AS phu,
                   GREATEST({', '.join(diem)}) AS diem, h.id AS dossier_id
            FROM app_cap_phep.ho_so h
            WHERE h.tenant = core.jwt_tenant() AND ({' OR '.join(dieu_kien)})"""
        return sql, tham_so
    if loai == "chu_dau_tu":
        tham_so = [mau]
        cccd = ""
        if len(so) == 12 and so == q.strip():
            tham_so.append(so)
            cccd = " OR h.cccd = $2"
        sql = f"""
            SELECT DISTINCT ON (l.subject_id) l.subject_id AS id, h.ho_ten AS nhan, h.cccd AS phu,
                   CASE WHEN {'h.cccd = $2 OR ' if cccd else ''}lower(h.ho_ten) = $1 THEN 1.0
                        WHEN lower(h.ho_ten) LIKE $1 || '%' THEN 0.8 ELSE 0.5 END AS diem,
                   h.id AS dossier_id
            FROM core.mdm_dossier_link l
            JOIN app_cap_phep.ho_so h ON h.id = l.dossier_id
            WHERE l.tenant = core.jwt_tenant() AND l.subject_id IS NOT NULL
              AND (lower(h.ho_ten) LIKE '%' || $1 || '%'{cccd})
            ORDER BY l.subject_id, h.created_at DESC"""
        return sql, tham_so
    if loai == "thua_dat":
        sql = f"""
            SELECT p.parcel_id AS id,
                   coalesce('Thửa ' || p.so_thua, '') || coalesce(', tờ ' || p.to_ban_do, '') AS nhan,
                   p.ma_dinh_danh_dia_diem AS phu,
                   GREATEST({DIEM.format(cot="coalesce(p.ma_dinh_danh_dia_diem, '')")},
                            {DIEM.format(cot="coalesce(p.so_thua || '/' || p.to_ban_do, p.so_thua, '')")}) AS diem,
                   (SELECT l.dossier_id FROM core.mdm_dossier_link l WHERE l.tenant = p.tenant AND l.parcel_id = p.parcel_id
                    ORDER BY l.updated_at DESC LIMIT 1) AS dossier_id
            FROM core.mdm_parcel p
            WHERE p.tenant = core.jwt_tenant() AND p.merged_into IS NULL
              AND (coalesce(p.ma_dinh_danh_dia_diem, '') LIKE $1 || '%'
                   OR coalesce(p.so_thua || '/' || p.to_ban_do, p.so_thua, '') LIKE $1 || '%')"""
        return sql, [mau]
    if loai == "cong_trinh":
        sql = f"""
            SELECT c.id, c.ma_cong_trinh AS nhan, c.dia_chi AS phu,
                   GREATEST({DIEM.format(cot="lower(c.ma_cong_trinh)")},
                            CASE WHEN lower(coalesce(c.dia_chi, '')) LIKE '%' || $1 || '%' THEN 0.5 ELSE 0 END) AS diem,
                   g.ho_so_id AS dossier_id
            FROM app_cap_phep.cong_trinh c
            LEFT JOIN app_cap_phep.giay_phep g ON g.id = c.giay_phep_id
            WHERE c.tenant = core.jwt_tenant()
              AND (lower(c.ma_cong_trinh) LIKE '%' || $1 || '%' OR lower(coalesce(c.dia_chi, '')) LIKE '%' || $1 || '%')"""
        return sql, [mau]
    sql = f"""
        SELECT g.id, g.so_giay_phep AS nhan, g.trang_thai || coalesce(' · ' || d.public_code, '') AS phu,
               GREATEST({DIEM.format(cot="lower(g.so_giay_phep)")},
                        CASE WHEN lower(coalesce(d.public_code, '')) = $1 THEN 1.0 ELSE 0 END) AS diem,
               g.ho_so_id AS dossier_id
        FROM app_cap_phep.giay_phep g
        LEFT JOIN core.signed_docs d ON d.id = g.signed_doc_id
        WHERE g.tenant = core.jwt_tenant()
          AND (lower(g.so_giay_phep) LIKE '%' || $1 || '%' OR lower(coalesce(d.public_code, '')) = $1)"""
    return sql, [mau]


@router.get("")
async def tim_kiem(
    q: str = Query(min_length=2, max_length=100),
    types: Optional[str] = None,
    limit: int = Query(default=5, ge=1, le=20),
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    bat_dau = time.monotonic()
    chon = [t.strip() for t in (types or "").split(",") if t.strip()] or list(LOAI)
    sai = [t for t in chon if t not in LOAI]
    if sai:
        raise LoiDH(400, "BAD_REQUEST", "Loại kết quả không hợp lệ", {"types": sai})
    q = q.strip()
    if len(q) < 2:
        raise LoiDH(400, "BAD_REQUEST", "Chuỗi tìm cần ít nhất 2 ký tự")

    nhom: List[Dict[str, Any]] = []
    async with get_db_connection(claims) as conn:
        for loai in chon:
            sql, tham_so = _truy_van(loai, q)
            try:
                async with conn.transaction():
                    tong = await conn.fetchval(f"SELECT count(*) FROM ({sql}) x", *tham_so)
                    rows = await conn.fetch(
                        f"SELECT * FROM ({sql}) x ORDER BY diem DESC, nhan LIMIT ${len(tham_so) + 1}", *tham_so, limit,
                    )
            except Exception:  # người gọi không có quyền đọc bảng của nhóm này (RLS/quyền bảng)
                continue
            if not tong:
                continue
            items = []
            for r in rows:
                diem = min(1.0, float(r["diem"] or 0))
                phu = che_cccd(r["phu"]) if loai == "chu_dau_tu" else r["phu"]
                items.append({"type": loai, "id": r["id"], "nhan": r["nhan"] or "", "phu": phu,
                              "khop": _khop(diem), "diem": diem, "dossier_id": r["dossier_id"]})
            nhom.append({"type": loai, "total": int(tong), "items": items})

    await log_audit_event(tenant=claims.tenant, action="search.query", actor_sub=claims.sub,
                          detail={"do_dai": len(q), "so_nhom": len(nhom)})
    return {"groups": nhom, "took_ms": int((time.monotonic() - bat_dau) * 1000)}
