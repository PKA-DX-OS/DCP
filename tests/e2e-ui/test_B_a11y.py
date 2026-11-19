# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-DS-05: kiểm axe-core mức serious/critical trên các màn chính."""

import os
import re
from pathlib import Path

import pytest

from tests.integration._auth import DEMO_ACCOUNTS_FILE, GATEWAY_URL, ROOT

sync_api = pytest.importorskip("playwright.sync_api")
BASE_URL = os.getenv("E2E_BASE_URL", GATEWAY_URL).rstrip("/")
AXE = ROOT / "apps" / "cap-phep" / "web" / "node_modules" / "axe-core" / "axe.min.js"


def _tai_khoan() -> dict[str, str]:
    if not DEMO_ACCOUNTS_FILE.exists():
        pytest.skip("Thiếu secrets/demo-accounts.txt")
    ds = {}
    for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        p = line.strip().split(":")
        if len(p) >= 2 and p[0] and not p[0].startswith("#"):
            ds[p[0]] = p[1]
    return ds


def _axe(page) -> list[dict]:
    page.add_script_tag(path=str(AXE))
    res = page.evaluate("async () => await axe.run(document, {resultTypes:['violations']})")
    return [v for v in res["violations"] if v["impact"] in ("serious", "critical")]


def _dang_nhap(page, username: str, password: str, url: str) -> None:
    page.goto(url, wait_until="domcontentloaded")
    page.get_by_role("button", name="Đăng nhập", exact=True).click()
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("#kc-login").click()
    page.wait_for_url(re.compile(re.escape(url) + r"(\?.*)?$"), timeout=20000)


def test_a11y_login_danh_sach_dashboard():
    accounts = _tai_khoan()
    if "cdt.minh" not in accounts or "ld.hoa" not in accounts:
        pytest.skip("Thiếu tài khoản demo")

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN", bypass_csp=True)
        page = ctx.new_page()
        try:
            page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
            assert _axe(page) == []
            page.get_by_role("button", name=re.compile("nền", re.I)).click()
            page.wait_for_timeout(250)
            assert _axe(page) == []
            page.get_by_role("button", name=re.compile("nền", re.I)).click()

            _dang_nhap(page, "cdt.minh", accounts["cdt.minh"], f"{BASE_URL}/")
            page.get_by_role("button", name="Hồ sơ của tôi", exact=True).click()
            page.locator("#table-ho-so").wait_for(timeout=20000)
            assert _axe(page) == []
        finally:
            ctx.close()

        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN", bypass_csp=True)
        page = ctx.new_page()
        try:
            _dang_nhap(page, "ld.hoa", accounts["ld.hoa"], f"{BASE_URL}/dieu-hanh/")
            page.get_by_text("Bảng điều hành lãnh đạo").wait_for(timeout=20000)
            assert _axe(page) == []
            page.get_by_role("button", name=re.compile("Giao diện (sáng|tối)")).click()
            page.wait_for_timeout(250)
            assert _axe(page) == []
        finally:
            ctx.close()

        if "kt.an" in accounts:
            ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN", bypass_csp=True)
            page = ctx.new_page()
            try:
                _dang_nhap(page, "kt.an", accounts["kt.an"], f"{BASE_URL}/dieu-hanh/")
                page.get_by_role("button", name="Kiểm toán", exact=True).click()
                page.get_by_text("Nhật ký kiểm toán").wait_for(timeout=20000)
                assert _axe(page) == []
            finally:
                ctx.close()
        browser.close()
