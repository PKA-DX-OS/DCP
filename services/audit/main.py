# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, status
from dxos_core.middleware import setup_standard_service
from dxos_core.jwt import verify_jwt_token
from dxos_core.audit import verify_audit_chain
from dxos_core.db import get_db_connection
from dxos_core.storage import storage_client

logger = logging.getLogger("dxos.audit")

app = FastAPI(title="DX-OS Audit Verification & WORM Seal Service", version="1.0.0")
setup_standard_service(app, "audit")


@app.on_event("startup")
async def startup_event():
    try:
        storage_client.ensure_buckets()
    except Exception as e:
        logger.warning(f"Chưa thể khởi tạo bucket S3 khi khởi động: {e}")


@app.get("/api/v1/audit/chain")
async def audit_chain(
    entity: Optional[str] = None,
    id: Optional[str] = None,
    limit: int = 200,
    authorization: str = Header(...),
):
    """Chuỗi kiểm toán theo đối tượng, kèm trạng thái xác minh toàn chuỗi của tenant (A-DATA-04)."""
    claims = verify_jwt_token(authorization)
    has_perm = any(r in claims.roles for r in ["dx:auditor", "dx:platform-admin", "dx:tenant-admin"])
    if not has_perm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Chỉ kiểm toán viên hoặc quản trị viên được xem chuỗi kiểm toán"},
        )
    limit = max(1, min(int(limit), 1000))
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT id, at, actor_sub, actor_type, action, object_type, object_id, detail,
                   prev_hash, hash
            FROM core.audit_log
            WHERE tenant = $1
              AND ($2::text IS NULL OR object_type = $2)
              AND ($3::text IS NULL OR object_id = $3)
            ORDER BY id
            LIMIT $4
            """,
            claims.tenant,
            entity,
            id,
            limit,
        )
    verification = await verify_audit_chain(claims.tenant)
    items = []
    for r in rows:
        items.append({
            "id": r["id"],
            "at": r["at"].isoformat() if r["at"] else None,
            "actor_sub": r["actor_sub"],
            "actor_type": r["actor_type"],
            "action": r["action"],
            "object_type": r["object_type"],
            "object_id": r["object_id"],
            "detail": r["detail"],
            "prev_hash": bytes(r["prev_hash"]).hex() if r["prev_hash"] else None,
            "hash": bytes(r["hash"]).hex() if r["hash"] else None,
        })
    return {
        "tenant": claims.tenant,
        "entity": entity,
        "object_id": id,
        "chain_valid": verification.get("valid", False),
        "head_hash": verification.get("head_hash"),
        "count": len(items),
        "items": items,
    }


@app.post("/api/v1/audit/verify")
async def verify_chain_post(authorization: str = Header(...)):
    """Alias POST cho kiểm toán viên/CI (A-DATA-04)."""
    claims = verify_jwt_token(authorization)
    has_perm = any(r in claims.roles for r in ["dx:auditor", "dx:platform-admin", "dx:tenant-admin"])
    if not has_perm:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"loi": "Không có quyền xác minh chuỗi kiểm toán"})
    return await verify_audit_chain(claims.tenant)


@app.get("/api/v1/audit/verify")
async def verify_chain_endpoint(
    authorization: str = Header(...),
):
    """
    Xác minh tính toàn vẹn của chuỗi băm kiểm toán (Audit Hash Chain).
    Dành cho kiểm toán viên (dx:auditor) hoặc quản trị viên hệ thống.
    """
    claims = verify_jwt_token(authorization)
    result = await verify_audit_chain(claims.tenant)
    return result


@app.post("/api/v1/audit/seal")
async def seal_audit_head(
    authorization: str = Header(...),
):
    """
    Niêm phong đỉnh chuỗi băm kiểm toán vào bucket WORM trên SeaweedFS và bảng core.audit_seal.
    """
    claims = verify_jwt_token(authorization)

    # 1. Kiểm tra vai trò kiểm toán / quản trị viên
    has_perm = any(r in claims.roles for r in ["dx:auditor", "dx:platform-admin", "admin", "dx:service"])
    if not has_perm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền niêm phong chuỗi kiểm toán",
        )

    # 2. Xác minh tính toàn vẹn chuỗi kiểm toán
    verification = await verify_audit_chain(claims.tenant)

    if not verification["valid"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"loi": "Không thể niêm phong chuỗi kiểm toán đang bị sai lệch!", "chi_tiet": verification},
        )

    last_id = verification.get("last_id", 0)
    head_hash = verification.get("head_hash") or ("00" * 32)
    now = datetime.now(timezone.utc)
    seal_key = f"{claims.tenant}/{now.strftime('%Y%m%d_%H%M%S')}_seal.json"

    seal_payload = json.dumps({
        "tenant": claims.tenant,
        "sealed_at": now.isoformat(),
        "last_audit_id": last_id,
        "head_hash": head_hash,
        "total_records": verification.get("count", 0),
    }, indent=2)

    try:
        storage_client.put_object("worm", seal_key, seal_payload.encode("utf-8"), "application/json")
    except Exception:
        storage_client.ensure_buckets()
        storage_client.put_object("worm", seal_key, seal_payload.encode("utf-8"), "application/json")

    async with get_db_connection(claims) as conn:
        await conn.execute(
            """
            INSERT INTO core.audit_seal (tenant, last_audit_id, head_hash, object_key)
            VALUES ($1, $2, decode($3, 'hex'), $4)
            """,
            claims.tenant,
            last_id,
            head_hash,
            seal_key,
        )

    return {
        "status": "sealed",
        "tenant": claims.tenant,
        "last_audit_id": last_id,
        "head_hash": head_hash,
        "object_key": seal_key,
    }
