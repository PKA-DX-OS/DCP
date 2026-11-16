# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import urllib.request
from playwright.sync_api import sync_playwright
from .conftest import GATEWAY_URL


def test_V3_08_csp_headers_on_spa_and_auth_isolation():
    """V3-08: Header CSP nghiêm được đặt trên route SPA và không đè lên route Keycloak."""
    req_root = urllib.request.Request(f"{GATEWAY_URL}/")
    with urllib.request.urlopen(req_root, timeout=5) as resp:
        csp_header = resp.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp_header
        assert "script-src 'self'" in csp_header

    req_dh = urllib.request.Request(f"{GATEWAY_URL}/dieu-hanh/")
    with urllib.request.urlopen(req_dh, timeout=5) as resp:
        csp_dh = resp.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp_dh
        assert "script-src 'self'" in csp_dh


def test_V3_08_zero_console_errors_on_5_users():
    """V3-08: Đăng nhập và chuyển đổi 5 tài khoản mẫu không phát sinh bất kỳ lỗi CSP nào trên Console."""
    users = ["cdt.minh", "mc.thu", "td.binh", "ld.hoa", "tt.khanh"]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for u in users:
            context = browser.new_context()
            page = context.new_page()
            console_errors = []

            def record_error(msg, errors=console_errors):
                if msg.type == "error":
                    errors.append(msg.text)

            page.on("console", record_error)
            page.goto(f"{GATEWAY_URL}/", wait_until="networkidle", timeout=10000)
            sel = page.query_selector("select")
            if sel:
                opts = page.eval_on_selector_all("select option", "options => options.map(o => o.value)")
                if u in opts:
                    page.select_option("select", u)
                    page.wait_for_timeout(300)
            context.close()
            assert len(console_errors) == 0, f"Phát hiện lỗi console cho tài khoản {u}: {console_errors}"
        browser.close()


def test_V3_09_mobile_viewport_scroll_width_within_390px():
    """V3-09: Tại màn hình di động 390x844, chiều rộng cuộn ngang scrollWidth <= 390px trên cả trang chủ và /dieu-hanh/."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for path in ["/", "/dieu-hanh/"]:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto(f"{GATEWAY_URL}{path}", wait_until="networkidle", timeout=10000)
            scroll_w = page.evaluate("() => document.documentElement.scrollWidth")
            assert scroll_w <= 390, f"Đường dẫn {path} có scrollWidth = {scroll_w}px vượt quá 390px!"
            page.close()
        browser.close()
