# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Chất lượng dữ liệu — contracts/dh/data-quality.yaml (D-DQ-03, D-DQ-04).

Rule khai báo trong core/postgres/22-data-quality.sql; scripts/data_quality_worker.py chạy rule.
API chỉ đọc điểm, rule, lần chạy, vấn đề và đổi trạng thái vấn đề (giao, đóng, bỏ qua).
"""

import json
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from dxos_core.audit import log_audit_event
from dxos_core.db import get_db_connection
from dxos_core.jwt import verify_jwt_token

from construction.dh import (
    VAI_DOC_DH, VAI_GIAO_DQ, VAI_QUAN_TRI_DU_LIEU, LoiDH, can_vai, co_vai, idempotent, kiem_khoa_idempotency, trang,
)

router = APIRouter(prefix="/api/v1/data-quality", tags=["data-quality"])

MIEN = ("cong_dan", "thua_dat", "ho_so", "giay_phep", "cong_trinh", "giay_to", "kiem_tra", "tai_chinh", "audit")
MUC_DO = ("info", "warn", "critical")
TRANG_THAI = ("open", "in_progress", "resolved", "ignored")


class GiaoVanDe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assigned_to: str = Field(min_length=1, max_length=200)
    note: Optional[str] = Field(default=None, max_length=1000)


class DongVanDe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(resolved|ignored)$")
    note: str = Field(min_length=3, max_length=1000)


def _kiem(gia_tri: Optional[str], hop_le: tuple, ten: str) -> None:
    if gia_tri is not None and gia_tri not in hop_le:
        raise LoiDH(400, "BAD_REQUEST", f"{ten} không hợp lệ")


def _van_de(r) -> Dict[str, Any]:
    return {k: r[k] for k in ("id", "rule_code", "domain", "entity_type", "entity_id", "field", "severity", "status",
                              "assigned_to", "note", "created_at", "resolved_at", "dossier_id")}


COT_VAN_DE = """
    SELECT i.id, i.rule_code, r.domain, i.entity_type, i.entity_id, i.field, i.severity, i.status,
           i.assigned_to, i.note, i.created_at, i.resolved_at, i.dossier_id
"""
SQL_VAN_DE = COT_VAN_DE + "FROM core.data_quality_issues i JOIN core.data_quality_rules r ON r.code = i.rule_code\n"
SQL_CHON_VAN_DE = COT_VAN_DE + "FROM i JOIN core.data_quality_rules r ON r.code = i.rule_code"


async def _lan_chay_moi_nhat(conn) -> Optional[Any]:
    return await conn.fetchrow(
        "SELECT id, finished_at FROM core.data_quality_runs WHERE status IN ('succeeded', 'partial') "
        "ORDER BY started_at DESC LIMIT 1"
    )


@router.get("/summary")
async def tong_quan(domain: Optional[str] = None, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_DOC_DH)
    _kiem(domain, MIEN, "domain")
    async with get_db_connection(claims) as conn:
        lan = await _lan_chay_moi_nhat(conn)
        rows = await conn.fetch(
            """
            SELECT r.domain, count(*) FILTER (WHERE r.enabled) AS rules,
                   count(*) FILTER (WHERE k.failed > 0) AS failed_rules,
                   sum(k.total) AS total, sum(k.failed) AS failed,
                   (SELECT count(*) FROM core.data_quality_issues i JOIN core.data_quality_rules r2 ON r2.code = i.rule_code
                    WHERE i.tenant = core.jwt_tenant() AND r2.domain = r.domain AND i.status IN ('open', 'in_progress')) AS open_issues
            FROM core.data_quality_rules r
            LEFT JOIN core.data_quality_results k
              ON k.rule_code = r.code AND k.run_id = $1 AND k.tenant = core.jwt_tenant()
            WHERE ($2::text IS NULL OR r.domain = $2)
            GROUP BY r.domain ORDER BY r.domain
            """,
            lan["id"] if lan else None, domain,
        )
    mien = []
    tong = loi = 0
    for r in rows:
        total, failed = int(r["total"] or 0), int(r["failed"] or 0)
        tong, loi = tong + total, loi + failed
        mien.append({"domain": r["domain"], "score": round(100.0 * (total - failed) / total, 1) if total else None,
                     "rules": int(r["rules"]), "failed_rules": int(r["failed_rules"]), "open_issues": int(r["open_issues"])})
    return {"run_id": lan["id"] if lan else None, "computed_at": lan["finished_at"] if lan else None,
            "overall_score": round(100.0 * (tong - loi) / tong, 1) if tong else None, "domains": mien}


@router.get("/rules")
async def ds_rule(domain: Optional[str] = None, severity: Optional[str] = None, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_DOC_DH)
    _kiem(domain, MIEN, "domain")
    _kiem(severity, MUC_DO, "severity")
    async with get_db_connection(claims) as conn:
        lan = await _lan_chay_moi_nhat(conn)
        rows = await conn.fetch(
            """
            SELECT r.code, r.domain, r.dimension, r.severity, r.description, r.owner, r.enabled,
                   k.total, k.failed
            FROM core.data_quality_rules r
            LEFT JOIN core.data_quality_results k ON k.rule_code = r.code AND k.run_id = $1 AND k.tenant = core.jwt_tenant()
            WHERE ($2::text IS NULL OR r.domain = $2) AND ($3::text IS NULL OR r.severity = $3)
            ORDER BY r.domain, r.code
            """,
            lan["id"] if lan else None, domain, severity,
        )
    return [
        {k: r[k] for k in ("code", "domain", "dimension", "severity", "description", "owner", "enabled")}
        | {"last_result": None if r["total"] is None else {
            "total": int(r["total"]), "failed": int(r["failed"]),
            "score": round(100.0 * (r["total"] - r["failed"]) / r["total"], 1) if r["total"] else 100.0}}
        for r in rows
    ]


@router.get("/runs")
async def ds_lan_chay(limit: int = Query(default=30, ge=1, le=100), authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_DOC_DH)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT r.id, r.started_at, r.finished_at, r.status, r.rule_errors,
                   (SELECT round(100.0 * (sum(total) - sum(failed)) / NULLIF(sum(total), 0), 1)
                    FROM core.data_quality_results k WHERE k.run_id = r.id AND k.tenant = core.jwt_tenant()) AS overall_score
            FROM core.data_quality_runs r ORDER BY r.started_at DESC LIMIT $1
            """,
            limit,
        )
    return [dict(r) | {"overall_score": float(r["overall_score"]) if r["overall_score"] is not None else None} for r in rows]


@router.get("/issues")
async def ds_van_de(
    domain: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    rule_code: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    assigned_to_me: bool = False,
    page: int = 1,
    page_size: int = 20,
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_DOC_DH)
    _kiem(domain, MIEN, "domain")
    _kiem(severity, MUC_DO, "severity")
    _kiem(status, TRANG_THAI, "status")
    page, page_size, offset = trang(page, page_size)
    loc = """
        WHERE i.tenant = core.jwt_tenant()
          AND ($1::text IS NULL OR r.domain = $1) AND ($2::text IS NULL OR i.severity = $2)
          AND ($3::text IS NULL OR i.status = $3) AND ($4::text IS NULL OR i.rule_code = $4)
          AND ($5::text IS NULL OR i.entity_type = $5)
          AND ($6::text IS NULL OR i.entity_id = $6 OR i.dossier_id::text = $6)
          AND (NOT $7 OR i.assigned_to = core.jwt_sub())
    """
    tham_so = [domain, severity, status, rule_code, entity_type, entity_id, assigned_to_me]
    async with get_db_connection(claims) as conn:
        tong = await conn.fetchval(
            "SELECT count(*) FROM core.data_quality_issues i JOIN core.data_quality_rules r ON r.code = i.rule_code " + loc,
            *tham_so,
        )
        rows = await conn.fetch(
            SQL_VAN_DE + loc + """
            ORDER BY CASE i.severity WHEN 'critical' THEN 0 WHEN 'warn' THEN 1 ELSE 2 END, i.created_at DESC
            LIMIT $8 OFFSET $9""",
            *tham_so, page_size, offset,
        )
    return {"items": [_van_de(r) for r in rows], "page": page, "page_size": page_size, "total": int(tong or 0)}


async def _lay_van_de(conn, issue_id: str):
    try:
        iid = UUID(issue_id)
    except ValueError:
        raise LoiDH(400, "BAD_REQUEST", "id không phải UUID")
    r = await conn.fetchrow(SQL_VAN_DE + " WHERE i.id = $1 AND i.tenant = core.jwt_tenant() FOR UPDATE OF i", iid)
    if r is None:
        raise LoiDH(404, "DQ_ISSUE_NOT_FOUND", "Không có vấn đề này trong phường của bạn")
    return iid, r


@router.post("/issues/{issue_id}/assign")
async def giao_van_de(issue_id: str, body: GiaoVanDe, authorization: str = Header(...),
                      idempotency_key: Optional[str] = Header(default=None)):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_GIAO_DQ, "Chỉ lãnh đạo, quản trị phường hoặc người quản lý dữ liệu được giao vấn đề")
    khoa = kiem_khoa_idempotency(idempotency_key)

    thong_bao = []
    assignee_info = {}
    async with get_db_connection(claims) as conn:
        async def lam():
            iid, r = await _lay_van_de(conn, issue_id)
            if r["status"] in ("resolved", "ignored"):
                raise LoiDH(409, "DQ_ISSUE_CLOSED", "Vấn đề đã đóng")
            nguoi_nhan = await conn.fetchrow(
                """
                SELECT id::text AS sub, username
                FROM core.users_directory
                WHERE (id::text = $1 OR username = $1)
                  AND tenant = core.jwt_tenant()
                  AND active
                LIMIT 1
                """,
                body.assigned_to,
            )
            if not nguoi_nhan:
                raise LoiDH(422, "DQ_ASSIGNEE_NOT_FOUND", "Không tìm thấy người nhận trong phường")
            assignee_sub = nguoi_nhan["sub"]
            assignee_info["sub"] = assignee_sub
            moi = await conn.fetchrow(
                "WITH i AS (UPDATE core.data_quality_issues SET status = 'in_progress', assigned_to = $2, "
                "note = COALESCE($3, note) WHERE id = $1 RETURNING *) " + SQL_CHON_VAN_DE,
                iid, assignee_sub, body.note,
            )
            thong_bao.append((f"Vấn đề {r['rule_code']} ({r['field'] or r['entity_type']}) cần xử lý.",
                              f"/?ho_so={r['dossier_id']}" if r["dossier_id"] else None))
            return 200, _van_de(moi)

        ma, kq = await idempotent(conn, claims, f"dq.assign.{issue_id}", khoa, lam)
    # web_user không ghi được core.notifications: gửi bằng kết nối dịch vụ, chỉ ở lần giao đầu (không phải gọi lại)
    target_sub = assignee_info.get("sub", body.assigned_to)
    for noi_dung, lien_ket in thong_bao:
        async with get_db_connection() as svc:
            await svc.execute(
                "INSERT INTO core.notifications (tenant, user_sub, title, body, link) VALUES ($1, $2, $3, $4, $5)",
                claims.tenant, target_sub, "Được giao xử lý vấn đề dữ liệu", noi_dung, lien_ket,
            )
    await log_audit_event(tenant=claims.tenant, action="dq.issue.assigned", actor_sub=claims.sub,
                          object_type="dq_issue", object_id=issue_id, detail={"assigned_to": target_sub})
    return JSONResponse(status_code=ma, content=kq)


@router.post("/issues/{issue_id}/resolve")
async def dong_van_de(issue_id: str, body: DongVanDe, authorization: str = Header(...),
                      idempotency_key: Optional[str] = Header(default=None)):
    claims = verify_jwt_token(authorization)
    can_vai(claims, VAI_DOC_DH)
    khoa = kiem_khoa_idempotency(idempotency_key)

    async with get_db_connection(claims) as conn:
        async def lam():
            iid, r = await _lay_van_de(conn, issue_id)
            if r["assigned_to"] != claims.sub and not co_vai(claims, VAI_QUAN_TRI_DU_LIEU):
                raise LoiDH(403, "FORBIDDEN", "Chỉ người được giao, quản trị phường hoặc người quản lý dữ liệu được đóng vấn đề")
            if r["status"] in ("resolved", "ignored"):
                raise LoiDH(409, "DQ_ISSUE_CLOSED", "Vấn đề đã đóng")
            moi = await conn.fetchrow(
                "WITH i AS (UPDATE core.data_quality_issues SET status = $2, note = $3, resolved_at = now() "
                "WHERE id = $1 RETURNING *) " + SQL_CHON_VAN_DE,
                iid, body.status, body.note,
            )
            await conn.execute(
                "INSERT INTO core.outbox (tenant, topic, payload) VALUES (core.jwt_tenant(), 'dq.issue.resolved', $1::jsonb)",
                json.dumps({"issue_id": issue_id, "status": body.status}),
            )
            return 200, _van_de(moi)

        ma, kq = await idempotent(conn, claims, f"dq.resolve.{issue_id}", khoa, lam)
    await log_audit_event(tenant=claims.tenant, action="dq.issue." + body.status, actor_sub=claims.sub,
                          object_type="dq_issue", object_id=issue_id, detail={})
    return JSONResponse(status_code=ma, content=kq)

