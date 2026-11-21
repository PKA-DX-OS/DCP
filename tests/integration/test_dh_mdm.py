# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
D-MDM-03: Test tích hợp các view 360 (v_dossier_360, v_permit_360, v_construction_360),
khớp schema HoSo360, che PII và đảm bảo cách ly phường tuyệt đối.
"""

import json
import re
import subprocess
import httpx
import pytest

from tests.integration._auth import GATEWAY_URL, get_token


def _h(user: str, **them) -> dict:
    return {"Authorization": f"Bearer {get_token(user)}"} | them


def run_psql(sql: str, user: str = "authenticator") -> subprocess.CompletedProcess:
    cmd = [
        "docker", "exec", "dxos-postgres", "psql",
        "-U", user, "-d", "dxos",
        "-v", "ON_ERROR_STOP=1", "-t", "-A", "-c", sql
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_v_dossier_360_khop_schema_va_che_pii():
    # 1. Gọi API 360 hồ sơ mẫu qua cán bộ một cửa phường A
    dossier_id = "8847bab8-33ef-4847-8e3d-50420b4c602a"
    r = httpx.get(
        f"{GATEWAY_URL}/api/v1/mdm/dossiers/{dossier_id}/360",
        headers=_h("mc.thu"),
        timeout=20.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()

    # Khớp cấu trúc HoSo360
    assert "ho_so" in body
    assert "chu_dau_tu" in body
    assert "thua_dat" in body
    assert "cong_trinh" in body
    assert "giay_phep" in body
    assert "kiem_tra" in body
    assert "tai_chinh" in body
    assert "canh_bao" in body
    assert "audit" in body

    # Kiểm tra che PII
    cdt = body["chu_dau_tu"]
    assert cdt is not None
    assert "001099001234" not in r.text  # Không lộ CCCD thật
    assert re.fullmatch(r"^\d{4}\*{6}\d{2}$", cdt["cccd_mask"])
    if cdt["dien_thoai_mask"]:
        assert "*" in cdt["dien_thoai_mask"]


def test_cach_ly_phuong_api_va_view_360():
    dossier_id = "8847bab8-33ef-4847-8e3d-50420b4c602a"

    # 1. Cán bộ phường A xem được hồ sơ phường A
    r_a = httpx.get(
        f"{GATEWAY_URL}/api/v1/mdm/dossiers/{dossier_id}/360",
        headers=_h("mc.thu"),
        timeout=20.0,
    )
    assert r_a.status_code == 200

    # 2. Cán bộ phường B gọi hồ sơ phường A -> 404 MDM_NOT_FOUND
    r_b = httpx.get(
        f"{GATEWAY_URL}/api/v1/mdm/dossiers/{dossier_id}/360",
        headers=_h("mc.phuongb"),
        timeout=20.0,
    )
    assert r_b.status_code == 404
    assert r_b.json()["code"] == "MDM_NOT_FOUND"

    # 3. Kiểm tra cách ly phường trực tiếp từ view v_dossier_360 qua RLS (security_invoker)
    claims_b = json.dumps({
        "sub": "test_phuongb",
        "tenant": "phuong-b",
        "roles": ["app:cap-phep:mot-cua"],
        "role": "web_user",
    })
    sql = f"""
    BEGIN;
    SET LOCAL ROLE web_user;
    SELECT set_config('request.jwt.claims', '{claims_b}', true);
    SELECT count(*) FROM core.v_dossier_360 WHERE dossier_id = '{dossier_id}';
    COMMIT;
    """
    res = run_psql(sql)
    assert res.returncode == 0
    # Dưới role web_user phường B, hồ sơ phường A hoàn toàn không xuất hiện (count = 0)
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip().isdigit()]
    assert lines[-1] == "0"


def test_v_permit_360_va_v_construction_360_cach_ly():
    # 1. Truy vấn v_permit_360 và v_construction_360 với cán bộ phường A
    claims_a = json.dumps({
        "sub": "test_phuonga",
        "tenant": "phuong-a",
        "roles": ["app:cap-phep:mot-cua"],
        "role": "web_user",
    })
    sql_a = f"""
    BEGIN;
    SET LOCAL ROLE web_user;
    SELECT set_config('request.jwt.claims', '{claims_a}', true);
    SELECT count(*) FROM core.v_permit_360 WHERE tenant = 'phuong-a';
    SELECT count(*) FROM core.v_construction_360 WHERE tenant = 'phuong-a';
    COMMIT;
    """
    res_a = run_psql(sql_a)
    assert res_a.returncode == 0
    lines_a = [line.strip() for line in res_a.stdout.strip().splitlines() if line.strip().isdigit()]
    assert int(lines_a[-2]) >= 1  # Có giấy phép phường A
    assert int(lines_a[-1]) >= 1  # Có công trình phường A

    # 2. Truy vấn từ người dùng phường B không thấy dữ liệu phường A
    claims_b = json.dumps({
        "sub": "test_phuongb",
        "tenant": "phuong-b",
        "roles": ["app:cap-phep:mot-cua"],
        "role": "web_user",
    })
    sql_b = f"""
    BEGIN;
    SET LOCAL ROLE web_user;
    SELECT set_config('request.jwt.claims', '{claims_b}', true);
    SELECT count(*) FROM core.v_permit_360 WHERE tenant = 'phuong-a';
    SELECT count(*) FROM core.v_construction_360 WHERE tenant = 'phuong-a';
    COMMIT;
    """
    res_b = run_psql(sql_b)
    assert res_b.returncode == 0
    lines_b = [line.strip() for line in res_b.stdout.strip().splitlines() if line.strip().isdigit()]
    assert lines_b[-2] == "0"
    assert lines_b[-1] == "0"
