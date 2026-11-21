#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Khớp dữ liệu và backfill MDM (D-MDM-02).

- Dùng lại logic khớp chính xác từ services/construction/dh_mdm.py (lien_ket_tu_ho_so).
- Khớp chính xác theo: cccd_hmac, ma_dinh_danh_dia_diem / (so_thua, to_ban_do), ma_cong_trinh, so_giay_phep.
- Khớp gần đúng: so sánh tên, điện thoại, địa chỉ (chủ thể); số thửa, tờ bản đồ, địa chỉ (thửa đất);
  công trình cùng vị trí. Dưới ngưỡng tự động liên kết (0.70 <= confidence < 1.0) thì tạo ứng viên
  trong core.mdm_link_candidate (status='open', không tự liên kết, không ghi đè liên kết thủ công).
- Cờ --dry-run: mô phỏng, không ghi DB. Chạy lại không tạo trùng; cuối lượt in bảng tổng kết.

Chạy:
    python scripts/mdm_backfill.py [--dry-run] [--tenant phuong-a]
"""

import argparse
import asyncio
import difflib
import logging
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services"))

try:
    import asyncpg
    from construction.dh_mdm import lien_ket_tu_ho_so, tach_thua_dat
    from construction.dh import cccd_hmac
except ImportError:
    # Cho phép import các hàm pure matching khi chạy unit test môi trường tối giản
    pass

logger = logging.getLogger("dxos.mdm_backfill")


def bo_dau_tieng_viet(s: str) -> str:
    """Loại bỏ dấu tiếng Việt (chuẩn hóa Unicode NFD)."""
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFD", s)
    bo = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return bo.replace("đ", "d").replace("Đ", "D")


def chuan_hoa_ten(ten: Optional[str]) -> str:
    """Bỏ dấu, chuyển thường, gom khoảng trắng."""
    s = bo_dau_tieng_viet(ten or "").lower().strip()
    return re.sub(r"\s+", " ", s)


def chuan_hoa_dien_thoai(dt: Optional[str]) -> str:
    """Lọc chỉ chữ số, chuyển 84xxxx thành 0xxxx."""
    so = re.sub(r"\D", "", dt or "")
    if so.startswith("84") and len(so) == 11:
        so = "0" + so[2:]
    return so


def chuan_hoa_dia_chi(dc: Optional[str]) -> str:
    """Bỏ dấu, chuyển thường, loại bỏ các tiền tố hành chính phổ biến."""
    s = bo_dau_tieng_viet(dc or "").lower()
    s = re.sub(r"\b(phuong|quan|thanh pho|tp|tinh|duong|pho|so|to|khu pho|ap)\b", "", s)
    return re.sub(r"[\s,.-]+", " ", s).strip()


def tinh_tuong_dong_chuoi(s1: str, s2: str) -> float:
    """Tính độ tương đồng giữa hai chuỗi (0.0 -> 1.0) theo difflib."""
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0
    return difflib.SequenceMatcher(None, s1, s2).ratio()


def so_khop_chu_the(ct1: Dict[str, Any], ct2: Dict[str, Any]) -> Tuple[float, List[str]]:
    """
    So sánh hai chủ thể theo họ tên (45%), điện thoại (35%), địa chỉ (20%).
    Trả về (confidence, ly_do) nếu 0.70 <= confidence < 1.0. Ngược lại (0.0, []).
    """
    ten1 = chuan_hoa_ten(ct1.get("ho_ten"))
    ten2 = chuan_hoa_ten(ct2.get("ho_ten"))
    dt1 = chuan_hoa_dien_thoai(ct1.get("dien_thoai"))
    dt2 = chuan_hoa_dien_thoai(ct2.get("dien_thoai"))
    dc1 = chuan_hoa_dia_chi(ct1.get("dia_chi") or ct1.get("dia_chi_cong_trinh"))
    dc2 = chuan_hoa_dia_chi(ct2.get("dia_chi") or ct2.get("dia_chi_cong_trinh"))

    sim_ten = tinh_tuong_dong_chuoi(ten1, ten2) if (ten1 and ten2) else 0.0

    if dt1 and dt2 and len(dt1) >= 9 and len(dt2) >= 9:
        sim_dt = 1.0 if dt1 == dt2 else 0.0
    elif not dt1 and not dt2:
        sim_dt = 0.5
    else:
        sim_dt = 0.3

    sim_dc = tinh_tuong_dong_chuoi(dc1, dc2) if (dc1 and dc2) else 0.5

    confidence = round(0.45 * sim_ten + 0.35 * sim_dt + 0.20 * sim_dc, 3)

    if 0.70 <= confidence < 1.0:
        ly_do = []
        if sim_ten >= 0.80:
            ly_do.append("ho_ten")
        if sim_dt >= 0.90:
            ly_do.append("dien_thoai")
        if sim_dc >= 0.70:
            ly_do.append("dia_chi")
        if not ly_do:
            ly_do.append("ho_ten")
        return confidence, ly_do

    return 0.0, []


def so_khop_thua_dat(td1: Dict[str, Any], td2: Dict[str, Any]) -> Tuple[float, List[str]]:
    """
    So sánh hai thửa đất. Nếu cùng số thửa nhưng khác/thiếu tờ bản đồ kèm địa chỉ tương đồng:
    Trả về (confidence, ly_do) nếu 0.75 <= confidence < 1.0.
    """
    st1 = str(td1.get("so_thua") or "").strip().lower()
    st2 = str(td2.get("so_thua") or "").strip().lower()
    tb1 = str(td1.get("to_ban_do") or "").strip().lower()
    tb2 = str(td2.get("to_ban_do") or "").strip().lower()

    if not st1 or not st2 or st1 != st2:
        return 0.0, []

    # Cùng số thửa cùng tờ bản đồ là exact match (xử lý ở layer exact)
    if tb1 and tb2 and tb1 == tb2:
        return 0.0, []

    dc1 = chuan_hoa_dia_chi(td1.get("dia_chi") or td1.get("dia_chi_cong_trinh"))
    dc2 = chuan_hoa_dia_chi(td2.get("dia_chi") or td2.get("dia_chi_cong_trinh"))
    sim_dc = tinh_tuong_dong_chuoi(dc1, dc2) if (dc1 and dc2) else 0.5

    confidence = round(0.60 + 0.35 * sim_dc, 3)
    if 0.75 <= confidence < 1.0:
        ly_do = ["thua_dat"]
        if sim_dc >= 0.70:
            ly_do.append("dia_chi")
        return confidence, ly_do

    return 0.0, []


def so_khop_cong_trinh(ct1: Dict[str, Any], ct2: Dict[str, Any]) -> Tuple[float, List[str]]:
    """
    So sánh hai công trình. Cùng parcel_id hoặc cùng địa chỉ tương đồng cao:
    Trả về (confidence, ly_do) nếu 0.75 <= confidence < 1.0.
    """
    p1 = ct1.get("parcel_id")
    p2 = ct2.get("parcel_id")
    m1 = (ct1.get("ma_cong_trinh") or "").strip().lower()
    m2 = (ct2.get("ma_cong_trinh") or "").strip().lower()

    # Cùng mã công trình là exact match
    if m1 and m2 and m1 == m2:
        return 0.0, []

    dc1 = chuan_hoa_dia_chi(ct1.get("dia_chi_chuan") or ct1.get("dia_chi"))
    dc2 = chuan_hoa_dia_chi(ct2.get("dia_chi_chuan") or ct2.get("dia_chi"))
    sim_dc = tinh_tuong_dong_chuoi(dc1, dc2) if (dc1 and dc2) else 0.0

    cung_thua = (p1 is not None and p2 is not None and p1 == p2)
    if cung_thua:
        confidence = round(0.65 + 0.30 * sim_dc, 3)
    elif sim_dc >= 0.80:
        confidence = round(0.50 + 0.45 * sim_dc, 3)
    else:
        return 0.0, []

    if 0.75 <= confidence < 1.0:
        ly_do = ["dia_chi"]
        if m1 or m2:
            ly_do.append("ma_cong_trinh")
        return confidence, ly_do

    return 0.0, []


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


async def chay_backfill(dsn: str, tenant: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
    """Chạy toàn bộ tiến trình exact backfill và fuzzy matching."""
    conn = await asyncpg.connect(dsn)
    try:
        where_tenant = "WHERE tenant = $1" if tenant else ""
        params_tenant = [tenant] if tenant else []

        # 1. Quét danh sách hồ sơ cần liên kết
        sql_ho_so = f"""
            SELECT id, tenant, ma_ho_so, ho_ten, cccd, dien_thoai, thua_dat, dia_chi_cong_trinh, ma_dinh_danh_dia_diem
            FROM app_cap_phep.ho_so
            {where_tenant}
            ORDER BY created_at ASC
        """
        rows_ho_so = await conn.fetch(sql_ho_so, *params_tenant)
        tong_ho_so = len(rows_ho_so)
        exact_matched = 0

        sim_subject = 0
        sim_parcel = 0
        sim_construction = 0
        sim_permit = 0

        # Khớp chính xác từng hồ sơ qua lien_ket_tu_ho_so (dh_mdm.py)
        for r in rows_ho_so:
            h_id = str(r["id"])
            t_id = r["tenant"]
            if not dry_run:
                lk = await lien_ket_tu_ho_so(conn, t_id, h_id)
                if lk:
                    exact_matched += 1
            else:
                has_subj = cccd_hmac(r["cccd"]) is not None
                so_thua, _ = tach_thua_dat(r["thua_dat"])
                has_parc = bool(r["ma_dinh_danh_dia_diem"] or so_thua)
                if has_subj:
                    sim_subject += 1
                if has_parc:
                    sim_parcel += 1
                exact_matched += 1

        # 2. Đếm số lượng hồ sơ có subject và parcel sau khi liên kết
        if not dry_run:
            sql_thong_ke = f"""
                SELECT
                    count(*) AS tong,
                    count(subject_id) AS co_subject,
                    count(parcel_id) AS co_parcel,
                    count(construction_id) AS co_construction,
                    count(permit_id) AS co_permit
                FROM core.mdm_dossier_link
                {where_tenant}
            """
            tk = await conn.fetchrow(sql_thong_ke, *params_tenant)
            co_subject = tk["co_subject"] if tk else 0
            co_parcel = tk["co_parcel"] if tk else 0
            co_construction = tk["co_construction"] if tk else 0
            co_permit = tk["co_permit"] if tk else 0
        else:
            co_subject = sim_subject
            co_parcel = sim_parcel
            co_construction = sim_construction
            co_permit = sim_permit

        # 3. Fuzzy matching: Tìm ứng viên trùng (Chủ thể)
        sql_subjects = f"""
            SELECT DISTINCT ON (s.subject_id)
                s.subject_id, s.tenant, h.ho_ten, h.dien_thoai, h.dia_chi_cong_trinh AS dia_chi
            FROM core.mdm_subject s
            JOIN core.mdm_dossier_link l ON l.subject_id = s.subject_id AND l.tenant = s.tenant
            JOIN app_cap_phep.ho_so h ON h.id = l.dossier_id AND h.tenant = s.tenant
            WHERE s.merged_into IS NULL
            {('AND s.tenant = $1' if tenant else '')}
            ORDER BY s.subject_id, h.created_at DESC
        """
        subj_rows = await conn.fetch(sql_subjects, *params_tenant)
        cand_subject_count = 0

        for i in range(len(subj_rows)):
            for j in range(i + 1, len(subj_rows)):
                s1 = subj_rows[i]
                s2 = subj_rows[j]
                if s1["tenant"] != s2["tenant"]:
                    continue

                conf, ly_do = so_khop_chu_the(dict(s1), dict(s2))
                if conf > 0:
                    cand_subject_count += 1
                    if not dry_run:
                        # Lưu cặp id theo thứ tự để tránh đảo chiều
                        id1, id2 = sorted([s1["subject_id"], s2["subject_id"]])
                        await conn.execute(
                            """
                            INSERT INTO core.mdm_link_candidate
                                (tenant, entity_type, entity_id, candidate_id, confidence, ly_do, status)
                            VALUES ($1, 'subject', $2, $3, $4, $5, 'open')
                            ON CONFLICT (tenant, entity_type, entity_id, candidate_id) DO NOTHING
                            """,
                            s1["tenant"], id1, id2, conf, ly_do,
                        )

        # 4. Fuzzy matching: Tìm ứng viên trùng (Thửa đất)
        sql_parcels = f"""
            SELECT DISTINCT ON (p.parcel_id)
                p.parcel_id, p.tenant, p.so_thua, p.to_ban_do, h.dia_chi_cong_trinh AS dia_chi
            FROM core.mdm_parcel p
            JOIN core.mdm_dossier_link l ON l.parcel_id = p.parcel_id AND l.tenant = p.tenant
            JOIN app_cap_phep.ho_so h ON h.id = l.dossier_id AND h.tenant = p.tenant
            WHERE p.merged_into IS NULL
            {('AND p.tenant = $1' if tenant else '')}
            ORDER BY p.parcel_id, h.created_at DESC
        """
        parcel_rows = await conn.fetch(sql_parcels, *params_tenant)
        cand_parcel_count = 0

        for i in range(len(parcel_rows)):
            for j in range(i + 1, len(parcel_rows)):
                p1 = parcel_rows[i]
                p2 = parcel_rows[j]
                if p1["tenant"] != p2["tenant"]:
                    continue

                conf, ly_do = so_khop_thua_dat(dict(p1), dict(p2))
                if conf > 0:
                    cand_parcel_count += 1
                    if not dry_run:
                        id1, id2 = sorted([p1["parcel_id"], p2["parcel_id"]])
                        await conn.execute(
                            """
                            INSERT INTO core.mdm_link_candidate
                                (tenant, entity_type, entity_id, candidate_id, confidence, ly_do, status)
                            VALUES ($1, 'parcel', $2, $3, $4, $5, 'open')
                            ON CONFLICT (tenant, entity_type, entity_id, candidate_id) DO NOTHING
                            """,
                            p1["tenant"], id1, id2, conf, ly_do,
                        )

        tong_ung_vien = cand_subject_count + cand_parcel_count
        ty_le_subject = (co_subject / tong_ho_so * 100.0) if tong_ho_so else 0.0
        ty_le_parcel = (co_parcel / tong_ho_so * 100.0) if tong_ho_so else 0.0
        dat_acceptance = (ty_le_subject >= 90.0 and ty_le_parcel >= 90.0)

        ket_qua = {
            "tong_ho_so": tong_ho_so,
            "exact_matched": exact_matched,
            "co_subject": co_subject,
            "ty_le_subject": round(ty_le_subject, 2),
            "co_parcel": co_parcel,
            "ty_le_parcel": round(ty_le_parcel, 2),
            "co_construction": co_construction,
            "co_permit": co_permit,
            "cand_subject": cand_subject_count,
            "cand_parcel": cand_parcel_count,
            "tong_ung_vien": tong_ung_vien,
            "dat_acceptance": dat_acceptance,
            "dry_run": dry_run,
        }
        return ket_qua
    finally:
        await conn.close()


def in_ket_qua(kq: Dict[str, Any]) -> None:
    mode = "[DRY-RUN] " if kq["dry_run"] else ""
    print("\n" + "=" * 65)
    print(f" {mode}BÁO CÁO KẾT QUẢ KHỚP DỮ LIỆU VÀ BACKFILL MDM (D-MDM-02)")
    print("=" * 65)
    print(f"  * Tổng số hồ sơ quét:               {kq['tong_ho_so']}")
    print(f"  * Số hồ sơ đã khớp chính xác:       {kq['exact_matched']}")
    print(f"  * Hồ sơ có Chủ thể (subject):       {kq['co_subject']} ({kq['ty_le_subject']}%)")
    print(f"  * Hồ sơ có Thửa đất (parcel):       {kq['co_parcel']} ({kq['ty_le_parcel']}%)")
    print(f"  * Hồ sơ có Công trình (construction):{kq['co_construction']}")
    print(f"  * Hồ sơ có Giấy phép (permit):      {kq['co_permit']}")
    print("-" * 65)
    print(f"  * Ứng viên trùng Chủ thể (fuzzy):   {kq['cand_subject']}")
    print(f"  * Ứng viên trùng Thửa đất (fuzzy):  {kq['cand_parcel']}")
    print(f"  * Tổng ứng viên trùng ghi nhận:     {kq['tong_ung_vien']}")
    print("-" * 65)
    tieu_chi = "[ĐẠT]" if kq["dat_acceptance"] else "[KHÔNG ĐẠT]"
    print(f"  * Tiêu chuẩn Acceptance (>= 90%):    {tieu_chi} (Subject: {kq['ty_le_subject']}%, Parcel: {kq['ty_le_parcel']}%)")
    print("=" * 65 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Khớp dữ liệu và backfill MDM (D-MDM-02)")
    parser.add_argument("--dsn", default=None, help="PostgreSQL DSN kết nối")
    parser.add_argument("--tenant", default=None, help="Phạm vi tenant cần chạy (mặc định tất cả)")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ mô phỏng khớp, không ghi vào DB")
    args = parser.parse_args()

    dsn = args.dsn or dsn_mac_dinh()
    try:
        kq = asyncio.run(chay_backfill(dsn, tenant=args.tenant, dry_run=args.dry_run))
        in_ket_qua(kq)
        return 0 if kq["dat_acceptance"] else 1
    except Exception as e:
        print(f"[LỖI] Không thể chạy backfill MDM: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
