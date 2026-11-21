# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Chỉ số hiệu quả vận hành H — contracts/dh/automation.yaml (D-MART).

Cùng định nghĩa với scripts/dh_baseline.py: thao tác thủ công và tự phục vụ từ core.audit_log
(actor_type = user, object_type = ho_so), chuyển tay từ ho_so_lich_su, làm lại từ ho_so.bo_sung,
thời gian xử lý theo ngày làm việc từ nộp đến ngày cấp. Không có số nhập tay; thiếu dữ liệu thì null.
Mốc là bản đo mới nhất trong core.h_baseline (dh_baseline.py --save).
"""

import json
import statistics
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Header, Query

from dxos_core.db import get_db_connection
from dxos_core.jwt import verify_jwt_token

from construction.dh import VAI_CHI_SO_H, LoiDH, can_vai

router = APIRouter(prefix="/api/v1/automation", tags=["automation"])
GIO_VN = timezone(timedelta(hours=7))

CHI_SO = [
    ("thao_tac_thu_cong_tb", "Thao tác thủ công / hồ sơ", "", "lower", "core.audit_log"),
    ("chuyen_tay_tb", "Lần chuyển tay / hồ sơ", "", "lower", "app_cap_phep.ho_so_lich_su"),
    ("ty_le_ho_so_phai_bo_sung_pct", "Hồ sơ phải bổ sung", "%", "lower", "core.audit_log"),
    ("thoi_gian_xu_ly_tb_ngay_lam_viec", "Thời gian nộp → ký", "ngày làm việc", "lower", "app_cap_phep.giay_phep"),
    ("ty_le_ky_dung_han_pct", "Ký đúng hạn", "%", "higher", "app_cap_phep.giay_phep"),
    ("ty_le_tu_phuc_vu_pct", "Thao tác do chủ đầu tư tự làm", "%", "higher", "core.audit_log"),
    ("trich_xuat_tu_dong", "Trích xuất tự động (OCR)", "", "higher", "app_cap_phep.ocr_extractions"),
]

SQL = """
WITH hs AS (
    SELECT * FROM app_cap_phep.ho_so
    WHERE tenant = $3 AND ($1::timestamptz IS NULL OR created_at >= $1)
      AND ($2::timestamptz IS NULL OR created_at < $2)
),
tt AS (
    SELECT a.object_id, a.actor_sub, a.action FROM core.audit_log a
    WHERE a.tenant = $3 AND a.actor_type = 'user' AND a.actor_sub IS NOT NULL AND a.object_type = 'ho_so'
),
tt_hs AS (SELECT h.id, count(t.object_id) AS n FROM hs h LEFT JOIN tt t ON t.object_id = h.id::text GROUP BY h.id),
ls AS (
    SELECT l.ho_so_id, l.changed_by,
           lag(l.changed_by) OVER (PARTITION BY l.ho_so_id ORDER BY l.changed_at, l.id) AS truoc
    FROM app_cap_phep.ho_so_lich_su l JOIN hs ON hs.id = l.ho_so_id WHERE l.changed_by IS NOT NULL
),
chuyen AS (
    SELECT h.id, count(*) FILTER (WHERE ls.truoc IS NOT NULL AND ls.truoc <> ls.changed_by) AS n
    FROM hs h LEFT JOIN ls ON ls.ho_so_id = h.id GROUP BY h.id
),
bs AS (SELECT object_id FROM tt JOIN hs ON hs.id::text = tt.object_id WHERE action = 'ho_so.bo_sung' GROUP BY object_id),
cap AS (SELECT h.created_at, h.han_tong_at, g.ngay_cap FROM hs h JOIN app_cap_phep.giay_phep g ON g.ho_so_id = h.id)
SELECT json_build_object(
    'tong_ho_so', (SELECT count(*) FROM hs),
    'thao_tac', (SELECT coalesce(json_agg(n), '[]'::json) FROM tt_hs),
    'chuyen_tay', (SELECT coalesce(json_agg(n), '[]'::json) FROM chuyen),
    'thao_tac_chu_dau_tu', (SELECT count(*) FROM tt JOIN hs ON hs.id::text = tt.object_id WHERE tt.actor_sub = hs.chu_dau_tu_sub),
    'thao_tac_nguoi_dung', (SELECT count(*) FROM tt JOIN hs ON hs.id::text = tt.object_id),
    'ho_so_phai_bo_sung', (SELECT count(*) FROM bs),
    'giay_phep', (SELECT count(*) FROM cap),
    'ky_dung_han', (SELECT count(*) FROM cap WHERE ngay_cap <= han_tong_at),
    'ngay_lam_viec', (SELECT coalesce(json_agg(app_cap_phep.so_ngay_lam_viec(created_at, ngay_cap)), '[]'::json) FROM cap)
)
"""


def _ngay(s: Optional[str], ten: str) -> Optional[date]:
    if s is None:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise LoiDH(400, "BAD_REQUEST", f"{ten} phải là ngày YYYY-MM-DD")


def _pct(a: int, b: int) -> Optional[float]:
    return round(100.0 * a / b, 1) if b else None


def tinh(raw: Dict[str, Any], so_ocr: Optional[int]) -> Dict[str, Optional[float]]:
    """Từ số đếm thô ra chỉ số (hàm thuần, cùng công thức dh_baseline.tinh)."""
    tong = int(raw.get("tong_ho_so") or 0)
    tt = [int(x) for x in raw.get("thao_tac") or []]
    ct = [int(x) for x in raw.get("chuyen_tay") or []]
    nlv = [int(x) for x in raw.get("ngay_lam_viec") or [] if x is not None]
    gp = int(raw.get("giay_phep") or 0)
    return {
        "thao_tac_thu_cong_tb": round(statistics.mean(tt), 2) if tt else None,
        "chuyen_tay_tb": round(statistics.mean(ct), 2) if ct else None,
        "ty_le_ho_so_phai_bo_sung_pct": _pct(int(raw.get("ho_so_phai_bo_sung") or 0), tong),
        "thoi_gian_xu_ly_tb_ngay_lam_viec": round(sum(nlv) / len(nlv), 1) if nlv else None,
        "ty_le_ky_dung_han_pct": _pct(int(raw.get("ky_dung_han") or 0), gp),
        "ty_le_tu_phuc_vu_pct": _pct(int(raw.get("thao_tac_chu_dau_tu") or 0), int(raw.get("thao_tac_nguoi_dung") or 0)),
        "trich_xuat_tu_dong": so_ocr,
    }


def chenh_lech(hien_tai: Optional[float], moc: Optional[float]) -> Optional[float]:
    if hien_tai is None or moc in (None, 0):
        return None
    return round((hien_tai - moc) / moc * 100.0, 1)


async def _chi_so(claims, tu: Optional[date], den: Optional[date]) -> Dict[str, Any]:
    if tu and den and tu > den:
        raise LoiDH(400, "BAD_REQUEST", "from phải trước hoặc bằng to")
    dau = datetime.combine(tu, time.min, GIO_VN) if tu else None
    cuoi = datetime.combine(den + timedelta(days=1), time.min, GIO_VN) if den else None
    ghi_chu: List[str] = []
    # Số đếm tổng hợp đọc cả bảng lịch sử mà web_user không có quyền: chạy bằng kết nối dịch vụ,
    # lọc đúng phường trong token (vai đã kiểm ở trên), chỉ trả số đếm.
    tenant = claims.tenant
    async with get_db_connection() as conn:
        raw = await conn.fetchval(SQL, dau, cuoi, tenant)
        raw = json.loads(raw) if isinstance(raw, str) else raw
        so_ocr: Optional[int] = 0
        if await conn.fetchval("SELECT to_regclass('app_cap_phep.ocr_extractions')") is not None:
            so_ocr = int(await conn.fetchval(
                "SELECT count(*) FROM app_cap_phep.ocr_extractions WHERE tenant = $3 AND status = 'confirmed' "
                "AND ($1::timestamptz IS NULL OR created_at >= $1) AND ($2::timestamptz IS NULL OR created_at < $2)",
                dau, cuoi, tenant,
            ) or 0)
        else:
            ghi_chu.append("Chưa có OCR nên trích xuất tự động là 0.")
        moc = await conn.fetchrow(
            "SELECT label, metrics FROM core.h_baseline WHERE tenant = $1 ORDER BY measured_at DESC LIMIT 1", tenant,
        )
    hien_tai = tinh(raw, so_ocr)
    so_moc = (json.loads(moc["metrics"]) if isinstance(moc["metrics"], str) else moc["metrics"]) if moc else {}
    if not moc:
        ghi_chu.append("Chưa lưu mốc v1.1 (chạy scripts/dh_baseline.py --save) nên baseline là null.")
    return {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "period": {"from": tu.isoformat() if tu else None, "to": den.isoformat() if den else None},
        "baseline_label": moc["label"] if moc else None,
        "so_ho_so": int(raw.get("tong_ho_so") or 0),
        "metrics": [
            {"key": k, "label": nhan, "unit": dv, "better": tot, "baseline": so_moc.get(k), "current": hien_tai[k],
             "delta_pct": chenh_lech(hien_tai[k], so_moc.get(k)), "source": nguon}
            for k, nhan, dv, tot, nguon in CHI_SO
        ],
        "ghi_chu": ghi_chu,
    }


@router.get("/metrics")
async def chi_so_hieu_qua(
    tu: Annotated[Optional[str], Query(alias="from")] = None,
    den: Annotated[Optional[str], Query(alias="to")] = None,
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_CHI_SO_H, "Chỉ lãnh đạo, quản trị phường hoặc kiểm toán viên xem chỉ số này")
    return await _chi_so(claims, _ngay(tu, "from"), _ngay(den, "to"))
