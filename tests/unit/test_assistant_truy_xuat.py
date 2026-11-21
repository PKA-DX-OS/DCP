# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""FIX-V11-13: trợ lý chọn đúng đoạn và câu theo ý câu hỏi trên kho tri thức thật của cap-phep;
câu hỏi không có căn cứ thì trả lời không tìm thấy."""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("services_assistant_truy_xuat", ROOT / "services/assistant/main.py")
assistant = importlib.util.module_from_spec(spec)
sys.modules["services_assistant_truy_xuat"] = assistant
spec.loader.exec_module(assistant)


def _kho_tri_thuc() -> list[dict]:
    """Dựng đoạn tri thức giống app_manager: mục ## của tệp quy định và trích dẫn pháp lý."""
    md = (ROOT / "apps/cap-phep/knowledge/quy-dinh-cap-phep.md").read_text(encoding="utf-8")
    doan = [{"id": i, "source": "quy-dinh", "chunk": f"## {c.strip()}"} for i, c in enumerate(md.split("## ")[1:]) if c.strip()]
    legal = ROOT / "core/legal"
    van_ban = {d["document_id"]: d for d in json.loads((legal / "danh_muc_van_ban.json").read_text(encoding="utf-8"))}
    for cit in json.loads((legal / "citations.json").read_text(encoding="utf-8")):
        doc = van_ban.get(cit["document_id"])
        if doc:
            pos = " ".join(x for x in [cit.get("clause"), cit.get("point")] if x)
            doan.append({
                "id": len(doan),
                "source": "legal/" + cit["citation_key"],
                "chunk": f"Văn bản {doc['code']} ({doc['title']}) — {cit['article']}{', ' + pos if pos else ''}: {cit['summary']}",
            })
    return doan


class _Conn:
    def __init__(self, rows):
        self.rows = rows

    async def fetch(self, *_):
        return self.rows


def _hoi(cau: str) -> tuple[list, str]:
    hits = asyncio.run(assistant.retrieve(_Conn(_kho_tri_thuc()), "phuong-a", cau, "cap-phep"))
    return hits, (assistant.extractive_answer(cau, hits) if hits else assistant.NOT_FOUND)


def test_hoi_giay_to_tra_loi_thanh_phan_ho_so():
    _, tra_loi = _hoi("Hồ sơ cấp phép xây dựng nhà ở riêng lẻ gồm những giấy tờ gì?")
    assert "đơn đề nghị" in tra_loi and "giấy tờ hợp pháp về đất đai" in tra_loi
    assert "07 ngày" not in tra_loi and "Thẩm quyền" not in tra_loi


def test_hoi_thoi_han_co_7_ngay():
    _, tra_loi = _hoi("Thời hạn giải quyết cấp phép là bao lâu?")
    assert "7 ngày làm việc" in tra_loi


def test_khong_co_can_cu_thi_khong_tim_thay():
    for cau in ("Khi nào phải xin điều chỉnh giấy phép?", "Thời tiết hôm nay thế nào?"):
        hits, tra_loi = _hoi(cau)
        assert hits == [] and tra_loi == assistant.NOT_FOUND, cau


def test_khong_tach_cau_o_dau_cham_phay():
    cau = assistant._cac_cau("Thời hạn là 07 ngày làm việc; thẩm định hồ sơ 03 ngày làm việc.")
    assert cau == ["Thời hạn là 07 ngày làm việc; thẩm định hồ sơ 03 ngày làm việc."]


def test_khai_niem_ngoai_kho_thi_khong_tim_thay():
    """FIX-V11-21: câu hỏi trùng cụm chung ("giấy tờ", "thời hạn") nhưng nói về khái niệm kho không có."""
    for cau in (
        "Đăng ký kết hôn cần giấy tờ gì?",
        "Đăng ký xe máy cần giấy tờ gì?",
        "Thời hạn sử dụng thẻ căn cước?",
        "Mật độ xây dựng tối đa là bao nhiêu?",
    ):
        hits, tra_loi = _hoi(cau)
        assert hits == [] and tra_loi == assistant.NOT_FOUND, cau


def test_cau_hoi_trong_kho_van_tra_loi():
    for cau in (
        "Lệ phí cấp phép là bao nhiêu?",
        "Ai có thẩm quyền cấp giấy phép?",
        "Nghiệm thu công trình gồm những gì?",
        "Thời hạn giải quyết cấp phép là bao lâu?",
    ):
        hits, _ = _hoi(cau)
        assert hits, cau


def test_ngoai_kho_bo_qua_so_va_tu_chung():
    assert assistant.ngoai_kho({"lâu", "54", "phép"}, {"phép"}) == set()
    assert assistant.ngoai_kho({"hôn", "phép"}, {"phép"}) == {"hôn"}
