# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
API 8 chỉ số điều hành cho lãnh đạo và phả hệ dữ liệu (C04).

- GET /api/v1/metrics[?thang=YYYY-MM]      : các chỉ số của tenant trong token; chỉ số khai báo
                                             $2/$3 (đầu/cuối kỳ) được lọc theo tháng
- GET /api/v1/metrics/{code}/lineage       : phả hệ của một chỉ số

Danh sách chỉ số không nằm trong lõi: app khai báo ở khóa `metrics` của app.yaml,
app_manager nạp vào core.app_policies (policy_type = 'metrics', kèm `thu_tu`).
Mỗi chỉ số chạy trong savepoint riêng: một chỉ số lỗi chỉ ảnh hưởng chính nó.
Chỉ trả số liệu tổng hợp (đếm, trung bình), không trả dữ liệu chi tiết cá nhân.
Giá trị null nghĩa là chưa có mẫu để tính (ví dụ trung bình khi chưa có bản ghi).
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, Header, HTTPException, Query, status

from dxos_core.middleware import setup_standard_service
from dxos_core.jwt import verify_jwt_token
from dxos_core.db import get_db_connection
from dxos_core.lineage import get_lineage_history, get_lineage_by_sources
from dxos_core.xem_dia_ban import ngu_canh_tong_hop

app = FastAPI(title="DX-OS Executive Metrics & Lineage API", version="1.0.0")
setup_standard_service(app, "metrics-api")
logger = logging.getLogger("dxos.metrics")

POLICY_TYPE = "metrics"
ALLOWED_QUERY_TYPES = {"lakehouse", "transactional", "hybrid", "audit"}
REQUIRED_KEYS = ("code", "name", "unit", "query_type", "sql")
FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|grant|revoke|create|truncate|copy|call|do)\b",
    re.IGNORECASE,
)



def _policy_data(raw: Any) -> Dict[str, Any]:
    """asyncpg có thể trả jsonb dạng chuỗi, nên cần giải mã an toàn."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


def validate_metric_policy(policy: Dict[str, Any]) -> Optional[str]:
    """Trả về lỗi (chuỗi) nếu cấu hình không hợp lệ, None nếu hợp lệ."""
    missing = [k for k in REQUIRED_KEYS if not policy.get(k)]
    if missing:
        return f"thiếu trường: {', '.join(missing)}"
    if policy["query_type"] not in ALLOWED_QUERY_TYPES:
        return f"query_type không hợp lệ: {policy['query_type']}"
    sql = str(policy["sql"]).strip()
    if not sql.lower().startswith("select"):
        return "SQL phải là SELECT"
    if ";" in sql:
        return "SQL không được chứa dấu ;"
    if "$1" not in sql:
        return "SQL phải dùng $1 làm tham số tenant"
    if ("$2" in sql) != ("$3" in sql):
        return "SQL lọc kỳ phải dùng cả $2 (đầu kỳ) và $3 (cuối kỳ)"
    if re.search(r"\$[4-9]", sql):
        return "SQL chỉ được dùng tham số $1, $2, $3"
    if FORBIDDEN_SQL.search(sql):
        return "SQL chứa từ khóa không được phép"
    return None


GIO_VN = timezone(timedelta(hours=7))
THANG_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def ky_thang(thang: Optional[str]) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Đầu và cuối kỳ (nửa mở) của tháng YYYY-MM theo giờ Việt Nam; không truyền thì không lọc."""
    if not thang:
        return None, None
    m = THANG_RE.match(thang)
    if not m:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={"loi": "Tham số thang phải có dạng YYYY-MM", "ma_loi": "VALIDATION_ERROR"})
    nam, so_thang = int(m.group(1)), int(m.group(2))
    dau = datetime(nam, so_thang, 1, tzinfo=GIO_VN)
    cuoi = datetime(nam + (so_thang == 12), so_thang % 12 + 1, 1, tzinfo=GIO_VN)
    return dau, cuoi


async def _load_policies(conn) -> List[Dict[str, Any]]:
    """Chỉ số đã nạp, theo thứ tự app khai báo (thu_tu), rồi theo mã."""
    rows = await conn.fetch(
        """
        SELECT policy_key, policy_data
        FROM core.app_policies
        WHERE policy_type = $1
        """,
        POLICY_TYPE,
    )
    loaded: List[Dict[str, Any]] = []
    for r in rows:
        data = _policy_data(r["policy_data"])
        data.setdefault("code", r["policy_key"])
        loaded.append(data)
    loaded.sort(key=lambda d: (d.get("thu_tu") if isinstance(d.get("thu_tu"), int) else 10**6, str(d["code"])))
    return loaded


@app.get("/api/v1/metrics")
async def get_executive_metrics(
    tenant: Optional[str] = None,
    thang: Annotated[Optional[str], Query(description="Kỳ báo cáo YYYY-MM (giờ Việt Nam)")] = None,
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    dau_ky, cuoi_ky = ky_thang(thang)
    ctx = ngu_canh_tong_hop(claims, tenant)
    tenant = ctx.tenant
    computed_at = datetime.now(timezone.utc).isoformat()

    async with get_db_connection(ctx) as conn:
        policies = await _load_policies(conn)
        results: List[Dict[str, Any]] = []
        for policy in policies:
            code = policy["code"]
            problem = validate_metric_policy(policy)
            if problem:
                results.append({"code": code, "name": policy.get("name", code), "unit": policy.get("unit", ""),
                                "value": None, "error": f"cau_hinh_sai: {problem}"})
                continue
            try:
                # Savepoint riêng cho từng chỉ số: lỗi SQL không làm hỏng các chỉ số khác
                theo_ky = "$2" in str(policy["sql"])
                tham_so = (tenant, dau_ky, cuoi_ky) if theo_ky else (tenant,)
                async with conn.transaction():
                    value = await conn.fetchval(policy["sql"], *tham_so)
                results.append({"code": code, "name": policy["name"], "unit": policy["unit"],
                                "value": value, "theo_ky": theo_ky})
            except Exception as exc:
                logger.warning(f"Lỗi tính chỉ số {code}: {exc}")
                results.append({"code": code, "name": policy["name"], "unit": policy["unit"],
                                "value": None, "error": "loi_tinh_toan"})

    return {"tenant": tenant, "thang": thang, "computed_at": computed_at, "metrics": results}


@app.get("/api/v1/metrics/{code}/lineage")
async def get_metric_lineage(code: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    async with get_db_connection(claims) as conn:
        policies = await _load_policies(conn)
    policy = next((p for p in policies if p["code"] == code), None)
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"loi": "Không có chỉ số này"})

    job = policy.get("lineage_job")
    bang_nguon = policy.get("bang_nguon", [])

    if policy.get("query_type") == "lakehouse" and job:
        events = await get_lineage_history(job, limit=10)
        events = [
            e for e in events
            if not isinstance(e.get("facets"), dict) or e["facets"].get("tenant") in (None, claims.tenant)
        ]
    elif bang_nguon:
        events = await get_lineage_by_sources(bang_nguon, tenant=claims.tenant, limit=10)
    else:
        events = []

    return {
        "metric_code": code,
        "bang_nguon": bang_nguon,
        "dieu_kien_loc": policy.get("dieu_kien_loc", ""),
        "job": job or "",
        "lineage_events": events,
    }