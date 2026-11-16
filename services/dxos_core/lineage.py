# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import uuid
from typing import Dict, Any, List, Optional
from dxos_core.db import get_db_connection


async def record_lineage_event(
    job: str,
    inputs: List[Dict[str, Any]],
    outputs: List[Dict[str, Any]],
    run_id: Optional[str] = None,
    facets: Optional[Dict[str, Any]] = None
) -> str:
    """
    Ghi nhận một sự kiện phả hệ dữ liệu theo định dạng chuẩn OpenLineage.
    """
    run_id = run_id or str(uuid.uuid4())
    facets = facets or {}

    async with get_db_connection() as conn:
        event_id = await conn.fetchval(
            """
            INSERT INTO core.lineage_events (job, run_id, inputs, outputs, facets)
            VALUES ($1, $2, $3::jsonb, $4::jsonb, $5::jsonb)
            RETURNING id::text
            """,
            job,
            run_id,
            json.dumps(inputs, ensure_ascii=False),
            json.dumps(outputs, ensure_ascii=False),
            json.dumps(facets, ensure_ascii=False),
        )
        return event_id


async def get_lineage_history(job: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Lấy danh sách các sự kiện phả hệ của một job."""
    async with get_db_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, event_time, job, run_id, inputs, outputs, facets
            FROM core.lineage_events
            WHERE job = $1
            ORDER BY event_time DESC
            LIMIT $2
            """,
            job,
            limit,
        )
        return [
            {
                "id": str(r["id"]),
                "event_time": r["event_time"].isoformat(),
                "job": r["job"],
                "run_id": r["run_id"],
                "inputs": json.loads(r["inputs"]) if isinstance(r["inputs"], str) else r["inputs"],
                "outputs": json.loads(r["outputs"]) if isinstance(r["outputs"], str) else r["outputs"],
                "facets": json.loads(r["facets"]) if isinstance(r["facets"], str) else r["facets"],
            }
            for r in rows
        ]
