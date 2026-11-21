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
import math
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
# Thuật ngữ đặc trưng: xuất hiện trong không quá 20% số đoạn của kho tri thức
TY_LE_DAC_TRUNG = 0.2
SNIPPET_CHARS = 280
NOT_FOUND = "Không tìm thấy căn cứ trong tri thức của địa bàn bạn."
STOPWORDS = {
    "là", "và", "của", "có", "không", "được", "thì", "cho", "các", "một", "những", "để",
    "với", "trong", "khi", "nào", "gì", "bao", "nhiêu", "tại", "này", "đó", "the", "is", "a",
    "phải", "cần", "vì", "sao", "thế", "ai",
}

# Từ hỏi, từ xưng hô và từ thủ tục chung: không mang chủ đề nên không cần có trong kho
TU_CHUNG = {
    "lâu", "đâu", "mấy", "giờ", "bị", "xin", "muốn", "hỏi", "giúp", "ạ", "nhỉ", "vậy", "ơi",
    "tôi", "mình", "em", "anh", "chị", "đăng", "thủ", "tục",
}


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    app: Optional[str] = Field(default=None, max_length=64)


def tokenize(text: str) -> Set[str]:
    return {t for t in re.findall(r"\w+", text.lower()) if len(t) >= 2 and t not in STOPWORDS}


def score_chunk(query_tokens: Set[str], chunk: str) -> int:
    return len(query_tokens & tokenize(chunk))


def cum_tu(text: str) -> Set[str]:
    """Cặp âm tiết liền nhau: tiếng Việt phần lớn là từ hai âm tiết, cặp phân biệt nghĩa tốt hơn từng âm."""
    am_tiet = [t for t in re.findall(r"\w+", text.lower())]
    return {f"{a} {b}" for a, b in zip(am_tiet, am_tiet[1:], strict=False) if a not in STOPWORDS and b not in STOPWORDS}


def thuat_ngu(text: str) -> Set[str]:
    return tokenize(text) | cum_tu(text)


def trong_so(van_ban: List[str]) -> Dict[str, float]:
    """IDF trên tập ứng viên: từ xuất hiện khắp nơi nặng ít, từ phân biệt nặng nhiều."""
    df: Dict[str, int] = {}
    for v in van_ban:
        for t in thuat_ngu(v):
            df[t] = df.get(t, 0) + 1
    n = len(van_ban)
    w = {t: math.log((n + 1) / (d + 1)) + 1.0 for t, d in df.items()}
    # Thuật ngữ không có trong tập ứng viên nhận trọng số cao nhất (hiếm nhất)
    w[""] = math.log(n + 1) + 1.0
    return w


def diem_khop(q_terms: Set[str], terms: Set[str], idf: Dict[str, float]) -> float:
    """Tổng trọng số thuật ngữ trùng; cụm hai âm tiết nhân 1.5 vì mang nghĩa rõ hơn."""
    mac_dinh = idf.get("", 1.0)
    return sum(idf.get(t, mac_dinh) * (1.5 if " " in t else 1.0) for t in q_terms & terms)


def ngoai_kho(query_tokens: Set[str], tu_vung: Set[str]) -> Set[str]:
    """Âm tiết nội dung của câu hỏi không có ở đoạn nào trong kho (bỏ qua số và từ chung).
    Câu hỏi nhắc tới khái niệm kho không có (ví dụ "kết hôn", "căn cước") thì kho không trả lời được,
    dù trùng vài cụm chung như "giấy tờ", "thời hạn"."""
    return {t for t in query_tokens if t not in tu_vung and t not in TU_CHUNG and not t.isdigit()}


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
    tu_vung: Set[str] = set()
    for r in rows:
        tu_vung |= tokenize(r["chunk"])
    if ngoai_kho(q, tu_vung):
        return []
    q_terms = thuat_ngu(question)
    idf = trong_so([r["chunk"] for r in rows])
    scored = []
    for r in rows:
        # Ngưỡng giữ nguyên theo số từ đơn khớp; thứ hạng theo trọng số để đoạn đúng ý lên đầu
        if score_chunk(q, r["chunk"]) >= threshold:
            scored.append((diem_khop(q_terms, thuat_ngu(r["chunk"]), idf), r))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        return []
    # Đoạn khớp nhất chỉ trùng từ chung của cả kho (không trùng thuật ngữ đặc trưng nào): không có căn cứ
    nguong_df = math.log((len(rows) + 1) / (TY_LE_DAC_TRUNG * len(rows) + 1)) + 1.0
    # Chỉ xét cụm hai âm tiết: một âm tiết lẻ (như "tiết", "nay") trùng ngẫu nhiên quá dễ
    dac_trung = {t for t in q_terms if " " in t and idf.get(t, 0.0) >= nguong_df}
    if not dac_trung & thuat_ngu(scored[0][1]["chunk"]):
        return []
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
HE_SO_THU_HANG = 0.15
NGUONG_TUONG_DOI = 0.75
_MARKDOWN = re.compile(r"^\s{0,3}(#{1,6}\s+|[-*+]\s+|\d+[.)]\s+|>\s*)|\*\*|__|`", re.MULTILINE)
# Không tách ở dấu ";": vế sau thường không đứng riêng được thành câu
_TACH_CAU = re.compile(r"(?<=[.!?])\s+|\n+")


_BO_DONG = re.compile(r"^\s*(#{1,6}\s.*|<!--.*|-->|SPDX-.*|-{3,}|>.*)$", re.MULTILINE)


def _tieu_de(chunk: str) -> str:
    """Tiêu đề mục (## ...) của đoạn: dùng để chấm điểm câu, không đưa vào câu trả lời."""
    m = re.search(r"^\s{0,3}#{1,6}\s+(.*)$", chunk, re.MULTILINE)
    return m.group(1) if m else ""


def _cac_cau(chunk: str) -> List[str]:
    """Tách đoạn tri thức thành câu: bỏ dòng tiêu đề, ghi chú, chú thích; bỏ ký hiệu markdown."""
    sach = _MARKDOWN.sub("", _BO_DONG.sub("", chunk))
    return [c.strip(" \t-•:;,") for c in _TACH_CAU.split(sach) if len(c.strip()) >= 20]


def extractive_answer(question: str, hits: List[Dict[str, Any]]) -> str:
    """Trả lời không có mô hình: ghép các câu trọn vẹn khớp câu hỏi nhất, giữ thứ tự trong nguồn,
    ghi [n] sau mỗi câu. Không cắt giữa chữ."""
    q = thuat_ngu(question)
    cau_theo_doan = [(i, _tieu_de(h["chunk"]), _cac_cau(h["chunk"])) for i, h in enumerate(hits)]
    idf = trong_so([c for _, _, ds in cau_theo_doan for c in ds])
    ung_vien = []
    for i, tieu_de, ds in cau_theo_doan:
        tu_tieu_de = thuat_ngu(tieu_de)
        for thu_tu, cau in enumerate(ds):
            # Câu được tính thêm từ của tiêu đề mục chứa nó (nửa trọng số)
            diem = diem_khop(q, thuat_ngu(cau), idf) + 0.5 * diem_khop(q, tu_tieu_de - thuat_ngu(cau), idf)
            # Đoạn xếp hạng cao hơn khi truy xuất được ưu tiên
            diem *= 1.0 - HE_SO_THU_HANG * min(i, 3)
            if diem > 0:
                ung_vien.append((diem, i, thu_tu, cau))
    ung_vien.sort(key=lambda x: (-x[0], x[1], x[2]))
    if ung_vien:
        # Bỏ câu kém xa câu khớp nhất để câu trả lời không lạc sang ý khác
        nguong = NGUONG_TUONG_DOI * ung_vien[0][0]
        ung_vien = [u for u in ung_vien if u[0] >= nguong]
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