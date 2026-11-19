# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
API thực thể NGSI-LD đọc trạng thái công trình từ core.entity_state (C03).

- GET /api/v1/ngsi-ld/v1/entities?type=...&limit=&offset=  : danh sách thực thể
- GET /api/v1/ngsi-ld/v1/entities/{entity_id}              : một thực thể, 404 nếu không có

Cách ly: truy vấn lọc theo tenant của token; RLS web_user cũng áp dụng.
"""

import json
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException, Query, status

from dxos_core.middleware import setup_standard_service
from dxos_core.jwt import verify_jwt_token
from dxos_core.db import get_db_connection

app = FastAPI(title="DX-OS NGSI-LD Service", version="1.0.0")
setup_standard_service(app, "ngsi-ld")

NGSI_LD_CONTEXT = "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"
BASE_PATH = "/api/v1/ngsi-ld/v1/entities"
MAX_LIMIT = 100
RESERVED_KEYS = {"id", "type", "@context"}


def _to_ngsi(row) -> Dict[str, Any]:
    attrs = row["attrs"]
    if isinstance(attrs, str):
        attrs = json.loads(attrs)

    body: Dict[str, Any] = {
        "id": row["entity_id"],
        "type": row["entity_type"],
        "modifiedAt": row["updated_at"].isoformat(),
    }
    for key, value in (attrs or {}).items():
        if key in RESERVED_KEYS:
            continue
        body[key] = {"type": "Property", "value": value}
    body["@context"] = [NGSI_LD_CONTEXT]
    return body


@app.get(BASE_PATH)
async def list_entities(
    authorization: str = Header(...),
    entity_type: Optional[str] = Query(None, alias="type", min_length=1, max_length=64),
    limit: int = Query(50, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> List[Dict[str, Any]]:
    claims = verify_jwt_token(authorization)

    sql = """
        SELECT entity_id, entity_type, attrs, updated_at
        FROM core.entity_state
        WHERE tenant = $1
          AND ($2::text IS NULL OR entity_type = $2)
        ORDER BY entity_id
        LIMIT $3 OFFSET $4
    """
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(sql, claims.tenant, entity_type, limit, offset)

    return [_to_ngsi(row) for row in rows]


@app.get(BASE_PATH + "/{entity_id}")
async def get_entity(entity_id: str, authorization: str = Header(...)) -> Dict[str, Any]:
    claims = verify_jwt_token(authorization)

    sql = """
        SELECT entity_id, entity_type, attrs, updated_at
        FROM core.entity_state
        WHERE tenant = $1 AND entity_id = $2
    """
    async with get_db_connection(claims) as conn:
        row = await conn.fetchrow(sql, claims.tenant, entity_id)

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"loi": "Không tìm thấy thực thể trong địa bàn của bạn"},
        )
    return _to_ngsi(row)