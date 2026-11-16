# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml
from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel
from dxos_core.middleware import setup_standard_service
from dxos_core.jwt import verify_jwt_token
from dxos_core.db import get_db_connection
from dxos_core.outbox import emit_outbox_event
from dxos_core.audit import log_audit_event
from dxos_core.lineage import record_lineage_event

logger = logging.getLogger("dxos-ingest")

app = FastAPI(title="DX-OS IoT Data Ingestion Service", version="1.0.0")
setup_standard_service(app, "ingest")

_CACHED_RULES: Dict[str, Any] = {}

try:
    import zoneinfo
    VN_TZ = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:
    VN_TZ = timezone(timedelta(hours=7))


class SensorReading(BaseModel):
    tenant: str
    site_id: str
    device_id: str
    ts: Optional[str] = None
    metrics: Dict[str, float]  # e.g. {"laeq_dba": 78.5, "pm10": 45.0, "pm25": 22.0}


def load_rules() -> Dict[str, Any]:
    global _CACHED_RULES
    if _CACHED_RULES:
        return _CACHED_RULES
    rule_paths = list(Path("apps").glob("*/rules/*.yaml"))
    for p in rule_paths:
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            if data and "rules" in data:
                _CACHED_RULES.update(data["rules"])
        except Exception as e:
            logger.warning(f"Không thể nạp tệp quy tắc {p}: {e}")
    return _CACHED_RULES


def check_threshold_breach(metric: str, value: float, ts: datetime) -> Optional[Dict[str, Any]]:
    """
    Đánh giá vi phạm ngưỡng hoàn toàn dựa trên cấu hình khai báo trong apps/*/rules/*.yaml.
    Thời gian được quy đổi chính xác theo múi giờ Asia/Ho_Chi_Minh.
    """
    rules = load_rules()
    ts_vn = ts.astimezone(VN_TZ)
    hour = ts_vn.hour

    for _, rule in rules.items():
        if not isinstance(rule, dict) or rule.get("metric") != metric:
            continue

        unit = rule.get("unit", "")
        window_minutes = rule.get("window_minutes", 60)
        action = rule.get("action", {})
        trigger_process = action.get("trigger_process")
        alert_topic = action.get("alert_topic", "alert.threshold")

        # Trường hợp quy tắc có ngưỡng theo khung giờ (ví dụ tiếng ồn ngày/đêm)
        if "thresholds" in rule and isinstance(rule["thresholds"], dict):
            day_cfg = rule["thresholds"].get("day", {})
            night_cfg = rule["thresholds"].get("night", {})
            from_h = day_cfg.get("from_hour", 6)
            to_h = day_cfg.get("to_hour", 21)
            is_daytime = from_h <= hour < to_h
            active_cfg = day_cfg if is_daytime else night_cfg
            limit = active_cfg.get("limit")
            time_window = "day" if is_daytime else "night"
            if limit is not None and value > float(limit):
                return {
                    "metric": metric,
                    "value": value,
                    "threshold": float(limit),
                    "time_window": time_window,
                    "window_minutes": window_minutes,
                    "unit": unit,
                    "trigger_process": trigger_process,
                    "alert_topic": alert_topic,
                }

        # Trường hợp quy tắc có ngưỡng cố định (ví dụ bụi mịn PM10, PM2.5)
        elif "limit" in rule:
            limit = rule.get("limit")
            if limit is not None and value > float(limit):
                return {
                    "metric": metric,
                    "value": value,
                    "threshold": float(limit),
                    "time_window": f"{window_minutes}m",
                    "window_minutes": window_minutes,
                    "unit": unit,
                    "trigger_process": trigger_process,
                    "alert_topic": alert_topic,
                }

    return None


@app.post("/api/v1/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_sensor_data(
    reading: SensorReading,
    authorization: str = Header(...),
):
    """
    Nhận dữ liệu cảm biến IoT từ HTTP/Gateway, xác thực bắt buộc vai trò dx:device hoặc dx:service,
    kiểm tra chặt chẽ tính toàn vẹn đa thuê ước (tenant isolation), ghi vào core.timeseries,
    cập nhật core.entity_state và đánh giá ngưỡng cảnh báo theo quy tắc động.
    """
    claims = verify_jwt_token(authorization)
    allowed_roles = {"dx:device", "dx:service", "dx:platform-admin"}
    if not any(r in allowed_roles for r in claims.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Chỉ thiết bị cảm biến (dx:device) hoặc dịch vụ hệ thống mới được đẩy dữ liệu"},
        )

    tenant = claims.tenant
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Token xác thực không chứa thông tin tenant"},
        )

    # Chống giả mạo tenant (Z-05): nếu body chỉ định tenant khác claims -> từ chối 403 và ghi audit
    if reading.tenant and reading.tenant != tenant:
        await log_audit_event(
            tenant=tenant,
            action="ingest.tenant_mismatch",
            actor_sub=claims.sub,
            object_type="device",
            object_id=reading.device_id,
            detail={
                "claimed_tenant": tenant,
                "body_tenant": reading.tenant,
                "site_id": reading.site_id,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": f"Đơn vị (tenant) trong nội dung gửi ({reading.tenant}) không khớp với token ({tenant})"},
        )

    now = datetime.now(timezone.utc)
    ts = datetime.fromisoformat(reading.ts.replace("Z", "+00:00")) if reading.ts else now
    entity_id = f"urn:ngsi-ld:Site:{reading.site_id}"

    async with get_db_connection(claims) as conn:
        # 1. Ghi nhận chuỗi thời gian timeseries
        for metric_name, val in reading.metrics.items():
            await conn.execute(
                """
                INSERT INTO core.timeseries (tenant, entity_id, metric, ts, value)
                VALUES ($1, $2, $3, $4, $5)
                """,
                tenant,
                entity_id,
                metric_name,
                ts,
                float(val),
            )

        # 2. Cập nhật trạng thái thực thể entity_state
        state_attrs = {
            metric: {"type": "Property", "value": val, "observedAt": ts.isoformat()}
            for metric, val in reading.metrics.items()
        }
        state_attrs["device_id"] = {"type": "Property", "value": reading.device_id}
        state_attrs["status"] = {"type": "Property", "value": "ONLINE"}

        await conn.execute(
            """
            INSERT INTO core.entity_state (tenant, entity_id, entity_type, attrs, updated_at)
            VALUES ($1, $2, 'Site', $3::jsonb, $4)
            ON CONFLICT (tenant, entity_id)
            DO UPDATE SET attrs = core.entity_state.attrs || EXCLUDED.attrs, updated_at = EXCLUDED.updated_at
            """,
            tenant,
            entity_id,
            json.dumps(state_attrs, ensure_ascii=False),
            ts,
        )

    # 3. Đánh giá vượt ngưỡng động theo quy tắc và phát cảnh báo outbox
    alerts = []
    for metric_name, val in reading.metrics.items():
        breach = check_threshold_breach(metric_name, val, ts)
        if breach:
            alerts.append(breach)
            await emit_outbox_event(
                tenant=tenant,
                topic=breach.get("alert_topic", "alert.threshold"),
                payload={
                    "tenant": tenant,
                    "site_id": reading.site_id,
                    "device_id": reading.device_id,
                    "breach": breach,
                    "window_minutes": breach.get("window_minutes", 60),
                    "entity_id": entity_id,
                    "ts": ts.isoformat(),
                },
            )

    # 4. Ghi nhận phả hệ OpenLineage qua HTTP
    await record_lineage_event(
        job="iot_ingest",
        inputs=[{"name": f"http:api/v1/ingest/site/{reading.site_id}"}],
        outputs=[{"name": "core.timeseries"}, {"name": "core.entity_state"}],
        facets={"metrics_count": len(reading.metrics), "alerts_triggered": len(alerts)},
    )

    return {
        "status": "ingested",
        "tenant": tenant,
        "site_id": reading.site_id,
        "metrics_recorded": len(reading.metrics),
        "alerts": alerts,
    }


_FUNC_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$")


async def _demo_sensor_policies() -> List[Dict[str, Any]]:
    """Đọc cấu hình demo_sensor do các app khai báo trong flow_policies (vai được phép, hàm kiểm vị trí)."""
    result: List[Dict[str, Any]] = []
    async with get_db_connection() as conn:
        rows = await conn.fetch(
            "SELECT policy_data FROM core.app_policies WHERE policy_type = 'flow_policies'"
        )
    for row in rows:
        data = row["policy_data"]
        data = json.loads(data) if isinstance(data, str) else (data or {})
        cfg = data.get("demo_sensor")
        if isinstance(cfg, dict):
            result.append(cfg)
    return result


@app.post("/api/v1/ingest/demo-sensor")
async def demo_sensor_endpoint(
    req: Dict[str, Any],
    authorization: str = Header(...),
):
    """
    Phát một số đo mô phỏng phía máy chủ (chỉ khi DEMO_MODE=true).
    Vai được phép và hàm kiểm tra vị trí thuộc địa bàn do app khai báo (flow_policies.demo_sensor).
    Cảnh báo chỉ phát khi luật ngưỡng thật báo vượt; không tự tạo cảnh báo (U-04).
    """
    demo_mode = os.environ.get("DEMO_MODE", "false").lower() in ("true", "1", "yes")
    if not demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Chức năng mô phỏng chỉ hoạt động khi DEMO_MODE=true"},
        )

    claims = verify_jwt_token(authorization)
    tenant = claims.tenant
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"loi": "Token không chứa địa bàn hợp lệ"},
        )

    policies = await _demo_sensor_policies()
    allowed_roles = {"dx:platform-admin", "dx:tenant-admin"}
    for cfg in policies:
        allowed_roles.update(cfg.get("roles", []))
    if not any(r in allowed_roles for r in claims.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Bạn không có quyền phát số đo mô phỏng"},
        )

    target_site = str(req.get("site_id") or "").strip()
    if not target_site or len(target_site) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"loi": "Thiếu mã vị trí (site_id)"},
        )

    metric_name = str(req.get("metric") or "laeq_dba")
    raw_value = req.get("value", req.get(metric_name))
    try:
        metric_val = float(raw_value)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"loi": "Thiếu hoặc sai giá trị đo (value)"},
        )

    # Vị trí phải thuộc địa bàn của người gọi: hỏi hàm kiểm tra do app khai báo
    site_ok = False
    async with get_db_connection() as conn:
        for cfg in policies:
            fn = cfg.get("site_check")
            if not fn or not _FUNC_NAME_RE.fullmatch(fn):
                continue
            if await conn.fetchval(f"SELECT {fn}($1, $2)", target_site, tenant):
                site_ok = True
                break
    if not site_ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"loi": "Không tìm thấy vị trí này trong địa bàn của bạn"},
        )

    now = datetime.now(timezone.utc)
    entity_id = f"urn:ngsi-ld:Site:{target_site}"

    async with get_db_connection(claims) as conn:
        await conn.execute(
            """
            INSERT INTO core.timeseries (tenant, entity_id, metric, ts, value)
            VALUES ($1, $2, $3, $4, $5)
            """,
            tenant,
            entity_id,
            metric_name,
            now,
            metric_val,
        )

    breach = check_threshold_breach(metric_name, metric_val, now)
    if breach:
        await emit_outbox_event(
            tenant=tenant,
            topic=breach.get("alert_topic", "alert.threshold"),
            payload={
                "tenant": tenant,
                "site_id": target_site,
                "device_id": f"demo-sensor-{target_site}",
                "breach": breach,
                "window_minutes": breach.get("window_minutes", 60),
                "entity_id": entity_id,
                "ts": now.isoformat(),
            },
        )

    return {
        "status": "breach" if breach else "within_limit",
        "tenant": tenant,
        "site_id": target_site,
        "metric": metric_name,
        "value": metric_val,
        "breach": breach,
    }
