# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import subprocess
import urllib.request
import urllib.error
from .conftest import get_token, GATEWAY_URL
from .grep_utils import grep_repo


def test_V3_07_static_isolation_of_domain_terms():
    """V3-07: Lõi core và services hoàn toàn không chứa từ khóa nghiệp vụ hoặc TTL ghi cứng."""
    pattern = "ho_so|giay.phep|cap.phep|interval '30 seconds'"
    output = grep_repo(pattern)
    assert output.strip() == "", f"Phát hiện rò rỉ nghiệp vụ vào core/services:\n{output}"


def test_V3_07_break_glass_ttl_configurable_from_settings():
    """V3-07 / X-04: TTL truy cập khẩn cấp đọc động từ core.settings (expires_at - approved_at == BREAK_GLASS_TTL)."""
    # Đặt TTL thử nghiệm là PT5M (5 phút) trong core.settings
    subprocess.run(
        [
            "docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-c",
            "INSERT INTO core.settings (key, value) VALUES ('BREAK_GLASS_TTL', 'PT5M') "
            "ON CONFLICT (key) DO UPDATE SET value = 'PT5M'; DELETE FROM core.break_glass;"
        ],
        check=True,
    )

    token_cuong = get_token("td.cuong")
    token_hoa = get_token("ld.hoa")

    try:
        # Lấy một hồ sơ mẫu
        req_list = urllib.request.Request(
            f"{GATEWAY_URL}/api/v1/rest/v_ho_so?limit=1",
            headers={"Authorization": f"Bearer {token_hoa}"},
        )
        with urllib.request.urlopen(req_list, timeout=5) as resp:
            dossiers = json.loads(resp.read().decode())
            target_id = dossiers[0]["id"]

        # td.cuong nộp yêu cầu xin truy cập khẩn
        req_xin = urllib.request.Request(
            f"{GATEWAY_URL}/api/v1/rest/rpc/xin_truy_cap_khan",
            data=json.dumps({"p_ho_so_id": target_id, "p_ly_do": "Kiem tra dot xuat thanh tra xay dung"}).encode(),
            headers={"Authorization": f"Bearer {token_cuong}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req_xin, timeout=5) as resp:
            assert resp.status == 200
            xin_res = json.loads(resp.read().decode())
            req_id = xin_res["request_id"]

        # Lấy sub của td.cuong
        payload = json.loads(__import__("base64").b64decode(token_cuong.split(".")[1] + "==").decode())
        cuong_sub = payload["sub"]

        # ld.hoa duyệt yêu cầu
        req_approve = urllib.request.Request(
            f"{GATEWAY_URL}/api/v1/rest/rpc/duyet_truy_cap_khan",
            data=json.dumps({"p_ho_so_id": target_id, "p_user_sub": cuong_sub, "p_dong_y": True}).encode(),
            headers={"Authorization": f"Bearer {token_hoa}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req_approve, timeout=5) as resp:
            assert resp.status == 200
            appr_res = json.loads(resp.read().decode())
            assert appr_res.get("status") == "approved"

        # Kiểm tra bản ghi trong DB: chênh lệch expires_at - approved_at phải đúng 5 phút (300 giây)
        sql_check = (
            f"SELECT extract(epoch from (expires_at - approved_at))::int "
            f"FROM core.break_glass WHERE id = '{req_id}';"
        )
        res = subprocess.run(
            ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-c", sql_check],
            capture_output=True,
            text=True,
            check=True,
        )
        diff_seconds = int(res.stdout.strip())
        assert diff_seconds == 300, f"Mong đợi TTL là 300 giây (PT5M), nhận được {diff_seconds} giây!"
    finally:
        # Khôi phục BREAK_GLASS_TTL về mặc định PT2H và xóa break_glass
        subprocess.run(
            [
                "docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-c",
                "UPDATE core.settings SET value = 'PT2H' WHERE key = 'BREAK_GLASS_TTL'; "
                "DELETE FROM core.break_glass;"
            ],
            check=False,
        )
