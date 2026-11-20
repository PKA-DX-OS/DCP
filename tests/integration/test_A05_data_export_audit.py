# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-DATA: metric, export, audit chain API."""

import httpx

from tests.integration._auth import GATEWAY_URL, get_token


def _h(user: str) -> dict:
    return {"Authorization": f"Bearer {get_token(user)}"}


def test_A05_metric_bo_sung_cho_dashboard():
    h = _h("ld.hoa")
    for path in (
        "/api/v1/metrics/status-breakdown",
        "/api/v1/metrics/trend?months=6",
        "/api/v1/metrics/workload",
        "/api/v1/metrics/planning-fail",
        "/api/v1/metrics/acceptance-progress",
        "/api/v1/metrics/on-time?months=6",
        "/api/v1/metrics/overdue",
        "/api/v1/metrics/today-tasks",
    ):
        resp = httpx.get(f"{GATEWAY_URL}{path}", headers=h, timeout=20.0)
        assert resp.status_code == 200, f"{path}: {resp.text}"
        body = resp.json()
        assert body.get("tenant") == "phuong-a"
        assert "items" in body


def test_A05_cong_dan_khong_duoc_xem_metric_bo_sung():
    resp = httpx.get(f"{GATEWAY_URL}/api/v1/metrics/trend", headers=_h("cdt.minh"), timeout=20.0)
    assert resp.status_code == 403, resp.text


def test_A05_xuat_excel_va_pdf():
    ho_so = httpx.get(f"{GATEWAY_URL}/api/v1/export/dossiers.xlsx", headers=_h("ld.hoa"), timeout=60.0)
    assert ho_so.status_code == 200, ho_so.text
    assert ho_so.content.startswith(b"PK")
    assert "spreadsheetml" in ho_so.headers.get("content-type", "")

    pdf = httpx.get(f"{GATEWAY_URL}/api/v1/export/metrics.pdf", headers=_h("ld.hoa"), timeout=60.0)
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")

    audit = httpx.get(f"{GATEWAY_URL}/api/v1/export/audit.xlsx", headers=_h("kt.an"), timeout=60.0)
    assert audit.status_code == 200, audit.text
    assert audit.content.startswith(b"PK")

    forbidden = httpx.get(f"{GATEWAY_URL}/api/v1/export/audit.xlsx", headers=_h("ld.hoa"), timeout=20.0)
    assert forbidden.status_code == 403, forbidden.text


def test_A05_audit_chain_va_verify():
    h = _h("kt.an")
    chain = httpx.get(f"{GATEWAY_URL}/api/v1/audit/chain?entity=ho_so", headers=h, timeout=30.0)
    assert chain.status_code == 200, chain.text
    body = chain.json()
    assert body["chain_valid"] is True
    assert body["count"] >= 1
    assert all(len(x["hash"]) == 64 for x in body["items"])

    verify = httpx.post(f"{GATEWAY_URL}/api/v1/audit/verify", headers=h, timeout=30.0)
    assert verify.status_code == 200, verify.text
    assert verify.json()["valid"] is True

    denied = httpx.get(f"{GATEWAY_URL}/api/v1/audit/chain", headers=_h("td.binh"), timeout=20.0)
    assert denied.status_code == 403, denied.text
