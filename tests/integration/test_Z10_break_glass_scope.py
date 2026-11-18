# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import base64
import json
import subprocess
import uuid
import httpx
from tests.integration.conftest import GATEWAY_URL, get_token


def parse_sub(tok: str) -> str:
    raw = tok.split(".")[1]
    raw += "=" * (-len(raw) % 4)
    return json.loads(base64.urlsafe_b64decode(raw))["sub"]


def run_sql(sql: str) -> str:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", sql]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout.strip()


def test_Z10_break_glass_approval_scope_and_isolation():
    # Token các vai
    ld_token = get_token("ld.hoa")
    td_token = get_token("td.binh")
    assert ld_token and td_token, "Token phải hợp lệ"
    hoa_sub = parse_sub(ld_token)
    binh_sub = parse_sub(td_token)

    hs_a = str(uuid.uuid4())
    hs_b = str(uuid.uuid4())

    # 1. Setup 2 hồ sơ (1 thuộc phuong-a, 1 thuộc phuong-b)
    run_sql(f"""
    INSERT INTO app_cap_phep.ho_so (id, tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai, dia_chi_cong_trinh, thua_dat, trang_thai, han_tong_at)
    VALUES ('{hs_a}', 'phuong-a', 'HS-BG-A', 'cdt_a', 'Nguyen A', '001200000010', '0901', 'Dia chi A', 'Thua A', 'CHO_DUYET', now() + interval '10 days'),
           ('{hs_b}', 'phuong-b', 'HS-BG-B', 'cdt_b', 'Nguyen B', '001200000011', '0902', 'Dia chi B', 'Thua B', 'CHO_DUYET', now() + interval '10 days');
    """)

    # 2. Tạo 3 yêu cầu break-glass:
    # - req_td: thẩm định viên td.binh xin truy cập hs_a (phuong-a)
    # - req_ld: chính lãnh đạo ld.hoa xin truy cập hs_a (phuong-a)
    # - req_b: cán bộ phuong-b xin truy cập hs_b (phuong-b)
    run_sql(f"""
    INSERT INTO core.break_glass (tenant, requester_sub, object_type, object_id, reason, status, expires_at)
    VALUES ('phuong-a', '{binh_sub}', 'ho_so', '{hs_a}', 'Can xem ho so A', 'pending', now() + interval '10 minutes'),
           ('phuong-a', '{hoa_sub}', 'ho_so', '{hs_a}', 'Lanh dao xin xem ho so A', 'pending', now() + interval '10 minutes'),
           ('phuong-b', 'td.phuongb', 'ho_so', '{hs_b}', 'Can xem ho so B', 'pending', now() + interval '10 minutes');
    """)

    try:
        # 3. Lãnh đạo ld.hoa gọi RPC duyet_truy_cap_khan cho yêu cầu của td.binh
        url = f"{GATEWAY_URL}/api/v1/rest/rpc/duyet_truy_cap_khan"
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                url,
                headers={"Authorization": f"Bearer {ld_token}"},
                json={
                    "p_object_type": "ho_so",
                    "p_object_id": hs_a,
                    "p_user_sub": binh_sub,
                    "p_dong_y": True,
                },
            )
            assert resp.status_code == 200, f"Duyệt yêu cầu cho td.binh thất bại: {resp.text}"

        # 4. Kiểm tra trạng thái trong DB:
        # - Yêu cầu của td.binh phải chuyển sang approved
        status_td = run_sql(f"SELECT status FROM core.break_glass WHERE object_id = '{hs_a}' AND requester_sub = '{binh_sub}';")
        assert status_td == "approved"

        # - Yêu cầu của chính lãnh đạo ld.hoa vẫn PHẢI là pending (không được tự duyệt)
        status_ld = run_sql(f"SELECT status FROM core.break_glass WHERE object_id = '{hs_a}' AND requester_sub = '{hoa_sub}';")
        assert status_ld == "pending", f"Yêu cầu của chính người duyệt không được tự động chuyển approved! Trạng thái: {status_ld}"

        # - Yêu cầu của phuong-b vẫn PHẢI là pending (không bị đụng tới bởi lãnh đạo phuong-a)
        status_b = run_sql(f"SELECT status FROM core.break_glass WHERE object_id = '{hs_b}';")
        assert status_b == "pending", f"Yêu cầu của phường khác không được bị duyệt chéo! Trạng thái: {status_b}"

    finally:
        run_sql(f"DELETE FROM core.break_glass WHERE object_id IN ('{hs_a}', '{hs_b}');")
        run_sql(f"DELETE FROM app_cap_phep.ho_so WHERE id IN ('{hs_a}', '{hs_b}');")
