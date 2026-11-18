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


def test_P01_break_glass_privacy_and_isolation():
    token_cdt = get_token("cdt.lan")
    token_td_binh = get_token("td.binh")
    token_td_cuong = get_token("td.cuong")
    token_ld_hoa = get_token("ld.hoa")
    token_ld_b = get_token("ld.phuongb")

    sub_binh = parse_sub(token_td_binh)
    sub_cuong = parse_sub(token_td_cuong)

    # 1. Setup test break glass requests
    obj_id_a1 = str(uuid.uuid4())
    obj_id_a2 = str(uuid.uuid4())
    obj_id_b1 = str(uuid.uuid4())

    run_sql(f"""
    INSERT INTO core.break_glass (tenant, requester_sub, object_type, object_id, reason, status, expires_at)
    VALUES ('phuong-a', '{sub_binh}', 'ho_so', '{obj_id_a1}', 'Ly do Binh A1', 'pending', now() + interval '1 hour'),
           ('phuong-a', '{sub_cuong}', 'ho_so', '{obj_id_a2}', 'Ly do Cuong A2', 'pending', now() + interval '1 hour'),
           ('phuong-b', 'sub_b_user', 'ho_so', '{obj_id_b1}', 'Ly do Phuong B1', 'pending', now() + interval '1 hour');
    """)

    try:
        with httpx.Client(base_url=GATEWAY_URL, timeout=10.0) as client:
            # Ca 1: Chu dau tu GET /api/v1/rest/break_glass phai bi chan (401/403/404)
            resp_view = client.get(
                "/api/v1/rest/break_glass",
                headers={"Authorization": f"Bearer {token_cdt}"},
            )
            assert resp_view.status_code in (401, 403, 404), (
                f"GET /rest/break_glass phai bi chan voi chu dau tu nhung tra ve {resp_view.status_code}: {resp_view.text}"
            )

            # Ca 2: Chu dau tu goi RPC ds_truy_cap_khan -> mang rong []
            resp_rpc_cdt = client.post(
                "/api/v1/rest/rpc/ds_truy_cap_khan",
                headers={"Authorization": f"Bearer {token_cdt}"},
                json={"p_trang_thai": "pending"},
            )
            assert resp_rpc_cdt.status_code == 200, f"ds_truy_cap_khan phai 200 nhung tra ve {resp_rpc_cdt.status_code}"
            data_cdt = resp_rpc_cdt.json()
            assert isinstance(data_cdt, list) and len(data_cdt) == 0, f"Chu dau tu khong duoc thay yeu cau nao: {data_cdt}"

            # Ca 3: Tham dinh vien td.binh goi ds_truy_cap_khan -> chi thay yeu cau cua minh
            resp_td = client.post(
                "/api/v1/rest/rpc/ds_truy_cap_khan",
                headers={"Authorization": f"Bearer {token_td_binh}"},
                json={"p_trang_thai": "pending"},
            )
            assert resp_td.status_code == 200
            data_td = resp_td.json()
            ids_td = [item["object_id"] for item in data_td]
            assert obj_id_a1 in ids_td, "td.binh phai thay yeu cau cua chinh minh"
            assert obj_id_a2 not in ids_td, "td.binh khong duoc thay yeu cau cua td.cuong"
            assert obj_id_b1 not in ids_td, "td.binh khong duoc thay yeu cau cua phuong B"

            # Ca 4: Lanh dao ld.hoa goi ds_truy_cap_khan -> thay cac yeu cau cua phuong A, khong thay phuong B
            resp_ld = client.post(
                "/api/v1/rest/rpc/ds_truy_cap_khan",
                headers={"Authorization": f"Bearer {token_ld_hoa}"},
                json={"p_trang_thai": "pending"},
            )
            assert resp_ld.status_code == 200
            data_ld = resp_ld.json()
            ids_ld = [item["object_id"] for item in data_ld]
            assert obj_id_a1 in ids_ld, "ld.hoa phai thay yeu cau a1"
            assert obj_id_a2 in ids_ld, "ld.hoa phai thay yeu cau a2"
            assert obj_id_b1 not in ids_ld, "ld.hoa khong duoc thay yeu cau cua phuong B"

            # Ca 5: Lanh dao phuong B goi ds_truy_cap_khan -> chi thay phuong B
            resp_ld_b = client.post(
                "/api/v1/rest/rpc/ds_truy_cap_khan",
                headers={"Authorization": f"Bearer {token_ld_b}"},
                json={"p_trang_thai": "pending"},
            )
            assert resp_ld_b.status_code == 200
            data_ld_b = resp_ld_b.json()
            ids_ld_b = [item["object_id"] for item in data_ld_b]
            assert obj_id_b1 in ids_ld_b, "ld.phuongb phai thay yeu cau b1"
            assert obj_id_a1 not in ids_ld_b, "ld.phuongb khong duoc thay yeu cau cua phuong A"

            # Ca 6: Khong co token -> 401 hoac 403
            resp_anon = client.post(
                "/api/v1/rest/rpc/ds_truy_cap_khan",
                json={"p_trang_thai": "pending"},
            )
            assert resp_anon.status_code in (401, 403), f"Anon phai bi tu choi: {resp_anon.status_code}"

    finally:
        run_sql(f"DELETE FROM core.break_glass WHERE object_id IN ('{obj_id_a1}', '{obj_id_a2}', '{obj_id_b1}');")
