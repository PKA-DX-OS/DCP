# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Trợ lý hỏi đáp có trích dẫn từ kho tri thức core.knowledge_chunks (C05).

- POST /api/v1/assistant/ask {question, app?}
- Chỉ dùng đoạn tri thức của tenant trong token. Không tìm thấy căn cứ thì không trả lời bịa.
- Có Ollama: sinh câu trả lời từ đúng các đoạn đã tìm, kèm số trích dẫn [n].
- Không có Ollama: trích nguyên văn đoạn liên quan nhất kèm trích dẫn (không suy diễn).
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
from fastapi import FastAPI, Header
from pydantic import BaseModel, Field

from dxos_core.middleware import setup_standard_service
from dxos_core.jwt import verify_jwt_token
from dxos_core.db import get_db_connection

app = FastAPI(title="DX-OS Assistant (RAG có trích dẫn)", version="1.0.0")
setup_standard_service(app, "assistant")
logger = logging.getLogger("dxos.assistant")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
ASSISTANT_MODEL = os.getenv("ASSISTANT_MODEL", "qwen2.5:0.5b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "8"))
TOP_K = 3
CANDIDATE_LIMIT = 500
SNIPPET_CHARS = 280
NOT_FOUND = "Không tìm thấy căn cứ trong tri thức của địa bàn bạn."
STOPWORDS = {
    "là", "và", "của", "có", "không", "được", "thì", "cho", "các", "một", "những", "để",
    "với", "trong", "khi", "nào", "gì", "bao", "nhiêu", "tại", "này", "đó", "the", "is", "a",
}


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    app: Optional[str] = Field(default=None, max_length=64)


def tokenize(text: str) -> Set[str]:
    return {t for t in re.findall(r"\w+", text.lower()) if len(t) >= 2 and t not in STOPWORDS}


def score_chunk(query_tokens: Set[str], chunk: str) -> int:
    return len(query_tokens & tokenize(chunk))


def min_match(query_tokens: Set[str]) -> int:
    """Câu hỏi ngắn cần ít nhất 1 từ khớp; câu dài cần ít nhất 2 từ khớp."""
    return 1 if len(query_tokens) <= 2 else 2


async def retrieve(conn, tenant: str, question: str, app_code: Optional[str]) -> List[Dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT id, app, source, chunk
        FROM core.knowledge_chunks
        WHERE tenant = $1 AND ($2::text IS NULL OR app = $2)
        ORDER BY created_at DESC
        LIMIT $3
        """,
        tenant, app_code, CANDIDATE_LIMIT,
    )
    q = tokenize(question)
    if not q:
        return []
    threshold = min_match(q)
    scored = []
    for r in rows:
        s = score_chunk(q, r["chunk"])
        if s >= threshold:
            scored.append((s, r))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [r for _, r in scored[:TOP_K]]


def make_citations(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "so": i + 1,
            "nguon": h["source"],
            "chunk_id": str(h["id"]),
            "trich": h["chunk"][:SNIPPET_CHARS],
        }
        for i, h in enumerate(hits)
    ]


async def generate_with_ollama(question: str, hits: List[Dict[str, Any]]) -> str:
    context = "\n".join(f"[{i + 1}] {h['chunk'][:SNIPPET_CHARS * 2]}" for i, h in enumerate(hits))
    prompt = (
        "Chỉ trả lời dựa trên các đoạn tri thức dưới đây. Ghi số [n] sau mỗi ý lấy từ đoạn n. "
        "Nếu các đoạn không đủ để trả lời, trả lời đúng một câu: " + NOT_FOUND + "\n\n"
        f"Tri thức:\n{context}\n\nCâu hỏi: {question}\nTrả lời:"
    )
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        resp = await client.post(
            f"{OLLAMA_URL.rstrip('/')}/api/generate",
            json={"model": ASSISTANT_MODEL, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        text = (resp.json().get("response") or "").strip()
    if not text:
        raise ValueError("Ollama trả về rỗng")
    return text


EXTRACT_CHARS = 600
EXTRACT_SENTENCES = 3
_MARKDOWN = re.compile(r"^\s{0,3}(#{1,6}\s+|[-*+]\s+|\d+[.)]\s+|>\s*)|\*\*|__|`", re.MULTILINE)
_TACH_CAU = re.compile(r"(?<=[.!?;])\s+|\n+")


_BO_DONG = re.compile(r"^\s*(#{1,6}\s.*|<!--.*|-->|SPDX-.*|-{3,}|>.*)$", re.MULTILINE)


def _cac_cau(chunk: str) -> List[str]:
    """Tách đoạn tri thức thành câu: bỏ dòng tiêu đề, ghi chú, chú thích; bỏ ký hiệu markdown."""
    sach = _MARKDOWN.sub("", _BO_DONG.sub("", chunk))
    return [c.strip(" \t-•:;,") for c in _TACH_CAU.split(sach) if len(c.strip()) >= 20]


def extractive_answer(question: str, hits: List[Dict[str, Any]]) -> str:
    """Trả lời không có mô hình: ghép các câu trọn vẹn khớp câu hỏi nhất, giữ thứ tự trong nguồn,
    ghi [n] sau mỗi câu. Không cắt giữa chữ."""
    q = tokenize(question)
    ung_vien = []
    for i, h in enumerate(hits):
        for thu_tu, cau in enumerate(_cac_cau(h["chunk"])):
            diem = len(q & tokenize(cau))
            if diem:
                ung_vien.append((diem, i, thu_tu, cau))
    ung_vien.sort(key=lambda x: (-x[0], x[1], x[2]))
    chon: List[Tuple[int, int, str]] = []
    do_dai = 0
    for _, i, thu_tu, cau in ung_vien:
        if len(chon) >= EXTRACT_SENTENCES:
            break
        if chon and do_dai + len(cau) > EXTRACT_CHARS:
            continue
        chon.append((i, thu_tu, cau))
        do_dai += len(cau)
    if not chon:
        cau_dau = (_cac_cau(hits[0]["chunk"]) or [hits[0]["chunk"].strip()])[0]
        if len(cau_dau) > EXTRACT_CHARS:
            cau_dau = cau_dau[:EXTRACT_CHARS].rsplit(" ", 1)[0] + "…"
        chon = [(0, 0, cau_dau)]
    chon.sort(key=lambda x: (x[0], x[1]))
    return " ".join(f"{cau.rstrip('.')}. [{i + 1}]" for i, _, cau in chon)


async def answer_question(question: str, hits: List[Dict[str, Any]]) -> Tuple[str, str]:
    try:
        return await generate_with_ollama(question, hits), "ollama"
    except Exception as exc:
        logger.warning(f"Ollama không khả dụng, dùng trích xuất trực tiếp: {exc}")
        return extractive_answer(question, hits), "trich_xuat"


@app.post("/api/v1/assistant/ask")
async def ask(body: AskRequest, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    question = body.question.strip()

    async with get_db_connection(claims) as conn:
        hits = await retrieve(conn, claims.tenant, question, body.app)

    if not hits:
        return {"answer": NOT_FOUND, "citations": [], "mode": "khong_co_can_cu"}

    answer, mode = await answer_question(question, hits)
    return {"answer": answer, "citations": make_citations(hits), "mode": mode}