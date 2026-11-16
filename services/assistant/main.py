# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import logging
import os
import re
import httpx
from typing import Optional
from fastapi import FastAPI, Header
from pydantic import BaseModel
from dxos_core.middleware import setup_standard_service
from dxos_core.jwt import verify_jwt_token
from dxos_core.db import get_db_connection

logger = logging.getLogger("dxos.assistant")
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", os.environ.get("OLLAMA_URL", "http://ollama:11434")).rstrip("/")

# Từ phổ biến không mang nghĩa tra cứu
_STOP = {
    "là", "bao", "nhiêu", "của", "và", "có", "cho", "được", "không", "những", "các", "thì", "mấy", "gì",
    "nào", "theo", "trong", "với", "khi", "này", "đó", "ra", "vào", "tôi", "bạn", "em", "anh", "chị", "hỏi",
    "cần", "phải", "một", "về", "như", "thế", "sao", "ở", "tại", "hay", "hoặc", "để", "lại",
}


def _tokens(text: str) -> list:
    return [w for w in re.findall(r"[0-9a-zA-ZÀ-ỹ.]+", text.lower()) if w.strip(".")]


def _score(question: str, chunk: str) -> int:
    """Điểm khớp: cặp từ liền nhau trùng được 3 điểm, từ đơn có nghĩa trùng được 1 điểm."""
    q = _tokens(question)
    c = _tokens(chunk)
    c_set = set(c)
    c_bi = set(zip(c, c[1:], strict=False))
    uni = sum(1 for w in set(q) if w not in _STOP and w in c_set)
    bi = sum(1 for p in set(zip(q, q[1:], strict=False)) if p in c_bi and not (p[0] in _STOP and p[1] in _STOP))
    return uni + 3 * bi

app = FastAPI(title="DX-OS AI Knowledge Assistant Service", version="1.0.0")
setup_standard_service(app, "assistant")


class AskRequest(BaseModel):
    question: str
    app: Optional[str] = "default"


def _best_excerpt(chunk: str, keywords: list[str], phrases: list[str], question: str) -> str:
    lines = []
    for line in chunk.splitlines():
        clean = line.strip().lstrip(">").strip()
        if not clean or clean.startswith("#") or clean.startswith("---"):
            continue
        if clean.startswith("*Ghi chú") or clean.startswith("Ghi chú"):
            continue
        if clean.endswith(":**") or clean.endswith(":"):
            continue
        lines.append(clean)
    priority_terms = ["thời hạn", "ban ngày", "ban đêm", "tiếng ồn", "độ ồn", "dba", "bụi mịn", "pm10", "pm2.5", "hồ sơ", "giấy tờ", "thẩm định", "lệ phí"]
    for term in priority_terms:
        if term in question.lower():
            for line in lines:
                if term in line.lower():
                    return line[:500]

    scored = []
    for line in lines:
        low = line.lower()
        score = sum(1 for keyword in keywords if keyword in low) + sum(3 for phrase in phrases if phrase in low)
        scored.append((score, line))
    if scored:
        best = max(scored, key=lambda item: item[0])
        if best[0] > 0:
            return best[1][:500]
    return " ".join(lines)[:500]


@app.post("/api/v1/assistant/ask")
async def ask_assistant(
    req: AskRequest,
    authorization: str = Header(...),
):
    """
    Hỏi đáp tra cứu quy chuẩn kỹ thuật bằng RAG (Retrieval-Augmented Generation).
    Tìm kiếm đoạn tri thức qua PostgREST/Database bằng chính JWT của người dùng.
    """
    claims = verify_jwt_token(authorization)
    question = req.question.strip()

    # Xếp hạng đoạn tri thức theo mức trùng từ với câu hỏi; không trả đoạn không liên quan
    async with get_db_connection(claims) as conn:
        all_rows = await conn.fetch(
            """
            SELECT source, chunk
            FROM core.knowledge_chunks
            WHERE tenant = $1
            LIMIT 2000
            """,
            claims.tenant,
        )
    scored = sorted(((_score(question, r["chunk"]), r) for r in all_rows), key=lambda x: x[0], reverse=True)
    rows = [r for sc, r in scored[:3] if sc >= 3]

    # Từ khoá và cụm hai từ, dùng để chọn câu trích phù hợp nhất khi không có LLM
    keywords = [w for w in _tokens(question) if len(w) >= 3 and w not in _STOP][:8]
    phrases = [f"{keywords[i]} {keywords[i + 1]}" for i in range(len(keywords) - 1)]

    if not rows:
        return {
            "question": question,
            "answer": "Không có trong tài liệu đã nạp.",
            "citations": [],
        }

    # Tổng hợp ngữ cảnh
    contexts = [f"[{r['source']}] {r['chunk']}" for r in rows]
    citations = list(dict.fromkeys(r["source"] for r in rows))

    # Nếu có Ollama online, gọi LLM; nếu không có, trích xuất đoạn văn phù hợp
    answer = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": "qwen2.5:0.5b",
                    "prompt": f"Dựa vào tài liệu sau, trả lời ngắn gọn câu hỏi: {question}\n\nNgữ cảnh:\n" + "\n".join(contexts),
                    "stream": False,
                },
            )
            if resp.status_code == 200:
                answer = resp.json().get("response")
    except Exception as e:
        logger.warning(f"Không thể kết nối mô hình LLM Ollama ({e}), trích xuất trực tiếp từ tri thức")

    if not answer:
        # Trả về đoạn văn phù hợp nhất với từ khóa, không trả header/markdown
        answer = f"Theo quy định tại tài liệu ({citations[0]}): " + _best_excerpt(rows[0]["chunk"], keywords, phrases, question)

    return {
        "question": question,
        "answer": answer,
        "citations": citations,
    }
