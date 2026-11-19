# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-LEGAL-01: tra cứu văn bản pháp luật và trích dẫn điều/khoản."""

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query, status

from dxos_core.db import get_db_connection
from dxos_core.jwt import verify_jwt_token

from construction.deps import yeu_cau_can_bo

router = APIRouter(prefix="/api/v1/planning/legal", tags=["Pháp lý"])


def _row(r) -> dict:
    return dict(r)


@router.get("/documents")
async def danh_muc_van_ban(
    q: Optional[str] = Query(default=None, max_length=200),
    limit: int = Query(default=100, ge=1, le=200),
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        if q:
            rows = await conn.fetch(
                """
                SELECT document_id, code, title, doc_type, issuer, issued_date, effective_date,
                       status, status_detail, group_name, source_url, sha256, file_name, tags
                FROM app_construction.legal_refs
                WHERE code ILIKE $1 OR title ILIKE $1
                ORDER BY code
                LIMIT $2
                """,
                f"%{q}%",
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT document_id, code, title, doc_type, issuer, issued_date, effective_date,
                       status, status_detail, group_name, source_url, sha256, file_name, tags
                FROM app_construction.legal_refs
                ORDER BY code
                LIMIT $1
                """,
                limit,
            )
    return [_row(r) for r in rows]


@router.get("/documents/{document_id}")
async def chi_tiet_van_ban(document_id: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        doc = await conn.fetchrow(
            """
            SELECT document_id, code, title, doc_type, issuer, issued_date, effective_date,
                   status, status_detail, group_name, source_url, sha256, file_name, notes, tags
            FROM app_construction.legal_refs
            WHERE document_id = $1
            """,
            document_id,
        )
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"loi": "Không tìm thấy văn bản"})
        cits = await conn.fetch(
            """
            SELECT citation_key, article, clause, point, topic, summary, effective_date, status,
                   source_url, sha256, can_doi_chieu
            FROM app_construction.legal_citations
            WHERE document_id = $1
            ORDER BY topic, article, clause NULLS FIRST
            """,
            document_id,
        )
    data = _row(doc)
    data["citations"] = [_row(c) for c in cits]
    return data


@router.get("/citations")
async def tra_cuu_trich_dan(
    topic: Optional[str] = Query(default=None, max_length=64),
    document_id: Optional[str] = Query(default=None, max_length=64),
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT c.citation_key, c.document_id, d.code AS document_code, d.title AS document_title,
                   c.article, c.clause, c.point, c.topic, c.summary, c.effective_date, c.status,
                   c.source_url, c.sha256, c.can_doi_chieu
            FROM app_construction.legal_citations c
            JOIN app_construction.legal_refs d ON d.document_id = c.document_id
            WHERE ($1::text IS NULL OR c.topic = $1)
              AND ($2::text IS NULL OR c.document_id = $2)
            ORDER BY c.topic, c.document_id, c.article
            """,
            topic,
            document_id,
        )
    return [_row(r) for r in rows]


@router.get("/citations/{citation_key}")
async def chi_tiet_trich_dan(citation_key: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        row = await conn.fetchrow(
            """
            SELECT c.citation_key, c.document_id, d.code AS document_code, d.title AS document_title,
                   c.article, c.clause, c.point, c.topic, c.summary, c.effective_date, c.status,
                   c.source_url, c.sha256, c.can_doi_chieu
            FROM app_construction.legal_citations c
            JOIN app_construction.legal_refs d ON d.document_id = c.document_id
            WHERE c.citation_key = $1
            """,
            citation_key,
        )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"loi": "Không tìm thấy trích dẫn"})
    return _row(row)
