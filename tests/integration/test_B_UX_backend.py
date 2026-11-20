# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-UX-01, B-UX-04, B-UX-05, B-UX-06 backend: dashboard, notification, audit, public lookup."""

import httpx

from tests.integration._auth import GATEWAY_URL, get_token


def _h(user: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {get_token(user)}"}


def test_BU01_dashboard_du_lieu_bieu_do_va_danh_sach():
    h = _h("ld.hoa")
    for path in (
        "/api/v1/metrics/status-breakdown",
        "/api/v1/metrics/trend?months=6",
        "/api/v1/metrics/workload",
        "/api/v1/metrics/overdue",
        "/api/v1/metrics/today-tasks",
    ):
        r = httpx.get(f"{GATEWAY_URL}{path}", headers=h, timeout=20.0)
        assert r.status_code == 200, f"{path}: {r.text}"
        body = r.json()
        assert body.get("tenant") == "phuong-a"
        assert "items" in body


def test_BU04_thong_bao_va_danh_dau_da_doc():
    h = _h("mc.thu")
    r = httpx.get(f"{GATEWAY_URL}/api/v1/flow/notifications", headers=h, timeout=20.0)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body and "unread" in body
    mark = httpx.post(f"{GATEWAY_URL}/api/v1/flow/notifications/read-all", headers=h, timeout=20.0)
    assert mark.status_code == 200, mark.text
    lai = httpx.get(f"{GATEWAY_URL}/api/v1/flow/notifications", headers=h, timeout=20.0)
    assert lai.status_code == 200
    assert lai.json()["unread"] == 0


def test_BU05_audit_chain_chi_kiem_toan_vien():
    h = _h("kt.an")
    chain = httpx.get(f"{GATEWAY_URL}/api/v1/audit/chain?limit=20", headers=h, timeout=20.0)
    assert chain.status_code == 200, chain.text
    body = chain.json()
    assert "items" in body and "chain_valid" in body
    verify = httpx.get(f"{GATEWAY_URL}/api/v1/audit/verify", headers=h, timeout=20.0)
    assert verify.status_code == 200, verify.text
    assert "valid" in verify.json()

    denied = httpx.get(f"{GATEWAY_URL}/api/v1/audit/chain", headers=_h("ld.hoa"), timeout=20.0)
    assert denied.status_code == 403, denied.text


def test_BU02_public_lookup_landing_va_chuyen_ma():
    r = httpx.get(f"{GATEWAY_URL}/kiem-tra/", timeout=20.0, headers={"Accept": "text/html"})
    assert r.status_code == 200, r.text
    assert 'id="ma-tra-cuu"' in r.text
    redirect = httpx.get(
        f"{GATEWAY_URL}/kiem-tra/tra",
        params={"ma": "DOC-KHONGCO"},
        timeout=20.0,
        follow_redirects=False,
    )
    assert redirect.status_code == 303
    assert redirect.headers["location"] == "/kiem-tra/DOC-KHONGCO"
