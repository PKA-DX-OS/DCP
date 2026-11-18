# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""S-07: giới hạn quyền đọc/ghi hồ sơ, giấy phép, công trình, phiếu kiểm tra."""

import subprocess

import httpx

from tests.integration._ho_so import GATEWAY_URL, get_token, submit_dossier


def test_S07_unassigned_reviewer_cannot_view_dossier():
    """Thẩm định viên chưa được phân công (và chưa có truy cập khẩn) không thấy hồ sơ."""
    token_minh = get_token("cdt.minh")
    token_cuong = get_token("td.cuong")

    resp = submit_dossier(token_minh, {
        "ho_ten": "Nguyen Van S07",
        "cccd": "001200000077",
        "dien_thoai": "0901000077",
        "dia_chi_cong_trinh": "77 Pho S07",
        "thua_dat": "Thua 7 To 7",
        "so_tang": 2,
        "dien_tich_san_m2": 120.0,
        "khu_quan_ly_kien_truc": True,
    }, tag_prefix="S07_rls")
    assert resp.status_code == 200, f"Nộp hồ sơ thất bại: {resp.text}"
    ho_so_id = resp.json()["id"]

    with httpx.Client(timeout=10.0) as client:
        own = client.get(f"{GATEWAY_URL}/api/v1/rest/v_ho_so?id=eq.{ho_so_id}",
                         headers={"Authorization": f"Bearer {token_minh}"})
        assert own.status_code == 200 and len(own.json()) == 1, "Chủ hồ sơ phải thấy hồ sơ của mình"

        other = client.get(f"{GATEWAY_URL}/api/v1/rest/v_ho_so?id=eq.{ho_so_id}",
                           headers={"Authorization": f"Bearer {token_cuong}"})
        assert other.status_code == 200, other.text
        assert other.json() == [], f"td.cuong chưa phân công không được thấy hồ sơ: {other.json()}"


def test_S07_web_user_cannot_insert_or_update_permits_and_works():
    """web_user bị cấm INSERT trên giay_phep, cong_trinh, phieu_kiem_tra (không ghi gì vào CSDL)."""
    sql_statements = [
        "SET ROLE web_user; INSERT INTO app_cap_phep.giay_phep (tenant, ho_so_id, so_giay_phep, signed_doc_id) VALUES ('phuong-a', '00000000-0000-0000-0000-000000000001', 'FAKE', '00000000-0000-0000-0000-000000000001');",
        "SET ROLE web_user; INSERT INTO app_cap_phep.cong_trinh (tenant, ma_cong_trinh, entity_id) VALUES ('phuong-a', 'FAKE-01', 'urn:dxos:test');",
        "SET ROLE web_user; INSERT INTO app_cap_phep.phieu_kiem_tra (tenant, nguon) VALUES ('phuong-a', 'cam_bien');",
    ]
    for sql in sql_statements:
        cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "dxos_svc", "-d", "dxos", "-c", sql]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        assert proc.returncode != 0, f"web_user không được ghi: {sql}"
        err = (proc.stderr + proc.stdout).lower()
        assert "permission denied" in err or "từ chối quyền" in err or "violates row-level security policy" in err, err
