# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Danh mục dữ liệu và hợp đồng dữ liệu — contracts/dh/catalog.yaml (D-CAT-01). Chỉ đọc."""

import json
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header

from dxos_core.db import get_db_connection
from dxos_core.jwt import verify_jwt_token

from construction.dh import VAI_DANH_MUC, LoiDH, can_vai

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])

PHAN_LOAI = ("public", "internal", "pii", "sensitive")
TEN_TAI_SAN = re.compile(r"^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$")

SQL_TAI_SAN = """
    SELECT a.asset, a.domain, a.description, a.owner, a.steward, a.classification, a.retention,
           a.freshness_sla, a.updated_at AS last_updated, a.version
    FROM core.data_assets a
"""


def _json(v: Any) -> Any:
    return json.loads(v) if isinstance(v, str) else v


async def _diem_dq(conn) -> Dict[str, Optional[float]]:
    """Điểm DQ của lần chạy gần nhất theo bảng nguồn của rule (entity_type ứng với tên bảng)."""
    try:
        async with conn.transaction():
            rows = await conn.fetch(
                """
                SELECT r.entity_type, round(100.0 * (sum(k.total) - sum(k.failed)) / NULLIF(sum(k.total), 0), 1) AS diem
                FROM core.data_quality_results k JOIN core.data_quality_rules r ON r.code = k.rule_code
                WHERE k.tenant = core.jwt_tenant()
                  AND k.run_id = (SELECT id FROM core.data_quality_runs WHERE status IN ('succeeded', 'partial')
                                  ORDER BY started_at DESC LIMIT 1)
                GROUP BY r.entity_type
                """
            )
    except Exception:
        return {}
    return {r["entity_type"]: float(r["diem"]) if r["diem"] is not None else None for r in rows}


def _tai_san(r, diem: Dict[str, Optional[float]]) -> Dict[str, Any]:
    d = dict(r)
    d["dq_score"] = diem.get(d["asset"].split(".", 1)[1])
    return d


@router.get("/assets")
async def ds_tai_san(domain: Optional[str] = None, classification: Optional[str] = None, owner: Optional[str] = None,
                     authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_DANH_MUC)
    if classification is not None and classification not in PHAN_LOAI:
        raise LoiDH(400, "BAD_REQUEST", "classification không hợp lệ")
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            SQL_TAI_SAN + """
            WHERE ($1::text IS NULL OR a.domain = $1) AND ($2::text IS NULL OR a.classification = $2)
              AND ($3::text IS NULL OR a.owner = $3)
            ORDER BY a.domain, a.asset""",
            domain, classification, owner,
        )
        diem = await _diem_dq(conn)
    return [_tai_san(r, diem) for r in rows]


@router.get("/assets/{asset}")
async def lay_tai_san(asset: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_DANH_MUC)
    if not TEN_TAI_SAN.fullmatch(asset):
        raise LoiDH(400, "BAD_REQUEST", "Tên tài sản phải dạng schema.bảng")
    schema, bang = asset.split(".", 1)
    async with get_db_connection(claims) as conn:
        r = await conn.fetchrow(SQL_TAI_SAN + " WHERE a.asset = $1", asset)
        if r is None:
            raise LoiDH(404, "CATALOG_NOT_FOUND", "Không có tài sản này trong danh mục")
        khai_bao = {c["name"]: c for c in await conn.fetch(
            "SELECT name, classification, description, masked_in_api FROM core.data_asset_columns WHERE asset = $1", asset,
        )}
        # Cột thật của bảng; cột chưa khai báo nhận phân loại của tài sản (internal nếu tài sản là public)
        cot = await conn.fetch(
            """
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2 ORDER BY ordinal_position
            """,
            schema, bang,
        )
        diem = await _diem_dq(conn)
    mac_dinh = "internal" if r["classification"] == "public" else r["classification"]
    columns = []
    for c in cot:
        kb = khai_bao.get(c["column_name"])
        columns.append({"name": c["column_name"], "type": c["data_type"],
                        "classification": kb["classification"] if kb else mac_dinh,
                        "description": kb["description"] if kb else None,
                        "masked_in_api": bool(kb["masked_in_api"]) if kb else False})
    if not columns:  # bảng chưa cài hoặc người gọi không thấy information_schema của bảng
        columns = [{"name": n, "type": "unknown", "classification": k["classification"], "description": k["description"],
                    "masked_in_api": bool(k["masked_in_api"])} for n, k in khai_bao.items()]
    return _tai_san(r, diem) | {"columns": columns}


@router.get("/contracts")
async def ds_hop_dong(asset: Optional[str] = None, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_DANH_MUC)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT asset, version, json_schema, sla, consumers, effective_from FROM core.data_contracts
            WHERE ($1::text IS NULL OR asset = $1) ORDER BY asset, effective_from DESC, version DESC
            """,
            asset,
        )
    return [dict(r) | {"json_schema": _json(r["json_schema"]), "sla": _json(r["sla"]), "consumers": list(r["consumers"])}
            for r in rows]
