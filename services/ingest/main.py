# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Tiếp nhận telemetry bụi/tiếng ồn từ cảm biến (C02).

- POST /api/v1/ingest: xác thực JWT, kiểm tra vai dx:device và tenant khớp.
- Ghi 3 chỉ số vào core.timeseries (entity_id = device_id).
- Tạo cảnh báo khi ồn vượt ngưỡng ban ngày/ban đêm; ghi audit cho cảnh báo.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from dxos_core.middleware import setup_standard_service
from dxos_core.jwt import verify_jwt_token
from dxos_core.db import get_db_connection
from dxos_core.audit import log_audit_event

logger = logging.getLogger("dxos.ingest")

app = FastAPI(title="DX-OS Ingest Service", version="1.0.0")
setup_standard_service(app, "ingest")

ICT = timezone(timedelta(hours=7))
REQUIRED_METRICS = ("laeq_dba", "pm10", "pm25")

# Ngưỡng ồn (dBA). Đọc từ môi trường; giá trị mặc định cần nhóm trưởng xác nhận.
NOISE_DAY_MAX = float(os.getenv("INGEST_NOISE_DAY_MAX", "70"))
NOISE_NIGHT_MAX = float(os.getenv("INGEST_NOISE_NIGHT_MAX", "55"))


class SensorReading(BaseModel):
    tenant: str = Field(min_length=1, max_length=64)
    site_id: str = Field(min_length=1, max_length=64)
    device_id: str = Field(min_length=1, max_length=128)
    source: str = Field(default="sensor", max_length=32)
    ts: Optional[datetime] = None
    metrics: Dict[str, float]


def _noise_limit(local_hour: int) -> float:
    if local_hour >= 21 or local_hour < 6:
        return NOISE_NIGHT_MAX
    return NOISE_DAY_MAX


def _as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


@app.post("/api/v1/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_reading(
    payload: SensorReading,
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)

    if not (claims.has_role("dx:device") or claims.has_role("dx:service")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Token không có vai trò thiết bị"},
        )
    if claims.tenant != payload.tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Tenant trong token không khớp với tenant của bản tin"},
        )

    missing = [m for m in REQUIRED_METRICS if m not in payload.metrics]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"loi": f"Thiếu chỉ số: {', '.join(missing)}"},
        )

    ts_utc = _as_utc(payload.ts) if payload.ts else datetime.now(timezone.utc)
    local_hour = ts_utc.astimezone(ICT).hour

    rows = [
        (payload.tenant, payload.device_id, metric, ts_utc, float(payload.metrics[metric]))
        for metric in REQUIRED_METRICS
    ]

    # Không truyền claims: ghi bằng kết nối dịch vụ, tenant đã được kiểm tra ở trên.
    async with get_db_connection() as conn:
        await conn.executemany(
            """
            INSERT INTO core.timeseries (tenant, entity_id, metric, ts, value)
            VALUES ($1, $2, $3, $4, $5)
            """,
            rows,
        )

    limit = _noise_limit(local_hour)
    alerts: List[Dict] = []
    noise = float(payload.metrics["laeq_dba"])
    if noise > limit:
        alert = {
            "rule": "noise_threshold",
            "metric": "laeq_dba",
            "value": noise,
            "limit": limit,
            "site_id": payload.site_id,
            "device_id": payload.device_id,
            "ts": ts_utc.isoformat(),
        }
        alerts.append(alert)
        await log_audit_event(
            tenant=payload.tenant,
            action="ingest.alert",
            actor_sub=claims.sub,
            actor_type="device",
            object_type="sensor",
            object_id=payload.device_id,
            detail=alert,
        )

    return {"status": "accepted", "alerts": alerts}