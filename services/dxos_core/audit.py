# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import hashlib
from typing import Dict, Any, Optional
from dxos_core.db import get_db_connection


def compute_audit_hash(
    prev_hash: bytes,
    tenant: str,
    actor_sub: Optional[str],
    actor_type: str,
    action: str,
    object_type: Optional[str],
    object_id: Optional[str],
    detail: Any
) -> bytes:
    """
    Tính mã băm SHA-256 của một bản ghi kiểm toán khớp chính xác với hàm SQL `core.record_audit`.
    """
    if isinstance(detail, str):
        detail_str = detail
    elif isinstance(detail, dict):
        detail_str = json.dumps(detail, separators=(',', ':'), ensure_ascii=False)
    else:
        detail_str = str(detail)

    data_str = (
        f"{tenant}|"
        f"{actor_sub or ''}|"
        f"{actor_type}|"
        f"{action}|"
        f"{object_type or ''}|"
        f"{object_id or ''}|"
        f"{detail_str}"
    )
    data_bytes = data_str.encode("utf-8")
    return hashlib.sha256(prev_hash + data_bytes).digest()


async def log_audit_event(
    tenant: str,
    action: str,
    actor_sub: Optional[str] = None,
    actor_type: str = "user",
    object_type: Optional[str] = None,
    object_id: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None
) -> int:
    """
    Ghi nhận một sự kiện vào chuỗi kiểm toán bất biến qua hàm SQL `core.record_audit`.
    """
    detail = detail or {}
    detail_json = json.dumps(detail, ensure_ascii=False)
    async with get_db_connection() as conn:
        audit_id = await conn.fetchval(
            """
            SELECT core.record_audit($1, $2, $3, $4, $5, $6, $7::jsonb)
            """,
            tenant,
            actor_sub,
            actor_type,
            action,
            object_type,
            object_id,
            detail_json,
        )
        return audit_id


async def verify_audit_chain(tenant: str) -> Dict[str, Any]:
    """
    Duyệt tuần tự chuỗi kiểm toán của tenant và xác minh tính hợp lệ của mã băm.
    Phát hiện chính xác ID của bản ghi đầu tiên bị sửa đổi hoặc chèn lén.
    """
    async with get_db_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, tenant, actor_sub, actor_type, action, object_type, object_id, detail::text AS detail_text, prev_hash, hash
            FROM core.audit_log
            WHERE tenant = $1
            ORDER BY id ASC
            """,
            tenant,
        )

    if not rows:
        return {"valid": True, "count": 0, "message": "Chưa có bản ghi kiểm toán nào."}

    initial_prev = b"\x00" * 32
    expected_prev = initial_prev

    for idx, row in enumerate(rows):
        cur_id = row["id"]
        row_prev = bytes(row["prev_hash"]) if row["prev_hash"] else initial_prev
        row_hash = bytes(row["hash"])

        # 1. Kiểm tra liên kết với bản ghi trước đó
        if row_prev != expected_prev:
            return {
                "valid": False,
                "tampered_id": cur_id,
                "reason": f"Liên kết đứt gãy tại bản ghi {cur_id}: prev_hash không khớp với bản ghi trước đó.",
                "index": idx,
            }

        # 2. Tính lại mã băm của bản ghi hiện tại
        expected_hash = compute_audit_hash(
            row_prev,
            row["tenant"],
            row["actor_sub"],
            row["actor_type"],
            row["action"],
            row["object_type"],
            row["object_id"],
            row["detail_text"],
        )

        # So khớp với mã băm lưu trữ
        if row_hash != expected_hash:
            return {
                "valid": False,
                "tampered_id": cur_id,
                "reason": f"Mã băm không khớp tại bản ghi {cur_id}! Dữ liệu nội dung đã bị can thiệp trái phép.",
                "index": idx,
            }

        expected_prev = row_hash

    return {
        "valid": True,
        "count": len(rows),
        "head_hash": rows[-1]["hash"].hex(),
        "last_id": rows[-1]["id"],
    }
