# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy cho lỗi N-06:
- Danh sách thẩm định viên được nạp động qua RPC app_cap_phep.ds_can_bo.
- Lãnh đạo phường A chỉ thấy thẩm định viên phường A (td.binh, td.cuong).
- Lãnh đạo phường B chỉ thấy thẩm định viên phường B (td.phuongb).
- Chủ đầu tư gọi RPC -> 403 Forbidden (mã SQL 42501).
- scripts/check_no_fakes.py chặn hoàn toàn mảng hằng chứa tài khoản demo hoặc giá trị mặc định trong UI.
"""

import subprocess
import httpx
from tests.integration.conftest import get_token


def test_N06_check_no_fakes_passes():
    """Kiểm tra check_no_fakes.py đạt exit 0 sau khi loại bỏ mã giả."""
    res = subprocess.run(["python", "scripts/check_no_fakes.py"], capture_output=True, text=True)
    assert res.returncode == 0, f"check_no_fakes thất bại:\n{res.stdout}\n{res.stderr}"
    assert "[PASS]" in res.stdout


def test_N06_ds_can_bo_isolation_by_tenant():
    """Lãnh đạo từng phường chỉ nhận danh sách cán bộ thuộc tenant của mình."""
    # 1. Lãnh đạo phường A gọi ds_can_bo
    token_hoa = get_token("ld.hoa")
    with httpx.Client(base_url="http://localhost:8080") as client:
        res_a = client.post(
            "/api/v1/rest/rpc/ds_can_bo",
            headers={"Authorization": f"Bearer {token_hoa}"},
            json={"p_vai": "tham-dinh"},
        )
        assert res_a.status_code == 200, f"ld.hoa gọi ds_can_bo thất bại: {res_a.status_code} - {res_a.text}"
        data_a = res_a.json()
        usernames_a = [o["username"] for o in data_a]
        assert "td.binh" in usernames_a, f"Thiếu td.binh trong phường A: {usernames_a}"
        assert "td.cuong" in usernames_a, f"Thiếu td.cuong trong phường A: {usernames_a}"
        assert "td.phuongb" not in usernames_a, f"Lộ td.phuongb của phường B sang phường A: {usernames_a}"

    # 2. Lãnh đạo phường B gọi ds_can_bo
    token_ld_b = get_token("ld.phuongb")
    with httpx.Client(base_url="http://localhost:8080") as client:
        res_b = client.post(
            "/api/v1/rest/rpc/ds_can_bo",
            headers={"Authorization": f"Bearer {token_ld_b}"},
            json={"p_vai": "tham-dinh"},
        )
        assert res_b.status_code == 200, f"ld.phuongb gọi ds_can_bo thất bại: {res_b.status_code} - {res_b.text}"
        data_b = res_b.json()
        usernames_b = [o["username"] for o in data_b]
        assert "td.phuongb" in usernames_b, f"Thiếu td.phuongb trong phường B: {usernames_b}"
        assert "td.binh" not in usernames_b, f"Lộ td.binh của phường A sang phường B: {usernames_b}"
        assert "td.cuong" not in usernames_b, f"Lộ td.cuong của phường A sang phường B: {usernames_b}"


def test_N06_ds_can_bo_forbidden_for_unauthorized_roles():
    """Chủ đầu tư hoặc người dùng không có vai trò lãnh đạo/một cửa gọi ds_can_bo -> 403 Forbidden (42501)."""
    token_minh = get_token("cdt.minh")
    with httpx.Client(base_url="http://localhost:8080") as client:
        res = client.post(
            "/api/v1/rest/rpc/ds_can_bo",
            headers={"Authorization": f"Bearer {token_minh}"},
            json={"p_vai": "tham-dinh"},
        )
        assert res.status_code == 403, f"Chủ đầu tư gọi ds_can_bo phải bị 403, nhận được {res.status_code}: {res.text}"
        body = res.json()
        assert body.get("code") == "42501" or "42501" in str(body), f"Mã lỗi phải là 42501: {body}"
