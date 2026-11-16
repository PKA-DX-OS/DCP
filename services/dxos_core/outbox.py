# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
from typing import Dict, Any, Optional
import asyncpg
from dxos_core.db import get_db_connection


async def emit_outbox_event(
    tenant: str,
    topic: str,
    payload: Dict[str, Any],
    conn: Optional[asyncpg.Connection] = None
) -> int:
    """
    Ghi một sự kiện nghiệp vụ vào bảng `core.outbox` theo Transactional Outbox pattern.
    """
    payload_json = json.dumps(payload, ensure_ascii=False)
    query = """
        INSERT INTO core.outbox (tenant, topic, payload)
        VALUES ($1, $2, $3::jsonb)
        RETURNING id
    """
    if conn:
        return await conn.fetchval(query, tenant, topic, payload_json)
    else:
        async with get_db_connection() as c:
            return await c.fetchval(query, tenant, topic, payload_json)
