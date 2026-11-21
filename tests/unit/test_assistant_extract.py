# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Trả lời trích xuất khi không có mô hình: câu trọn vẹn, đúng ý câu hỏi, không lộ markdown."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("services_assistant_extract", ROOT / "services/assistant/main.py")
assistant = importlib.util.module_from_spec(spec)
sys.modules["services_assistant_extract"] = assistant
spec.loader.exec_module(assistant)

CHUNK = """## 1. Thẩm Quyền và Thời Hạn Giải Quyết (Luật Xây dựng 2025 & NĐ 217/2026/NĐ-CP)

1. **Thẩm quyền cấp phép:** Ủy ban nhân dân cấp xã/phường có thẩm quyền cấp giấy phép xây dựng đối với công trình nhà ở riêng lẻ trên địa bàn quản lý.
2. **Hình thức tiếp nhận:** Tiếp nhận hồ sơ trực tuyến 100% qua cổng dịch vụ công trực tuyến.
3. **Thời hạn giải quyết tổng thể:** Tối đa không quá **7 ngày làm việc** kể từ ngày nhận đủ hồ sơ hợp lệ.
4. **Thời hạn thẩm định:** Thẩm định viên thực hiện thẩm định kỹ thuật trong vòng **3 ngày làm việc**.
"""


def test_tra_loi_dung_y_va_khong_cat_giua_chu():
    ans = assistant.extractive_answer("Thời hạn giải quyết cấp phép là bao lâu?", [{"chunk": CHUNK}])
    assert "7 ngày làm việc" in ans
    assert "#" not in ans and "**" not in ans
    assert ans.endswith("[1]")
    assert len(ans) <= assistant.EXTRACT_CHARS + 40


def test_ghi_so_nguon_theo_doan():
    hits = [{"chunk": "Lệ phí cấp giấy phép xây dựng nhà ở riêng lẻ do tỉnh quy định."}, {"chunk": CHUNK}]
    ans = assistant.extractive_answer("Thời hạn giải quyết cấp phép là bao lâu?", hits)
    assert "[2]" in ans


def test_khong_cau_nao_khop_thi_lay_cau_dau_tron_ven():
    ans = assistant.extractive_answer("xyz abc", [{"chunk": CHUNK}])
    assert ans.startswith("1. Thẩm Quyền") is False
    assert ans.endswith("[1]")
