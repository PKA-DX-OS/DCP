# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Phả hệ dữ liệu — contracts/dh/lineage.yaml (D-CAT-02).

Đọc core.lineage_events (OpenLineage tối giản). Sự kiện của một thực thể tìm theo
facets.entity = {"type", "id"}; chỉ sự kiện của phường người gọi (facets.tenant).
"""

import json
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Header, Query

from dxos_core.db import get_db_connection
from dxos_core.jwt import verify_jwt_token

from construction.dh import VAI_DOC_DH, LoiDH, can_vai

router = APIRouter(prefix="/api/v1/lineage", tags=["lineage"])

NGUON_THUC_THE = {
    "ho_so": "SELECT id FROM app_cap_phep.ho_so WHERE id = $1 AND tenant = core.jwt_tenant()",
    "giay_phep": "SELECT id FROM app_cap_phep.giay_phep WHERE id = $1 AND tenant = core.jwt_tenant()",
    "cong_trinh": "SELECT id FROM app_cap_phep.cong_trinh WHERE id = $1 AND tenant = core.jwt_tenant()",
}


def _json(v: Any) -> Any:
    return json.loads(v) if isinstance(v, str) else v


def _ten_tap(ds: Dict[str, Any]) -> str:
    return ".".join(x for x in (ds.get("namespace"), ds.get("name")) if x) or json.dumps(ds, sort_keys=True)


def do_thi(entity_type: str, entity_id: str, su_kien: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Nút (thực thể, job, tập dữ liệu) và cạnh vào → job → ra từ danh sách sự kiện (hàm thuần)."""
    goc = f"entity:{entity_type}:{entity_id}"
    nut: Dict[str, Dict[str, str]] = {goc: {"id": goc, "kind": "entity", "name": f"{entity_type} {entity_id}"}}
    canh: List[Dict[str, Any]] = []
    for e in su_kien:
        job_id = f"job:{e['job']}"
        nut.setdefault(job_id, {"id": job_id, "kind": "job", "name": e["job"]})
        chung = {"job": e["job"], "run_id": e["run_id"], "event_time": e["event_time"]}
        canh.append({"from": goc, "to": job_id} | chung)
        for ds in _json(e["inputs"]) or []:
            ten = _ten_tap(ds)
            nut.setdefault(f"dataset:{ten}", {"id": f"dataset:{ten}", "kind": "dataset", "name": ten})
            canh.append({"from": f"dataset:{ten}", "to": job_id} | chung)
        for ds in _json(e["outputs"]) or []:
            ten = _ten_tap(ds)
            nut.setdefault(f"dataset:{ten}", {"id": f"dataset:{ten}", "kind": "dataset", "name": ten})
            canh.append({"from": job_id, "to": f"dataset:{ten}"} | chung)
    return {"entity_type": entity_type, "id": entity_id, "nodes": list(nut.values()), "edges": canh}


@router.get("/jobs/{job}")
async def lich_su_job(job: str, limit: int = Query(default=50, ge=1, le=200), authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_DOC_DH)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT id, event_time, job, run_id, inputs, outputs, facets FROM core.lineage_events
            WHERE job = $1 AND (facets ->> 'tenant' IS NULL OR facets ->> 'tenant' = core.jwt_tenant())
            ORDER BY event_time DESC LIMIT $2
            """,
            job, limit,
        )
    return [dict(r) | {"inputs": _json(r["inputs"]), "outputs": _json(r["outputs"]), "facets": _json(r["facets"])}
            for r in rows]


@router.get("/{entity_type}/{entity_id}")
async def pha_he_thuc_the(entity_type: str, entity_id: str, depth: int = Query(default=2, ge=1, le=5),
                          authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_DOC_DH)
    if entity_type not in NGUON_THUC_THE:
        raise LoiDH(400, "BAD_REQUEST", "entity_type phải là ho_so, giay_phep hoặc cong_trinh")
    try:
        eid = UUID(entity_id)
    except ValueError:
        raise LoiDH(400, "BAD_REQUEST", "id không phải UUID")
    async with get_db_connection(claims) as conn:
        if await conn.fetchval(NGUON_THUC_THE[entity_type], eid) is None:
            raise LoiDH(404, "LINEAGE_NOT_FOUND", "Không có thực thể này trong phường của bạn")
        rows = await conn.fetch(
            """
            SELECT event_time, job, run_id, inputs, outputs FROM core.lineage_events
            WHERE facets -> 'entity' ->> 'type' = $1 AND facets -> 'entity' ->> 'id' = $2
              AND (facets ->> 'tenant' IS NULL OR facets ->> 'tenant' = core.jwt_tenant())
            ORDER BY event_time DESC LIMIT $3
            """,
            entity_type, str(eid), 20 * depth,
        )
    return do_thi(entity_type, str(eid), [dict(r) for r in rows])
