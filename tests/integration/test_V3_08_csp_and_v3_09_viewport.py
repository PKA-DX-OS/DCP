# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""V3-08: CSP chặt trên hai SPA, không đè lên trang đăng nhập Keycloak, không lỗi console khi tải.
V3-09: màn hình 390x844 không cuộn ngang.

Cần Playwright cho Python: `pip install playwright && python -m playwright install chromium`.
"""

import httpx
import pytest

from tests.integration.conftest import GATEWAY_URL

TRANG = ["/", "/dieu-hanh/"]


@pytest.mark.parametrize("path", TRANG)
def test_V3_08_csp_headers_on_spa(path):
    r = httpx.get(f"{GATEWAY_URL}{path}", timeout=10.0, follow_redirects=True)
    assert r.status_code == 200
    csp = r.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp, f"{path} thiếu CSP default-src: {csp!r}"
    assert "script-src 'self'" in csp, f"{path} thiếu CSP script-src: {csp!r}"
    assert "unsafe-eval" not in csp


def test_V3_08_keycloak_khong_bi_csp_spa_de():
    r = httpx.get(f"{GATEWAY_URL}/auth/realms/dxos/.well-known/openid-configuration", timeout=10.0)
    assert r.status_code == 200
    assert "script-src 'self'" not in r.headers.get("Content-Security-Policy", ""), "CSP của SPA không được áp lên Keycloak"


@pytest.mark.parametrize("path", TRANG)
def test_V3_08_khong_loi_console_khi_tai(path):
    sync_api = pytest.importorskip("playwright.sync_api", reason="Chưa cài Playwright (pip install playwright)")
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        loi: list[str] = []
        page.on("console", lambda m: loi.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: loi.append(str(e)))
        page.goto(f"{GATEWAY_URL}{path}", wait_until="networkidle", timeout=20000)
        browser.close()
    csp = [x for x in loi if "Content Security Policy" in x or "Refused to" in x]
    assert not csp, f"{path} vi phạm CSP: {csp}"
    assert not loi, f"{path} có lỗi console: {loi}"


@pytest.mark.parametrize("path", TRANG)
def test_V3_09_mobile_viewport_scroll_width_within_390px(path):
    sync_api = pytest.importorskip("playwright.sync_api", reason="Chưa cài Playwright (pip install playwright)")
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(f"{GATEWAY_URL}{path}", wait_until="networkidle", timeout=20000)
        w = page.evaluate("() => document.documentElement.scrollWidth")
        browser.close()
    assert w <= 390, f"{path} rộng {w}px, vượt 390px"
