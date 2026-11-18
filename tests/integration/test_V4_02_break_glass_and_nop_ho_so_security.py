# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy bảo mật V4-02:
- cdt.minh (chủ đầu tư) tạo yêu cầu truy cập khẩn -> 403 Forbidden
- mc.phuongb (phường B) tạo yêu cầu cho hồ sơ phường A -> 403 Forbidden
- mc.phuongb (cán bộ một cửa) nộp hồ sơ như chủ đầu tư -> 403 Forbidden
- Cán bộ hợp lệ td.cuong xin truy cập khẩn hồ sơ phường A -> 200 OK
- Chủ đầu tư cdt.minh nộp hồ sơ hợp lệ -> 200 OK
"""

import os
import json
import subprocess
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

def run_psql(sql):
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", sql]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return res.stdout.strip()

def test_V4_02_xin_truy_cap_khan_and_nop_ho_so_authorization():
    t_minh = get_token("cdt.minh")
    t_phuongb = get_token("mc.phuongb")
    t_cuong = get_token("td.cuong")

    # Hồ sơ phường A
    hs_phuonga = run_psql("SELECT id FROM app_cap_phep.ho_so WHERE tenant = 'phuong-a' LIMIT 1;")
    assert hs_phuonga, "Phải có ít nhất một hồ sơ ở phuong-a"

    # 1. cdt.minh (chủ đầu tư) không có quyền xin truy cập khẩn
    st1, b1 = call_rpc("xin_truy_cap_khan", {
        "p_ho_so_id": hs_phuonga,
        "p_ly_do": "Chủ đầu tư xin truy cập khẩn trái phép"
    }, t_minh)
    assert st1 == 403, f"cdt.minh xin truy cập khẩn phải bị từ chối 403, nhận được {st1}: {b1}"
    assert "quyền yêu cầu truy cập khẩn cấp" in b1

    # 2. mc.phuongb (phường B) xin truy cập khẩn hồ sơ phường A -> bị từ chối
    st2, b2 = call_rpc("xin_truy_cap_khan", {
        "p_ho_so_id": hs_phuonga,
        "p_ly_do": "Cán bộ phường B xin truy cập khẩn hồ sơ phường A"
    }, t_phuongb)
    assert st2 == 403, f"mc.phuongb xin truy cập khẩn chéo phường phải bị từ chối 403, nhận được {st2}: {b2}"

    # 3. mc.phuongb (cán bộ một cửa) không có quyền nộp hồ sơ
    st3, b3 = call_rpc("nop_ho_so", {
        "ho_ten": "Bùi Minh Phương",
        "cccd": "001099008888",
        "dien_thoai": "0911223344",
        "dia_chi_cong_trinh": "123 Đường Phường B",
        "thua_dat": "Thửa 9",
        "so_tang": 2,
        "dien_tich_san_m2": 120.0,
        "khu_quan_ly_kien_truc": False
    }, t_phuongb)
    assert st3 == 403, f"mc.phuongb nộp hồ sơ phải bị từ chối 403, nhận được {st3}: {b3}"
    assert "Chỉ chủ đầu tư mới có quyền nộp hồ sơ" in b3

    # 4. td.cuong (thẩm định viên phường A) xin truy cập khẩn hợp lệ -> 200
    st4, b4 = call_rpc("xin_truy_cap_khan", {
        "p_ho_so_id": hs_phuonga,
        "p_ly_do": "Thẩm định viên phường A xin truy cập khẩn hợp lệ"
    }, t_cuong)
    assert st4 == 200, f"td.cuong xin truy cập khẩn hợp lệ phải được 200, nhận được {st4}: {b4}"

    # 5. cdt.minh (chủ đầu tư) nộp hồ sơ hợp lệ kèm đủ giấy tờ -> 200
    from tests.integration.conftest import submit_dossier
    nop_resp = submit_dossier(t_minh, {
        "ho_ten": "Nguyễn Bình Minh",
        "cccd": "001090000001",
        "dien_thoai": "0901234567",
        "dia_chi_cong_trinh": "Số 99 Phố Mẫu, Phường A",
        "thua_dat": "Thửa 99",
        "so_tang": 3,
        "dien_tich_san_m2": 150.0,
        "khu_quan_ly_kien_truc": True
    }, tag_prefix="V4-02")
    assert nop_resp.status_code == 200, f"cdt.minh nộp hồ sơ hợp lệ phải được 200, nhận được {nop_resp.status_code}: {nop_resp.text}"
