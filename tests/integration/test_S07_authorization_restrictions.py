# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import subprocess
import urllib.request
import urllib.error
import json
from tests.integration.conftest import get_token, GATEWAY_URL


def test_S07_unassigned_reviewer_cannot_view_dossier():
    subprocess.run(
        ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-c", "DELETE FROM core.break_glass;"],
        check=False,
    )
    # td.cuong không được phân công hồ sơ của cdt.minh
    token_minh = get_token("cdt.minh")
    token_cuong = get_token("td.cuong")

    # Lấy hồ sơ cdt.minh
    req = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/rest/v_ho_so?limit=1",
        headers={"Authorization": f"Bearer {token_minh}"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        ho_so_id = json.loads(resp.read().decode())[0]["id"]

    # td.cuong cố gắng truy vấn hồ sơ cụ thể này
    req_cuong = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/rest/v_ho_so?id=eq.{ho_so_id}",
        headers={"Authorization": f"Bearer {token_cuong}"},
    )
    with urllib.request.urlopen(req_cuong, timeout=5) as resp:
        # RLS ẩn bản ghi (trả về mảng rỗng)
        rows = json.loads(resp.read().decode())
        assert len(rows) == 0, f"Thẩm định viên không được phân công không được phép thấy hồ sơ này! Nhận được: {rows}"


def test_S07_web_user_cannot_insert_or_update_permits_and_works():
    # web_user bị cấm INSERT/UPDATE trên giay_phep, cong_trinh, phieu_kiem_tra
    sql_statements = [
        "SET ROLE web_user; INSERT INTO app_cap_phep.giay_phep (tenant, ho_so_id, so_giay_phep, signed_doc_id) VALUES ('phuong-a', '00000000-0000-0000-0000-000000000001', 'FAKE', '00000000-0000-0000-0000-000000000001');",
        "SET ROLE web_user; INSERT INTO app_cap_phep.cong_trinh (tenant, ma_cong_trinh, entity_id) VALUES ('phuong-a', 'FAKE-01', 'urn:dxos:test');",
        "SET ROLE web_user; INSERT INTO app_cap_phep.phieu_kiem_tra (tenant, nguon) VALUES ('phuong-a', 'cam_bien');",
    ]

    for sql in sql_statements:
        cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "dxos_svc", "-d", "dxos", "-c", sql]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode != 0
        err = proc.stderr.lower() + proc.stdout.lower()
        assert "permission denied" in err or "từ chối quyền" in err or "violates row-level security policy" in err
