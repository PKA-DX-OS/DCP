# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Dữ liệu chủ (D-MDM-02 khớp đúng, D-MDM-03, D-360-01).

- lien_ket_tu_ho_so: tạo/khớp chủ thể (HMAC CCCD), thửa đất (mã định danh địa điểm hoặc số thửa/tờ
  bản đồ), công trình (mã công trình), giấy phép cho một hồ sơ; không ghi đè liên kết thủ công.
  Chạy bằng kết nối dịch vụ sau khi API đã kiểm người gọi thấy hồ sơ.
- tom_tat: nhãn hiển thị của một thực thể (họ tên đọc từ hồ sơ nguồn, không lưu ở MDM).
- vang: theo `merged_into` đến bản ghi vàng.
"""

import re
from typing import Any, Dict, Optional
from uuid import UUID

from construction.dh import cccd_hmac

BANG = {
    "subject": ("core.mdm_subject", "subject_id"),
    "parcel": ("core.mdm_parcel", "parcel_id"),
    "construction": ("core.mdm_construction", "construction_id"),
    "organization": ("core.mdm_organization", "org_id"),
}
COT_LIEN_KET = {"subject": "subject_id", "parcel": "parcel_id", "construction": "construction_id", "permit": "permit_id"}
_THUA_TO = re.compile(r"^\s*(?:thửa\s*)?(\d+[a-z]?)\s*[/,;-]\s*(?:tờ\s*)?(\d+[a-z]?)\s*$", re.IGNORECASE)


def tach_thua_dat(thua_dat: Optional[str]) -> tuple:
    """'12/3' hoặc 'thửa 12, tờ 3' → ('12', '3'); dạng khác giữ nguyên làm số thửa."""
    s = (thua_dat or "").strip()
    if not s:
        return None, None
    m = _THUA_TO.match(s)
    if m:
        return m.group(1).lower(), m.group(2).lower()
    return s.lower(), None


async def vang(conn, loai: str, id_: Optional[UUID]) -> Optional[UUID]:
    """Bản ghi vàng của một thực thể (theo chuỗi merged_into, tối đa 10 bước)."""
    if id_ is None or loai not in BANG:
        return id_
    bang, khoa = BANG[loai]
    for _ in range(10):
        tiep = await conn.fetchval(f"SELECT merged_into FROM {bang} WHERE {khoa} = $1", id_)
        if tiep is None:
            return id_
        id_ = tiep
    return id_


async def _chu_the(conn, tenant: str, ho_so: Dict[str, Any]) -> Optional[UUID]:
    ma = cccd_hmac(ho_so.get("cccd"))
    if ma is None:
        return None
    moi = await conn.fetchval(
        """
        INSERT INTO core.mdm_subject (tenant, cccd_hmac, source, source_ref)
        VALUES ($1, $2, 'ho_so', $3)
        ON CONFLICT (tenant, cccd_hmac) WHERE merged_into IS NULL AND cccd_hmac IS NOT NULL DO NOTHING
        RETURNING subject_id
        """,
        tenant, ma, str(ho_so["id"]),
    )
    return moi or await conn.fetchval(
        "SELECT subject_id FROM core.mdm_subject WHERE tenant = $1 AND cccd_hmac = $2 AND merged_into IS NULL",
        tenant, ma,
    )


async def _thua_dat(conn, tenant: str, ho_so: Dict[str, Any]) -> Optional[UUID]:
    ma = ho_so.get("ma_dinh_danh_dia_diem")
    so_thua, to_ban_do = tach_thua_dat(ho_so.get("thua_dat"))
    if ma and re.fullmatch(r"\d{12}", ma):
        moi = await conn.fetchval(
            """
            INSERT INTO core.mdm_parcel (tenant, ma_dinh_danh_dia_diem, so_thua, to_ban_do, source, source_ref)
            VALUES ($1, $2, $3, $4, 'ho_so', $5)
            ON CONFLICT (tenant, ma_dinh_danh_dia_diem)
                WHERE merged_into IS NULL AND ma_dinh_danh_dia_diem IS NOT NULL DO NOTHING
            RETURNING parcel_id
            """,
            tenant, ma, so_thua, to_ban_do, str(ho_so["id"]),
        )
        return moi or await conn.fetchval(
            "SELECT parcel_id FROM core.mdm_parcel WHERE tenant = $1 AND ma_dinh_danh_dia_diem = $2 AND merged_into IS NULL",
            tenant, ma,
        )
    if not so_thua:
        return None
    co = await conn.fetchval(
        """
        SELECT parcel_id FROM core.mdm_parcel
        WHERE tenant = $1 AND so_thua = $2 AND to_ban_do IS NOT DISTINCT FROM $3 AND merged_into IS NULL
        ORDER BY created_at LIMIT 1
        """,
        tenant, so_thua, to_ban_do,
    )
    return co or await conn.fetchval(
        """
        INSERT INTO core.mdm_parcel (tenant, so_thua, to_ban_do, source, source_ref)
        VALUES ($1, $2, $3, 'ho_so', $4) RETURNING parcel_id
        """,
        tenant, so_thua, to_ban_do, str(ho_so["id"]),
    )


async def _cong_trinh(conn, tenant: str, ma: Optional[str], dia_chi: Optional[str], parcel_id) -> Optional[UUID]:
    if not ma:
        return None
    moi = await conn.fetchval(
        """
        INSERT INTO core.mdm_construction (tenant, ma_cong_trinh, parcel_id, dia_chi_chuan, source)
        VALUES ($1, $2, $3, $4, 'ho_so')
        ON CONFLICT (tenant, ma_cong_trinh) WHERE merged_into IS NULL AND ma_cong_trinh IS NOT NULL DO NOTHING
        RETURNING construction_id
        """,
        tenant, ma, parcel_id, dia_chi,
    )
    return moi or await conn.fetchval(
        "SELECT construction_id FROM core.mdm_construction WHERE tenant = $1 AND ma_cong_trinh = $2 AND merged_into IS NULL",
        tenant, ma,
    )


async def lien_ket_tu_ho_so(conn, tenant: str, ho_so_id: str) -> Optional[Dict[str, Any]]:
    """Khớp đúng các thực thể của một hồ sơ và ghi liên kết (chỉ điền phần còn trống)."""
    hs = await conn.fetchrow(
        """
        SELECT id, cccd, thua_dat, ma_dinh_danh_dia_diem
        FROM app_cap_phep.ho_so WHERE id = $1::uuid AND tenant = $2
        """,
        ho_so_id, tenant,
    )
    if hs is None:
        return None
    hs = dict(hs)
    gp = await conn.fetchrow(
        """
        SELECT g.id, c.ma_cong_trinh, c.dia_chi
        FROM app_cap_phep.giay_phep g
        LEFT JOIN app_cap_phep.cong_trinh c ON c.giay_phep_id = g.id
        WHERE g.ho_so_id = $1 AND g.tenant = $2
        ORDER BY (g.trang_thai = 'hieu_luc') DESC, g.ngay_cap DESC
        LIMIT 1
        """,
        hs["id"], tenant,
    )
    subject_id = await _chu_the(conn, tenant, hs)
    parcel_id = await _thua_dat(conn, tenant, hs)
    construction_id = await _cong_trinh(conn, tenant, gp["ma_cong_trinh"] if gp else None,
                                        gp["dia_chi"] if gp else None, parcel_id)
    await conn.execute(
        """
        INSERT INTO core.mdm_dossier_link (tenant, dossier_id, subject_id, parcel_id, construction_id, permit_id, source)
        VALUES ($1, $2, $3, $4, $5, $6, 'ho_so')
        ON CONFLICT (tenant, dossier_id) DO UPDATE
        SET subject_id = COALESCE(core.mdm_dossier_link.subject_id, EXCLUDED.subject_id),
            parcel_id = COALESCE(core.mdm_dossier_link.parcel_id, EXCLUDED.parcel_id),
            construction_id = COALESCE(core.mdm_dossier_link.construction_id, EXCLUDED.construction_id),
            permit_id = COALESCE(core.mdm_dossier_link.permit_id, EXCLUDED.permit_id),
            updated_at = now()
        """,
        tenant, hs["id"], subject_id, parcel_id, construction_id, gp["id"] if gp else None,
    )
    row = await conn.fetchrow("SELECT * FROM core.mdm_dossier_link WHERE tenant = $1 AND dossier_id = $2", tenant, hs["id"])
    return dict(row) if row else None


async def tom_tat(conn, loai: str, id_: Optional[UUID]) -> Optional[Dict[str, Any]]:
    """ThucTheTomTat theo hợp đồng; None nếu không có hoặc người gọi không thấy."""
    if id_ is None:
        return None
    if loai == "subject":
        r = await conn.fetchrow(
            """
            SELECT s.subject_id AS id, s.confidence, s.source,
                   (SELECT h.ho_ten FROM core.mdm_dossier_link l JOIN app_cap_phep.ho_so h ON h.id = l.dossier_id
                    WHERE l.tenant = s.tenant AND l.subject_id = s.subject_id
                    ORDER BY h.created_at DESC LIMIT 1) AS nhan
            FROM core.mdm_subject s WHERE s.subject_id = $1
            """,
            id_,
        )
        return r and {"type": "subject", "id": r["id"], "nhan": r["nhan"] or "Chủ thể chưa có tên",
                      "ma": None, "confidence": float(r["confidence"]), "source": r["source"]}
    if loai == "parcel":
        r = await conn.fetchrow(
            "SELECT parcel_id AS id, so_thua, to_ban_do, ma_dinh_danh_dia_diem AS ma, confidence, source "
            "FROM core.mdm_parcel WHERE parcel_id = $1",
            id_,
        )
        if not r:
            return None
        nhan = " ".join(x for x in [f"Thửa {r['so_thua']}" if r["so_thua"] else "",
                                    f"tờ {r['to_ban_do']}" if r["to_ban_do"] else ""] if x) or (r["ma"] or "Thửa đất")
        return {"type": "parcel", "id": r["id"], "nhan": nhan, "ma": r["ma"],
                "confidence": float(r["confidence"]), "source": r["source"]}
    if loai == "construction":
        r = await conn.fetchrow(
            "SELECT construction_id AS id, ma_cong_trinh AS ma, dia_chi_chuan, confidence, source "
            "FROM core.mdm_construction WHERE construction_id = $1",
            id_,
        )
        return r and {"type": "construction", "id": r["id"], "nhan": r["ma"] or r["dia_chi_chuan"] or "Công trình",
                      "ma": r["ma"], "confidence": float(r["confidence"]), "source": r["source"]}
    if loai == "organization":
        r = await conn.fetchrow(
            "SELECT org_id AS id, ten, mst, confidence, source FROM core.mdm_organization WHERE org_id = $1", id_,
        )
        return r and {"type": "organization", "id": r["id"], "nhan": r["ten"], "ma": r["mst"],
                      "confidence": float(r["confidence"]), "source": r["source"]}
    if loai == "permit":
        r = await conn.fetchrow("SELECT id, so_giay_phep FROM app_cap_phep.giay_phep WHERE id = $1", id_)
        return r and {"type": "permit", "id": r["id"], "nhan": r["so_giay_phep"], "ma": r["so_giay_phep"],
                      "confidence": 1.0, "source": "ho_so"}
    return None


async def lien_ket_ho_so(conn, dossier_id, link: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """LienKetHoSo theo hợp đồng (thực thể đã gộp hiện bản ghi vàng)."""
    kq: Dict[str, Any] = {"dossier_id": dossier_id}
    for loai, cot in COT_LIEN_KET.items():
        id_ = link.get(cot) if link else None
        kq[loai] = await tom_tat(conn, loai, await vang(conn, loai, id_))
    return kq
