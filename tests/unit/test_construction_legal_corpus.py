# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-LEGAL-01: kiểm tra tính toàn vẹn của kho văn bản pháp luật đóng gói trong repo."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGAL = ROOT / "core" / "legal"


def load(name: str) -> list[dict]:
    return json.loads((LEGAL / name).read_text(encoding="utf-8"))


def test_du_50_van_ban_va_ma_khong_trung():
    docs = load("danh_muc_van_ban.json")
    assert len(docs) == 50
    ids = [d["document_id"] for d in docs]
    assert len(ids) == len(set(ids))
    for doc in docs:
        assert re.fullmatch(r"[0-9a-f]{64}", doc["sha256"] or ""), f"Sai SHA-256: {doc['document_id']}"
        assert doc["code"] and doc["title"]
        assert doc["status"] in {"Còn hiệu lực", "Hết hiệu lực", "Còn hiệu lực một phần", "Chưa có hiệu lực"}


def test_moi_trich_dan_tro_dung_van_ban_con_hieu_luc():
    docs = {d["document_id"]: d for d in load("danh_muc_van_ban.json")}
    citations = load("citations.json")
    assert citations
    keys = [c["citation_key"] for c in citations]
    assert len(keys) == len(set(keys))
    for cit in citations:
        assert cit["document_id"] in docs, f"Trích dẫn mồ côi: {cit['citation_key']}"
        doc = docs[cit["document_id"]]
        assert "Hết hiệu lực" != doc["status"], f"Không dùng văn bản hết hiệu lực làm căn cứ: {doc['code']}"
        assert cit["article"], f"Thiếu điều/khoản: {cit['citation_key']}"
        assert cit["topic"] and cit["summary"]


def test_co_can_cu_dieu_60_va_tham_quyen_dieu_53():
    citations = {c["citation_key"]: c for c in load("citations.json")}
    assert citations["ND217-D60-K3"]["document_id"] == "VB-02"
    assert citations["ND217-D60-K3"]["article"] == "Điều 60"
    assert citations["ND217-D60-K3"]["clause"] == "khoản 3"
    assert "cam kết" in citations["ND217-D60-K3"]["summary"].lower()
    for key in ("ND217-D53-K1", "ND217-D53-K2", "ND217-D53-K3"):
        assert citations[key]["article"] == "Điều 53"
    assert citations["ND217-D54"]["article"] == "Điều 54"
    assert citations["ND217-D55"]["article"] == "Điều 55"
    assert citations["ND217-D56-K3"]["article"] == "Điều 56"


def test_khong_dung_dieu_57_cho_nha_o_rieng_le():
    citations = {c["citation_key"]: c for c in load("citations.json")}
    assert "không dùng" in citations["ND217-D57"]["summary"].lower()
