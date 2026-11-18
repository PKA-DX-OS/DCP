# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy V4-05:
- Hồ sơ không tồn tại hoặc không thuộc địa bàn khi gọi bo_sung_ho_so phải trả HTTP 404 (thay vì HTTP 500).
- Các lỗi nghiệp vụ và phân quyền trong RPC trả mã 4xx, không trả 500.
"""

import os
import json
import urllib.request
import urllib.parse

def get_demo_passwords():
    pw = {}
    for p in ["secrets/demo-accounts.txt", "D:/v1PMNM-clean/secrets/demo-accounts.txt"]:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and ":" in line and not line.startswith("#"):
                        parts = line.split(":")
                        pw[parts[0]] = parts[1]
            break
    return pw

def get_token(username):
    passwords = get_demo_passwords()
    data = urllib.parse.urlencode({
        "grant_type": "password",
        "client_id": "dx-test",
        "username": username,
        "password": passwords.get(username, "Password123!")
    }).encode("utf-8")
    req = urllib.request.Request("http://localhost:8080/auth/realms/dxos/protocol/openid-connect/token", data=data)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))["access_token"]

def call_rpc(func_name, params, token):
    url = f"http://localhost:8080/api/v1/rest/rpc/{func_name}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = json.dumps(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")

def test_V4_05_bo_sung_ho_so_not_found_returns_404_not_500():
    t_minh = get_token("cdt.minh")
    t_phuongb = get_token("mc.phuongb")

    # 1. cdt.minh gọi bo_sung_ho_so với UUID không tồn tại
    non_existent_id = "00000000-0000-0000-0000-000000000000"
    st1, b1 = call_rpc("bo_sung_ho_so", {
        "p_ho_so_id": non_existent_id,
        "p_dia_chi_cong_trinh": "Địa chỉ mới"
    }, t_minh)

    assert st1 == 404, f"Hồ sơ không tồn tại phải trả 404, nhưng nhận được {st1}: {b1}"
    assert "Không tìm thấy hồ sơ" in b1 or "PT404" in b1

    # 2. mc.phuongb gọi bo_sung_ho_so với hồ sơ phường A (không tồn tại trong tenant phuong-b)
    hs_phuonga = "184cb019-a759-4615-9b3a-de1eadfea216"
    st2, b2 = call_rpc("bo_sung_ho_so", {
        "p_ho_so_id": hs_phuonga,
        "p_dia_chi_cong_trinh": "Địa chỉ chéo phường"
    }, t_phuongb)

    assert st2 == 404, f"Hồ sơ khác tenant phải trả 404, nhưng nhận được {st2}: {b2}"
    assert "Không tìm thấy hồ sơ" in b2 or "PT404" in b2
