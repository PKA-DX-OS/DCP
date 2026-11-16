# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import logging
from fastapi import FastAPI, Header
from dxos_core.middleware import setup_standard_service
from dxos_core.jwt import verify_jwt_token
from dxos_core.db import get_db_connection
from dxos_core.lineage import get_lineage_history

app = FastAPI(title="DX-OS Executive Metrics & Lineage API", version="1.0.0")
setup_standard_service(app, "metrics-api")
logger = logging.getLogger("metrics-api")


def _policy_data(raw) -> dict:
    """asyncpg trả cột jsonb dưới dạng chuỗi khi chưa đăng ký codec, nên cần tự giải mã."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


@app.get("/api/v1/metrics")
async def get_executive_metrics(
    authorization: str = Header(...),
):
    """
    Trả về 5 chỉ số điều hành then chốt của thuê ước (tenant) hiện tại.
    """
    claims = verify_jwt_token(authorization)
    tenant = claims.tenant

    async with get_db_connection(claims) as conn:
        # 1. Số lượt truy cập bị từ chối (403 / access.denied từ audit)
        denied_count = await conn.fetchval(
            """
            SELECT count(*)
            FROM core.audit_log
            WHERE tenant = $1 AND action = 'access.denied'
            """,
            tenant,
        )

        # 2. Số cảnh báo công trường vượt ngưỡng
        site_alerts_count = await conn.fetchval(
            """
            SELECT count(*)
            FROM core.outbox
            WHERE tenant = $1 AND topic = 'alert.threshold'
            """,
            tenant,
        )

        # 3. Nạp danh sách chỉ số từ core.app_policies (V3-07)
        app_metric_rows = await conn.fetch(
            """
            SELECT policy_key, policy_data
            FROM core.app_policies
            WHERE policy_type = 'metrics'
            ORDER BY id ASC
            """
        )
        metric_values = {}
        for r in app_metric_rows:
            data = _policy_data(r["policy_data"])
            m_code = data.get("code") or r["policy_key"]
            m_sql = data.get("sql")
            if m_sql:
                try:
                    # Savepoint riêng cho từng chỉ số: một câu lỗi không làm hỏng cả giao dịch
                    async with conn.transaction():
                        val = await conn.fetchval(m_sql, tenant)
                    metric_values[m_code] = val or 0
                except Exception as e:
                    logger.warning(f"Lỗi tính toán chỉ số {m_code}: {e}")
                    metric_values[m_code] = 0

        # Tỷ lệ đúng hạn được tính nếu có số liệu tổng và quá hạn
        val_total = None
        val_overdue = None
        for k, v in metric_values.items():
            if "moi" in k or "tong" in k:
                val_total = v
            elif "qua_han" in k:
                val_overdue = v
        if val_total is not None and val_total > 0 and val_overdue is not None:
            ty_le_dung_han = round(max(0.0, (1.0 - (val_overdue / val_total)) * 100.0), 1)
        else:
            ty_le_dung_han = 100.0

        metrics_list = []
        if app_metric_rows:
            for r in app_metric_rows:
                data = _policy_data(r["policy_data"])
                m_code = data.get("code") or r["policy_key"]
                if m_code in metric_values:
                    val = metric_values[m_code]
                elif "dung_han" in m_code or "rate" in m_code:
                    val = ty_le_dung_han
                elif m_code == "truy_cap_tu_choi":
                    val = denied_count or 0
                elif m_code == "canh_bao_cong_truong":
                    val = site_alerts_count or 0
                else:
                    val = 0
                metrics_list.append({
                    "code": m_code,
                    "name": data.get("name", m_code),
                    "value": val,
                    "unit": data.get("unit", ""),
                })
        else:
            metrics_list = [
                {"code": "truy_cap_tu_choi", "name": "Lượt truy cập bị từ chối (403)", "value": denied_count or 0, "unit": "lượt"},
                {"code": "canh_bao_cong_truong", "name": "Cảnh báo vượt ngưỡng", "value": site_alerts_count or 0, "unit": "lượt"},
            ]

    return {
        "tenant": tenant,
        "metrics": metrics_list,
    }


@app.get("/api/v1/metrics/{code}/lineage")
async def get_metric_lineage(
    code: str,
    authorization: str = Header(...),
):
    """
    Truy xuất chuỗi phả hệ OpenLineage hình thành nên chỉ số điều hành.
    """
    claims = verify_jwt_token(authorization)
    job_map = {
        "canh_bao_cong_truong": "iot_ingest",
        "truy_cap_tu_choi": "audit_verification",
    }
    job_name = job_map.get(code, "export_warm_lakehouse")
    events = await get_lineage_history(job_name, limit=10)

    # Chỉ trả sự kiện của địa bàn người gọi; chưa có sự kiện thật thì trả danh sách rỗng (không dựng dữ liệu mẫu)
    events = [
        e for e in events
        if not isinstance(e.get("facets"), dict) or e["facets"].get("tenant") in (None, claims.tenant)
    ]

    return {
        "metric_code": code,
        "job": job_name,
        "lineage_events": events,
    }
