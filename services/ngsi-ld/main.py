# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
from typing import Optional, List
from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel
from dxos_core.middleware import setup_standard_service
from dxos_core.jwt import verify_jwt_token
from dxos_core.db import get_db_connection

app = FastAPI(title="DX-OS NGSI-LD Context Entity Service", version="1.0.0")
setup_standard_service(app, "ngsi-ld")

NGSI_LD_CONTEXT = [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
    "https://raw.githubusercontent.com/smart-data-models/dataModel.Environment/master/context.jsonld",
]


class SubscriptionRequest(BaseModel):
    description: Optional[str] = None
    entities: List[dict]
    notification: dict


@app.get("/api/v1/ngsi-ld/v1/entities")
async def get_entities(
    type: Optional[str] = None,
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    async with get_db_connection(claims) as conn:
        if type:
            rows = await conn.fetch(
                """
                SELECT entity_id, entity_type, attrs, updated_at
                FROM core.entity_state
                WHERE tenant = $1 AND entity_type = $2
                """,
                claims.tenant,
                type,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT entity_id, entity_type, attrs, updated_at
                FROM core.entity_state
                WHERE tenant = $1
                """,
                claims.tenant,
            )

    results = []
    for r in rows:
        attrs = json.loads(r["attrs"]) if isinstance(r["attrs"], str) else r["attrs"]
        entity = {
            "id": r["entity_id"],
            "type": r["entity_type"],
            "@context": NGSI_LD_CONTEXT,
            **attrs,
        }
        results.append(entity)

    return results


@app.get("/api/v1/ngsi-ld/v1/entities/{entity_id:path}")
async def get_entity_by_id(
    entity_id: str,
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    async with get_db_connection(claims) as conn:
        row = await conn.fetchrow(
            """
            SELECT entity_id, entity_type, attrs, updated_at
            FROM core.entity_state
            WHERE tenant = $1 AND entity_id = $2
            """,
            claims.tenant,
            entity_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail={"loi": "Không tìm thấy thực thể NGSI-LD"})

    attrs = json.loads(row["attrs"]) if isinstance(row["attrs"], str) else row["attrs"]
    return {
        "id": row["entity_id"],
        "type": row["entity_type"],
        "@context": NGSI_LD_CONTEXT,
        **attrs,
    }


@app.post("/api/v1/ngsi-ld/v1/subscriptions", status_code=status.HTTP_201_CREATED)
async def create_subscription(
    req: SubscriptionRequest,
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    # Lưu thông tin đăng ký subscription nội bộ
    return {
        "id": f"urn:ngsi-ld:Subscription:{claims.tenant}:1",
        "type": "Subscription",
        "status": "active",
        "description": req.description,
    }
