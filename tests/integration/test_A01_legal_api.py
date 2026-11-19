# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-LEGAL-01: API tra cứu kho pháp luật qua APISIX + phân quyền."""

import httpx

from tests.integration._auth import GATEWAY_URL, get_token


def _get(path: str, token: str) -> httpx.Response:
    return httpx.get(f"{GATEWAY_URL}{path}", headers={"Authorization": f"Bearer {token}"}, timeout=20.0)


def test_A01_danh_muc_50_van_ban():
    token = get_token("td.binh")
    resp = _get("/api/v1/planning/legal/documents?limit=200", token)
    assert resp.status_code == 200, resp.text
    docs = resp.json()
    assert len(docs) == 50
    ma = {d["code"] for d in docs}
    assert "217/2026/NĐ-CP" in ma
    assert "135/2025/QH15" in ma


def test_A01_trich_dan_dieu_60_co_can_cu():
    token = get_token("td.binh")
    resp = _get("/api/v1/planning/legal/citations/ND217-D60-K3", token)
    assert resp.status_code == 200, resp.text
    cit = resp.json()
    assert cit["article"] == "Điều 60"
    assert cit["clause"] == "khoản 3"
    assert cit["document_code"] == "217/2026/NĐ-CP"


def test_A01_cong_dan_khong_duoc_tra_cuu_kho_noi_bo():
    token = get_token("cdt.minh")
    resp = _get("/api/v1/planning/legal/documents", token)
    assert resp.status_code == 403, resp.text
