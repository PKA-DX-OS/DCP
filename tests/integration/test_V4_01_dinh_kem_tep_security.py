# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy bảo mật V4-01: Ngăn chặn đính kèm tệp trái phép vào hồ sơ người khác hoặc phường khác.
- cdt.minh gọi rpc/dinh_kem_tep cho hồ sơ không phải của mình -> 403 Forbidden
- mc.phuongb gọi rpc/dinh_kem_tep cho hồ sơ phường A -> 403 Forbidden
- Kiểm tra toàn vẹn CSDL: bảng app_cap_phep.ho_so_tep không tăng số lượng bản ghi.
"""

import os
import json
import subprocess
import urllib.request
import urllib.parse

def get_demo_passwords():
    pw = {}
    accounts_file = "secrets/demo-accounts.txt"
    if os.path.exists(accounts_file):
        with open(accounts_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and ":" in line and not line.startswith("#"):
                    parts = line.split(":")
                    pw[parts[0]] = parts[1]
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

def test_V4_01_dinh_kem_tep_cannot_attach_to_other_citizen_or_tenant():
    t_minh = get_token("cdt.minh")
    t_phuongb = get_token("mc.phuongb")

    # Hồ sơ của cdt.lan ở phường A
    hs_lan_id = "ceea6132-1bc0-4347-9cdd-82c9a34ab163"
    # Hồ sơ của phường A
    hs_minh_id = "184cb019-a759-4615-9b3a-de1eadfea216"

    # Lấy một file_id mẫu
    dummy_file = run_psql("SELECT id FROM core.files LIMIT 1;")
    assert dummy_file, "Không tìm thấy file mẫu trong core.files"

    count_before_lan = int(run_psql(f"SELECT count(*) FROM app_cap_phep.ho_so_tep WHERE ho_so_id = '{hs_lan_id}';"))
    count_before_minh = int(run_psql(f"SELECT count(*) FROM app_cap_phep.ho_so_tep WHERE ho_so_id = '{hs_minh_id}';"))

    # 1. cdt.minh gọi rpc/dinh_kem_tep cho hồ sơ của cdt.lan
    st1, body1 = call_rpc("dinh_kem_tep", {
        "p_ho_so_id": hs_lan_id,
        "p_file_id": dummy_file,
        "p_loai": "ban_ve_mat_bang"
    }, t_minh)
    assert st1 == 403, f"cdt.minh đính kèm tệp hồ sơ người khác phải bị từ chối 403, nhận được {st1}: {body1}"

    # 2. mc.phuongb gọi rpc/dinh_kem_tep cho hồ sơ phường A
    st2, body2 = call_rpc("dinh_kem_tep", {
        "p_ho_so_id": hs_minh_id,
        "p_file_id": dummy_file,
        "p_loai": "ban_ve_mat_bang"
    }, t_phuongb)
    assert st2 == 403, f"mc.phuongb đính kèm tệp hồ sơ phường khác phải bị từ chối 403, nhận được {st2}: {body2}"

    # 3. Kiểm tra CSDL không thêm dòng nào
    count_after_lan = int(run_psql(f"SELECT count(*) FROM app_cap_phep.ho_so_tep WHERE ho_so_id = '{hs_lan_id}';"))
    count_after_minh = int(run_psql(f"SELECT count(*) FROM app_cap_phep.ho_so_tep WHERE ho_so_id = '{hs_minh_id}';"))

    assert count_after_lan == count_before_lan, "Số lượng tệp đính kèm của hồ sơ cdt.lan bị thay đổi trái phép!"
    assert count_after_minh == count_before_minh, "Số lượng tệp đính kèm của hồ sơ phường A bị thay đổi trái phép!"
