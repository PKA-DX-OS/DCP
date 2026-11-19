# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-LEGAL-08: bộ kiểm tra tuân thủ LEGAL-15 (backend)."""

import httpx

from tests.integration._auth import GATEWAY_URL, get_token
from tests.integration._ho_so import run_sql


def test_A07_manifest_khong_dung_dieu_57_va_khong_doi_du_an():
    rows = run_sql("SELECT ten FROM app_cap_phep.document_requirements;")
    text = rows.lower()
    assert "quyết định phê duyệt dự án" not in text
    assert "tổng mặt bằng" not in text
    # Điều 57 không được dùng làm manifest cho nhà ở riêng lẻ.
    refs = run_sql(
        "SELECT count(*) FROM app_construction.legal_citations "
        "WHERE citation_key = 'ND217-D57' AND summary NOT LIKE '%không dùng%';"
    )
    assert int(refs) == 0


def test_A07_bat_buoc_cam_ket_va_giay_to_dat():
    rows = run_sql(
        "SELECT loai || '|' || bat_buoc FROM app_cap_phep.document_requirements "
        "WHERE loai IN ('cam_ket_an_toan','giay_to_dat','pccc','nha_thau','le_phi');"
    )
    d = {line.split("|")[0]: line.split("|")[1] for line in rows.splitlines() if line}
    assert d["cam_ket_an_toan"] == "true"
    assert d["giay_to_dat"] == "true"
    assert d["pccc"] == "false"
    assert d["nha_thau"] == "false"
    assert d["le_phi"] == "false"


def test_A07_tham_quyen_khong_con_huyen_la_cap_hien_hanh():
    rows = run_sql("SELECT DISTINCT co_quan_cap FROM app_construction.tham_quyen_cap_phep;")
    assert "UBND cấp huyện" not in rows
    assert "UBND cấp xã" in rows
    assert "Sở Xây dựng" in rows


def test_A07_audit_day_du_cho_kiem_tra_quy_hoach():
    # Mỗi lần check phải có audit; gọi một lần mới rồi đếm theo id.
    token = get_token("td.binh")
    resp = httpx.post(
        f"{GATEWAY_URL}/api/v1/planning/check",
        headers={"Authorization": f"Bearer {token}"},
        json={"thua_dat_id": "TD-A-02", "proposal": {"so_tang": 2, "loai_dat": "dat_o"}},
        timeout=30.0,
    )
    assert resp.status_code == 200, resp.text
    ket_qua_id = resp.json()["id"]
    count = run_sql(
        "SELECT count(*) FROM core.audit_log WHERE tenant = 'phuong-a' "
        f"AND action = 'planning.checked' AND detail->>'ket_qua_id' = '{ket_qua_id}';"
    )
    assert int(count) >= 1


def test_A07_dsar_co_han_sla():
    token = get_token("cdt.minh")
    resp = httpx.post(
        f"{GATEWAY_URL}/api/v1/rest/rpc/gui_yeu_cau_dsar",
        headers={"Authorization": f"Bearer {token}"},
        json={"p_type": "access", "p_legal_basis_note": "Kiểm thử SLA"},
        timeout=20.0,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("ack_due_at") and body.get("due_at")
    assert body["due_at"] > body["ack_due_at"]
