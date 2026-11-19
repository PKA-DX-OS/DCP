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


def extractive_answer(hits: List[Dict[str, Any]]) -> str:
    top = hits[0]["chunk"][:SNIPPET_CHARS].strip()
    return f"Theo tri thức của địa bàn [1]: {top}"


async def answer_question(question: str, hits: List[Dict[str, Any]]) -> Tuple[str, str]:
    try:
        return await generate_with_ollama(question, hits), "ollama"
    except Exception as exc:
        logger.warning(f"Ollama không khả dụng, dùng trích xuất trực tiếp: {exc}")
        return extractive_answer(hits), "trich_xuat"


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