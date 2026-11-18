# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""V2-09: truy cập khẩn: bị chặn 403, xin quyền, không tự duyệt được, lãnh đạo duyệt thì mở được.

Dùng một hồ sơ mới nộp nên không có yêu cầu truy cập khẩn cũ; không xóa dữ liệu nào.
"""

import httpx

from tests.integration._ho_so import GATEWAY_URL, get_token, sub_of, submit_dossier


def _rpc(token: str, ten: str, body: dict) -> httpx.Response:
    return httpx.post(f"{GATEWAY_URL}/api/v1/rest/rpc/{ten}",
                      headers={"Authorization": f"Bearer {token}"}, json=body, timeout=10.0)


def test_break_glass_flow_and_sod():
    token_minh = get_token("cdt.minh")
    token_cuong = get_token("td.cuong")
    token_hoa = get_token("ld.hoa")
    cuong_sub = sub_of(token_cuong)

    resp = submit_dossier(token_minh, {
        "ho_ten": "Tran Van V209",
        "cccd": "001200000209",
        "dien_thoai": "0901000209",
        "dia_chi_cong_trinh": "209 Pho V2-09",
        "thua_dat": "Thua 9 To 2",
        "so_tang": 2,
        "dien_tich_san_m2": 120.0,
        "khu_quan_ly_kien_truc": True,
    }, tag_prefix="V2_09_break_glass")
    assert resp.status_code == 200, resp.text
    target_id = resp.json()["id"]

    # 1. td.cuong mở hồ sơ chưa được giao -> 403, kèm gợi ý xin truy cập khẩn
    r = _rpc(token_cuong, "mo_ho_so", {"p_id": target_id})
    assert r.status_code == 403, f"Mở hồ sơ chưa được giao phải 403: {r.status_code} {r.text}"
    assert r.json().get("can_xin_truy_cap_khan") is True

    # 2. td.cuong xin truy cập khẩn
    r = _rpc(token_cuong, "xin_truy_cap_khan", {"p_ho_so_id": target_id, "p_ly_do": "Kiem tra ho so khan cap phuc vu thanh tra"})
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "pending"

    # 3. SoD: người xin không tự duyệt được
    r = _rpc(token_cuong, "duyet_truy_cap_khan", {"p_ho_so_id": target_id, "p_user_sub": cuong_sub, "p_dong_y": True})
    assert r.status_code in (400, 403), f"Người xin không được tự duyệt: {r.status_code} {r.text}"
    assert _rpc(token_cuong, "mo_ho_so", {"p_id": target_id}).status_code == 403

    # 4. Lãnh đạo duyệt
    r = _rpc(token_hoa, "duyet_truy_cap_khan", {"p_ho_so_id": target_id, "p_user_sub": cuong_sub, "p_dong_y": True})
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "approved"

    # 5. td.cuong mở được hồ sơ
    r = _rpc(token_cuong, "mo_ho_so", {"p_id": target_id})
    assert r.status_code == 200, f"Sau khi được duyệt phải mở được hồ sơ: {r.status_code} {r.text}"
    assert r.json().get("id") == target_id
