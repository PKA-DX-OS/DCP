# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import urllib.request
import urllib.error
from .conftest import get_token, GATEWAY_URL


def test_break_glass_flow_and_sod():
    import subprocess
    subprocess.run(["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-c", "DELETE FROM core.break_glass;"], check=False)

    token_cuong = get_token("td.cuong")
    token_hoa = get_token("ld.hoa")

    # 1. Tìm hồ sơ không thuộc phân công của td.cuong
    try:
        req_list = urllib.request.Request(
            f"{GATEWAY_URL}/api/v1/rest/v_ho_so?limit=5",
            headers={"Authorization": f"Bearer {token_hoa}"},
        )
        with urllib.request.urlopen(req_list, timeout=5) as resp:
            dossiers = json.loads(resp.read().decode())
            assert len(dossiers) > 0

        target_id = dossiers[0]["id"]

        # 2. td.cuong thử mở hồ sơ ban đầu -> Bị chặn 403
        req_open = urllib.request.Request(
            f"{GATEWAY_URL}/api/v1/rest/rpc/mo_ho_so",
            data=json.dumps({"p_id": target_id}).encode(),
            headers={"Authorization": f"Bearer {token_cuong}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req_open, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                assert data.get("can_xin_truy_cap_khan") is True
        except urllib.error.HTTPError as e:
            assert e.code == 403

        # 3. td.cuong nộp yêu cầu xin truy cập khẩn
        req_xin = urllib.request.Request(
            f"{GATEWAY_URL}/api/v1/rest/rpc/xin_truy_cap_khan",
            data=json.dumps({"p_ho_so_id": target_id, "p_ly_do": "Kiem tra ho so khan cap phuc vu thanh tra"}).encode(),
            headers={"Authorization": f"Bearer {token_cuong}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req_xin, timeout=5) as resp:
            assert resp.status == 200
            xin_res = json.loads(resp.read().decode())
            assert xin_res.get("status") == "pending"

        # Lấy sub của td.cuong
        token_payload = json.loads(__import__("base64").b64decode(token_cuong.split(".")[1] + "==").decode())
        cuong_sub = token_payload.get("sub")

        # 4. Kiểm tra SoD: td.cuong cố tình TỰ DUYỆT yêu cầu của chính mình -> BẮT BUỘC 403
        req_self_approve = urllib.request.Request(
            f"{GATEWAY_URL}/api/v1/rest/rpc/duyet_truy_cap_khan",
            data=json.dumps({"p_ho_so_id": target_id, "p_user_sub": cuong_sub, "p_dong_y": True}).encode(),
            headers={"Authorization": f"Bearer {token_cuong}", "Content-Type": "application/json"},
        )
        self_approve_blocked = False
        try:
            with urllib.request.urlopen(req_self_approve, timeout=5) as resp:
                pass
        except urllib.error.HTTPError as e:
            assert e.code in (400, 403)
            self_approve_blocked = True
        assert self_approve_blocked, "Người xin truy cập khẩn không được phép tự duyệt yêu cầu!"

        # 5. ld.hoa (Lãnh đạo) duyệt yêu cầu truy cập khẩn -> 200 OK
        req_approve = urllib.request.Request(
            f"{GATEWAY_URL}/api/v1/rest/rpc/duyet_truy_cap_khan",
            data=json.dumps({"p_ho_so_id": target_id, "p_user_sub": cuong_sub, "p_dong_y": True}).encode(),
            headers={"Authorization": f"Bearer {token_hoa}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req_approve, timeout=5) as resp:
            assert resp.status == 200
            appr_res = json.loads(resp.read().decode())
            assert appr_res.get("status") == "approved"

        # 6. Ngay sau khi duyệt: td.cuong mở hồ sơ -> HTTP 200 OK
        with urllib.request.urlopen(req_open, timeout=5) as resp:
            assert resp.status == 200
            opened_doc = json.loads(resp.read().decode())
            assert opened_doc.get("id") == target_id
    finally:
        subprocess.run(["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-c", "DELETE FROM core.break_glass;"], check=False)
